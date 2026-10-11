"""Auditor of the four owners and of self-contamination (design §4.2), re-derived from the journal FILE alone.

Checks (each violation is reported with the record seq):
  CHAIN        hash chain, sequence numbers
  CAPABILITY   every record's kind is one its owner may write
  COMMIT_BASIS every COMMIT decision re-computed from the referenced INBOUND (channel role, boundary verification,
               origin) gives the same disposition and basis; lessons only from the teacher channel; retractions only
               by the same source
  EVIDENCE     every certified belief, library operator and credit update is rooted ONLY in verified observations
               (and verified receipts): never in HYPOTHESIS / PREDICTION / SIMULATION / RECALL / SIM-REPLAY material
  DRIVE        every executed quantum product (hypothesis, prediction, proposal, plan, contradiction, explanation,
               recall) and every outbound act references a DRIVE decision
  MEDIATE      every external action references a committed, unrevoked human permission for that switch
  RETRACTION   a retracted lesson is never used again
  MIGRATION    (CL-R5 G0.4) a CODE_UPGRADE: CODE_UPGRADE_BEGIN only as the genesis, exactly one closing CODE_UPGRADE
               citing it; between them only adopted inbound, no outbound act, only internal structural DRIVE quanta;
               nothing adopted after the closing record.  A journal reference inside an adopted event names a record
               of the parent and is resolved through the adoption map (`adopted_from`, `parent_refs`).
`audit_adoption(new, parent)` checks the faithfulness of an adoption against the parent journal file.
"""
from __future__ import annotations

import json
from typing import Dict, List

from .constitution import decide
from .journal import GENESIS, KINDS, rec_hash

QUANTUM_PRODUCTS = {'HYPOTHESIS', 'PREDICTION', 'PROPOSAL', 'PLAN', 'CONTRADICTION', 'EXPLANATION', 'RECALL',
                    'SIMULATION'}
NEVER_EVIDENCE = {'HYPOTHESIS', 'PREDICTION', 'SIMULATION', 'RECALL', 'EXPLANATION', 'PROPOSAL', 'PLAN',
                  'INTERPRETATION', 'CONTRADICTION'}


def load(path: str) -> List[dict]:
    out = []
    with open(path, encoding='utf8') as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


N_CERT = 6                    # CL-R5 G0.1: fresh confident-correct predictions a certificate needs (S and W)


def audit(path: str) -> dict:
    recs = load(path)
    v: Dict[str, List] = {k: [] for k in ('CHAIN', 'CAPABILITY', 'COMMIT_BASIS', 'EVIDENCE', 'DRIVE', 'MEDIATE',
                                          'RETRACTION', 'MIGRATION')}
    counts: Dict[str, int] = {}
    prev = GENESIS
    for i, r in enumerate(recs):
        if r.get('seq') != i or r.get('prev') != prev or rec_hash(prev, r) != r.get('hash'):
            v['CHAIN'].append(i)
        prev = r.get('hash')
        if r['kind'] not in KINDS.get(r['owner'], ()):
            v['CAPABILITY'].append(i)
        counts[f"{r['owner']}/{r['kind']}"] = counts.get(f"{r['owner']}/{r['kind']}", 0) + 1
    by = {r['seq']: r for r in recs}
    # G2.3 auditor performance-only patch: O(n) verified host receipt index.
    # Before: each acquired contrast scanned ALL previous journal records.
    # Equivalent authorization: same raw content, same host envelope, earlier seq.
    from .temporal_patterns import trace_root as _tr, validate_trace as _vt
    from .metric_concepts import metric_root as _mr, measured as _vm
    from .relational_programs import witness_root as _rr, features as _rf
    verified_roots={'TEMPORAL_SIM_RECEIPT':{},'METRIC_SIM_RECEIPT':{},'RELATIONAL_SIM_RECEIPT':{},'JOINT_SIM_RECEIPT':{},'STORY_SIM_RECEIPT':{}}
    for _rec in recs:
        if _rec['kind']!='INBOUND':continue
        _ev=_rec['payload'].get('event') or {}
        _kind=_ev.get('type')
        if _kind not in verified_roots or (_ev.get('role'),_ev.get('verified_by'),_ev.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            continue
        _content=_ev.get('content') or {};_w=_content.get('witness');_root=_content.get('root')
        try:
            if _kind=='STORY_SIM_RECEIPT':
                from .story_meanings import event_root as _sr,validate as _sv
                _evstory=_content.get('event');_sv(_evstory);_calculated=_sr(_evstory)
            elif _kind=='JOINT_SIM_RECEIPT':
                from .joint_language import joint_root as _jr
                _calculated=_jr(_w,_content.get('scene'))
            elif _kind=='TEMPORAL_SIM_RECEIPT':_vt(_w);_calculated=_tr(_w)
            elif _kind=='METRIC_SIM_RECEIPT':_vm(_w);_calculated=_mr(_w)
            else:_rf(_w);_calculated=_rr(_w)
            if _calculated==_root:verified_roots[_kind].setdefault(_root,_rec['seq'])
        except (TypeError,ValueError,KeyError):pass
    # G2.7 audit performance repair, not a policy relaxation: previously
    # every grounding/event/relational lesson scanned the complete earlier
    # journal. Cache only host-authenticated receipts, with their earliest seq.
    # A lesson is valid only when receipt_seq < lesson_seq, exactly as before.
    from .event_semantics import content_root as _er, measured_trace as _et
    grounding_index={};event_trace_index={}
    for _rec in recs:
        if _rec['kind']!='INBOUND':continue
        _e=_rec['payload'].get('event') or {}
        if (_e.get('role'),_e.get('verified_by'),_e.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            continue
        _kind=_e.get('type');_c=_e.get('content') or {};_root=_c.get('root')
        if _kind=='GROUNDING_SIM_RECEIPT' and isinstance(_root,str):
            grounding_index.setdefault(_root,_rec['seq'])
        elif _kind=='EVENT_TRACE_SIM_RECEIPT' and isinstance(_root,str):
            try:
                _et(_c['witness'])
                if _er(_c['witness'])==_root:event_trace_index.setdefault(_root,_rec['seq'])
            except (TypeError,ValueError,PermissionError,KeyError):pass
    # CL-R5 G0.4: parent seq -> adopted seq (a journal reference inside an adopted event names a PARENT record)
    adopt_map = {r['payload']['adopted_from']: r['seq'] for r in recs
                 if r['kind'] == 'INBOUND' and 'adopted_from' in r['payload']}

    def lesson_ref(ib):
        tgt = ib['payload']['event'].get('content', {}).get('lesson_seq')
        if 'adopted_from' in ib['payload'] and tgt is not None:
            pr = ib['payload'].get('parent_refs') or {}
            return adopt_map.get(int(pr.get('lesson_seq', tgt)), -1)
        return tgt

    def inbound(seq):
        r = by.get(seq)
        return r if r is not None and r['owner'] == 'MEDIATE' and r['kind'] == 'INBOUND' else None

    # --- committed verified observations / receipts
    committed_obs, committed_receipts = set(), set()
    decisions_for: Dict[int, list] = {}
    def basis_of(r):
        b = r['payload'].get('basis_seq')
        if b is None or b not in r['refs']:
            return None
        return b
    for r in recs:
        if r['kind'] == 'COMMIT_DECISION' and basis_of(r) is not None:
            decisions_for.setdefault(basis_of(r), []).append(r)
    for s, ds in decisions_for.items():
        ib = inbound(s)
        if ib is None:
            continue
        ev = ib['payload']['event']
        for d in ds:
            dd = d['payload']['decision']
            if dd['disposition'] == 'COMMIT' and dd.get('basis') == 'VERIFIED_OBSERVATION' and \
                    ev['type'] in ('PERCEPT', 'ENTITY_OBS') and ev.get('role') == 'SENSOR' and ev.get('verified_by') == 'SENSOR':
                committed_obs.add(s)
            if dd['disposition'] == 'COMMIT' and dd.get('basis') == 'VERIFIED_RECEIPT':
                committed_receipts.add(s)

    lessons: Dict[int, dict] = {}            # lesson inbound seq -> {'channel', 'retracted_at'}
    frame_lessons: Dict[int, dict] = {}      # G1.2 independent language convention lessons
    discourse_lessons: Dict[int, dict] = {}  # G1.3 source-linked two-event lessons
    weak_lessons: Dict[int, dict] = {}       # G1.4 source-linked weak-boundary lessons
    grounding_lessons: Dict[int, dict] = {}  # G1.5 attested situated language demonstrations
    event_trace_lessons: Dict[int, dict] = {}  # G1.8 event meanings from attested simulation traces
    relational_lessons: Dict[int, dict] = {}  # G2.1
    temporal_lessons: Dict[int, dict] = {}  # G2.2
    metric_lessons: Dict[int, dict] = {}  # G2.3
    joint_lessons: Dict[int, dict] = {}   # G2.4
    text_story_lessons: Dict[int, dict] = {} # G2.6
    morph_story_lessons: Dict[int, dict] = {} # G2.7
    story_lessons: Dict[int, dict] = {}   # G2.5
    dialogue_lessons: Dict[int, dict] = {} # G2.8
    permissions: Dict[tuple, int] = {}       # (world, switch) -> commit seq
    op_map = {'PERCEPT': 'ADMIT_OBSERVATION', 'ENTITY_OBS': 'ADMIT_OBSERVATION', 'WORLD_INTRO': 'ADMIT_OBSERVATION',
              'RECEIPT': 'ADMIT_RECEIPT', 'LESSON': 'ADMIT_LESSON', 'PERMISSION': 'ADMIT_PERMISSION',
              'UTTERANCE': 'RECORD_UTTERANCE', 'QUESTION': 'RECORD_UTTERANCE', 'GOAL': 'RECORD_UTTERANCE',
              'RETRACT': 'RETRACT_LESSON', 'LANG_EXPERIENCE': 'ADMIT_LANG_DEMO', 'LANG_QUERY': 'RECORD_UTTERANCE',
              'CLOCK_ANCHOR': 'ADMIT_CLOCK_ANCHOR', 'CLOCK_QUERY': 'RECORD_UTTERANCE',
              'FRAME_SIM_RECEIPT':'RECORD_UTTERANCE', 'FRAME_TEACH':'ADMIT_LANG_DEMO',
              'FRAME_QUERY':'RECORD_UTTERANCE', 'FRAME_RETRACT':'RETRACT_LESSON',
              'DISCOURSE_TEACH':'ADMIT_LANG_DEMO','DISCOURSE_QUERY':'RECORD_UTTERANCE',
              'DISCOURSE_RETRACT':'RETRACT_LESSON',
              'WEAK_DISCOURSE_TEACH':'ADMIT_LANG_DEMO',
              'WEAK_DISCOURSE_QUERY':'RECORD_UTTERANCE',
              'WEAK_DISCOURSE_RETRACT':'RETRACT_LESSON',
              'GROUNDING_SIM_RECEIPT':'RECORD_UTTERANCE',
              'GROUNDING_TEACH':'ADMIT_LANG_DEMO',
              'GROUNDING_QUERY':'RECORD_UTTERANCE',
              'GROUNDING_RETRACT':'RETRACT_LESSON',
              'EVENT_TRACE_SIM_RECEIPT':'RECORD_UTTERANCE',
              'EVENT_TRACE_TEACH':'ADMIT_LANG_DEMO',
              'EVENT_TRACE_QUERY':'RECORD_UTTERANCE',
              'EVENT_TRACE_RETRACT':'RETRACT_LESSON',
              'RELATIONAL_SIM_RECEIPT':'RECORD_UTTERANCE',
              'RELATIONAL_TEACH':'ADMIT_LANG_DEMO',
              'RELATIONAL_QUERY':'RECORD_UTTERANCE',
              'RELATIONAL_RETRACT':'RETRACT_LESSON',
              'TEMPORAL_SIM_RECEIPT':'RECORD_UTTERANCE',
              'TEMPORAL_TEACH':'ADMIT_LANG_DEMO',
              'TEMPORAL_QUERY':'RECORD_UTTERANCE',
              'TEMPORAL_RETRACT':'RETRACT_LESSON',
              'METRIC_SIM_RECEIPT':'RECORD_UTTERANCE',
              'METRIC_TEACH':'ADMIT_LANG_DEMO',
              'METRIC_QUERY':'RECORD_UTTERANCE',
              'METRIC_RETRACT':'RETRACT_LESSON',
              'JOINT_SIM_RECEIPT':'RECORD_UTTERANCE','JOINT_TEACH':'ADMIT_LANG_DEMO',
              'JOINT_QUERY':'RECORD_UTTERANCE','JOINT_RETRACT':'RETRACT_LESSON',
              'STORY_SIM_RECEIPT':'RECORD_UTTERANCE',
              'STORY_TEACH':'ADMIT_LANG_DEMO','STORY_QUERY':'RECORD_UTTERANCE',
              'STORY_INTERNAL_QUERY':'RECORD_UTTERANCE','STORY_RETRACT':'RETRACT_LESSON',
              'TEXT_STORY_TEACH':'ADMIT_LANG_DEMO','TEXT_STORY_QUERY':'RECORD_UTTERANCE',
              'TEXT_STORY_RETRACT':'RETRACT_LESSON',
              'MORPH_STORY_TEACH':'ADMIT_LANG_DEMO','MORPH_STORY_QUERY':'RECORD_UTTERANCE',
              'MORPH_STORY_RETRACT':'RETRACT_LESSON',
              'DIALOGUE_SENSOR':'ADMIT_OBSERVATION','DIALOGUE_GROUND':'ADMIT_OBSERVATION',
              'DIALOGUE_TURN':'RECORD_UTTERANCE','DIALOGUE_QUERY':'RECORD_UTTERANCE',
              'DIALOGUE_TEACH':'ADMIT_LANG_DEMO','DIALOGUE_RETRACT':'RETRACT_LESSON'}
    for r in recs:
        p = r['payload']
        k = r['kind']
        if k == 'COMMIT_DECISION':
            subj = p.get('subject')
            dd = p['decision']
            if subj in ('BELIEF_STATUS', 'LIBRARY_OPERATOR', 'WEIGHT_UPDATE'):
                ev_refs = p.get('evidence', [])
                bad = [e for e in ev_refs if e not in committed_obs]
                for ls in p.get('lessons', []):
                    les = lessons.get(ls)
                    if les is None or les['retracted_at'] is not None:
                        bad.append(ls)
                if subj == 'WEIGHT_UPDATE' and not any(by.get(x, {}).get('kind') == 'DECISION' and
                                                       by[x]['payload'].get('choice') == 'SLEEP' for x in r['refs']):
                    v['DRIVE'].append((r['seq'], 'weight update without a DRIVE sleep decision'))
                if bad:
                    v['EVIDENCE'].append((r['seq'], 'evidence not a committed verified observation', bad[:5]))
                if subj == 'BELIEF_STATUS' and p.get('status') == 'CERTIFIED' and not ev_refs:
                    v['EVIDENCE'].append((r['seq'], 'certified without evidence'))
                elif subj == 'BELIEF_STATUS' and p.get('status') == 'CERTIFIED':
                    # CL-R5 G0.1: a certificate cites the streak that earned it: >= N_CERT distinct admitted
                    # observations OF THE SAME WORLD, all earlier than the certificate
                    wit = set(ev_refs)
                    other_world = [e for e in wit if inbound(e) is not None and
                                   (inbound(e)['payload']['event'].get('content') or {}).get('world') != p.get('world')]
                    if len(wit) < N_CERT:
                        v['EVIDENCE'].append((r['seq'], f'certificate cites fewer than {N_CERT} witnesses', len(wit)))
                    if other_world or any(e >= r['seq'] for e in wit):
                        v['EVIDENCE'].append((r['seq'], 'certificate witness from another world or from the future'))
                if subj == 'LIBRARY_OPERATOR':
                    pr = by.get(p.get('proposal'))
                    if pr is None or pr['kind'] != 'PROPOSAL' or not any(by.get(x, {}).get('kind') == 'DECISION' for x in pr['refs']):
                        v['DRIVE'].append((r['seq'], 'library operator without a DRIVE-decided proposal'))
                    if len(set(tuple(u) for u in pr['payload'].get('from_certified_mechanisms', []))) < 2:
                        v['EVIDENCE'].append((r['seq'], 'library operator from fewer than two targets'))
                continue
            if subj in ('CODE_UPGRADE_BEGIN', 'CODE_UPGRADE'):
                exp = decide(operation='ADOPT_LIFE', channel_role='SELF', verified_by='MIGRATION', origin='').to_dict()
                if (exp['disposition'], exp.get('basis')) != (dd['disposition'], dd.get('basis')):
                    v['COMMIT_BASIS'].append((r['seq'], 'migration decision differs from SYSTEM_MIGRATION'))
                continue
            b = basis_of(r)
            ib = inbound(b) if b is not None else None
            if ib is None:
                v['COMMIT_BASIS'].append((r['seq'], 'decision without an INBOUND basis record'))
                continue
            ev = ib['payload']['event']
            op = op_map.get(ev['type'], 'UNKNOWN_' + ev['type'])
            if subj == 'ADMIT_LESSON' and ev['type'] == 'UTTERANCE':
                op = 'ADMIT_LESSON'
            same = False
            if op == 'RETRACT_LESSON':
                tgt = lesson_ref(ib)
                les = lessons.get(tgt) or frame_lessons.get(tgt) or discourse_lessons.get(tgt) or weak_lessons.get(tgt) or grounding_lessons.get(tgt) or event_trace_lessons.get(tgt) or relational_lessons.get(tgt) or temporal_lessons.get(tgt) or metric_lessons.get(tgt) or joint_lessons.get(tgt) or story_lessons.get(tgt) or text_story_lessons.get(tgt) or morph_story_lessons.get(tgt) or dialogue_lessons.get(tgt)
                same = bool(les) and les['channel'] == ev.get('channel') and les['retracted_at'] is None
            exp = decide(operation=op, channel_role=ev.get('role'), verified_by=ev.get('verified_by'),
                         origin=ev.get('origin', ''), same_source_as_retracted=same).to_dict()
            if ev['type'] == 'WORLD_INTRO':
                exp = decide(operation=op, channel_role='SENSOR', verified_by='SENSOR', origin='').to_dict()
            if (exp['disposition'], exp.get('basis')) != (dd['disposition'], dd.get('basis')):
                v['COMMIT_BASIS'].append((r['seq'], 'recomputed decision differs', exp['disposition'], dd['disposition']))
            if op == 'ADMIT_LESSON' and dd['disposition'] == 'COMMIT':
                if ev.get('role') != 'TEACHER':
                    v['COMMIT_BASIS'].append((r['seq'], 'lesson committed from a non-teacher channel'))
                lessons[ib['seq']] = {'channel': ev.get('channel'), 'retracted_at': None}
            if op == 'RETRACT_LESSON' and dd['disposition'] == 'COMMIT':
                tgt = lesson_ref(ib)
                if tgt in lessons:
                    lessons[tgt]['retracted_at'] = r['seq']
                if tgt in frame_lessons:
                    frame_lessons[tgt]['retracted_at']=r['seq']
                if tgt in discourse_lessons:
                    discourse_lessons[tgt]['retracted_at']=r['seq']
                if tgt in weak_lessons:
                    weak_lessons[tgt]['retracted_at']=r['seq']
                if tgt in grounding_lessons:
                    grounding_lessons[tgt]['retracted_at']=r['seq']
                if tgt in event_trace_lessons:
                    event_trace_lessons[tgt]['retracted_at']=r['seq']
                if tgt in relational_lessons:
                    relational_lessons[tgt]['retracted_at']=r['seq']
                if tgt in temporal_lessons:
                    temporal_lessons[tgt]['retracted_at']=r['seq']
                if tgt in metric_lessons:
                    metric_lessons[tgt]['retracted_at']=r['seq']
                if tgt in joint_lessons:
                    joint_lessons[tgt]['retracted_at']=r['seq']
                if tgt in story_lessons:
                    story_lessons[tgt]['retracted_at']=r['seq']
                if tgt in text_story_lessons:
                    text_story_lessons[tgt]['retracted_at']=r['seq']
                if tgt in morph_story_lessons:
                    morph_story_lessons[tgt]['retracted_at']=r['seq']
                if tgt in dialogue_lessons:
                    dialogue_lessons[tgt]['retracted_at']=r['seq']
            if op == 'ADMIT_PERMISSION' and dd['disposition'] == 'COMMIT':
                c = ev['content']
                for sw in c.get('switches', []):
                    if c.get('grant'):
                        permissions[(c['world'], sw)] = r['seq']
                    else:
                        permissions.pop((c['world'], sw), None)
        elif k == 'EVALUATION' and p.get('organ') == 'FRAME' and p.get('status')=='LEARNED_CONVENTION':
            teacher_inbound=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                             inbound(x)['payload']['event']['type']=='FRAME_TEACH'),None)
            if teacher_inbound is not None:
                te=teacher_inbound['payload']['event']
                frame_lessons[teacher_inbound['seq']]={'channel':te.get('channel'),'retracted_at':None}
        elif k == 'EVALUATION' and p.get('organ') == 'DISCOURSE' and p.get('status')=='LEARNED_DISCOURSE':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                      inbound(x)['payload']['event']['type']=='DISCOURSE_TEACH'),None)
            if src is not None:
                ev=src['payload']['event']
                discourse_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
            # A lesson MUST cite an admitted LANGUAGE_CONVENTION decision.
            if not any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                    by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION'
                    for x in r['refs']):
                v['EVIDENCE'].append((r['seq'],'discourse lesson without an admissible linguistic source'))
        elif k == 'EVALUATION' and p.get('organ') == 'WEAK_DISCOURSE' and p.get('status')=='LEARNED_WEAK_PAIR':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                      inbound(x)['payload']['event']['type']=='WEAK_DISCOURSE_TEACH'),None)
            if src is not None:
                ev=src['payload']['event']
                weak_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
            if not any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                       by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION'
                       for x in r['refs']):
                v['EVIDENCE'].append((r['seq'],'weak lesson without admissible linguistic source'))
        elif k == 'EVALUATION' and p.get('organ')=='GROUNDING' and p.get('status')=='ACQUIRED_DEMO':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None
                      and inbound(x)['payload']['event']['type']=='GROUNDING_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION'
                and by[x]['payload']['decision']['disposition']=='COMMIT'
                for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'unadmitted grounding demonstration'))
            else:
                ev=src['payload']['event']
                grounding_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                root=(ev.get('content') or {}).get('world_receipt_root')
                witnesses=grounding_index.get(root,r['seq']) < r['seq']
                if not witnesses:
                    v['EVIDENCE'].append((r['seq'],'grounded lesson without host-attested simulator receipt'))
        elif k == 'EVALUATION' and p.get('organ')=='EVENT_TRACE' and p.get('status')=='ACQUIRED_EVENT_EXAMPLE':
            from .event_semantics import content_root, measured_trace
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None
                      and inbound(x)['payload']['event']['type']=='EVENT_TRACE_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION'
                and by[x]['payload']['decision']['disposition']=='COMMIT'
                for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'event example without admitted teacher'))
            else:
                ev=src['payload']['event']
                event_trace_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                root=(ev.get('content') or {}).get('world_receipt_root')
                okay=event_trace_index.get(root,r['seq'])<r['seq']
                if not okay:
                    v['EVIDENCE'].append((r['seq'],'event example missing content-addressed simulated transcript'))
        elif k=='EVALUATION' and p.get('organ')=='RELATIONAL' and p.get('status')=='ACQUIRED_CONTRAST':
            from .relational_programs import witness_root, features
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                inbound(x)['payload']['event'].get('type')=='RELATIONAL_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION'
                and by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION'
                and by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'unadmitted relational lesson'))
            else:
                ev=src['payload']['event'];q=ev.get('content') or {}
                relational_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                for field in ('positive_root','contrast_root'):
                    root=q.get(field)
                    okay=verified_roots['RELATIONAL_SIM_RECEIPT'].get(root,r['seq'])<r['seq']
                    if not okay:v['EVIDENCE'].append((r['seq'],'missing independent content-addressed simulator contrast',field))
        elif k=='EVALUATION' and p.get('organ')=='TEMPORAL' and p.get('status')=='ACQUIRED_CONTRAST':
            from .temporal_patterns import trace_root,validate_trace
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                inbound(x)['payload']['event'].get('type')=='TEMPORAL_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'unadmitted temporal lesson'))
            else:
                ev=src['payload']['event'];q=ev.get('content') or {}
                temporal_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                for field in ('positive_root','contrast_root'):
                    root=q.get(field);okay=False
                    okay=verified_roots['TEMPORAL_SIM_RECEIPT'].get(root,r['seq'])<r['seq']
                    if not okay:v['EVIDENCE'].append((r['seq'],'missing host-attested temporal evidence',field))
        elif k=='EVALUATION' and p.get('organ')=='METRIC' and p.get('status')=='ACQUIRED_CONTRAST':
            from .metric_concepts import metric_root,measured
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                inbound(x)['payload']['event'].get('type')=='METRIC_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'unadmitted metric lesson'))
            else:
                ev=src['payload']['event'];q=ev.get('content') or {}
                metric_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                for field in ('positive_root','contrast_root'):
                    root=q.get(field);okay=False
                    okay=verified_roots['METRIC_SIM_RECEIPT'].get(root,r['seq'])<r['seq']
                    if not okay:v['EVIDENCE'].append((r['seq'],'missing host-attested metric evidence',field))
        elif k=='EVALUATION' and p.get('organ')=='JOINT' and p.get('status')=='ACQUIRED_JOINT_EXAMPLE':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                      inbound(x)['payload']['event'].get('type')=='JOINT_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'joint language from unadmitted teacher'))
            else:
                ev=src['payload']['event'];q=ev.get('content') or {}
                joint_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                root=q.get('root')
                if not (root in verified_roots['JOINT_SIM_RECEIPT'] and
                        verified_roots['JOINT_SIM_RECEIPT'][root]<src['seq']):
                    v['EVIDENCE'].append((r['seq'],'joint meaning not grounded in prior host scene+trace'))
        elif k=='EVALUATION' and p.get('organ')=='STORY' and p.get('status')=='ACQUIRED_STORY_QUESTION':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                      inbound(x)['payload']['event'].get('type')=='STORY_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:v['EVIDENCE'].append((r['seq'],'story lesson unadmitted'))
            else:
                ev=src['payload']['event'];q=ev.get('content') or {}
                story_lessons[src['seq']]={'channel':ev.get('channel'),'retracted_at':None}
                # A story must preexist the linguistic interpretation, from host-only receipts.
                found=any((inbound(t) and inbound(t)['payload']['event'].get('type')=='STORY_SIM_RECEIPT'
                  and inbound(t)['payload']['event'].get('content',{}).get('event',{}).get('story_id')==q.get('story_id'))
                  for t in verified_roots['STORY_SIM_RECEIPT'].values() if t<src['seq'])
                if not found:v['EVIDENCE'].append((r['seq'],'story language lesson without prior world receipt'))
        elif k=='EVALUATION' and p.get('organ')=='TEXT_STORY' and p.get('status')=='ACQUIRED_ATTESTED_TEXT_MEANING':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                inbound(x)['payload']['event'].get('type')=='TEXT_STORY_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'text story language not admitted by COMMIT'))
            else:
                text_story_lessons[src['seq']]={'channel':src['payload']['event'].get('channel'),'retracted_at':None}
                supports=p.get('supports') or []
                roots=verified_roots['STORY_SIM_RECEIPT']
                if not supports or any(root not in roots or roots[root]>=src['seq'] for root in supports):
                    v['EVIDENCE'].append((r['seq'],'text story taught without preceding verified simulator receipt'))
        elif k=='EVALUATION' and p.get('organ')=='MORPH_STORY' and p.get('status')=='ACQUIRED_ATTESTED_MORPH_MEANING':
            src=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                inbound(x)['payload']['event'].get('type')=='MORPH_STORY_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            if src is None or not approved:
                v['EVIDENCE'].append((r['seq'],'morph story not committed by lawful teacher'))
            else:
                morph_story_lessons[src['seq']]={'channel':src['payload']['event'].get('channel'),'retracted_at':None}
                supports=p.get('supports') or []
                roots=verified_roots['STORY_SIM_RECEIPT']
                if not supports or any(root not in roots or roots[root]>=src['seq'] for root in supports):
                    v['EVIDENCE'].append((r['seq'],'morph story missing earlier host receipt'))
        elif k=='EVALUATION' and p.get('organ')=='DIALOGUE' and p.get('status') in ('ACQUIRED_CONTEXTUAL_WORD_ROLE','ACQUIRED_CONTEXTUAL_REFERENCE'):
            teacher=next((inbound(x) for x in r['refs'] if inbound(x) is not None and
                         inbound(x)['payload']['event'].get('type')=='DIALOGUE_TEACH'),None)
            approved=any(by.get(x,{}).get('kind')=='COMMIT_DECISION' and
                         by[x]['payload']['decision'].get('basis')=='LANGUAGE_CONVENTION' and
                         by[x]['payload']['decision'].get('disposition')=='COMMIT' for x in r['refs'])
            root=p.get('grounding_root')
            ground=inbound(root) if isinstance(root,int) else None
            ground_ev=(ground['payload']['event'] if ground else {})
            matching=False
            if teacher and ground:
                tt=teacher['payload']['event'].get('content') or {}
                gc=ground_ev.get('content') or {}
                matching=(tt.get('session')==gc.get('session') and
                          tt.get('message_id')==gc.get('message_id') and
                          tt.get('turn_channel')==ground_ev.get('channel') and
                          tt.get('grounding_id')==gc.get('grounding_id'))
            if not teacher or not approved or ground is None or not matching or root>=teacher['seq'] or                     (ground_ev.get('role'),ground_ev.get('verified_by'))!=('SENSOR','SENSOR'):
                v['EVIDENCE'].append((r['seq'],'deictic lesson lacks earlier verified referent grounding'))
            else:
                if p.get('status')=='ACQUIRED_CONTEXTUAL_REFERENCE':
                    tt=teacher['payload']['event'].get('content') or {}
                    roots=p.get('context_roots') or []
                    valid_roots=bool(roots) and all(
                        isinstance(z,int) and z<teacher['seq'] and
                        inbound(z) is not None and
                        (inbound(z)['payload']['event'].get('role'),
                         inbound(z)['payload']['event'].get('verified_by'),
                         inbound(z)['payload']['event'].get('type'))==
                        ('SENSOR','SENSOR','DIALOGUE_GROUND') for z in roots)
                    if tt.get('lesson_type')!='CONTEXT_REFERENCE' or not gc.get('semantic_kind') or not valid_roots:
                        v['EVIDENCE'].append((r['seq'],'reference language requires earlier host-grounded antecedents'))
                dialogue_lessons[teacher['seq']]={'channel':teacher['payload']['event'].get('channel'),
                                                  'retracted_at':None}
        elif k == 'EVALUATION' and p.get('organ') == 'LANG':
            # CL-R5 G1: the language organ learns only from an admitted demonstration (world or teacher convention)
            ok = False
            for x in r['refs']:
                c = by.get(x)
                if c is not None and c['kind'] == 'COMMIT_DECISION' and c['payload']['decision']['disposition'] == 'COMMIT' \
                        and c['payload']['decision'].get('basis') in ('VERIFIED_OBSERVATION', 'VERIFIED_RECEIPT', 'LANGUAGE_CONVENTION'):
                    ok = True
            if not ok:
                v['EVIDENCE'].append((r['seq'], 'language learned from a demonstration that was not admitted'))
        elif k == 'EVALUATION' and 'updates' in p:
            # a credit update: rooted in exactly one committed verified observation (+ receipts if interventional)
            srcs = [x for x in r['refs'] if inbound(x) is not None and inbound(x)['payload']['event']['type'] in ('PERCEPT', 'ENTITY_OBS')]
            cur = [x for x in srcs if by[x]['world_t'] == r['world_t']]
            if not cur or any(x not in committed_obs for x in cur):
                v['EVIDENCE'].append((r['seq'], 'credit update not rooted in a committed verified observation'))
            for x in r['refs']:
                if by.get(x, {}).get('kind') in NEVER_EVIDENCE:
                    v['EVIDENCE'].append((r['seq'], 'credit update references non-evidence', x))
                ibx = inbound(x)
                if ibx is not None and ibx['payload']['event'].get('role') == 'SIM_FEED':
                    v['EVIDENCE'].append((r['seq'], 'credit update references a SIM feed', x))
                if ibx is not None and ibx['payload']['event']['type'] == 'RECEIPT' and x not in committed_receipts:
                    v['EVIDENCE'].append((r['seq'], 'interventional credit from an uncommitted receipt', x))
            if p.get('interventional') and not any(inbound(x) is not None and inbound(x)['payload']['event']['type'] == 'RECEIPT'
                                                   for x in r['refs']):
                v['EVIDENCE'].append((r['seq'], 'interventional credit without a receipt'))
        elif k in QUANTUM_PRODUCTS:
            if not any(by.get(x, {}).get('kind') == 'DECISION' for x in r['refs']):
                v['DRIVE'].append((r['seq'], f'{k} without a DRIVE decision'))
        elif k == 'OUTBOUND':
            dseq = p.get('decision')
            d = by.get(dseq)
            if d is None or d['kind'] != 'DECISION' or dseq not in r['refs']:
                v['DRIVE'].append((r['seq'], 'outbound without a DRIVE decision'))
            if p['kind'] == 'ACTION':
                c = p['content']
                for sw in c.get('action', {}):
                    ps = permissions.get((c['world'], sw))
                    if ps is None or ps not in r['refs']:
                        v['MEDIATE'].append((r['seq'], 'action without a committed permission', c['world'], sw))
        # retracted lessons are never used again
        if lessons or frame_lessons:
            for x in r['refs']:
                les = lessons.get(x) or frame_lessons.get(x)
                if les and les['retracted_at'] is not None and r['seq'] > les['retracted_at']:
                    v['RETRACTION'].append((r['seq'], 'uses retracted lesson', x))
    # --- CL-R5 G0.4: the CODE_UPGRADE boundary
    subj_of = lambda r: r['payload'].get('subject') if r['kind'] == 'COMMIT_DECISION' else None
    begins = [r for r in recs if subj_of(r) == 'CODE_UPGRADE_BEGIN']
    closes = [r for r in recs if subj_of(r) == 'CODE_UPGRADE']
    if begins and (begins[0]['seq'] != 0 or len(begins) > 1):
        v['MIGRATION'].append((begins[-1]['seq'], 'CODE_UPGRADE_BEGIN that is not the genesis, or repeated'))
    if not begins or begins[0]['seq'] != 0:
        for r in recs:
            if 'adopted_from' in r['payload'] or subj_of(r) == 'CODE_UPGRADE':
                v['MIGRATION'].append((r['seq'], 'adopted record or CODE_UPGRADE without a CODE_UPGRADE_BEGIN genesis'))
                break
    else:
        if len(closes) != 1:
            v['MIGRATION'].append((0, f'{len(closes)} closing CODE_UPGRADE records (exactly one is required)'))
        end = closes[0]['seq'] if closes else len(recs)
        if closes and 0 not in closes[0]['refs']:
            v['MIGRATION'].append((end, 'closing CODE_UPGRADE does not cite the genesis'))
        for r in recs[1:end]:
            if r['kind'] == 'OUTBOUND':
                v['MIGRATION'].append((r['seq'], 'outbound act during an adoption'))
            elif r['kind'] == 'INBOUND' and 'adopted_from' not in r['payload']:
                v['MIGRATION'].append((r['seq'], 'new (not adopted) inbound during an adoption'))
            elif r['kind'] == 'DECISION' and r['payload'].get('choice') not in ('EXTEND', 'ABSTRACT', 'SLEEP'):
                v['MIGRATION'].append((r['seq'], 'non-structural DRIVE quantum during an adoption'))
        for r in recs[end + 1:]:
            if 'adopted_from' in r['payload']:
                v['MIGRATION'].append((r['seq'], 'adopted record after the closing CODE_UPGRADE'))
    total = sum(len(x) for x in v.values())
    return {'records': len(recs), 'violations': {k: len(x) for k, x in v.items()}, 'total_violations': total,
            'examples': {k: x[:5] for k, x in v.items() if x}, 'counts_by_owner_kind': counts,
            'committed_observations': len(committed_obs), 'committed_receipts': len(committed_receipts),
            'lessons': {str(k): v_ for k, v_ in lessons.items()}}


def audit_state(state: dict) -> dict:
    """State-level check: no family derived from a retracted lesson survives."""
    bad = []
    retracted = {int(k) for k, les in state.get('lessons', {}).items() if les.get('status') == 'RETRACTED'}
    for w, wd in state.get('worlds', {}).items():
        for n, td in wd.get('targets', {}).items():
            for f in td.get('families', []):
                o = str(f.get('origin', ''))
                if o.startswith('lesson@') and int(o.split('@')[1]) in retracted:
                    bad.append((w, n, o))
    return {'resurrected_lesson_families': bad}


def audit_adoption(new_path: str, parent_path: str) -> dict:
    """CL-R5 G0.4: is the journal at `new_path` a FAITHFUL adoption of the journal file at `parent_path`?
      - the genesis names the parent file (sha256 of its bytes), its head and length;
      - every parent INBOUND is adopted exactly once, in the same order, at the same tick, with the same event;
        the parent's resolution of a journal reference inside an event is carried unchanged;
      - every parent act (OUTBOUND, or a historical act it had itself adopted) is carried exactly once as a
        BOUNDARY_NOTE at the same tick with the same content; none is re-sent;
      - every parent task decision is copied, except decisions about tasks the parent opened without an inbound
        event (corrections found by its own review: they are re-derived by the new code, reported as unmapped);
      - the closing record cites the genesis and the sha256 of adoption_report.json next to the new journal."""
    import hashlib
    import os
    with open(parent_path, 'rb') as f:
        raw = f.read()
    par = [json.loads(l) for l in raw.decode('utf8').splitlines() if l.strip()]
    new = load(new_path)
    probs: List[str] = []
    canon = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    g = new[0] if new else {}
    gp = g.get('payload') or {}
    if g.get('kind') != 'COMMIT_DECISION' or gp.get('subject') != 'CODE_UPGRADE_BEGIN':
        return {'ok': False, 'problems': ['the genesis is not CODE_UPGRADE_BEGIN']}
    pa = gp.get('parent') or {}
    if pa.get('journal_sha256') != hashlib.sha256(raw).hexdigest():
        probs.append('the parent file sha256 differs from the one named in the genesis')
    if pa.get('head') != (par[-1]['hash'] if par else None) or pa.get('records') != len(par):
        probs.append('the parent head or length differs from the genesis')
    closes = [r for r in new if r['kind'] == 'COMMIT_DECISION' and r['payload'].get('subject') == 'CODE_UPGRADE']
    if len(closes) != 1:
        probs.append(f'{len(closes)} closing CODE_UPGRADE records')
    end = closes[0]['seq'] if closes else len(new)
    # inbound
    pin = [r for r in par if r['kind'] == 'INBOUND']
    nin = [r for r in new[:end] if r['kind'] == 'INBOUND']
    if [r['payload'].get('adopted_from') for r in nin] != [r['seq'] for r in pin]:
        probs.append('the adopted inbound sequence differs from the parent inbound sequence (missing, repeated or '
                     'reordered events)')
    retract_res = {r['payload'].get('basis_seq'): r['payload'].get('lesson_seq') for r in par
                   if r['kind'] == 'COMMIT_DECISION' and r['payload'].get('subject') == 'RETRACT_LESSON'}
    bad_in = 0
    for a, b in zip(pin, nin):
        same = (canon(a['payload']['event']) == canon(b['payload']['event']) and a['world_t'] == b['world_t']
                and a.get('narrated_t') == b.get('narrated_t'))
        if a['payload']['event'].get('type') == 'RETRACT':
            same = same and (b['payload'].get('parent_refs') or {}).get('lesson_seq') == retract_res.get(a['seq'])
        bad_in += not same
    if bad_in:
        probs.append(f'{bad_in} adopted inbound events differ from the parent events')
    # acts
    pout = []
    for r in par:
        if r['kind'] == 'OUTBOUND':
            pout.append((r['seq'], r['world_t'], {k: r['payload'][k] for k in ('channel', 'kind', 'content')}))
        elif r['kind'] == 'BOUNDARY_NOTE' and 'historical_outbound' in r['payload']:
            pout.append((r['seq'], r['world_t'], r['payload']['historical_outbound']))
    nout = [r for r in new[:end] if r['kind'] == 'BOUNDARY_NOTE' and 'historical_outbound' in r['payload']]
    if [r['payload'].get('adopted_from') for r in nout] != [x[0] for x in pout]:
        probs.append('the historical acts differ from the parent acts (missing, repeated or reordered)')
    bad_out = sum(1 for x, r in zip(pout, nout) if canon(x[2]) != canon(r['payload']['historical_outbound'])
                  or x[1] != r['world_t'])
    if bad_out:
        probs.append(f'{bad_out} historical acts differ in content or tick')
    if any(r['kind'] == 'OUTBOUND' for r in new[:end]):
        probs.append('an act was sent during the adoption')
    # task decisions
    opened_by_inbound = {}
    for r in par:
        if r['kind'] == 'TASK' and r['payload'].get('op') == 'OPEN':
            opened_by_inbound[r['payload']['task']] = any(par[x]['kind'] == 'INBOUND' for x in r['refs'])
    ptask = [r for r in par if r['kind'] == 'TASK' and r['payload'].get('op') != 'OPEN']
    copied = [(r['payload'].get('note') or {}).get('historical_from_parent_seq') for r in new[:end]
              if r['kind'] == 'TASK' and isinstance(r['payload'].get('note'), dict)]
    if len(copied) != len(set(copied)):
        probs.append('a parent task decision was copied more than once')
    cs = set(copied)
    unmapped = [r for r in ptask if r['seq'] not in cs]
    wrongly_unmapped = [r['seq'] for r in unmapped if opened_by_inbound.get(r['payload']['task'], False)]
    if wrongly_unmapped:
        probs.append(f'{len(wrongly_unmapped)} decisions about tasks opened by inbound events were not carried over')
    # closing record and report
    rep = os.path.join(os.path.dirname(os.path.abspath(new_path)), 'adoption_report.json')
    if closes:
        cp = closes[0]['payload']
        if 0 not in closes[0]['refs']:
            probs.append('the closing record does not cite the genesis')
        if os.path.exists(rep):
            with open(rep, 'rb') as f:
                if hashlib.sha256(f.read()).hexdigest() != cp.get('adoption_report_sha256'):
                    probs.append('adoption_report.json differs from the sha256 in the closing record')
        else:
            probs.append('adoption_report.json is missing next to the journal')
    return {'ok': not probs, 'problems': probs, 'parent_records': len(par), 'parent_inbound': len(pin),
            'adopted_inbound': len(nin), 'parent_acts': len(pout), 'historical_acts': len(nout),
            'parent_task_decisions': len(ptask), 'copied_task_decisions': len(ptask) - len(unmapped),
            'unmapped_task_decisions_tasks_without_inbound': len(unmapped) - len(wrongly_unmapped),
            'close_seq': end if closes else None}
