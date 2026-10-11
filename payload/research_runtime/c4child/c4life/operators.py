"""Operator space of the structural learner S: typed functions on small finite domains.

A SIGNATURE is (input domain sizes..., output domain size); domains are 2 (bool) or 4 (small counter).
An operator is the full table of a function over all input configurations (row-major order); it is represented once,
by its shortest program (observational equivalence on the WHOLE finite domain = semantic equivalence).
Universal primitives (fixed in code, the honest boundary of what is 'given'):
  leaves  IN(i), constants 0/1 (bool) and 0..3 (counter)
  bool    NOT, AND, OR, XOR, IF(bool, x, x)
  counter EQ, GE (-> bool), ADD (mod 4), IF
Everything else is learned: library operators are tables promoted from certified mechanisms (with provenance) and
then usable as single symbols.  Enumerations are kept per library version, so a world's prior is frozen at its birth
(no double counting)."""
from __future__ import annotations

import itertools
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

BOOL, CNT = 2, 4
BASE_OPS = {  # name: (arg types, result type) ; types are domain sizes
    'NOT': ((BOOL,), BOOL), 'AND': ((BOOL, BOOL), BOOL), 'OR': ((BOOL, BOOL), BOOL), 'XOR': ((BOOL, BOOL), BOOL),
    'EQ': ((CNT, CNT), BOOL), 'GE': ((CNT, CNT), BOOL), 'ADD': ((CNT, CNT), CNT),
}
COMMUTATIVE = {'AND', 'OR', 'XOR', 'EQ', 'ADD'}


def configs(in_domains: Tuple[int, ...]) -> np.ndarray:
    """All input configurations, row-major; shape (n_conf, n_inputs)."""
    if not in_domains:
        return np.zeros((1, 0), dtype=np.int8)
    return np.array(list(itertools.product(*[range(d) for d in in_domains])), dtype=np.int8)


def strides(in_domains: Tuple[int, ...]) -> np.ndarray:
    s, out = 1, []
    for d in reversed(in_domains):
        out.append(s)
        s *= d
    return np.array(list(reversed(out)), dtype=np.int64)


class LibOp:
    __slots__ = ('name', 'in_domains', 'out_domain', 'table', 'program', 'version', 'provenance')

    def __init__(self, name, in_domains, out_domain, table, program, version, provenance):
        self.name, self.in_domains, self.out_domain = name, tuple(in_domains), out_domain
        self.table, self.program, self.version, self.provenance = np.asarray(table, dtype=np.int8), program, version, provenance

    def to_dict(self):
        return {'name': self.name, 'in_domains': list(self.in_domains), 'out_domain': self.out_domain,
                'table': self.table.tolist(), 'program': self.program, 'version': self.version,
                'provenance': self.provenance}


def prog_size(p) -> int:
    if p[0] in ('IN', 'C'):
        return 1
    return 1 + sum(prog_size(a) for a in p[1:] if isinstance(a, (list, tuple)))


def prog_str(p, names=None) -> str:
    if p[0] == 'IN':
        return names[p[1]] if names else f'x{p[1]}'
    if p[0] == 'C':
        return str(p[1])
    if p[0] == 'LIB':
        return f'{p[1]}(' + ', '.join(prog_str(a, names) for a in p[2:]) + ')'
    return f'{p[0]}(' + ', '.join(prog_str(a, names) for a in p[1:]) + ')'


class Signature:
    """All operators of one signature AT ONE LIBRARY VERSION, by increasing program size.  A world born at library
    version v uses only signatures enumerated with library operators of version <= v: its prior is frozen at birth
    (abstractions learned later never re-weight the data they came from)."""

    def __init__(self, in_domains: Tuple[int, ...], out_domain: int, version: int = 0):
        self.in_domains, self.out_domain, self.version = tuple(in_domains), out_domain, version
        self.conf = configs(self.in_domains)
        self.n_conf = len(self.conf)
        self.terms: Dict[int, Dict[bytes, Tuple[int, tuple]]] = {BOOL: {}, CNT: {}}   # type -> key -> (size, prog)
        self.vecs: Dict[int, Dict[bytes, np.ndarray]] = {BOOL: {}, CNT: {}}
        self.by_size: Dict[int, Dict[int, List[bytes]]] = {BOOL: {}, CNT: {}}
        self.max_size = 0
        self.candidates_evaluated = 0
        self.skipped_products = 0
        # operators (= terms of the output type), in birth order
        self.op_keys: List[bytes] = []
        self.op_index: Dict[bytes, int] = {}
        self.op_tables: np.ndarray = np.zeros((0, self.n_conf), dtype=np.int8)
        self.op_progs: List[tuple] = []
        self.op_size: List[int] = []
        self.op_depends: np.ndarray = np.zeros((0, len(self.in_domains)), dtype=bool)
        self._sizes = None

    # -------------------------------------------------------------- enumeration
    def _add(self, typ: int, vec: np.ndarray, size: int, prog: tuple, new_ops: list):
        key = vec.astype(np.int8).tobytes()
        old = self.terms[typ].get(key)
        if old is not None and old[0] <= size:
            return
        self.terms[typ][key] = (size, prog)
        self.vecs[typ][key] = vec.astype(np.int8)
        self.by_size[typ].setdefault(size, []).append(key)
        if typ == self.out_domain and key not in self.op_index:
            self.op_index[key] = len(self.op_keys)
            self.op_keys.append(key)
            self.op_progs.append(prog)
            self.op_size.append(size)
            new_ops.append(vec.astype(np.int8))

    def _stack(self, typ, size):
        keys = self.by_size[typ].get(size, [])
        if not keys:
            return keys, None
        return keys, np.stack([self.vecs[typ][k] for k in keys])

    def _first_new(self, typ, R: np.ndarray, size: int):
        """Indices (in flat order) of rows of R that are new functions of type typ at this size."""
        if len(R) == 0:
            return []
        u, first = np.unique(R, axis=0, return_index=True)
        out = []
        for i in np.sort(first):
            key = R[i].tobytes()
            old = self.terms[typ].get(key)
            if old is None or old[0] > size:
                out.append(int(i))
        return out

    def grow(self, library: List[LibOp], max_candidates: Optional[int] = None) -> Dict[str, int]:
        """Enumerate all programs of size max_size+1 (with the given library operators).  Returns counts."""
        new_ops: list = []
        n0 = self.candidates_evaluated
        size = self.max_size + 1
        if size == 1:
            for i, d in enumerate(self.in_domains):
                self._add(d, self.conf[:, i].copy(), 1, ('IN', i), new_ops)
            for typ, consts in ((BOOL, (0, 1)), (CNT, (0, 1, 2, 3))):
                for c in consts:
                    self._add(typ, np.full(self.n_conf, c, dtype=np.int8), 1, ('C', c), new_ops)
            self.candidates_evaluated += len(self.in_domains) + 6
        else:
            keys, V = self._stack(BOOL, size - 1)
            if V is not None:
                R = (1 - V).astype(np.int8)
                self.candidates_evaluated += len(keys)
                for i in self._first_new(BOOL, R, size):
                    self._add(BOOL, R[i], size, ('NOT', self.terms[BOOL][keys[i]][1]), new_ops)
            for op, (argt, tr) in BASE_OPS.items():
                if op == 'NOT':
                    continue
                ta, tb = argt
                for s1 in range(1, size - 1):
                    s2 = size - 1 - s1
                    if op in COMMUTATIVE and s1 > s2:
                        continue
                    ka, A = self._stack(ta, s1)
                    kb, Bm = self._stack(tb, s2)
                    if A is None or Bm is None:
                        continue
                    X, Y = A[:, None, :].astype(np.int16), Bm[None, :, :].astype(np.int16)
                    if op == 'AND':
                        R = X & Y
                    elif op == 'OR':
                        R = X | Y
                    elif op == 'XOR':
                        R = X ^ Y
                    elif op == 'EQ':
                        R = (X == Y)
                    elif op == 'GE':
                        R = (X >= Y)
                    else:  # ADD
                        R = (X + Y) % CNT
                    R = R.astype(np.int8).reshape(-1, self.n_conf)
                    self.candidates_evaluated += R.shape[0]
                    nb = len(kb)
                    for flat in self._first_new(tr, R, size):
                        i, j = divmod(flat, nb)
                        self._add(tr, R[flat], size, (op, self.terms[ta][ka[i]][1], self.terms[tb][kb[j]][1]), new_ops)
                    if max_candidates and self.candidates_evaluated - n0 > max_candidates:
                        break
            for typ in (BOOL, CNT):
                for s1 in range(1, size - 2):
                    for s2 in range(1, size - 1 - s1):
                        s3 = size - 1 - s1 - s2
                        kc, C = self._stack(BOOL, s1)
                        ka, A = self._stack(typ, s2)
                        kb, Bm = self._stack(typ, s3)
                        if C is None or A is None or Bm is None:
                            continue
                        if len(kc) * len(ka) * len(kb) > 2_000_000:
                            self.skipped_products += 1         # bounded: very large IF products are skipped (counted)
                            continue
                        R = np.where(C[:, None, None, :] == 1, A[None, :, None, :], Bm[None, None, :, :])
                        R = R.reshape(-1, self.n_conf).astype(np.int8)
                        self.candidates_evaluated += R.shape[0]
                        na, nb = len(ka), len(kb)
                        for flat in self._first_new(typ, R, size):
                            c, rest = divmod(flat, na * nb)
                            a, b = divmod(rest, nb)
                            self._add(typ, R[flat], size, ('IF', self.terms[BOOL][kc[c]][1], self.terms[typ][ka[a]][1],
                                                           self.terms[typ][kb[b]][1]), new_ops)
            for lop in library:
                m = len(lop.in_domains)
                st = strides(lop.in_domains)
                for split in _compositions(size - 1, m):
                    stacks = [self._stack(lop.in_domains[j], split[j]) for j in range(m)]
                    if any(V is None for _, V in stacks):
                        continue
                    dims = [len(k) for k, _ in stacks]
                    if int(np.prod(dims)) > 2_000_000:
                        self.skipped_products += 1
                        continue
                    idx = np.zeros(dims + [self.n_conf], dtype=np.int64)
                    for j, (k, V) in enumerate(stacks):
                        shape = [1] * m + [self.n_conf]
                        shape[j] = len(k)
                        idx = idx + V.astype(np.int64).reshape(shape) * int(st[j])
                    R = lop.table[idx].reshape(-1, self.n_conf).astype(np.int8)
                    self.candidates_evaluated += R.shape[0]
                    for flat in self._first_new(lop.out_domain, R, size):
                        combo = np.unravel_index(flat, dims)
                        prog = ('LIB', lop.name) + tuple(self.terms[lop.in_domains[j]][stacks[j][0][combo[j]]][1]
                                                          for j in range(m))
                        self._add(lop.out_domain, R[flat], size, prog, new_ops)
        self.max_size = size
        if new_ops:
            T = np.stack(new_ops)
            self.op_tables = np.concatenate([self.op_tables, T]) if len(self.op_tables) else T
            self.op_depends = np.concatenate([self.op_depends, self._depends(T)]) if len(self.op_depends) else self._depends(T)
        self._sizes = None
        return {'size': size, 'new_operators': len(new_ops), 'candidates': self.candidates_evaluated - n0}

    def _depends(self, T: np.ndarray) -> np.ndarray:
        """Which inputs each table actually depends on (shape (n, n_inputs))."""
        out = np.zeros((len(T), len(self.in_domains)), dtype=bool)
        st = strides(self.in_domains)
        for i, d in enumerate(self.in_domains):
            base = self.conf.copy()
            for v in range(1, d):
                alt = base.copy()
                alt[:, i] = (alt[:, i] + v) % d
                idx = (alt.astype(np.int64) * st).sum(1)
                out[:, i] |= (T != T[:, idx]).any(1)
        return out

    def sizes(self) -> np.ndarray:
        if self._sizes is None or len(self._sizes) != len(self.op_size):
            self._sizes = np.array(self.op_size, dtype=np.int64)
        return self._sizes

    # ------------------------------------------------------------ exact persistence (no pickle)
    def digest(self) -> str:
        import hashlib
        h = hashlib.sha256()
        for k, z in zip(self.op_keys, self.op_size):
            h.update(k)
            h.update(int(z).to_bytes(2, 'little'))
        return h.hexdigest()

    def to_dict(self) -> dict:
        """The enumeration is a pure function of (inputs, output, library version, size): only that and a digest
        are stored; loading re-derives it and checks the digest."""
        return {'in_domains': list(self.in_domains), 'out_domain': self.out_domain, 'version': self.version,
                'max_size': self.max_size, 'n_ops': len(self.op_keys), 'digest': self.digest()}


def _tup(x):
    if isinstance(x, list):
        return tuple(_tup(v) for v in x)
    return x


def _compositions(total: int, parts: int):
    if parts == 1:
        if total >= 1:
            yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in _compositions(total - first, parts - 1):
            yield (first,) + rest


class OperatorSpace:
    """All signatures (one enumeration per library version in use) plus the learned library (append-only)."""

    def __init__(self):
        self.sigs: Dict[Tuple, Signature] = {}
        self.library: List[LibOp] = []
        self.version = 0

    def sig(self, in_domains, out_domain, version: int) -> Signature:
        key = (tuple(in_domains), out_domain, int(version))
        if key not in self.sigs:
            self.sigs[key] = Signature(tuple(in_domains), out_domain, int(version))
        return self.sigs[key]

    def symbols(self, version: int) -> int:
        """Alphabet size for the description length at a library version (base ops + leaves + visible lib ops)."""
        return len(BASE_OPS) + 1 + 4 + 6 + sum(1 for l in self.library if l.version <= version)

    def bits_per_symbol(self, version: int) -> float:
        return math.log2(self.symbols(version))

    def ensure(self, in_domains, out_domain, size: int, version: int) -> Signature:
        s = self.sig(in_domains, out_domain, version)
        lib = [l for l in self.library if l.version <= version]
        while s.max_size < size:
            s.grow(lib)
        return s

    def add_library_op(self, in_domains, out_domain, table, program, provenance) -> LibOp:
        self.version += 1
        name = f'OP{self.version}'
        op = LibOp(name, in_domains, out_domain, table, program, self.version, provenance)
        self.library.append(op)
        return op

    def enumeration_cost(self) -> dict:
        return {'signatures': len(self.sigs), 'operators': sum(len(s.op_keys) for s in self.sigs.values()),
                'candidates_evaluated': sum(s.candidates_evaluated for s in self.sigs.values()),
                'skipped_products': sum(s.skipped_products for s in self.sigs.values())}

    def to_dict(self) -> dict:
        return {'version': self.version, 'library': [l.to_dict() for l in self.library],
                'sigs': [s.to_dict() for k, s in sorted(self.sigs.items(), key=lambda kv: str(kv[0]))]}

    @classmethod
    def from_dict(cls, d) -> 'OperatorSpace':
        sp = cls()
        sp.version = d['version']
        sp.library = [LibOp(l['name'], l['in_domains'], l['out_domain'], l['table'], _tup(l['program']), l['version'],
                            l['provenance']) for l in d['library']]
        for sd in d['sigs']:
            s = sp.ensure(tuple(sd['in_domains']), sd['out_domain'], sd['max_size'], sd['version'])
            if len(s.op_keys) != sd['n_ops'] or s.digest() != sd['digest']:
                raise ValueError(f'operator enumeration not reproducible for {sd["in_domains"]} v{sd["version"]}')
        return sp
