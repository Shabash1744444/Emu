"""Cold checkpoint on a COPY of D8 (design §4.6): the D8 graph, its H3 templates, runtime state and organs are
carried over unchanged; the life kernel's state is added as organs/c4life_*.json:
  organs/c4life_snapshot.json  the derived state (exact, compact)
  organs/c4life_journal.json   the whole hash-chained journal (the history; the snapshot is only a cache of it)
  organs/c4life_meta.json      schema, journal head, state hash, provenance (which D8 file, its sha256)
The canonical G331/D8 originals are only READ.  Loading re-creates a kernel home and resumes it with the journal
verified (Divergence = not the same life).

usage (CLI):
  python3 -I -B -m c4life.c4m_export export HOME D8.c4m OUT.c4m G331_RUNTIME_DIR
  python3 -I -B -m c4life.c4m_export import IN.c4m NEW_HOME G331_RUNTIME_DIR
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Optional


def _ckpt(runtime_dir: str):
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    from c4child import checkpoint
    return checkpoint


def _sha_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def graph_digest(g) -> str:
    """Digest of the D8 graph's facts as a set (ids, relations, values, statuses) — must be unchanged."""
    d = g.to_dict()
    rows = sorted(json.dumps({k: x.get(k) for k in ('fact_id', 'subject', 'relation', 'object_value', 'polarity', 'status')},
                             ensure_ascii=False, sort_keys=True) for x in d.get('facts', []))
    return hashlib.sha256('\n'.join(rows).encode('utf8')).hexdigest()


def export_c4m(home: str, d8_path: str, out_path: str, runtime_dir: str, note: Optional[str] = None) -> dict:
    ck = _ckpt(runtime_dir)
    g, h, manifest, rs, organs = ck.load_c4m_compact(d8_path, with_runtime=True, with_organs=True, hydrate_cold=True)
    before = graph_digest(g)
    with open(os.path.join(home, 'snapshot.json'), encoding='utf8') as f:
        snap = json.load(f)
    with open(os.path.join(home, 'journal.jsonl'), encoding='utf8') as f:
        journal = [json.loads(l) for l in f if l.strip()]
    if len(journal) != snap['journal_len'] or journal[-1]['hash'] != snap['journal_head']:
        raise ValueError('snapshot and journal do not belong to the same moment of the same life')
    from .kernel import Life
    life = Life.resume(home)
    state_hash = life.state_hash()
    life.close()
    meta_c4life = {'schema': 'C4LIFE_C4M_ORGANS_V0.1', 'journal_len': len(journal), 'journal_head': snap['journal_head'],
                   'state_hash': state_hash, 'base_model': os.path.basename(d8_path), 'base_model_sha256': _sha_file(d8_path),
                   'base_graph_digest': before, 'note': note or 'CL-R4 research checkpoint (noncanonical)',
                   'canonical': False}
    organs = dict(organs or {})
    organs['c4life_snapshot'] = snap
    organs['c4life_journal'] = journal
    organs['c4life_meta'] = meta_c4life
    meta = dict(manifest.get('meta') or {})
    meta['c4life'] = {k: meta_c4life[k] for k in ('schema', 'journal_head', 'state_hash', 'base_model_sha256', 'canonical')}
    ck.save_c4m_compact(out_path, g, h, meta=meta, runtime_state=rs, organs=organs, include_cold=True)
    # verify: the D8 graph inside the export is the same graph
    g2, h2, m2, rs2, org2 = ck.load_c4m_compact(out_path, with_runtime=True, with_organs=True, hydrate_cold=True)
    after = graph_digest(g2)
    return {'out': out_path, 'sha256': _sha_file(out_path), 'graph_unchanged': before == after,
            'organs': sorted(org2), **meta_c4life}


def import_c4m(c4m_path: str, home: str, runtime_dir: str):
    ck = _ckpt(runtime_dir)
    g, h, manifest, organs = ck.load_c4m_compact(c4m_path, with_organs=True)
    if 'c4life_meta' not in organs:
        raise ValueError('no c4life organs in this checkpoint')
    os.makedirs(home, exist_ok=True)
    if os.listdir(home):
        raise ValueError('import target must be an empty directory')
    with open(os.path.join(home, 'journal.jsonl'), 'w', encoding='utf8') as f:
        for r in organs['c4life_journal']:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(os.path.join(home, 'snapshot.json'), 'w', encoding='utf8') as f:
        json.dump(organs['c4life_snapshot'], f, ensure_ascii=False, sort_keys=True)
    from .journal import Journal
    from .kernel import Life
    j = Journal(os.path.join(home, 'journal.jsonl'))
    if not j.verify_chain() or j.head() != organs['c4life_meta']['journal_head']:
        raise ValueError('journal chain broken in checkpoint')
    j.close()
    life = Life.resume(home)
    if life.state_hash() != organs['c4life_meta']['state_hash']:
        raise ValueError('derived state differs from the exported one')
    return life, organs['c4life_meta']


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'export':
        print(json.dumps(export_c4m(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]), ensure_ascii=False, indent=1))
    elif cmd == 'import':
        life, meta = import_c4m(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps({'resumed_world_t': life.world_t, 'journal_len': len(life.j), 'state_hash': life.state_hash(),
                          'meta': meta}, ensure_ascii=False, indent=1))
