"""Append-only, hash-chained experience journal with owner capabilities.

Every record is written by exactly one of the four constitutional owners and only kinds that owner may write:
  MEDIATE  the boundary: inbound transport/percepts/receipts, outbound acts, permissions
  EVAL     interpretation, hypotheses, predictions, simulations, recall, contradictions, explanations, proposals
  COMMIT   constitutional decisions (COMMIT | CLAIM_ONLY | REJECT) — the only owner that changes admitted state
  DRIVE    decisions (which quantum / which act), tasks, rest and wake
Clocks are separate fields: `step` (internal order of thought steps), `world_t` (environment clock), `narrated_t`
(time the content talks about, exact or an interval), `due_t` (plan deadlines).  `wall` is informational and is NOT
part of the hash, so a replay on another machine/day yields the same chain.
Resume protocol: a journal reopened with `verify_tail=True` re-executes appends against the existing tail; an append
that equals the stored record is accepted without writing (idempotent: nothing is re-sent), a different one raises
`Divergence` (non-determinism is detected, never silently overwritten)."""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

OWNERS = ('EVAL', 'COMMIT', 'DRIVE', 'MEDIATE')
KINDS = {
    'MEDIATE': {'INBOUND', 'OUTBOUND', 'RECEIPT', 'PERMISSION', 'BOUNDARY_NOTE'},
    'EVAL': {'INTERPRETATION', 'HYPOTHESIS', 'PREDICTION', 'SIMULATION', 'EVALUATION', 'RECALL', 'CONTRADICTION',
             'EXPLANATION', 'PROPOSAL', 'PLAN'},
    'COMMIT': {'COMMIT_DECISION'},
    'DRIVE': {'DECISION', 'TASK', 'REST', 'WAKE', 'BUDGET'},
}
GENESIS = '0' * 64


class Divergence(RuntimeError):
    """A resumed process produced a record different from the one already in the journal."""


class CapabilityError(PermissionError):
    pass


class OwnerCap:
    """An unforgeable-by-convention write capability for one owner (issued only by the journal)."""
    __slots__ = ('owner', '_j')

    def __init__(self, owner: str, journal: 'Journal'):
        self.owner = owner
        self._j = journal

    def __repr__(self):
        return f'<cap {self.owner}>'


def canonical(rec: Dict[str, Any]) -> str:
    body = {k: v for k, v in rec.items() if k not in ('hash', 'wall')}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=_default)


def _default(x):
    if isinstance(x, (set, frozenset)):
        return sorted(x)
    if hasattr(x, 'tolist'):
        return x.tolist()
    raise TypeError(f'not JSON-serialisable: {type(x)}')


def rec_hash(prev: str, rec: Dict[str, Any]) -> str:
    return hashlib.sha256((prev + canonical(rec)).encode('utf8')).hexdigest()


class Journal:
    def __init__(self, path: Optional[str] = None, *, fsync: bool = False):
        self.records: List[Dict[str, Any]] = []
        self.path = path
        self.fsync = fsync
        self._caps = {o: OwnerCap(o, self) for o in OWNERS}
        self._fh = None
        self._tail: List[Dict[str, Any]] = []          # records after the resume point, to be verified
        self.last_verified = False
        self.recovered_bytes = 0
        if path and os.path.exists(path):
            self._load(path)
        if path:
            self._fh = open(path, 'a', encoding='utf8')

    # ------------------------------------------------------------------ capabilities
    def cap(self, owner: str) -> OwnerCap:
        """Issued once to the kernel, which hands each owner only its own capability."""
        return self._caps[owner]

    # ------------------------------------------------------------------ reading
    def __len__(self):
        return len(self.records)

    def head(self) -> str:
        return self.records[-1]['hash'] if self.records else GENESIS

    def get(self, seq: int) -> Dict[str, Any]:
        return self.records[seq]

    def by_kind(self, owner: Optional[str] = None, kind: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        for r in self.records:
            if (owner is None or r['owner'] == owner) and (kind is None or r['kind'] == kind):
                yield r

    # ------------------------------------------------------------------ writing
    def append(self, cap: OwnerCap, kind: str, payload: Dict[str, Any], *, refs: Iterable[int] = (), step: int = 0,
               world_t: Optional[int] = None, narrated_t: Any = None, due_t: Optional[int] = None) -> Dict[str, Any]:
        if not isinstance(cap, OwnerCap) or self._caps.get(cap.owner) is not cap:
            raise CapabilityError('forged or foreign capability')
        if kind not in KINDS[cap.owner]:
            raise CapabilityError(f'{cap.owner} may not write {kind}')
        refs = sorted(set(int(r) for r in refs))
        n = len(self.records)
        if any(r < 0 or r >= n for r in refs):
            raise ValueError(f'reference to a non-existent record {refs} (journal has {n})')
        rec = {'seq': n, 'owner': cap.owner, 'kind': kind, 'step': int(step), 'world_t': world_t,
               'narrated_t': narrated_t, 'due_t': due_t, 'payload': payload, 'refs': refs, 'prev': self.head()}
        rec['hash'] = rec_hash(rec['prev'], rec)
        self.last_verified = False
        if self._tail:                                  # resume: verify instead of writing
            old = self._tail.pop(0)
            if old['hash'] != rec['hash']:
                raise Divergence(f'record {n}: resumed process wrote {canonical(rec)[:300]} '
                                 f'but the journal holds {canonical(old)[:300]}')
            self.records.append(old)
            self.last_verified = True
            return old
        rec['wall'] = round(time.time(), 3)
        self.records.append(rec)
        if self._fh:
            self._fh.write(json.dumps(rec, ensure_ascii=False, default=_default) + '\n')
            self._fh.flush()
            if self.fsync:
                os.fsync(self._fh.fileno())
        return rec

    # ------------------------------------------------------------------ persistence
    def _load(self, path: str):
        good, prev, size_ok = [], GENESIS, 0
        with open(path, 'rb') as f:
            raw = f.read()
        pos = 0
        for line in raw.split(b'\n'):
            if not line.strip():
                pos += len(line) + 1
                continue
            try:
                rec = json.loads(line.decode('utf8'))
                ok = rec.get('prev') == prev and rec_hash(prev, rec) == rec.get('hash') and rec.get('seq') == len(good)
            except (ValueError, UnicodeDecodeError):
                ok = False
            if not ok:                                  # torn or corrupted tail: everything after is dropped
                break
            good.append(rec)
            prev = rec['hash']
            pos += len(line) + 1
            size_ok = pos
        if size_ok < len(raw):
            self.recovered_bytes = len(raw) - size_ok
            with open(path, 'r+b') as f:
                f.truncate(size_ok)
        self.records = good

    def resume_at(self, n: int):
        """Keep records [0, n) as the state source; records from n on must be re-produced identically."""
        self._tail = self.records[n:]
        self.records = self.records[:n]

    @property
    def verifying(self) -> bool:
        return bool(self._tail)

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def verify_chain(self) -> bool:
        prev = GENESIS
        for i, r in enumerate(self.records):
            if r['seq'] != i or r['prev'] != prev or rec_hash(prev, r) != r['hash']:
                return False
            prev = r['hash']
        return True
