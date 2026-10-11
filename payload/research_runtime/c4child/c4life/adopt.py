"""CL-R5 G0.4 — CODE_UPGRADE: this kernel version adopts the life lived by a previous version (design §G0.4, §G0.5).

The parent's journal is evidence and is never changed.  It is read in binary mode only (never through `Journal`,
which repairs a torn tail by truncating the file), verified completely, and checked to be byte-identical after the
adoption.  Refusal is fail-closed (`AdoptionRefused.reason`):
  CHAIN                a line does not parse, a record is out of sequence or its prev/hash link is wrong (tampering,
                       truncation, a torn tail)
  PARENT_NOT_CLOSED    the parent did not stop at a tick boundary (its own last snapshot does not close its journal);
                       it must first be resumed and closed by its own code
  UNKNOWN_KIND         an (owner, kind) pair, decision subject, outbound kind or task operation this code does not
                       know, or an inbound event type the parent understood and this code would not
  PARENT_VIOLATES_LAWS the parent breaks a law that makes its RECORD trustworthy (CHAIN, CAPABILITY, COMMIT_BASIS,
                       DRIVE, MEDIATE, MIGRATION).  Laws about DERIVED beliefs (EVIDENCE, RETRACTION) are reported, not
                       adopted: no derived belief is adopted at all, the new learners re-derive everything from the
                       parent's inbound events (DEVIATIONS_G0.md §3)
  TARGET_EXISTS        the new home exists already (nothing is ever overwritten)
The only alternative to a refused adoption is a fork: a new life that adopts nothing.

Adoption, built in NEW_HOME + '.adopting' and renamed to NEW_HOME only when complete:
  1. genesis COMMIT `CODE_UPGRADE_BEGIN` (basis SYSTEM_MIGRATION): sha256 of the parent journal file, its head and
     length, the parent's configuration and lineage, both code digests;
  2. every tick of the parent, in order: its inbound events are delivered again with `adopted_from` (and, for an event
     that names a journal record, the parent's own resolution of that name); THIS constitution decides them and THESE
     learners learn from them; the parent's acts (OUTBOUND) and task decisions are carried over as history
     (BOUNDARY_NOTE / TASK with the parent's seq) and never re-sent; DRIVE runs only internal structural quanta;
  3. `adoption_report.json`: the parent's knowledge (last belief statuses, library, tasks) against the re-derived one;
  4. closing COMMIT `CODE_UPGRADE` (refs the genesis) with the report's sha256 and the state hash; snapshot.
The result is a deterministic function of (parent journal, parent configuration, this code): adopting twice gives the
same journal head and state hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from typing import Callable, Dict, List, Optional, Tuple

from .audit import audit
from .journal import GENESIS, KINDS, rec_hash
from .kernel import Life
from .operators import prog_str

READ_LAWS = ('CHAIN', 'CAPABILITY', 'COMMIT_BASIS', 'DRIVE', 'MEDIATE', 'MIGRATION')
DERIVED_LAWS = ('EVIDENCE', 'RETRACTION')
SUBJECTS = {'ADMIT_OBSERVATION', 'ADMIT_RECEIPT', 'ADMIT_LESSON', 'RETRACT_LESSON', 'RECORD_UTTERANCE',
            'ADMIT_PERMISSION', 'BELIEF_STATUS', 'LIBRARY_OPERATOR', 'WEIGHT_UPDATE', 'CODE_UPGRADE_BEGIN',
            'CODE_UPGRADE', 'ADMIT_LANG_DEMO'}
OUTBOUND_KINDS = {'ACTION', 'ANSWER', 'ASK', 'REPORT', 'CORRECTION'}
TASK_OPS = {'OPEN', 'ANSWERED', 'ANSWERED_PARTIAL', 'OPEN_UNKNOWN', 'ANSWERED_LATER', 'DONE', 'WAITING_FOR_TURN',
            'EXECUTING', 'ACHIEVED_VERIFIED'}
CFG_KEYS = ('learner', 'budget', 'reactive', 'always_busy', 'snapshot_every', 'quiet_report_limit', 'no_library',
            'w_seed')


class AdoptionRefused(RuntimeError):
    def __init__(self, reason: str, detail):
        super().__init__(f'{reason}: {detail}')
        self.reason, self.detail = reason, detail


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def event_types() -> set:
    """Inbound event types this code understands (has a MEDIATE handler for)."""
    return {n[4:].upper() for n in dir(Life) if n.startswith('_in_') and callable(getattr(Life, n))}


# ---------------------------------------------------------------------- 1. read-only verification of the parent
def read_parent(home: str) -> Tuple[List[dict], dict]:
    path = os.path.join(home, 'journal.jsonl')
    with open(path, 'rb') as f:
        raw = f.read()
    if not raw:
        raise AdoptionRefused('CHAIN', 'empty journal')
    if not raw.endswith(b'\n'):
        raise AdoptionRefused('CHAIN', 'the journal does not end with a complete record (torn tail)')
    recs, prev = [], GENESIS
    for i, line in enumerate(raw.split(b'\n')[:-1]):
        try:
            r = json.loads(line.decode('utf8'))
        except (ValueError, UnicodeDecodeError):
            raise AdoptionRefused('CHAIN', f'line {i} is not a JSON record')
        if not isinstance(r, dict) or r.get('seq') != i or r.get('prev') != prev or rec_hash(prev, r) != r.get('hash'):
            raise AdoptionRefused('CHAIN', f'record {i}: sequence number or hash link broken')
        recs.append(r)
        prev = r['hash']
    return recs, {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'head': prev,
                  'records': len(recs)}


def parent_cfg(home: str, info: dict) -> dict:
    """The configuration (learner, budget, ...) is not part of the journal; it is read from the parent's own last
    snapshot, which must close the journal exactly (same length and head) = the parent stopped at a tick boundary."""
    p = os.path.join(home, 'snapshot.json')
    if not os.path.exists(p):
        raise AdoptionRefused('PARENT_NOT_CLOSED', 'no snapshot.json next to the journal')
    with open(p, 'rb') as f:
        d = json.loads(f.read().decode('utf8'))
    if d.get('journal_len') != info['records'] or d.get('journal_head') != info['head']:
        raise AdoptionRefused('PARENT_NOT_CLOSED', {'snapshot_len': d.get('journal_len'), 'journal_len': info['records']})
    cfg = d.get('cfg') or {}
    return {k: cfg[k] for k in CFG_KEYS if k in cfg}


def check_known(recs: List[dict]) -> None:
    types = event_types()
    decision_of: Dict[int, dict] = {}
    for r in recs:
        if r['kind'] == 'COMMIT_DECISION' and r['payload'].get('basis_seq') is not None:
            decision_of.setdefault(r['payload']['basis_seq'], r['payload'])
    for r in recs:
        o, k, p = r.get('owner'), r.get('kind'), r.get('payload') or {}
        if k not in KINDS.get(o, ()):
            raise AdoptionRefused('UNKNOWN_KIND', f'record {r["seq"]}: ({o}, {k})')
        if k == 'COMMIT_DECISION':
            subj = p.get('subject')
            if subj not in SUBJECTS and (p.get('decision') or {}).get('reason') != f'UNAUTHORIZED_OPERATION:UNKNOWN_{subj}':
                raise AdoptionRefused('UNKNOWN_KIND', f'record {r["seq"]}: decision subject {subj}')
        elif k == 'INBOUND':
            typ = (p.get('event') or {}).get('type')
            if typ not in types:
                d = decision_of.get(r['seq'])
                if d is None or (d.get('decision') or {}).get('reason') != f'UNAUTHORIZED_OPERATION:UNKNOWN_{typ}':
                    raise AdoptionRefused('UNKNOWN_KIND', f'record {r["seq"]}: inbound event type {typ} understood by '
                                                          f'the parent, unknown to this code')
        elif k == 'OUTBOUND' and p.get('kind') not in OUTBOUND_KINDS:
            raise AdoptionRefused('UNKNOWN_KIND', f'record {r["seq"]}: outbound kind {p.get("kind")}')
        elif k == 'BOUNDARY_NOTE' and 'historical_outbound' in p and p['historical_outbound'].get('kind') not in OUTBOUND_KINDS:
            raise AdoptionRefused('UNKNOWN_KIND', f'record {r["seq"]}: historical outbound kind')
        elif k == 'TASK' and p.get('op') not in TASK_OPS:
            raise AdoptionRefused('UNKNOWN_KIND', f'record {r["seq"]}: task operation {p.get("op")}')


def check_laws(path: str) -> dict:
    a = audit(path)
    bad = {k: a['violations'].get(k, 0) for k in READ_LAWS if a['violations'].get(k, 0)}
    if bad:
        raise AdoptionRefused('PARENT_VIOLATES_LAWS', {'violations': bad,
                                                       'examples': {k: a['examples'].get(k) for k in bad}})
    return a


# ---------------------------------------------------------------------- 2. the adoption
def _plan(recs: List[dict]):
    """Group the parent's journal by tick: inbound events (with the parent's seq), history (acts and task decisions),
    and the parent's own resolution of journal references inside events (RETRACT -> lesson)."""
    inbound, history, task_inbound, refs = {}, {}, {}, {}
    retract_decision = {r['payload'].get('basis_seq'): r['payload'] for r in recs
                        if r['kind'] == 'COMMIT_DECISION' and r['payload'].get('subject') == 'RETRACT_LESSON'}
    for r in recs:
        k, p, t = r['kind'], r['payload'], r['world_t']
        if k == 'INBOUND':
            inbound.setdefault(t, []).append(r)
            if p['event'].get('type') == 'RETRACT':
                d = retract_decision.get(r['seq'])
                if d is None or 'lesson_seq' not in d:
                    raise AdoptionRefused('UNKNOWN_KIND', f'retraction {r["seq"]} without the parent\'s resolution of '
                                                          f'its lesson reference')
                refs[r['seq']] = {'lesson_seq': int(d['lesson_seq'])}
        elif k == 'OUTBOUND':
            history.setdefault(t, []).append({'seq': r['seq'], 'kind': 'OUTBOUND',
                                              'payload': {x: p[x] for x in ('channel', 'kind', 'content')}})
        elif k == 'BOUNDARY_NOTE' and 'historical_outbound' in p:
            history.setdefault(t, []).append({'seq': r['seq'], 'kind': 'OUTBOUND', 'payload': p['historical_outbound']})
        elif k == 'TASK':
            if p.get('op') == 'OPEN':
                ins = [x for x in r['refs'] if recs[x]['kind'] == 'INBOUND']
                if ins:
                    task_inbound[p['task']] = ins[0]
            else:
                history.setdefault(t, []).append({'seq': r['seq'], 'kind': 'TASK', 'payload': p})
    return inbound, history, task_inbound, refs


def adopt(parent_home: str, new_home: str, *, parent_code_digest: str, new_code_digest: str,
          progress: Optional[Callable[[int, int], None]] = None) -> dict:
    if os.path.exists(new_home):
        raise AdoptionRefused('TARGET_EXISTS', new_home)
    recs, info = read_parent(parent_home)
    cfg = parent_cfg(parent_home, info)
    check_known(recs)
    par_audit = check_laws(info['path'])
    inbound, history, task_inbound, refs = _plan(recs)
    ticks = [r['world_t'] for r in recs if isinstance(r.get('world_t'), int) and r['world_t'] >= 0]
    t0, t1 = min(inbound), max(ticks)
    g0 = recs[0]['payload'] if recs[0]['kind'] == 'COMMIT_DECISION' else {}
    parent_lineage = None
    if g0.get('subject') == 'CODE_UPGRADE_BEGIN':
        gp = g0.get('parent') or {}
        parent_lineage = {'journal_sha256': gp.get('journal_sha256'), 'head': gp.get('head'),
                          'records': gp.get('records'), 'code_digest': gp.get('code_digest')}

    tmp = new_home + '.adopting'
    if os.path.exists(tmp):
        shutil.rmtree(tmp)                    # an interrupted earlier adoption: a pure function of the parent, redone
    life = Life(tmp, **cfg)
    parent = {'journal_sha256': info['sha256'], 'head': info['head'], 'records': info['records'],
              'bytes': info['bytes'], 'ticks': [t0, t1], 'code_digest': parent_code_digest, 'cfg': cfg,
              'lineage': parent_lineage}
    g = life.code_upgrade_record('CODE_UPGRADE_BEGIN', {
        'parent': parent, 'new_code_digest': new_code_digest,
        'parent_audit': {'violations': par_audit['violations'], 'total': par_audit['total_violations']},
        'procedure': 'CL-R5 G0.4 c4life/adopt.py: inbound replayed and re-derived; acts and task decisions carried '
                     'as history; no derived belief adopted'})
    assert g['seq'] == 0
    life.lineage = {'parent_journal_sha256': info['sha256'], 'parent_head': info['head'],
                    'parent_records': info['records'], 'parent_code_digest': parent_code_digest,
                    'new_code_digest': new_code_digest, 'genesis_seq': 0, 'parent_lineage': parent_lineage}
    life.adopting = True
    life._adopt_refs = refs
    n_in = n_hist = 0
    for t in range(t0, t1 + 1):
        evr = inbound.get(t, [])
        hist = history.get(t, [])
        life.tick_adopt(t, [json.loads(json.dumps(r['payload']['event'], ensure_ascii=False)) for r in evr],
                        [r['seq'] for r in evr], hist, task_inbound)
        n_in += len(evr)
        n_hist += len(hist)
        if progress and (t - t0) % 500 == 0:
            progress(t, t1)
    life.adopting = False
    report = knowledge_report(recs, life, task_inbound, parent, par_audit, new_code_digest)
    rep_bytes = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode('utf8')
    rep_sha = hashlib.sha256(rep_bytes).hexdigest()
    with open(os.path.join(tmp, 'adoption_report.json'), 'wb') as f:
        f.write(rep_bytes)
    sh = life.state_hash()
    c = life.code_upgrade_record('CODE_UPGRADE', {
        'parent_journal_sha256': info['sha256'], 'parent_head': info['head'], 'adoption_report_sha256': rep_sha,
        'state_hash': sh, 'journal_len_before_close': len(life.j), 'replayed_inbound': n_in,
        'historical_records': n_hist, 'unmapped_task_ops': life.cost.get('adoption_unmapped_task_ops', 0),
        'continues_at_tick': t1 + 1}, refs=[0])
    life.lineage.update({'closed_seq': c['seq'], 'adoption_report_sha256': rep_sha})
    life._adopt_inbound, life._adopt_task, life._adopt_refs = {}, {}, {}
    life.snapshot()
    head, length, final_hash = life.j.head(), len(life.j), life.state_hash()
    life.close()
    if file_sha256(info['path']) != info['sha256']:
        raise RuntimeError('the parent journal changed during the adoption')   # read-only: must never happen
    os.rename(tmp, new_home)
    return {'new_home': new_home, 'journal_len': length, 'journal_head': head, 'state_hash_at_close': sh,
            'state_hash_final': final_hash, 'adoption_report_sha256': rep_sha, 'replayed_inbound': n_in,
            'historical_records': n_hist, 'ticks': [t0, t1], 'continues_at_tick': t1 + 1,
            'summary': report['summary']}


# ---------------------------------------------------------------------- 3. the knowledge report
def knowledge_report(recs, life: Life, task_inbound: Dict[str, int], parent: dict, par_audit: dict,
                     new_code_digest: str) -> dict:
    amap = dict(life._adopt_inbound)

    def norm(m):                               # lesson@<parent seq> -> lesson@<adopted seq>
        if not isinstance(m, str):
            return m
        return re.sub(r'lesson@(\d+)', lambda mo: f'lesson@{amap.get(int(mo.group(1)), "parent:" + mo.group(1))}', m)
    par: Dict[Tuple[str, str], dict] = {}
    for r in recs:
        p = r['payload']
        if r['kind'] == 'COMMIT_DECISION' and p.get('subject') == 'BELIEF_STATUS':
            par[(p['world'], p['target'])] = {'status': p['status'], 'mechanism': p.get('mechanism'), 'seq': r['seq'],
                                              't': r['world_t']}
    new: Dict[Tuple[str, str], dict] = {}
    for w in sorted(life.worlds):
        wm = life.worlds[w]
        static = life.world_meta[w]['static']
        for n in sorted(wm.targets):
            names = wm.names if not static else [m for m in wm.names if m != n]
            desc = wm.targets[n].map_description(names)
            new[(w, n)] = {'certified': bool(life.cert_state.get((w, n), False)), 'mechanism': desc.get('map')}
    rows = {'confirmed': [], 'different_mechanism': [], 'not_rederived_now_unknown': [], 'new_certified': [],
            'neither': []}
    for key in sorted(set(par) | set(new)):
        pc = par.get(key, {}).get('status') == 'CERTIFIED'
        nc = new.get(key, {}).get('certified', False)
        row = {'world': key[0], 'target': key[1], 'parent_status': par.get(key, {}).get('status'),
               'parent_mechanism': par.get(key, {}).get('mechanism'), 'new_mechanism': new.get(key, {}).get('mechanism')}
        if pc and nc:
            rows['confirmed' if norm(row['parent_mechanism']) == row['new_mechanism'] else 'different_mechanism'].append(row)
        elif pc:
            rows['not_rederived_now_unknown'].append(row)
        elif nc:
            rows['new_certified'].append(row)
        else:
            rows['neither'].append({'world': key[0], 'target': key[1]})
    # library
    par_lib = []
    for r in recs:
        if r['kind'] == 'COMMIT_DECISION' and r['payload'].get('subject') == 'LIBRARY_OPERATOR':
            lo = recs[r['payload']['proposal']]['payload']['library_operator']
            par_lib.append({'program': lo['program'], 'in_domains': list(lo['in_domains']), 'out_domain': lo['out_domain'],
                            'table': list(lo['table'])})
    new_lib = []
    for l in life.space.library:
        d = l.to_dict()
        new_lib.append({'name': d['name'], 'program': prog_str(l.program), 'in_domains': list(d['in_domains']),
                        'out_domain': d['out_domain'], 'table': [int(x) for x in d['table']]})
    key = lambda x: (tuple(x['in_domains']), x['out_domain'], tuple(int(v) for v in x['table']))
    nk = {key(x) for x in new_lib}
    pk = {key(x) for x in par_lib}
    lib = {'parent': par_lib, 'new': new_lib, 'confirmed': [x for x in par_lib if key(x) in nk],
           'not_rederived': [x for x in par_lib if key(x) not in nk], 'new_only': [x for x in new_lib if key(x) not in pk]}
    # tasks
    par_tasks: Dict[str, dict] = {}
    for r in recs:
        if r['kind'] == 'TASK':
            p = r['payload']
            if p['op'] == 'OPEN':
                q = (p.get('payload') or {}).get('q') or (p.get('payload') or {}).get('goal') or {}
                par_tasks[p['task']] = {'kind': p.get('kind'), 'status': 'OPEN', 'qid': q.get('qid') or q.get('gid')}
            elif p['task'] in par_tasks:
                par_tasks[p['task']]['status'] = p['op']
    mapping = {pt: life._adopt_task.get(amap.get(pin, -1)) for pt, pin in sorted(task_inbound.items())}
    new_tasks = {tid: {'kind': t['kind'], 'status': t['status'], 'asked': bool(t.get('asked'))}
                 for tid, t in sorted(life.tasks.items())}
    task_rows = []
    for pt, x in sorted(par_tasks.items()):
        nt = mapping.get(pt)
        task_rows.append({'parent_task': pt, 'kind': x['kind'], 'qid': x['qid'], 'parent_status': x['status'],
                          'new_task': nt, 'new_status': new_tasks.get(nt, {}).get('status') if nt else None})
    mism = [r_ for r_ in task_rows if r_['new_task'] and r_['parent_status'] != r_['new_status']]
    summary = {'beliefs_confirmed': len(rows['confirmed']), 'beliefs_different_mechanism': len(rows['different_mechanism']),
               'beliefs_not_rederived': len(rows['not_rederived_now_unknown']), 'beliefs_new': len(rows['new_certified']),
               'library_confirmed': len(lib['confirmed']), 'library_not_rederived': len(lib['not_rederived']),
               'library_new': len(lib['new_only']), 'tasks_parent': len(par_tasks),
               'tasks_mapped': sum(1 for r_ in task_rows if r_['new_task']),
               'tasks_status_mismatch': len(mism), 'own_statements_carried': len(life.persp.own_statements()),
               'parent_derived_law_violations': {k: par_audit['violations'].get(k, 0) for k in DERIVED_LAWS}}
    return {'schema': 'CL-R5 G0.4 adoption report v1', 'parent': parent, 'new_code_digest': new_code_digest,
            'summary': summary, 'beliefs': rows, 'library': lib, 'tasks': task_rows,
            'parent_audit': {'violations': par_audit['violations'], 'total': par_audit['total_violations'],
                             'examples': par_audit['examples'],
                             'note': 'EVIDENCE/RETRACTION concern derived beliefs of the parent; none is adopted'},
            'note': 'a different mechanism string can still be the same function; "not re-derived" means: not '
                    'certified by the new code from the same evidence, i.e. UNKNOWN now'}


def tree_digest(root: str) -> str:
    """The code version of a tree: the digest of the first freeze file (design/FREEZE_CODE_G0R3/_G0R2/_G0/.json)
    whose files are all unchanged; otherwise 'UNFROZEN:' / 'MODIFIED_SINCE_FREEZE:' + a digest of the code files
    computed like tools/freeze.py."""
    from pathlib import Path
    R = Path(root)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    files = sorted([*R.glob('c4life/*.py'), *R.glob('experiments/*.py'), *R.glob('tools/*.py'),
                    *([R / 'reg' / 'reg_harness.py'] if (R / 'reg' / 'reg_harness.py').exists() else []),
                    *([R / 'tests' / 'test_c4life.py'] if (R / 'tests' / 'test_c4life.py').exists() else [])])
    computed = hashlib.sha256(json.dumps({str(p.relative_to(R)): sha(p) for p in files}, sort_keys=True).encode()).hexdigest()
    found = False
    for name in ('FREEZE_CODE_G1.json', 'FREEZE_CODE_G0R3.json', 'FREEZE_CODE_G0R2.json', 'FREEZE_CODE_G0.json',
                 'FREEZE_CODE.json'):
        fp = R / 'design' / name
        if fp.exists():
            found = True
            fz = json.loads(fp.read_text(encoding='utf8'))
            if all((R / f).exists() and sha(R / f) == h for f, h in fz['files'].items()):
                return fz['digest']
    return ('MODIFIED_SINCE_FREEZE:' if found else 'UNFROZEN:') + computed


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    parent, new = argv[0], argv[1]
    opt = lambda n, d=None: argv[argv.index(n) + 1] if n in argv else d
    try:
        res = adopt(parent, new, parent_code_digest=opt('--parent-code-digest', 'UNKNOWN'),
                    new_code_digest=opt('--new-code-digest', 'UNKNOWN'),
                    progress=lambda t, t1: print(json.dumps({'adopting_tick': t, 'of': t1}), file=sys.stderr, flush=True))
    except AdoptionRefused as e:
        print(json.dumps({'refused': e.reason, 'detail': e.detail}, ensure_ascii=False, default=str))
        return 3
    print(json.dumps(res, ensure_ascii=False))
    return 0
