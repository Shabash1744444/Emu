"""The life kernel: a continuously existing, owner-separated cognitive process (CL-R4).

One call `tick(t, events)` = one tick of the world clock:
  1. MEDIATE records every inbound event exactly as delivered by the host (channel identity and boundary
     verification are set by the host adapter, never by content);
  2. COMMIT decides each one (COMMIT | CLAIM_ONLY | REJECT) on a lawful basis;
  3. only committed material changes admitted state (observations -> learner credit; lessons -> proposals;
     permissions -> what DRIVE may do; retractions -> exact rebuild without the lesson);
  4. DRIVE spends up to `budget` quanta on the most valuable process (answer, experiment, extension, abstraction,
     review, resolve, plan, ask) or RESTs until a wake condition; every executed quantum and every outbound act
     references its DRIVE decision; outbound acts leave only through MEDIATE (actions only with permission).
The journal is the history; everything else is derived and snapshotted for speed.  A resumed kernel re-executes the
tail of the journal in verify mode: identical records are accepted (nothing is re-sent), any divergence is an error.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import SCHEMA
from .constitution import decide
from .journal import Journal
from .operators import OperatorSpace, prog_str, strides
from .perspective import SELF, Perspective, SourceReliability, effective, prop_key
from .slearner import WorldModelS
from . import wlearner as WL
from . import lang as LANG
from .temporal import ClockMap, ClockAnchor
from .frame_induction import GroundedFrameInducer
from .discourse_induction import DiscourseInducer
from .weak_discourse import WeakBoundaryInducer
from .grounded_language import SituatedLexicon
from .event_semantics import EventMeaningInducer, measured_trace, content_root
from .relational_programs import RelationalInducer, witness_root, features
from .temporal_patterns import TemporalInducer, trace_root, validate_trace
from .metric_concepts import MetricInducer, metric_root, measured
from .joint_language import JointUtteranceInducer, joint_root
from .story_meanings import StoryMind, MeaningQuestionLearner, event_root, canon
from .text_story_induction import PatternInducer, NarrativeMind, attested_atomic_story
from .morph_story import MorphStory
from .interaction_identity import InteractionIdentity, canonical as dialogue_canonical
from dataclasses import asdict

THETA_REST = 0.05          # bits per quantum below which nothing is worth doing
QUIET_REPORT_LIMIT = 1     # unsolicited reports per quiet period (no pestering)
WAKE_TIMER = 50            # a resting DRIVE re-evaluates at least this often (ticks)
LESSON_BONUS = 3.0         # nats added to the prior of a lesson's hypothesis (a proposal, never a certificate)


def _sjson(x) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))


def compile_program(prog, input_names: List[str], domains: Dict[str, int], out_domain: int) -> np.ndarray:
    """A teacher's formal statement (base DSL over variable names) -> table over the inputs (MEDIATE codec)."""
    from .world import ev
    import itertools
    rows = []
    for combo in itertools.product(*[range(domains[n]) for n in input_names]):
        st = dict(zip(input_names, combo))
        rows.append(ev(prog, st, st.get('__SELF__')))
    return np.array(rows, dtype=np.int8)


class Life:
    def __init__(self, home: str, *, learner: str = 'S', budget: int = 3, reactive: bool = False,
                 always_busy: bool = False, snapshot_every: int = 100, quiet_report_limit: int = QUIET_REPORT_LIMIT,
                 no_library: bool = False, w_seed: int = 0):
        os.makedirs(home, exist_ok=True)
        self.home = home
        self.cfg = {'learner': learner, 'budget': budget, 'reactive': reactive, 'always_busy': always_busy,
                    'snapshot_every': snapshot_every, 'quiet_report_limit': quiet_report_limit,
                    'no_library': no_library, 'w_seed': w_seed}
        self.j = Journal(os.path.join(home, 'journal.jsonl'))
        self.MED, self.EVA, self.COM, self.DRV = (self.j.cap(o) for o in ('MEDIATE', 'EVAL', 'COMMIT', 'DRIVE'))
        self.outbox: List[dict] = []            # delivered to the host only for NEWLY written OUTBOUND records
        self._reset_state()
        if len(self.j):
            # a journal without a snapshot: the process restarts from genesis and must reproduce it exactly
            self.j.resume_at(0)

    # ================================================================== state
    def _reset_state(self):
        self.step = 0
        self.world_t = -1
        self.space = OperatorSpace()
        self.worlds: Dict[str, Any] = {}
        self.world_meta: Dict[str, dict] = {}
        self.persp = Perspective()
        self.rel = SourceReliability()
        self.tasks: Dict[str, dict] = {}
        self.permissions: Dict[str, Dict[str, int]] = {}     # world -> switch -> COMMIT seq of the grant
        self.lessons: Dict[int, dict] = {}                   # INBOUND seq -> lesson record (status ADMITTED/RETRACTED)
        self.interv: Dict[str, Dict[int, int]] = {}          # world -> tick at which a switch value was set by us -> receipt seq
        self.last_percept: Dict[str, dict] = {}              # world -> {'t', 'seq', 'percept'}
        self.percept_log: Dict[str, Dict[int, int]] = {}     # world -> t -> percept INBOUND seq (verified)
        # CL-R5 G0.1: the kernel keeps no witness list of its own; the learner's streak owns its evidence (_witness)
        self.cert_state: Dict[Tuple[str, str], bool] = {}
        self.cert_mech: Dict[Tuple[str, str], str] = {}      # CL-R5 G0.1: the mechanism of the admitted certificate
        self.drive = {'resting': False, 'rest_since': None, 'mult': {}, 'quiet_reports': 0, 'last_user_t': -1,
                      'pending_surprise': False, 'last_review_t': -1, 'changes_since_review': 0}
        self.cost = {'quanta': 0, 'quanta_by_kind': {}, 'inbound': 0, 'outbound': 0, 'eval_seconds': 0.0,
                     'learner_updates': 0, 'rest_ticks': 0, 'wakes': 0, 'initiative_msgs': 0,
                     'ops_enumerated': 0, 'rebuilds': 0}
        self.counters = {'task': 0}
        self.slow = WL.SlowModules(self.cfg.get('w_seed', 0)) if self.cfg.get('learner') == 'W' else None
        self.channels: Dict[str, str] = {}                   # role -> channel seen (host-verified transport)
        self.mech_claims: List[dict] = []                    # mechanism claims of sources, scored when decidable
        self.regime_events: List[list] = []                  # [world, target, t]: memory contradicted / certificate failed
        self.ask_stats: Dict[str, List[int]] = {}            # channel -> [asks, inbound messages after an ask]
        self.lang = None                                     # CL-R5 G1: the language organ (created by experience)
        self.external_clock = None                            # G1.1: exists only after admitted clock observation
        self.frame_organ = None                               # G1.2: opt-in language convention learner
        self.frame_sim_receipts = {}                          # sandbox records, NEVER real-world observation
        self.frame_teacher_lessons = {}                       # independent language claims and withdrawals
        self.discourse_organ = None                            # G1.3: two-event discourse learner
        self.discourse_teacher_lessons = {}                   # G1.3: separately retractable language lessons
        self.weak_discourse_organ = None                       # G1.4: unaligned weak boundary learner
        self.weak_discourse_lessons = {}                      # G1.4: same-source retraction
        self.grounding_organ = None                            # G1.5: text-grounded apprenticeship
        self.grounding_sim_receipts = {}                      # sandbox witness, NEVER real-world truth
        self.grounding_teacher_lessons = {}                   # source-specific admissible demos
        # G1.8 event learning: separate simulations, linguistic claims and predictions.
        self.event_trace_sim_receipts = {}
        self.event_trace_teacher_lessons = {}
        self.event_trace_surface_vocab = []
        self.event_trace_organ = None
        # G2.1: new, generic learned relational programs; sandbox claims only.
        self.relational_organ = None
        self.relational_sim_receipts = {}
        self.relational_teacher_lessons = {}
        # G2.2: new sensor-agnostic temporal structure induction (sandbox only).
        self.temporal_organ = None
        self.temporal_sim_receipts = {}
        self.temporal_teacher_lessons = {}
        # G2.3: learned measurements from external timestamps; NOT tick counts.
        self.metric_organ = None
        self.metric_sim_receipts = {}
        self.metric_teacher_lessons = {}
        # G2.4: joined event utterance, with separately witnessed scene/trace.
        self.joint_organ = None
        self.joint_sim_receipts = {}
        self.joint_teacher_lessons = {}
        # G2.5 meaning-before-language: simulated events, nested claims, learned query wording.
        self.story_mind = None
        self.story_questions = None
        self.story_sim_receipts = {}
        self.story_teacher_lessons = {}
        self.text_story_learner = None
        self.text_story_teacher_lessons = {}
        self.text_story_narratives = {}
        self.morph_story_learner = None
        self.morph_story_teacher_lessons = {}
        self.morph_story_narratives = {}
        self.interaction_identity = None  # G2.8 speaker/channel/voice and deictic learning
        self.dialogue_teacher_lessons = {}
        self.lineage: Optional[dict] = None                  # CL-R5 G0.4: the parent life adopted at a CODE_UPGRADE
        self.adopting = False                                # transient: replaying a parent journal (no outbound)
        self._adopt_inbound: Dict[int, int] = {}             # transient: parent inbound seq -> adopted inbound seq
        self._adopt_task: Dict[int, str] = {}                # transient: adopted inbound seq -> task id
        self._adopt_refs: Dict[int, dict] = {}               # transient: parent inbound seq -> the parent's own
        #                                                      resolution of a journal reference inside that event

    # ================================================================== the tick
    _ORDER = {'WORLD_INTRO': 0, 'RECEIPT': 1, 'PERCEPT': 2, 'ENTITY_OBS': 2, 'FRAME_SIM_RECEIPT': 2, 'FRAME_TEACH': 3, 'DISCOURSE_TEACH': 3, 'WEAK_DISCOURSE_TEACH': 3, 'GROUNDING_SIM_RECEIPT': 2, 'GROUNDING_TEACH': 3, 'EVENT_TRACE_SIM_RECEIPT': 2, 'EVENT_TRACE_TEACH': 3, 'RELATIONAL_SIM_RECEIPT':2, 'RELATIONAL_TEACH':3, 'TEMPORAL_SIM_RECEIPT':2, 'TEMPORAL_TEACH':3, 'METRIC_SIM_RECEIPT':2, 'METRIC_TEACH':3, 'JOINT_SIM_RECEIPT':2, 'JOINT_TEACH':3, 'STORY_SIM_RECEIPT':2, 'STORY_TEACH':3, 'TEXT_STORY_TEACH':3,'MORPH_STORY_TEACH':3,'DIALOGUE_SENSOR':2,'DIALOGUE_TURN':3,'DIALOGUE_GROUND':3,'DIALOGUE_TEACH':4}

    def _inbound_tick(self, t, events, origins=None) -> bool:
        self.world_t = t
        self.outbox = []
        had_user = False
        pairs = list(zip(events, origins if origins is not None else [None] * len(events)))
        for ev, o in sorted(pairs, key=lambda eo: (self._ORDER.get(eo[0]['type'], 3), eo[0].get('channel', ''), _sjson(eo[0]))):
            self._inbound(ev, adopted_from=o)
            if ev.get('role') in ('USER', 'TEACHER') and ev['type'] in ('QUESTION', 'GOAL', 'LESSON', 'PERMISSION', 'RETRACT', 'UTTERANCE', 'DIALOGUE_TURN', 'DIALOGUE_QUERY'):
                had_user = True
        if had_user:
            self.drive['quiet_reports'] = 0
            self.drive['last_user_t'] = t
        return had_user

    def tick(self, t: int, events: List[dict]) -> List[dict]:
        had_user = self._inbound_tick(t, events)
        self._drive_loop(t, woken=had_user)
        return list(self.outbox)

    # ================================================================== CL-R5 G0.4: adoption of a parent journal
    def tick_adopt(self, t: int, events: List[dict], origins: List[int], history: List[dict], parent_task_inbound: Dict[str, int]):
        """One tick of the parent life replayed under THIS code: its inbound events are admitted again by this
        constitution and learned again by these learners; its own acts (outbound) and task decisions are carried
        over as history (never re-sent); DRIVE runs only internal structural quanta (no outbound is possible)."""
        had_user = self._inbound_tick(t, events, origins)
        for r in sorted(history, key=lambda r: r['seq']):
            if r['kind'] == 'OUTBOUND':
                self._historical_outbound(r)
            else:
                self._historical_task(r, parent_task_inbound)
        self._drive_loop(t, woken=had_user)
        if self.outbox:
            raise RuntimeError('adoption produced outbound acts')

    def _historical_outbound(self, pr):
        p = pr['payload']
        note = self.j.append(self.MED, 'BOUNDARY_NOTE', {'historical_outbound': {'channel': p['channel'], 'kind': p['kind'],
                                                                                 'content': p['content']},
                                                         'adopted_from': pr['seq'],
                                                         'note': 'an act of this life under its previous code version; not re-sent'},
                             step=self._s(), world_t=self.world_t)
        kind, content = p['kind'], p['content']
        if kind in ('ANSWER', 'REPORT', 'CORRECTION'):
            claim = {'op': 'ANSWER', 'content': content}
            r = self.persp.add(speaker=SELF, content=claim, t_said=self.world_t, narrated=None, seq=note['seq'],
                               channel_role='SELF', own=True)
            r['answer'] = dict(content, channel=p['channel'])
        if kind == 'ASK':
            self.ask_stats.setdefault(p['channel'], [0, 0])[0] += 1
        if content.get('unsolicited') if isinstance(content, dict) else False:
            self.drive['quiet_reports'] += 1
        return note

    def _historical_task(self, pr, parent_task_inbound):
        p = pr['payload']
        pin = parent_task_inbound.get(p['task'])
        tid = self._adopt_task.get(self._adopt_inbound.get(pin, -1)) if pin is not None else None
        if tid is None or tid not in self.tasks:
            self.cost['adoption_unmapped_task_ops'] = self.cost.get('adoption_unmapped_task_ops', 0) + 1
            return
        note = p.get('note')
        if isinstance(note, str) and note.startswith('asked'):
            self.tasks[tid]['asked'] = True
        self._task_status(tid, p['op'], note={'historical_from_parent_seq': pr['seq'], 'parent_note': note})

    # ================================================================== MEDIATE: inbound
    def _inbound(self, ev: dict, adopted_from: Optional[int] = None):
        self.cost['inbound'] += 1
        role, ch = ev.get('role'), ev.get('channel')
        if role in ('USER', 'TEACHER') and ch and ev.get('verified_by') == 'TRANSPORT':
            self.channels.setdefault(role, ch)
            st = self.ask_stats.get(ch)
            if st is not None and st[0] > st[1]:
                st[1] += 1                                   # somebody answered on a channel we had asked
        payload = {'event': ev}
        if adopted_from is not None:
            payload['adopted_from'] = int(adopted_from)
            if int(adopted_from) in self._adopt_refs:
                payload['parent_refs'] = self._adopt_refs[int(adopted_from)]
        rec = self.j.append(self.MED, 'INBOUND', payload, step=self._s(), world_t=self.world_t,
                            narrated_t=ev.get('narrated'))
        if adopted_from is not None:
            self._adopt_inbound[int(adopted_from)] = rec['seq']
        typ = ev['type']
        handler = getattr(self, '_in_' + typ.lower(), None)
        if handler is None:
            self.j.append(self.COM, 'COMMIT_DECISION', {'decision': decide(operation='UNKNOWN_' + typ, channel_role=ev.get('role'),
                                                                         verified_by=ev.get('verified_by'), origin=ev.get('origin', '')).to_dict(),
                                                        'subject': typ, 'basis_seq': rec['seq']}, refs=[rec['seq']],
                          step=self._s(), world_t=self.world_t)
            return
        handler(rec, ev)

    def _s(self) -> int:
        self.step += 1
        return self.step

    def _commit(self, operation, ev, rec, extra=None, refs=(), **kw):
        d = decide(operation=operation, channel_role=ev.get('role'), verified_by=ev.get('verified_by'),
                   origin=ev.get('origin', ''), **kw)
        payload = {'decision': d.to_dict(), 'subject': operation, 'basis_seq': rec['seq']}
        if extra:
            payload.update(extra)
        c = self.j.append(self.COM, 'COMMIT_DECISION', payload, refs=[rec['seq']] + list(refs), step=self._s(),
                          world_t=self.world_t)
        return d, c

    # ---------------------------------------------------------------- world boundary
    def _in_world_intro(self, rec, ev):
        c = ev['content']
        w = c['world']
        d, crec = self._commit('ADMIT_OBSERVATION', dict(ev, role='SENSOR', verified_by='SENSOR'), rec,
                               {'world': w, 'body_schema': True})
        if w in self.worlds:
            return
        self.world_meta[w] = {'names': c['names'], 'domains': c['domains'], 'switches': c['switches'],
                              'static': bool(c.get('static')), 'targets': c.get('targets'),
                              'lib_version': self.space.version, 'intro_seq': rec['seq'], 'intro_t': self.world_t}
        self.worlds[w] = self._new_world_model(w)
        self.interv[w], self.percept_log[w] = {}, {}

    def _new_world_model(self, w):
        m = self.world_meta[w]
        if self.cfg['learner'] == 'S':
            return WorldModelS(w, m['names'], m['domains'], m['switches'], self.space, m['lib_version'], m['static'],
                               m.get('targets'))
        return WL.WorldModelW(w, m['names'], m['domains'], m['switches'], slow=self.slow,
                              seed=int(hashlib.sha256(w.encode()).hexdigest()[:8], 16) + self.cfg.get('w_seed', 0),
                              static=m['static'], targets=m.get('targets'))

    def _in_receipt(self, rec, ev):
        c = ev['content']
        d, crec = self._commit('ADMIT_RECEIPT', ev, rec, {'world': c['world'], 'action': c['action'], 'status': c['status']})
        if d.disposition == 'COMMIT' and c['status'] == 'EXECUTED':
            slot = self.interv.setdefault(c['world'], {}).setdefault(int(c['effective_t']), {'seqs': [], 'vars': []})
            slot['seqs'].append(rec['seq'])
            slot['vars'] = sorted(set(slot['vars']) | set(c['action'].keys()))

    def _in_percept(self, rec, ev):
        c = ev['content']
        w = c['world']
        d, crec = self._commit('ADMIT_OBSERVATION', ev, rec, {'world': w})
        if d.disposition != 'COMMIT' or w not in self.worlds:
            return
        self.percept_log[w][self.world_t] = rec['seq']
        prev = self.last_percept.get(w)
        t0 = time.process_time()
        slot = self.interv.get(w, {}).get(self.world_t - 1)
        intervened_prev = slot is not None
        res = self.worlds[w].observe(self.world_t, c['percept'], intervened_prev, int_vars=(slot or {}).get('vars', []),
                                     seq=rec['seq'])
        self.cost['eval_seconds'] += time.process_time() - t0
        self.cost['learner_updates'] += len(res)
        self.last_percept[w] = {'t': self.world_t, 'seq': rec['seq'], 'percept': dict(c['percept'])}
        if not res:
            return
        refs = [crec['seq'], rec['seq']] + ([prev['seq']] if prev else []) + list((slot or {}).get('seqs', []))
        summary = {n: {k: r[k] for k in ('p_true', 'confident', 'correct', 'fresh', 'map_changed', 'certified')
                       if k in r} for n, r in sorted(res.items())}
        for n, r in res.items():
            if 'change_point' in r:
                summary[n]['change_point'] = r['change_point']
            if r.get('certificate_failed'):
                summary[n]['certificate_failed'] = True
        erec = self.j.append(self.EVA, 'EVALUATION', {'world': w, 'transition_to_t': self.world_t,
                                                     'interventional': intervened_prev,
                                                     'set_by_us': (slot or {}).get('vars', []), 'updates': summary},
                             refs=refs, step=self._s(), world_t=self.world_t)
        for n, r in sorted(res.items()):
            key = (w, n)
            if r.get('confident') and not r.get('correct'):
                self.drive['pending_surprise'] = True
            if 'change_point' in r or r.get('map_changed') or r.get('certificate_failed'):
                self.drive['changes_since_review'] += 1
            if 'change_point' in r or r.get('certificate_failed'):
                self.regime_events.append([w, n, self.world_t])
            was = self.cert_state.get(key, False)
            now = bool(r.get('certified'))
            if now != was:
                self.cert_state[key] = now
                self._renew_resolution(w)
                desc = self.worlds[w].targets[n].map_description(self.worlds[w].names)
                status = 'CERTIFIED' if now else 'REFUTED'
                self._admit_mech(key, now, desc)
                ev_refs = self._witness(w, n)[-12:] if now else [rec['seq']]
                self.j.append(self.COM, 'COMMIT_DECISION',
                              {'decision': decide(operation='ADMIT_BELIEF_STATUS', channel_role='SELF', verified_by=None,
                                                  origin='').to_dict(),
                               'subject': 'BELIEF_STATUS', 'world': w, 'target': n, 'status': status,
                               'mechanism': desc.get('map'), 'family_origin': desc.get('family_origin'),
                               'evidence': ev_refs},
                              refs=[erec['seq']] + ev_refs, step=self._s(), world_t=self.world_t)
                self.drive['pending_surprise'] = True
                if now:
                    self._check_mech_claims(w, n)
        # sources: claims about this tick's states can now be checked against our own verified observation
        self._check_claims_against(w, self.world_t, c['percept'], rec['seq'])

    def _check_mech_claims(self, w, n):
        """A source's claim about a mechanism is scored once our own CERTIFIED mechanism decides it: a conflict on
        an asserted entry = disagreement; a complete certified table without conflict = agreement."""
        wm = self.worlds.get(w)
        if wm is None or n not in wm.targets:
            return
        tm = wm.targets[n]
        names = wm.names if not wm.static else [m for m in wm.names if m != n]
        ours = None
        for cl in self.mech_claims:
            c = cl['claim']
            if cl['checked'] or c.get('world') != w or c.get('var') != n:
                continue
            if ours is None:
                mech = tm.mechanism(names)
                ours = {'inputs': mech['inputs'], 'domains': mech['domains'], 'table': mech['table']}
                complete = mech['complete']
            try:
                ins = list(c['inputs'])
                doms = {m: wm.domains[wm.idx[m]] for m in ins}
                prog = _rename_self(c['program'], n)
                if tm.self_idx is not None:
                    ins = ins + ['__SELF__']
                    doms['__SELF__'] = tm.out_domain
                tab = compile_program(prog, ins, doms, tm.out_domain)
            except Exception:
                continue
            theirs = {'inputs': ins, 'domains': [doms[m] for m in ins], 'table': [int(v) for v in tab]}
            conflict = _conflict({'q': 'MECHANISM'}, {'mechanism': theirs}, {'mechanism': ours})
            if not conflict and not complete:
                continue                                        # not decidable yet
            cl['checked'] = True
            agreed = not conflict
            self.rel.score(cl['speaker'], agreed)
            self.j.append(self.EVA, 'EVALUATION', {'source_check': cl['speaker'], 'agreed': agreed,
                                                  'about': ['MECH', w, n], 'claim': c},
                          refs=[cl['seq']] + self._witness(w, n)[-6:], step=self._s(), world_t=self.world_t)

    def _renew_resolution(self, w):
        """New certified knowledge (or its loss) makes unresolved questions about that world worth retrying, and
        makes it worth returning to what we said before (review)."""
        self.drive['mult'].pop('REVIEW|own', None)
        for tid, task in sorted(self.tasks.items()):
            q = task['payload'].get('q') or {}
            if task['status'] == 'OPEN_UNKNOWN' and q.get('world') == w:
                self.drive['mult'].pop(f'RESOLVE|{tid}', None)

    def _in_entity_obs(self, rec, ev):
        c = ev['content']
        w = c['world']
        d, crec = self._commit('ADMIT_OBSERVATION', ev, rec, {'world': w})
        if d.disposition != 'COMMIT' or w not in self.worlds:
            return
        wm = self.worlds[w]
        row = dict(c['features'])
        row.update(c['labels'])
        res = wm.observe_static(row, seq=rec['seq'])
        self.cost['learner_updates'] += len(res)
        summary = {n: {k: r[k] for k in ('p_true', 'confident', 'correct', 'fresh', 'map_changed', 'certified')}
                   for n, r in sorted(res.items())}
        erec = self.j.append(self.EVA, 'EVALUATION', {'world': w, 'entity': c['entity'], 'updates': summary},
                             refs=[crec['seq'], rec['seq']], step=self._s(), world_t=self.world_t)
        for n, r in sorted(res.items()):
            key = (w, n)
            if 'change_point' in r or r.get('certificate_failed'):
                self.regime_events.append([w, n, self.world_t])
            was, now = self.cert_state.get(key, False), bool(r.get('certified'))
            if now != was:
                self.cert_state[key] = now
                self._renew_resolution(w)
                if now:
                    self._check_mech_claims(w, n)
                desc = wm.targets[n].map_description([m for m in wm.names if m != n])
                self._admit_mech(key, now, desc)
                ev_refs = self._witness(w, n)[-12:] if now else [rec['seq']]
                self.j.append(self.COM, 'COMMIT_DECISION',
                              {'decision': decide(operation='ADMIT_BELIEF_STATUS', channel_role='SELF', verified_by=None, origin='').to_dict(),
                               'subject': 'BELIEF_STATUS', 'world': w, 'target': n,
                               'status': 'CERTIFIED' if now else 'REFUTED', 'mechanism': desc.get('map'),
                               'family_origin': desc.get('family_origin'), 'evidence': ev_refs},
                              refs=[erec['seq']] + ev_refs, step=self._s(), world_t=self.world_t)

    # ---------------------------------------------------------------- utterances and perspective
    def _speaker(self, ev):
        ch = ev.get('channel', '')
        return ch.split(':', 1)[1] if ':' in ch else ch.upper()

    def _in_utterance(self, rec, ev):
        c = ev['content']
        speaker = self._speaker(ev)
        d, crec = self._commit('RECORD_UTTERANCE', ev, rec, {'speaker': speaker})
        narrated = ev.get('narrated')
        self.persp.add(speaker=speaker, content=c, t_said=self.world_t, narrated=narrated, seq=rec['seq'],
                       channel_role=ev.get('role', ''))
        base, pol = effective(c)
        interp = {'speaker': speaker, 'claim': c, 'effective_polarity': pol, 'base_op': base.get('op'),
                  'narrated': narrated, 't_said': self.world_t,
                  'note': 'a source assertion: recorded with its speaker and times, never as a world fact'}
        if base.get('op') == 'ROLE':
            interp['role_claim'] = base.get('role')
            interp['identity_unchanged'] = True          # identity comes from the channel only
        self.j.append(self.EVA, 'INTERPRETATION', interp, refs=[crec['seq'], rec['seq']], step=self._s(),
                      world_t=self.world_t, narrated_t=narrated)
        if base.get('op') == 'LESSON_CLAIM':                # lesson-shaped content outside the teacher channel
            self._commit('ADMIT_LESSON', ev, rec, {'content': c, 'speaker': speaker})
            if pol and isinstance(base.get('lesson'), dict) and base['lesson'].get('op') == 'MECH':
                self.mech_claims.append({'speaker': speaker, 'seq': rec['seq'], 'claim': base['lesson'], 'checked': False})
                lw, lv = base['lesson'].get('world'), base['lesson'].get('var')
                if self.cert_state.get((lw, lv)):
                    self._check_mech_claims(lw, lv)
        # check against our own verified observations if it is about a past state we saw
        if base.get('op') == 'STATE' and isinstance(narrated, int):
            seq = self.percept_log.get(base['world'], {}).get(narrated)
            if seq is not None:
                obs = self.j.get(seq)['payload']['event']['content']['percept'].get(base['var'])
                agreed = (int(base['value']) == int(obs)) == pol
                self.rel.score(speaker, agreed)
                self.j.append(self.EVA, 'EVALUATION', {'source_check': speaker, 'agreed': agreed, 'about_t': narrated,
                                                      'claim': c}, refs=[rec['seq'], seq], step=self._s(), world_t=self.world_t)
        if base.get('op') == 'STATE' and narrated is None:
            pass                                             # unknown time: stored as said, never placed on the clock

    def _check_claims_against(self, w, t, percept, pseq):
        for r in self.persp.said:
            base, pol = effective(r['content'])
            if base.get('op') == 'STATE' and base.get('world') == w and r['narrated'] == t and not r['own']:
                if r.get('checked'):
                    continue
                r['checked'] = True
                agreed = (int(base['value']) == int(percept[base['var']])) == pol
                self.rel.score(r['speaker'], agreed)
                self.j.append(self.EVA, 'EVALUATION', {'source_check': r['speaker'], 'agreed': agreed, 'about_t': t,
                                                      'claim': r['content']}, refs=[r['seq'], pseq], step=self._s(), world_t=self.world_t)

    # ---------------------------------------------------------------- lessons, retraction, permissions
    def _in_lesson(self, rec, ev):
        c = ev['content']
        d, crec = self._commit('ADMIT_LESSON', ev, rec, {'content': c, 'speaker': self._speaker(ev)})
        if d.disposition != 'COMMIT':
            return
        self.lessons[rec['seq']] = {'status': 'ADMITTED', 'content': c, 'speaker': self._speaker(ev),
                                    'channel': ev.get('channel'), 'commit_seq': crec['seq']}
        if c.get('op') == 'MECH':
            self.mech_claims.append({'speaker': self._speaker(ev), 'seq': rec['seq'], 'claim': c, 'checked': False})
            if self.cert_state.get((c.get('world'), c.get('var'))):
                self._check_mech_claims(c.get('world'), c.get('var'))
        self._apply_lesson(rec['seq'], c, crec)

    def _apply_lesson(self, lseq, c, crec=None, worlds=None):
        worlds = self.worlds if worlds is None else worlds
        w = c.get('world')
        if c.get('op') != 'MECH' or w not in worlds:
            return
        if self.cfg['learner'] == 'W':
            return self._apply_lesson_w(worlds[w], lseq, c)
        wm = worlds[w]
        tm = wm.targets.get(c['var'])
        if tm is None:
            return
        if lseq in self.lessons and 'target_n_obs' not in self.lessons[lseq]:
            self.lessons[lseq]['target_n_obs'] = tm.n_obs
        self._lesson_family(wm, tm, lseq, c)

    def _lesson_family(self, wm, tm, lseq, c):
        """A lawful lesson becomes ONE private hypothesis (its table) with a prior bonus: a proposal, never a
        certificate — only future verified observations can certify it."""
        tgt = c['var']
        inputs = list(c['inputs'])
        P = tuple(sorted(wm.idx[n] if not wm.static else [m for m in wm.names if m != tgt].index(n) for n in inputs))
        names_ctx = wm.names if not wm.static else [m for m in wm.names if m != tgt]
        in_names = [names_ctx[i] for i in P]
        doms = {n: wm.domains[wm.idx[n]] for n in in_names}
        prog = _rename_self(c['program'], tgt)
        if tm.self_idx is not None:
            in_names2 = in_names + ['__SELF__']
            doms['__SELF__'] = tm.out_domain
        else:
            in_names2 = in_names
        table = compile_program(prog, in_names2, doms, tm.out_domain)
        fam = tm._add_family(P, np.array([0]), specialist=True, lag=False, origin=f'lesson@{lseq}',
                             private=table[None, :], private_size=prog_size_names(prog))
        if fam is not None:
            tm.add_bonus(fam, LESSON_BONUS)

    def _apply_lesson_w(self, wm, lseq, c):
        """For the weighted learner a lesson is a set of LABELLED SAMPLES generated from the taught program (other
        variables drawn deterministically from the lesson's seq), kept with the lesson's lineage and used by sleep."""
        import random as _r
        tgt = c['var']
        tm = wm.targets.get(tgt)
        if tm is None:
            return
        rng = _r.Random(lseq)
        names_ctx = wm.names if not wm.static else [m for m in wm.names if m != tgt]
        doms = {m: wm.domains[wm.idx[m]] for m in wm.names}
        prog = _rename_self(c['program'], tgt)
        for _ in range(32):
            st = {m: rng.randrange(doms[m]) for m in wm.names}
            stp = {m: rng.randrange(doms[m]) for m in wm.names}
            env = dict(st)
            env['__SELF__'] = st.get(tgt, 0)
            from .world import ev as _ev
            y = _ev(prog, env, env['__SELF__'])
            x = tuple(st[m] for m in names_ctx)
            xp = tuple(stp[m] for m in names_ctx) if tm.self_idx is not None else None
            tm.lesson_rows.append((x, xp, int(y), int(lseq)))

    def _in_retract(self, rec, ev):
        target_seq = int(ev['content']['lesson_seq'])
        if 'adopted_from' in rec['payload']:
            # CL-R5 G0.4: a journal reference inside an ADOPTED event names a record of the PARENT journal (as the
            # parent resolved it when the event was delivered); it is translated through the adoption map
            pr = rec['payload'].get('parent_refs') or {}
            target_seq = self._adopt_inbound.get(int(pr.get('lesson_seq', target_seq)), -1)
        les = self.lessons.get(target_seq)
        same = bool(les) and les['channel'] == ev.get('channel')
        d, crec = self._commit('RETRACT_LESSON', ev, rec, {'lesson_seq': target_seq}, refs=[target_seq] if les else [],
                               same_source_as_retracted=same)
        if d.disposition == 'COMMIT' and les and les['status'] == 'ADMITTED':
            les['status'] = 'RETRACTED'
            les['retracted_by'] = crec['seq']
            # CL-R5 G0 (found by attack A1, W): the source withdrew its claim — a withdrawn claim is not scored
            # later against our own knowledge (that would be a use of the retracted lesson)
            for cl in self.mech_claims:
                if cl['seq'] == target_seq and not cl['checked']:
                    cl['checked'] = True
                    cl['withdrawn'] = True
            w = les['content'].get('world')
            if self.cfg['learner'] == 'W':
                self._rebuild_all_w()
            elif w in self.worlds:
                self._rebuild_target(w, les['content'].get('var'))
            self._reconcile_status(crec['seq'])

    def _rebuild_target(self, w, n):
        """Exact revision for S: only the target the lesson was about depends on it (targets are independent
        mixtures), so only that target is re-derived from its own admitted rows, extensions and remaining lessons."""
        wm = self.worlds[w]
        if n not in wm.targets:
            return self._rebuild_world(w)
        self.cost['rebuilds'] += 1
        t0 = time.process_time()
        events = []
        for r in self.j.records:
            p = r['payload']
            if r['owner'] == 'EVAL' and r['kind'] == 'HYPOTHESIS' and p.get('world') == w and p.get('target') == n \
                    and p.get('extension') and 'target_n_obs' in p:
                events.append((p['target_n_obs'], 'EXTEND', p['extension']))
        for ls, les in sorted(self.lessons.items()):
            c = les['content']
            if les['status'] == 'ADMITTED' and c.get('world') == w and c.get('var') == n and 'target_n_obs' in les:
                events.append((les['target_n_obs'], 'LESSON', (ls, c)))
        wm.rebuild_target(n, events, lesson_fn=lambda tm, pay: self._lesson_family(wm, tm, pay[0], pay[1]))
        self.cost['rebuild_seconds'] = self.cost.get('rebuild_seconds', 0.0) + time.process_time() - t0

    def _rebuild_world(self, w):
        """Exact revision: the world model is re-derived from the journal as if the retracted lesson never came."""
        self.cost['rebuilds'] += 1
        t0 = time.process_time()
        wm = self._new_world_model(w)
        pseqs = set(self.percept_log[w].values())
        for r in self.j.records:
            p = r['payload']
            if r['owner'] == 'MEDIATE' and r['kind'] == 'INBOUND':
                ev = p['event']
                if ev.get('content', {}).get('world') != w:
                    continue
                if ev['type'] == 'PERCEPT' and r['seq'] in pseqs:
                    tt = r['world_t']
                    slot = self.interv.get(w, {}).get(tt - 1)
                    wm.observe(tt, ev['content']['percept'], slot is not None, int_vars=(slot or {}).get('vars', []),
                               seq=r['seq'])
                elif ev['type'] == 'ENTITY_OBS':
                    row = dict(ev['content']['features'])
                    row.update(ev['content']['labels'])
                    wm.observe_static(row, seq=r['seq'])
                elif ev['type'] == 'LESSON' and self.lessons.get(r['seq'], {}).get('status') == 'ADMITTED':
                    self.worlds[w] = wm
                    self._apply_lesson(r['seq'], ev['content'])
            elif r['owner'] == 'EVAL' and r['kind'] == 'HYPOTHESIS' and p.get('world') == w and p.get('extension'):
                wm.extend(p['target'], p['extension'])
        self.worlds[w] = wm
        self.cost['rebuild_seconds'] = self.cost.get('rebuild_seconds', 0.0) + time.process_time() - t0

    def _rebuild_all_w(self):
        """Exact revision for the weighted learner: slow weights are shared by all worlds, so EVERYTHING is
        re-derived from the journal (observations, admitted lessons, and every sleep quantum at its place, with
        its own seed) as if the retracted lesson never came.  Its cost is the price of reversibility for W."""
        self.cost['rebuilds'] += 1
        t0 = time.process_time()
        self.slow = WL.SlowModules(self.cfg.get('w_seed', 0))
        models: Dict[str, Any] = {}
        pseqs = {w: set(d.values()) for w, d in self.percept_log.items()}
        for r in self.j.records:
            p = r['payload']
            if r['owner'] == 'MEDIATE' and r['kind'] == 'INBOUND':
                ev = p['event']
                w = (ev.get('content') or {}).get('world')
                if ev['type'] == 'WORLD_INTRO' and w in self.world_meta and self.world_meta[w]['intro_seq'] == r['seq']:
                    models[w] = self._new_world_model(w)
                elif w not in models:
                    continue
                elif ev['type'] == 'PERCEPT' and r['seq'] in pseqs.get(w, ()):
                    tt = r['world_t']
                    slot = self.interv.get(w, {}).get(tt - 1)
                    models[w].observe(tt, ev['content']['percept'], slot is not None,
                                      int_vars=(slot or {}).get('vars', []), seq=r['seq'])
                elif ev['type'] == 'ENTITY_OBS':
                    row = dict(ev['content']['features'])
                    row.update(ev['content']['labels'])
                    models[w].observe_static(row, seq=r['seq'])
                elif ev['type'] == 'LESSON' and self.lessons.get(r['seq'], {}).get('status') == 'ADMITTED':
                    self._apply_lesson(r['seq'], ev['content'], worlds=models)
            elif r['owner'] == 'DRIVE' and r['kind'] == 'DECISION' and p.get('choice') == 'SLEEP':
                WL.sleep(self.slow, [t for w in sorted(models) for n, t in sorted(models[w].targets.items())],
                         seed=r['seq'])
        self.worlds.update(models)
        self.cost['rebuild_seconds'] = self.cost.get('rebuild_seconds', 0.0) + time.process_time() - t0

    # ---------------------------------------------------------------- G1.1 opt-in mediated external clock
    def _in_clock_anchor(self, rec, ev):
        c = ev.get('content') or {}
        try:
            sample = ClockAnchor(session=str(c['session']), monotonic_us=int(c['monotonic_us']),
                                 utc_us=int(c['utc_us']), uncertainty_us=int(c['uncertainty_us']),
                                 source=str(ev.get('channel') or 'HOST_SENSOR'), attested=False,
                                 journal_seq=rec['seq'], adopted_from=rec['payload'].get('adopted_from'))
        except (KeyError, ValueError, TypeError) as exc:
            self.j.append(self.EVA, 'EVALUATION', {'clock_sample_rejected': str(exc)},
                          refs=[rec['seq']], step=self._s(), world_t=self.world_t)
            return
        dec, committed = self._commit('ADMIT_CLOCK_ANCHOR', ev, rec,
                                       {'sample_source': sample.source, 'host_wall_is_not_authority': True})
        if dec.disposition != 'COMMIT':
            return
        if self.external_clock is None:
            self.external_clock = ClockMap()
        self.external_clock.add(sample)
        self.j.append(self.EVA, 'EVALUATION', {'organ': 'EXTERNAL_CLOCK',
                      'accepted_anchor': rec['seq'], 'note': 'UTC measured by host; no tick-to-second assumption'},
                      refs=[rec['seq'], committed['seq']], step=self._s(), world_t=self.world_t)

    def _in_clock_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE', ev, rec)
        q = ev.get('content') or {}
        interval = None
        if self.external_clock is not None and isinstance(q, dict):
            try:
                interval = self.external_clock.estimate_utc(str(q['session']), int(q['monotonic_us']))
            except (KeyError, ValueError, TypeError):
                pass
        pred = ({'status': 'ESTIMATED', 'utc_interval_us': [interval.lo_us, interval.hi_us],
                 'provenance': interval.provenance, 'clock_status': interval.status}
                if interval is not None else {'status':'UNKNOWN', 'reason':'NO_BRACKETING_ANCHORS_OR_CLOCK_JUMP'})
        if self.adopting:
            self.j.append(self.EVA, 'INTERPRETATION', {'organ': 'EXTERNAL_CLOCK', 'prediction': pred,
                          'adopted': True}, refs=[rec['seq']], step=self._s(), world_t=self.world_t)
            return
        dec = self.j.append(self.DRV, 'DECISION', {'choice':'ANSWER_CLOCK',
                 'args': {'qid': q.get('qid') if isinstance(q, dict) else None},
                 'value': 0.0, 'top': []}, refs=[rec['seq']], step=self._s(), world_t=self.world_t)
        self.j.append(self.EVA, 'INTERPRETATION', {'organ':'EXTERNAL_CLOCK', 'prediction': pred},
                      refs=[rec['seq'], dec['seq']], step=self._s(), world_t=self.world_t)
        self._send(dec, ev.get('channel') or 'user', 'ANSWER',
                   {'qid': q.get('qid') if isinstance(q, dict) else None, 'prediction': pred}, refs=[rec['seq']])

    # ---------------------------------------------------------------- G1.2: sandbox-bound frame induction (opt-in)
    def _in_frame_sim_receipt(self, rec, ev):
        # SANDBOX != REAL WORLD. The verified simulator adapter must be supplied
        # by the trusted host process, never by JSON copied from a web page.
        self._commit('RECORD_UTTERANCE', ev, rec)
        if (ev.get('role'), ev.get('verified_by'), ev.get('origin')) != ('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        data = ev.get('content') or {}
        root = data.get('root')
        if not isinstance(root,str) or not root.startswith('sandbox:') or not isinstance(data.get('witness'),dict) or not isinstance(data.get('entities'),dict):
            return
        canonical = {'witness':data['witness'],'entities':data['entities'],
                     'utterance_time':data.get('utterance_time')}
        if 'node_roots' in data:
            canonical['node_roots'] = data['node_roots']
        if root in self.frame_sim_receipts and self.frame_sim_receipts[root] != canonical:
            self.j.append(self.EVA,'EVALUATION',{'organ':'FRAME','status':'CONFLICTING_SIM_RECEIPT_ROOT',
                        'root':root},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        self.frame_sim_receipts[root] = canonical

    def _in_frame_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        content=ev.get('content') or {}
        root=content.get('world_receipt_root')
        receipt=self.frame_sim_receipts.get(root)
        if receipt is None or not isinstance(content.get('utterance'),str):
            self.j.append(self.EVA,'EVALUATION',{'organ':'FRAME','status':'NO_ATTESTED_SIM_RECEIPT'},
                         refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)
            return
        spec=receipt['witness']
        ex={'utterance':content['utterance'],'entities':receipt['entities'],
            'teacher_source':str(ev.get('channel') or 'teacher')+'@'+str(rec['seq']), 'world_receipt_root':root,
            'origin':'SIMULATION','witness':spec,
            'utterance_time':receipt['utterance_time'],'time_axis':spec.get('time_axis')}
        if self.frame_organ is None:self.frame_organ=GroundedFrameInducer()
        try:
            ok=self.frame_organ.observe(ex,verified_receipts={root:receipt})
            result='LEARNED_CONVENTION' if ok else 'DUPLICATE_RECEIPT'
            if ok:
                self.frame_teacher_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                    'teacher_source':ex['teacher_source'],'root':root,'status':'ADMITTED'}
        except (ValueError,PermissionError,KeyError,TypeError) as e:
            result='REJECTED:'+type(e).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'FRAME','status':result,'root':root},
                      refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_frame_retract(self, rec, ev):
        content=ev.get('content') or {}
        try: target=int(content['lesson_seq'])
        except (KeyError,ValueError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False)
            return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)), -1)
        lesson=self.frame_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},
                         same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.frame_organ.retract_teacher(lesson['teacher_source'])
            lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'FRAME','status':'RETRACTED_LESSON',
                    'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_frame_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {}
        qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'FRAME','status':'ADOPTED_QUERY_NOT_REANSWERED'},
                          refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_FRAME',
                       'args':{'qid':qid},'value':0.,'top':[]},
                       refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        if self.frame_organ is None:
            result={'status':'UNKNOWN','reason':'NO_FRAME_EXPERIENCE'}
        else:
            if not self.frame_organ.trained:self.frame_organ.fit()
            try:
                pred=self.frame_organ.propose_frame(q.get('utterance',''),q.get('entities') or {},
                   episode_id=str(qid or 'query:'+str(rec['seq'])),world=str(q.get('world','SANDBOX')),
                   speaker=str(q.get('speaker',ev.get('channel') or 'unknown')),
                   source=str(ev.get('channel') or 'user'),source_root='utterance:'+str(rec['seq']),
                   predicate_slot=str(q.get('predicate_slot','action')),
                   polarity_slot=str(q.get('polarity_slot','polarity')),
                   utterance_time=q.get('utterance_time'))
                if pred['status']=='CANDIDATE':
                    result={'status':'CANDIDATE','confidence':pred['confidence'],
                            'frame':asdict(pred['frame']),'trace':pred['trace']}
                else:result=pred
            except (ValueError,TypeError,KeyError) as e:
                result={'status':'UNKNOWN','reason':'INPUT_INVALID:'+type(e).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'FRAME','qid':qid,'prediction':result},
                      refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',{'qid':qid,'prediction':result},refs=[rec['seq']])

    # ---------------------------------------------------------------- G1.3: opt-in discourse relation learning (experimental)
    def _in_discourse_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        content=ev.get('content') or {}
        try:
            root=str(content['graph_root'])
            graph=self.frame_sim_receipts[root]
            clauses=[]
            receipts={root:graph}
            for piece in content['clauses']:
                nr=str(piece['world_receipt_root'])
                att=self.frame_sim_receipts[nr]
                receipts[nr]=att
                clauses.append({'utterance':piece['utterance'], 'world_receipt_root':nr,
                                'witness':att['witness'],'entities':att['entities']})
            teacher_source=str(ev.get('channel') or 'teacher')+'@'+str(rec['seq'])
            ex={'utterance':content['utterance'],'clauses':clauses,
                'teacher_source':teacher_source,'origin':'SIMULATION',
                'graph_root':root,'link_witness':graph['witness']}
            if self.discourse_organ is None:self.discourse_organ=DiscourseInducer()
            learned=self.discourse_organ.observe(ex,verified_receipts=receipts)
            result='LEARNED_DISCOURSE' if learned else 'DUPLICATE_DISCOURSE_RECEIPT'
            if learned:
                self.discourse_teacher_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                        'teacher_source':teacher_source,'root':root,'status':'ADMITTED'}
        except (ValueError,PermissionError,KeyError,TypeError,IndexError) as e:
            result='REJECTED:'+type(e).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'DISCOURSE','status':result,
                     'root':content.get('graph_root')},refs=[rec['seq'],c['seq']],
                     step=self._s(),world_t=self.world_t)

    def _in_discourse_retract(self, rec, ev):
        content=ev.get('content') or {}
        try: target=int(content['lesson_seq'])
        except (KeyError,ValueError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False)
            return
        lesson=self.discourse_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},
                         same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.discourse_organ.retract_teacher(lesson['teacher_source'])
            lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'DISCOURSE',
                          'status':'RETRACTED_DISCOURSE_LESSON','lesson_seq':target},
                          refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_discourse_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'DISCOURSE',
                         'status':'ADOPTED_QUERY_NOT_REANSWERED'},refs=[rec['seq']],
                         step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_DISCOURSE',
                       'args':{'qid':qid},'value':0.,'top':[]},
                       refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        if self.discourse_organ is None:
            result={'status':'UNKNOWN','reason':'NO_DISCOURSE_EXPERIENCE'}
        else:
            if not self.discourse_organ.trained:self.discourse_organ.fit()
            try:
                result=self.discourse_organ.predict(str(q['utterance']),q.get('entities') or {},
                   speaker=self._speaker(ev),source_root='utterance:'+str(rec['seq']),
                   world=str(q.get('world','SANDBOX')),utterance_time=q.get('utterance_time'),
                   predicate_slot=q.get('predicate_slot'),polarity_slot=q.get('polarity_slot'))
            except (ValueError,TypeError,KeyError) as e:
                result={'status':'UNKNOWN','reason':'INPUT_INVALID:'+type(e).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'DISCOURSE','qid':qid,
                      'prediction':result},refs=[rec['seq'],dec['seq']],
                      step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',
                  {'qid':qid,'prediction':result},refs=[rec['seq']])

    # ---------------------------------------------------------------- G1.4: experimental unaligned grounding. NEW research events only.
    def _in_weak_discourse_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        content=ev.get('content') or {}
        root=str(content.get('graph_root') or '')
        result='REJECTED:NO_WORLD_GRAPH'
        try:
            graph=self.frame_sim_receipts[root]
            roots=[str(r) for r in graph['node_roots']]
            verified={root:graph}
            for r in roots:verified[r]=self.frame_sim_receipts[r]
            if self.frame_organ is None:
                raise ValueError('first acquire single-event language examples')
            if not self.frame_organ.trained:self.frame_organ.fit()
            if self.weak_discourse_organ is None:
                # Copy the atomic evidence, do not alias its mutable state.
                self.weak_discourse_organ=WeakBoundaryInducer(
                    GroundedFrameInducer.from_dict(self.frame_organ.to_dict()))
            teacher=str(ev.get('channel') or 'teacher')+'@'+str(rec['seq'])
            ex={'utterance':content['utterance'],'entities':content['entities'],
                'graph_root':root,'link_witness':graph['witness'],
                'origin':'SIMULATION','teacher_source':teacher}
            ok=self.weak_discourse_organ.observe_pair(ex,verified_receipts=verified)
            result='LEARNED_WEAK_PAIR' if ok else 'DUPLICATE_GRAPH'
            if ok:
                self.weak_discourse_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                    'teacher_source':teacher,'root':root,'status':'ADMITTED'}
        except (ValueError,PermissionError,KeyError,TypeError,IndexError) as exc:
            result='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'WEAK_DISCOURSE','status':result,'root':root},
                      refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_weak_discourse_retract(self, rec, ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (KeyError,TypeError,ValueError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False)
            return
        lesson=self.weak_discourse_lessons.get(str(target))
        same=bool(lesson) and lesson['status']=='ADMITTED' and lesson['channel']==ev.get('channel')
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},
                         same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.weak_discourse_organ.retract_teacher(lesson['teacher_source'])
            lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'WEAK_DISCOURSE',
                'status':'RETRACTED_WEAK_PAIR','lesson_seq':target},
                refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_weak_discourse_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'WEAK_DISCOURSE',
                  'status':'ADOPTED_QUERY_NOT_REANSWERED'},refs=[rec['seq']],
                  step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_WEAK_DISCOURSE',
                  'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],
                  step=self._s(),world_t=self.world_t)
        if self.weak_discourse_organ is None:
            result={'status':'UNKNOWN','reason':'NO_WEAK_DISCOURSE_EXPERIENCE'}
        else:
            if not self.weak_discourse_organ.trained:self.weak_discourse_organ.fit()
            try:
                result=self.weak_discourse_organ.predict(str(q['utterance']),q.get('entities') or {},
                   speaker=self._speaker(ev),source_root='utterance:'+str(rec['seq']),
                   world=str(q.get('world','SANDBOX')),utterance_time=q.get('utterance_time'),
                   predicate_slot=q.get('predicate_slot'),polarity_slot=q.get('polarity_slot'))
            except (ValueError,TypeError,KeyError,IndexError) as exc:
                result={'status':'UNKNOWN','reason':'INPUT_INVALID:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'WEAK_DISCOURSE','qid':qid,
                    'prediction':result},refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',
                   {'qid':qid,'prediction':result},refs=[rec['seq']])

    # ---------------------------------------------------------------- G1.5: lexicon learned from witnessed demonstrations
    def _in_grounding_sim_receipt(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin')) != ('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        content=ev.get('content') or {}
        root=content.get('root')
        if not isinstance(root,str) or not root.startswith('sandbox:'):
            return
        witness=content.get('witness')
        if not isinstance(witness,dict) or witness.get('origin')!='SIMULATION':
            return
        try:
            from .grounded_language import _atoms
            _atoms(witness)
            canonical=json.loads(_sjson(witness))
        except (KeyError,ValueError,TypeError):
            return
        if root in self.grounding_sim_receipts:
            if self.grounding_sim_receipts[root]!=canonical:
                self.j.append(self.EVA,'EVALUATION',{'organ':'GROUNDING',
                    'status':'CONFLICTING_SIM_RECEIPT_ROOT','root':root},refs=[rec['seq']],
                    step=self._s(),world_t=self.world_t)
            return
        self.grounding_sim_receipts[root]=canonical

    def _in_grounding_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        content=ev.get('content') or {}
        root=content.get('world_receipt_root')
        witness=self.grounding_sim_receipts.get(root)
        if witness is None or not isinstance(content.get('utterance'),str):
            status='NO_ATTESTED_SIM_RECEIPT'
        else:
            try:
                if self.grounding_organ is None:self.grounding_organ=SituatedLexicon()
                who=str(ev.get('channel') or 'unknown')+'@'+str(rec['seq'])
                ok=self.grounding_organ.observe(content['utterance'],root,{root:witness},who)
                status='ACQUIRED_DEMO' if ok else 'DUPLICATE_DEMO'
                if ok:
                    self.grounding_teacher_lessons[str(rec['seq'])]={
                        'channel':ev.get('channel'),'source':who,'root':root,'status':'ADMITTED'}
            except (KeyError,TypeError,ValueError,PermissionError) as exc:
                status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'GROUNDING','status':status,'root':root},
            refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_grounding_retract(self, rec, ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (KeyError,TypeError,ValueError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        lesson=self.grounding_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.grounding_organ.revoke(lesson['source'])
            lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'GROUNDING','status':'RETRACTED_DEMO',
                'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_grounding_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {}; qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'GROUNDING',
                'status':'ADOPTED_QUERY_NOT_REANSWERED'},refs=[rec['seq']],
                step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'PROPOSE_GROUNDED_ACTION',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],
            step=self._s(),world_t=self.world_t)
        if self.grounding_organ is None:
            result={'status':'ASK','reason':'NO_GROUNDING_EXPERIENCE',
                    'question':{'intent':'REQUEST_GROUNDED_EXAMPLE'}}
        else:
            try:
                result=self.grounding_organ.predict(q.get('utterance',''),q.get('scene'))
            except (KeyError,ValueError,TypeError) as exc:
                result={'status':'UNKNOWN','reason':'INPUT_INVALID:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'GROUNDING','qid':qid,
            'prediction':result},refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        # NOTE: a proposal is NOT external execution. Human/sandbox host must
        # separately authorize and attest any future action.
        self._send(dec,ev.get('channel') or 'user','ANSWER',
            {'qid':qid,'prediction':result},refs=[rec['seq']])

    # ---------------------------------------------------------------- G2.1: general relational programme discovery (sandbox)
    def _in_relational_sim_receipt(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        c=ev.get('content') or {};w=c.get('witness');root=c.get('root')
        try:
            features(w)
            if root!=witness_root(w):return
            canon=json.loads(_sjson(w))
        except (TypeError,ValueError,KeyError):return
        if root in self.relational_sim_receipts:
            if canon!=self.relational_sim_receipts[root]:
                self.j.append(self.EVA,'EVALUATION',{'organ':'RELATIONAL','status':'CONFLICTING_ROOT'},
                    refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        self.relational_sim_receipts[root]=canon

    def _in_relational_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        q=ev.get('content') or {};rp=q.get('positive_root');rn=q.get('contrast_root')
        status='NO_ATTESTED_CONTRAST'
        if rp in self.relational_sim_receipts and rn in self.relational_sim_receipts:
            try:
                if self.relational_organ is None:self.relational_organ=RelationalInducer()
                source=str(ev.get('channel') or 'teacher')+'@'+str(rec['seq'])
                ok=self.relational_organ.observe(q.get('utterance'),rp,rn,self.relational_sim_receipts,source)
                status='ACQUIRED_CONTRAST' if ok else 'DUPLICATE_CONTRAST'
                if ok:self.relational_teacher_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                             'source':source,'positive_root':rp,'negative_root':rn,'status':'ADMITTED'}
            except (ValueError,KeyError,PermissionError,TypeError) as exc:
                status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'RELATIONAL','status':status,
                      'positive_root':rp,'negative_root':rn},refs=[rec['seq'],c['seq']],
                      step=self._s(),world_t=self.world_t)

    def _in_relational_retract(self, rec, ev):
        q=ev.get('content') or {}
        try:target=int(q['lesson_seq'])
        except (ValueError,KeyError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.relational_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.relational_organ.revoke(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'RELATIONAL','status':'RETRACTED_CONTRAST',
                'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_relational_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'RELATIONAL',
                  'status':'ADOPTED_QUERY_NOT_REANSWERED'},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_RELATIONAL',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        try:
            pred=(self.relational_organ.predict(q.get('utterance'),q.get('witness'))
                 if self.relational_organ else {'status':'ASK','reason':'NO_RELATIONAL_EXPERIENCE'})
        except (TypeError,ValueError,KeyError) as exc:
            pred={'status':'UNKNOWN','reason':'INVALID_INPUT:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'RELATIONAL','qid':qid,'prediction':pred},
                refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',{'qid':qid,'prediction':pred},refs=[rec['seq']])

    # ---------------------------------------------------- G2.2: temporal structure induction
    def _in_temporal_sim_receipt(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        content=ev.get('content') or {};w=content.get('witness');root=content.get('root')
        try:
            validate_trace(w)
            if root!=trace_root(w):return
            canon=json.loads(_sjson(w))
        except (ValueError,TypeError,KeyError):return
        if root in self.temporal_sim_receipts:
            if canon!=self.temporal_sim_receipts[root]:
                self.j.append(self.EVA,'EVALUATION',{'organ':'TEMPORAL','status':'CONFLICTING_ROOT'},
                              refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        self.temporal_sim_receipts[root]=canon

    def _in_temporal_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        q=ev.get('content') or {};rp=q.get('positive_root');rn=q.get('contrast_root')
        status='NO_ATTESTED_CONTRAST'
        if rp in self.temporal_sim_receipts and rn in self.temporal_sim_receipts:
            try:
                if self.temporal_organ is None:self.temporal_organ=TemporalInducer()
                source=str(ev.get('channel') or 'teacher')+'@'+str(rec['seq'])
                ok=self.temporal_organ.observe(q.get('utterance'),rp,rn,self.temporal_sim_receipts,source)
                status='ACQUIRED_CONTRAST' if ok else 'DUPLICATE_CONTRAST'
                if ok:self.temporal_teacher_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                      'source':source,'positive_root':rp,'negative_root':rn,'status':'ADMITTED'}
            except (ValueError,TypeError,KeyError,PermissionError) as exc:
                status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'TEMPORAL','status':status,
                 'positive_root':rp,'negative_root':rn},refs=[rec['seq'],c['seq']],
                 step=self._s(),world_t=self.world_t)

    def _in_temporal_retract(self, rec, ev):
        q=ev.get('content') or {}
        try:target=int(q['lesson_seq'])
        except (ValueError,TypeError,KeyError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.temporal_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.temporal_organ.revoke(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'TEMPORAL','status':'RETRACTED_CONTRAST',
                   'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_temporal_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'TEMPORAL','status':'ADOPTED_QUERY_NOT_REANSWERED'},
                 refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_TEMPORAL',
                 'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        try:
            pred=(self.temporal_organ.predict(q.get('utterance'),q.get('witness')) if self.temporal_organ
                  else {'status':'ASK','reason':'NO_TEMPORAL_EXPERIENCE'})
        except (ValueError,TypeError,KeyError) as exc:
            pred={'status':'UNKNOWN','reason':'INVALID_INPUT:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'TEMPORAL','qid':qid,'prediction':pred},
             refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',{'qid':qid,'prediction':pred},refs=[rec['seq']])

    # ---------------------------------------------------- G2.3: comparative timestamp algebra
    def _in_metric_sim_receipt(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        content=ev.get('content') or {};w=content.get('witness');root=content.get('root')
        try:
            measured(w)
            if root!=metric_root(w):return
            canon=json.loads(_sjson(w))
        except (ValueError,TypeError,KeyError):return
        if root in self.metric_sim_receipts:
            if canon!=self.metric_sim_receipts[root]:
                self.j.append(self.EVA,'EVALUATION',{'organ':'METRIC','status':'CONFLICTING_ROOT'},
                              refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        self.metric_sim_receipts[root]=canon

    def _in_metric_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        q=ev.get('content') or {};rp=q.get('positive_root');rn=q.get('contrast_root')
        status='NO_ATTESTED_CONTRAST'
        if rp in self.metric_sim_receipts and rn in self.metric_sim_receipts:
            try:
                if self.metric_organ is None:self.metric_organ=MetricInducer()
                source=str(ev.get('channel') or 'teacher')+'@'+str(rec['seq'])
                ok=self.metric_organ.observe(q.get('utterance'),rp,rn,self.metric_sim_receipts,source)
                status='ACQUIRED_CONTRAST' if ok else 'DUPLICATE_CONTRAST'
                if ok:self.metric_teacher_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                      'source':source,'positive_root':rp,'negative_root':rn,'status':'ADMITTED'}
            except (ValueError,TypeError,KeyError,PermissionError) as exc:
                status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'METRIC','status':status,
                 'positive_root':rp,'negative_root':rn},refs=[rec['seq'],c['seq']],
                 step=self._s(),world_t=self.world_t)

    def _in_metric_retract(self, rec, ev):
        q=ev.get('content') or {}
        try:target=int(q['lesson_seq'])
        except (ValueError,TypeError,KeyError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.metric_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.metric_organ.revoke(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'METRIC','status':'RETRACTED_CONTRAST',
                   'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_metric_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'METRIC','status':'ADOPTED_QUERY_NOT_REANSWERED'},
                 refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_METRIC',
                 'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        try:
            pred=(self.metric_organ.predict(q.get('utterance'),q.get('witness')) if self.metric_organ
                  else {'status':'ASK','reason':'NO_METRIC_EXPERIENCE'})
        except (ValueError,TypeError,KeyError) as exc:
            pred={'status':'UNKNOWN','reason':'INVALID_INPUT:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'METRIC','qid':qid,'prediction':pred},
             refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',{'qid':qid,'prediction':pred},refs=[rec['seq']])

    # ---------------------------------------------------------------- G1.8: event dynamics from sandbox witness + teacher language
    def _in_event_trace_sim_receipt(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        # Host controls the channel and attests a SIMULATION event, not a real-world fact.
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin')) != ('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        c=ev.get('content') or {}
        witness=c.get('witness')
        root=c.get('root')
        try:
            measured_trace(witness)
            if content_root(witness)!=root:
                raise ValueError('receipt root does not match event trace bytes')
            canonical=json.loads(_sjson(witness))
        except (ValueError,TypeError,PermissionError):
            return
        if root in self.event_trace_sim_receipts:
            if self.event_trace_sim_receipts[root]!=canonical:
                self.j.append(self.EVA,'EVALUATION',{'organ':'EVENT_TRACE',
                    'status':'CONFLICTING_SIM_RECEIPT','root':root},refs=[rec['seq']],
                    step=self._s(),world_t=self.world_t)
            return
        self.event_trace_sim_receipts[root]=canonical
        # Aliases are host-supplied *surface labels*, not learned Russian grammar.
        aliases=(canonical['trace'].get('surface_aliases') or {})
        if isinstance(aliases,dict):
            from .grounded_language import tokenize
            safe=set(self.event_trace_surface_vocab)
            for value in aliases.values():
                if isinstance(value,str) and 0<len(value)<80:
                    safe.update(tokenize(value))
            self.event_trace_surface_vocab=sorted(safe)

    def _in_event_trace_teach(self, rec, ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        data=ev.get('content') or {}
        root=data.get('world_receipt_root');wit=self.event_trace_sim_receipts.get(root)
        status='NO_ATTESTED_EVENT_TRACE'
        if wit is not None and isinstance(data.get('utterance'),str):
            try:
                if self.event_trace_organ is None:self.event_trace_organ=EventMeaningInducer()
                who=str(ev.get('channel') or 'unknown')+'@'+str(rec['seq'])
                ok=self.event_trace_organ.observe(data['utterance'],root,wit,who)
                status='ACQUIRED_EVENT_EXAMPLE' if ok else 'DUPLICATE_EVENT_EXAMPLE'
                if ok:
                    self.event_trace_teacher_lessons[str(rec['seq'])]={
                       'channel':ev.get('channel'),'source':who,'root':root,'status':'ADMITTED'}
            except (KeyError,ValueError,TypeError,PermissionError) as exc:
                status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'EVENT_TRACE',
            'status':status,'root':root},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_event_trace_retract(self, rec, ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (KeyError,TypeError,ValueError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        lesson=self.event_trace_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.event_trace_organ.revoke(lesson['source'])
            lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'EVENT_TRACE','status':'RETRACTED_EVENT_EXAMPLE',
                 'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_event_trace_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'EVENT_TRACE',
               'status':'ADOPTED_QUERY_NOT_REANSWERED'},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        decision=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_EVENT_TRACE',
              'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],
              step=self._s(),world_t=self.world_t)
        if self.event_trace_organ is None:
            prediction={'status':'ASK','reason':'NO_EVENT_EXPERIENCE'}
        else:
            try:
                prediction=self.event_trace_organ.predict(q.get('utterance',''),
                   speaker=ev.get('channel'),
                   utterance_utc_ns=q.get('utterance_utc_ns'),
                   grounded_surface_tokens=self.event_trace_surface_vocab)
            except (ValueError,TypeError) as exc:
                prediction={'status':'UNKNOWN','reason':'INVALID_INPUT:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'EVENT_TRACE','qid':qid,
                'prediction':prediction},refs=[rec['seq'],decision['seq']],
                step=self._s(),world_t=self.world_t)
        self._send(decision,ev.get('channel') or 'user','ANSWER',
                   {'qid':qid,'prediction':prediction},refs=[rec['seq']])

    # ----------------------------------------------------- G2.4: joined event interpretation
    def _in_joint_sim_receipt(self, rec, ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        c=ev.get('content') or {};w=c.get('witness');scene=c.get('scene');root=c.get('root')
        try:
            if joint_root(w,scene)!=root:return
            # Observation must match BOTH the trace and the scene; not a
            # teacher-provided scene later grafted onto a verified trace.
            canon=json.loads(_sjson({'witness':w,'scene':scene}))
        except (KeyError,TypeError,ValueError,PermissionError):return
        if root in self.joint_sim_receipts:
            if canon!=self.joint_sim_receipts[root]:
                self.j.append(self.EVA,'EVALUATION',{'organ':'JOINT','status':'CONFLICTING_ROOT'},
                    refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        self.joint_sim_receipts[root]=canon

    def _in_joint_teach(self,rec,ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        data=ev.get('content') or {};root=data.get('root');status='NO_JOINT_SIM_RECEIPT'
        if root in self.joint_sim_receipts:
            try:
                ww=self.joint_sim_receipts[root]
                if self.joint_organ is None:self.joint_organ=JointUtteranceInducer()
                who=str(ev.get('channel') or 'teacher')+'@'+str(rec['seq'])
                ok=self.joint_organ.observe(data['utterance'],root,ww['witness'],ww['scene'],who)
                status='ACQUIRED_JOINT_EXAMPLE' if ok else 'DUPLICATE_JOINT_EXAMPLE'
                if ok:self.joint_teacher_lessons[str(rec['seq'])]={
                    'channel':ev.get('channel'),'source':who,'root':root,'status':'ADMITTED'}
            except (TypeError,KeyError,ValueError,PermissionError) as exc:
                status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'JOINT','status':status,'root':root},
            refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_joint_retract(self,rec,ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (ValueError,KeyError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.joint_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.joint_organ.revoke(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'JOINT','status':'RETRACTED_JOINT_EXAMPLE',
              'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_joint_query(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'JOINT',
                'status':'ADOPTED_QUERY_NOT_REANSWERED'},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        decision=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_JOINT',
                'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        if self.joint_organ is None:
            prediction={'status':'ASK','reason':'NO_JOINT_EXPERIENCE'}
        else:
            try:prediction=self.joint_organ.predict(q.get('utterance',''),q.get('scene'),
                    ev.get('channel'),q.get('utterance_utc_ns'))
            except (ValueError,TypeError,KeyError) as exc:
                prediction={'status':'UNKNOWN','reason':'INVALID_QUERY:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'JOINT','qid':qid,
               'prediction':prediction},refs=[rec['seq'],decision['seq']],step=self._s(),world_t=self.world_t)
        self._send(decision,ev.get('channel') or 'user','ANSWER',
            {'qid':qid,'prediction':prediction},refs=[rec['seq']])

    # ----------------------------------------------------- G2.5 meaning-before-language
    def _in_story_sim_receipt(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if (ev.get('role'),ev.get('verified_by'),ev.get('origin'))!=('SIM_FEED','SIM_HOST','SIMULATION'):
            return
        d=ev.get('content') or {};event=d.get('event');root=d.get('root')
        try:
            if event_root(event)!=root:return
            if self.story_mind is None:self.story_mind=StoryMind()
            acquired=self.story_mind.observe(event,root)
            if acquired:self.story_sim_receipts[root]={'event':event,'inbound_seq':rec['seq']}
            status='ACQUIRED_STORY_EVENT' if acquired else 'DUPLICATE_STORY_EVENT'
        except (ValueError,TypeError,PermissionError) as exc:status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'STORY','status':status,'root':root},
            refs=[rec['seq']],step=self._s(),world_t=self.world_t)

    def _in_story_teach(self,rec,ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        x=ev.get('content') or {};status='NO_STORY_EVIDENCE'
        if self.story_mind and x.get('story_id') in self.story_mind.stories:
            try:
                if self.story_questions is None:self.story_questions=MeaningQuestionLearner()
                source=str(ev.get('channel'))+'@'+str(rec['seq'])
                record=self.story_questions.observe(self.story_mind,x['story_id'],x['utterance'],
                        x['aliases'],x['key'],x['answer'],source)
                status='ACQUIRED_STORY_QUESTION'
                self.story_teacher_lessons[str(rec['seq'])]={'channel':ev.get('channel'),
                    'source':source,'status':'ADMITTED','story_id':x['story_id']}
            except (ValueError,KeyError,TypeError) as exc:status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'STORY','status':status},
            refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_story_retract(self,rec,ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (ValueError,KeyError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.story_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.story_questions.revoke(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'STORY','status':'RETRACTED_STORY_QUESTION',
                  'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_story_query(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'STORY','status':'ADOPTED_QUERY_NOT_REANSWERED'},
                refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        decision=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_STORY',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        if self.story_mind is None or self.story_questions is None:
            prediction={'status':'UNKNOWN','reason':'NO_STORY_LANGUAGE_EXPERIENCE'}
        else:
            try:prediction=self.story_questions.predict(self.story_mind,q['story_id'],
                     q['utterance'],q['aliases'],q['key'])
            except (ValueError,TypeError,KeyError) as exc:
                prediction={'status':'UNKNOWN','reason':'INVALID_STORY_QUERY:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'STORY','qid':qid,
            'prediction':prediction},refs=[rec['seq'],decision['seq']],step=self._s(),world_t=self.world_t)
        self._send(decision,ev.get('channel') or 'user','ANSWER',
            {'qid':qid,'prediction':prediction},refs=[rec['seq']])

    def _in_story_internal_query(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_STORY_INTERNAL',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        prediction=(self.story_mind.ask(q.get('story_id'),q.get('query') or {}) if self.story_mind
                    else {'status':'UNKNOWN','reason':'NO_STORY'})
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'STORY','qid':qid,'prediction':prediction},
            refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',
            {'qid':qid,'prediction':prediction},refs=[rec['seq']])

    # ----------------------------------------------------- G2.6 raw-surface -> narrated-story
    def _in_text_story_teach(self,rec,ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        x=ev.get('content') or {}
        status='NO_SIMULATOR_SUPPORT';support=[]
        try:
            support=attested_atomic_story(self.story_mind,x['story_id'],x['meaning'])
            if support:
                if self.text_story_learner is None:self.text_story_learner=PatternInducer()
                source=str(ev.get('channel'))+'@'+str(rec['seq'])
                self.text_story_learner.teach(x['utterance'],x['meaning'],
                    x['persons'],x['objects'],source=source,context=x.get('context'))
                self.text_story_teacher_lessons[str(rec['seq'])]={
                    'channel':ev.get('channel'),'source':source,'status':'ADMITTED',
                    'supports':support,'story_id':x['story_id']}
                status='ACQUIRED_ATTESTED_TEXT_MEANING'
        except (ValueError,KeyError,TypeError) as exc:status='REJECTED:'+type(exc).__name__
        self.j.append(self.EVA,'EVALUATION',{'organ':'TEXT_STORY','status':status,
              'supports':support[:3]},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_text_story_retract(self,rec,ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (ValueError,KeyError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.text_story_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.text_story_learner.retract(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'TEXT_STORY','status':'RETRACTED_TEXT_LESSON',
              'lesson_seq':target},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_text_story_query(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            # Historical user text is neither a host observation nor a new
            # outbound act. Re-derive its SOURCE-SCOPED interpretation from
            # this moment's already acquired grammar and preserve the old
            # narrative in active memory. Never re-answer a historical query.
            status='ADOPTED_TEXT_NOT_INTERPRETABLE'
            if self.text_story_learner is not None:
                try:
                    prediction=self.text_story_learner.parse(q['paragraph'],q['persons'],q['objects'],
                        context=q.get('context'))
                    if prediction.get('status')=='PARSED':
                        narrated=NarrativeMind()
                        result=narrated.consume(prediction,source='utterance:'+str(rec['seq']))
                        if result.get('status')=='ADMITTED_NARRATIVE':
                            self.text_story_narratives[str(rec['seq'])]={
                                'channel':ev.get('channel'),'source_inbound_seq':rec['seq'],
                                'scope':'NARRATED_ONLY','interpretation':narrated.to_dict()}
                            status='ADOPTED_NARRATED_ONLY_REDERIVED'
                except (ValueError,KeyError,TypeError):pass
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'TEXT_STORY','status':status},
                refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_TEXT_STORY',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        if self.text_story_learner is None:
            prediction={'status':'UNKNOWN','reason':'NO_ATTESTED_LANGUAGE_EXPERIENCE'}
        else:
            try:
                prediction=self.text_story_learner.parse(q['paragraph'],q['persons'],q['objects'],
                    context=q.get('context'))
                if prediction['status']=='PARSED':
                    narrated=NarrativeMind()
                    result=narrated.consume(prediction,source='utterance:'+str(rec['seq']))
                    if result['status']!='ADMITTED_NARRATIVE':prediction=result
                    else:
                        # Append the interpretation as a SOURCE-SCOPED NARRATIVE,
                        # not as a simulator fact. It survives cold restart.
                        self.text_story_narratives[str(rec['seq'])]={
                            'channel':ev.get('channel'),'source_inbound_seq':rec['seq'],
                            'scope':'NARRATED_ONLY','interpretation':narrated.to_dict()}
                        obj=q.get('ask_holder')
                        if obj:prediction={**prediction,'holder':narrated.ask_holder(obj)}
            except (ValueError,KeyError,TypeError) as exc:
                prediction={'status':'UNKNOWN','reason':'INVALID_TEXT_STORY_QUERY:'+type(exc).__name__}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'TEXT_STORY','qid':qid,
            'prediction':prediction},refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',
            {'qid':qid,'prediction':prediction},refs=[rec['seq']])

    # ---------------------------------------------- G2.8 bounded conversation presence/identity
    def _in_dialogue_sensor(self,rec,ev):
        d,c=self._commit('ADMIT_OBSERVATION',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='VERIFIED_OBSERVATION':return
        x=ev.get('content') or {};status='INVALID_SENSOR_RECORD'
        try:
            if self.interaction_identity is None:self.interaction_identity=InteractionIdentity()
            self.interaction_identity.sensor(x['session'],ev['channel'],x['message_id'],
                clusters=x.get('clusters'),authenticated_principal=x.get('authenticated_principal'),root=rec['seq'])
            status='ATTESTED_CHANNEL_SENSOR'
        except (ValueError,KeyError,TypeError):pass
        self.j.append(self.EVA,'EVALUATION',{'organ':'DIALOGUE','status':status},
            refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_dialogue_turn(self,rec,ev):
        d,c=self._commit('RECORD_UTTERANCE',ev,rec)
        status='UNVERIFIED_CHANNEL_TURN';result=None;x=ev.get('content') or {}
        if ev.get('role') in ('USER','TEACHER') and ev.get('verified_by')=='TRANSPORT':
            try:
                if self.interaction_identity is None:self.interaction_identity=InteractionIdentity()
                result=self.interaction_identity.observe(x['session'],ev['channel'],x['message_id'],
                    utterance=x.get('utterance',''),claimed_name=x.get('claimed_name'),
                    farewell=x.get('farewell_claim',False),addressed_to=x.get('addressed_to'),
                    host_routed=(ev.get('host_routed_to')=='SELF_C4'))
                status='PROVISIONAL_SPEAKER_TRACKED'
            except (ValueError,TypeError,KeyError):status='UNRESOLVED_DIALOGUE_TURN'
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'DIALOGUE','status':status,'result':result},
            refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)
        if status!='PROVISIONAL_SPEAKER_TRACKED' or self.adopting:return
        # ASK is an explicitly gated DRIVE act, not a rule that assigns an identity.
        # Only ask once per uncertainty episode: subsequent turns do not spam.
        prompt=self.interaction_identity.should_ask_identity(x['session'],ev['channel'])
        if prompt['ask']:
            dec=self.j.append(self.DRV,'DECISION',{'choice':'ASK_DIALOGUE_IDENTITY',
                'args':{'reason':prompt['reason']},'value':0.,'top':[]},
                refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            self.interaction_identity.mark_asked(x['session'],ev['channel'])
            self._send(dec,ev['channel'],'ASK',
                {'question':'С кем я сейчас разговариваю?',
                 'uncertainty':prompt['reason'],'not_a_verified_identity':True},refs=[rec['seq']])

    def _in_dialogue_ground(self,rec,ev):
        d,c=self._commit('ADMIT_OBSERVATION',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='VERIFIED_OBSERVATION':return
        q=ev.get('content') or {};status='REJECTED_GROUNDING'
        try:
            if self.interaction_identity is None:raise ValueError('NO_DIALOGUE')
            self.interaction_identity.ground(q['session'],ev['channel'],q['message_id'],
                q['grounding_id'],q['target_ref'],q['argument_slot'],rec['seq'],
                kind=q.get('semantic_kind'),agreement=q.get('agreement_class'))
            status='ATTESTED_CONTEXTUAL_TARGET'
        except (ValueError,KeyError,TypeError):pass
        self.j.append(self.EVA,'EVALUATION',{'organ':'DIALOGUE','status':status},
            refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_dialogue_teach(self,rec,ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        x=ev.get('content') or {};status='NO_ATTESTED_DIALOGUE_CONTEXT';support_root=None;context_roots=[]
        try:
            if self.interaction_identity is None:raise ValueError('NO_DIALOGUE')
            turn_key=dialogue_canonical([dialogue_canonical([x['session'],x['turn_channel']]),x['message_id']])
            source=str(ev.get('channel'))+'@'+str(rec['seq'])
            grounding_key=dialogue_canonical([turn_key,x['grounding_id']])
            if x.get('lesson_type')=='CONTEXT_REFERENCE':
                self.interaction_identity.teach_reference(x['form'],source,grounding_key)
                context_roots=[item['support_root'] for item in
                    self.interaction_identity.previous_referents(turn_key)]
                status='ACQUIRED_CONTEXTUAL_REFERENCE'
            elif x.get('lesson_type') is None:
                self.interaction_identity.learn_from_grounding(x['form'],source,grounding_key)
                status='ACQUIRED_CONTEXTUAL_WORD_ROLE'
            else:raise ValueError('UNKNOWN_LESSON_KIND')
            support_root=int(self.interaction_identity.groundings[grounding_key]['root'])
            self.dialogue_teacher_lessons[str(rec['seq'])]={'source':source,'channel':ev['channel'],'active':True}
        except (ValueError,KeyError,TypeError):status='REJECTED_UNGROUNDED_WORD_ROLE'
        self.j.append(self.EVA,'EVALUATION',{'organ':'DIALOGUE','status':status,'grounding_root':support_root,
             'context_roots':context_roots},
            refs=[rec['seq'],c['seq']]+([int(support_root)] if support_root is not None else []),
            step=self._s(),world_t=self.world_t)

    def _in_dialogue_retract(self,rec,ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (ValueError,KeyError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.dialogue_teacher_lessons.get(str(target))
        same=bool(lesson and lesson['active'] and lesson['channel']==ev.get('channel'))
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.interaction_identity.retract_source(lesson['source']);lesson['active']=False
            self.j.append(self.EVA,'EVALUATION',{'organ':'DIALOGUE',
                'status':'RETRACTED_CONTEXTUAL_WORD_ROLE','lesson_seq':target},
                refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_dialogue_query(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        if self.adopting:
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'DIALOGUE','status':'HISTORICAL_QUERY_NOT_REANSWERED'},
                refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        q=ev.get('content') or {};qid=q.get('qid')
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_DIALOGUE',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        prediction={'status':'UNKNOWN','reason':'NO_DIALOGUE_EXPERIENCE'}
        if self.interaction_identity is not None:
            try:
                if q['query_type']=='SPEAKER':
                    prediction=self.interaction_identity.inspect(q['session'],ev['channel'],q['message_id'])
                elif q['query_type']=='DEIXIS':
                    prediction=self.interaction_identity.resolve_word(q['word'],q['argument_slot'],
                        q['session'],ev['channel'],q['message_id'],q.get('antecedents'),q.get('perspective'))
                elif q['query_type']=='CLARIFICATION':
                    prediction=self.interaction_identity.should_ask_identity(q['session'],ev['channel'],
                        high_stakes=q.get('high_stakes',False))
                elif q['query_type']=='REFERENCE_SCAN':
                    prediction=self.interaction_identity.resolve_references(q['session'],ev['channel'],q['message_id'])
            except (KeyError,ValueError,TypeError):prediction={'status':'UNKNOWN','reason':'INVALID_DIALOGUE_QUERY'}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'DIALOGUE','qid':qid,'prediction':prediction},
            refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',
            {'qid':qid,'prediction':prediction},refs=[rec['seq']])

    # ------------------------------------------------ G2.7 inflection & semantic role reversal
    def _in_morph_story_teach(self,rec,ev):
        d,c=self._commit('ADMIT_LANG_DEMO',ev,rec)
        if d.disposition!='COMMIT' or d.basis!='LANGUAGE_CONVENTION':return
        q=ev.get('content') or {}
        support=[];status='NO_SIMULATOR_SUPPORT'
        try:
            support=attested_atomic_story(self.story_mind,q['story_id'],q['meaning'])
            if support:
                if self.morph_story_learner is None:self.morph_story_learner=MorphStory()
                source=str(ev.get('channel'))+'@'+str(rec['seq'])
                self.morph_story_learner.teach(q['utterance'],q['meaning'],q['persons'],q['objects'],source,
                                              context=q.get('context'))
                self.morph_story_teacher_lessons[str(rec['seq'])]={
                    'channel':ev.get('channel'),'source':source,'status':'ADMITTED','supports':support,
                    'story_id':q['story_id']}
                status='ACQUIRED_ATTESTED_MORPH_MEANING'
        except (ValueError,KeyError,TypeError):status='REJECTED_UNRESOLVED_LANGUAGE'
        self.j.append(self.EVA,'EVALUATION',{'organ':'MORPH_STORY','status':status,
             'supports':support[:3]},refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_morph_story_retract(self,rec,ev):
        try:target=int((ev.get('content') or {})['lesson_seq'])
        except (ValueError,KeyError,TypeError):
            self._commit('RETRACT_LESSON',ev,rec,same_source_as_retracted=False);return
        if 'adopted_from' in rec['payload']:
            old=rec['payload'].get('parent_refs') or {}
            target=self._adopt_inbound.get(int(old.get('lesson_seq',target)),-1)
        lesson=self.morph_story_teacher_lessons.get(str(target))
        same=bool(lesson) and lesson['channel']==ev.get('channel') and lesson['status']=='ADMITTED'
        d,c=self._commit('RETRACT_LESSON',ev,rec,{'lesson_seq':target},same_source_as_retracted=same)
        if d.disposition=='COMMIT' and same:
            self.morph_story_learner.retract(lesson['source']);lesson['status']='RETRACTED'
            self.j.append(self.EVA,'EVALUATION',{'organ':'MORPH_STORY',
                'status':'RETRACTED_MORPH_LESSON','lesson_seq':target},
                refs=[rec['seq'],c['seq']],step=self._s(),world_t=self.world_t)

    def _in_morph_story_query(self,rec,ev):
        self._commit('RECORD_UTTERANCE',ev,rec)
        q=ev.get('content') or {};qid=q.get('qid')
        if self.adopting:
            status='ADOPTED_MORPH_NOT_INTERPRETABLE'
            if self.morph_story_learner is not None:
                try:
                    parsed=self.morph_story_learner.parse(q['paragraph'],q['persons'],q['objects'],q.get('context'))
                    if parsed.get('status')=='PARSED':
                        narrated=NarrativeMind()
                        res=narrated.consume(parsed,source='utterance:'+str(rec['seq']))
                        if res.get('status')=='ADMITTED_NARRATIVE':
                            self.morph_story_narratives[str(rec['seq'])]={
                                'channel':ev.get('channel'),'scope':'NARRATED_ONLY',
                                'source_inbound_seq':rec['seq'],'interpretation':narrated.to_dict()}
                            status='ADOPTED_MORPH_NARRATIVE_REDERIVED'
                except (ValueError,KeyError,TypeError):pass
            self.j.append(self.EVA,'INTERPRETATION',{'organ':'MORPH_STORY','status':status},
                refs=[rec['seq']],step=self._s(),world_t=self.world_t)
            return
        dec=self.j.append(self.DRV,'DECISION',{'choice':'ANSWER_MORPH_STORY',
            'args':{'qid':qid},'value':0.,'top':[]},refs=[rec['seq']],step=self._s(),world_t=self.world_t)
        if self.morph_story_learner is None:
            prediction={'status':'UNKNOWN','reason':'NO_ATTESTED_INFLECTION_LESSONS'}
        else:
            try:
                prediction=self.morph_story_learner.parse(q['paragraph'],q['persons'],q['objects'],q.get('context'))
                if prediction['status']=='PARSED':
                    story=NarrativeMind();result=story.consume(prediction,source='utterance:'+str(rec['seq']))
                    if result['status']!='ADMITTED_NARRATIVE':prediction=result
                    else:
                        self.morph_story_narratives[str(rec['seq'])]={
                            'channel':ev.get('channel'),'scope':'NARRATED_ONLY',
                            'source_inbound_seq':rec['seq'],'interpretation':story.to_dict()}
                        if q.get('ask_holder'):
                            prediction={**prediction,'holder':story.ask_holder(q['ask_holder'])}
            except (ValueError,KeyError,TypeError):
                prediction={'status':'UNKNOWN','reason':'INVALID_MORPH_STORY_QUERY'}
        self.j.append(self.EVA,'INTERPRETATION',{'organ':'MORPH_STORY','qid':qid,
            'prediction':prediction},refs=[rec['seq'],dec['seq']],step=self._s(),world_t=self.world_t)
        self._send(dec,ev.get('channel') or 'user','ANSWER',{'qid':qid,'prediction':prediction},refs=[rec['seq']])

    # ---------------------------------------------------------------- CL-R5 G1: language from experience
    def _in_lang_experience(self, rec, ev):
        d, c = self._commit('ADMIT_LANG_DEMO', ev, rec)
        if d.disposition != 'COMMIT':
            return
        if self.lang is None:
            self.lang = LANG.make_learner(self.cfg.get('lang', 'S'))
        self.lang.observe(ev.get('content') or {})
        self.j.append(self.EVA, 'EVALUATION', {'organ': 'LANG', 'learner': self.lang.kind, 'learned_from': rec['seq'],
                                               'basis': d.basis}, refs=[rec['seq'], c['seq']], step=self._s(),
                      world_t=self.world_t)

    def _in_lang_query(self, rec, ev):
        self._commit('RECORD_UTTERANCE', ev, rec)                # what is asked is a source assertion, not a fact
        q = dict(ev.get('content') or {})
        qid = q.pop('qid', None)
        if self.lang is None:
            pred, conf, trace = {'type': 'UNKNOWN'}, 0.0, {'why': 'NO_LANGUAGE_EXPERIENCE'}
        else:
            pred, conf, trace = self.lang.predict(q)
        if self.adopting:                                        # the parent's answer is carried as history
            self.j.append(self.EVA, 'INTERPRETATION', {'organ': 'LANG', 'qid': qid, 'prediction': pred,
                                                       'confidence': conf, 'adopted': True}, refs=[rec['seq']],
                          step=self._s(), world_t=self.world_t)
            return
        dec = self.j.append(self.DRV, 'DECISION', {'choice': 'ANSWER_LANG', 'args': {'qid': qid}, 'value': conf,
                                                   'top': []}, refs=[rec['seq']], step=self._s(), world_t=self.world_t)
        self.j.append(self.EVA, 'INTERPRETATION', {'organ': 'LANG', 'learner': self.lang.kind if self.lang else None,
                                                   'qid': qid, 'prediction': pred, 'confidence': conf,
                                                   'trace': json.loads(json.dumps(trace, ensure_ascii=False, default=str))},
                      refs=[rec['seq'], dec['seq']], step=self._s(), world_t=self.world_t)
        self._send(dec, ev.get('channel') or 'user', 'ANSWER', {'qid': qid, 'prediction': pred, 'confidence': conf},
                   refs=[rec['seq']])

    def _in_permission(self, rec, ev):
        c = ev['content']
        d, crec = self._commit('ADMIT_PERMISSION', ev, rec, {'world': c['world'], 'switches': c['switches'],
                                                             'grant': c['grant']})
        if d.disposition == 'COMMIT':
            per = self.permissions.setdefault(c['world'], {})
            for s in c['switches']:
                if c['grant']:
                    per[s] = crec['seq']
                else:
                    per.pop(s, None)

    # ---------------------------------------------------------------- questions and goals -> tasks
    def _in_question(self, rec, ev):
        d, crec = self._commit('RECORD_UTTERANCE', ev, rec, {'speaker': self._speaker(ev), 'question': True})
        self._new_task('ANSWER', {'q': ev['content'], 'asker': self._speaker(ev), 'channel': ev.get('channel')},
                       refs=[rec['seq'], crec['seq']], urgent=True)

    def _in_goal(self, rec, ev):
        d, crec = self._commit('RECORD_UTTERANCE', ev, rec, {'speaker': self._speaker(ev), 'goal': True})
        self._new_task('GOAL', {'goal': ev['content'], 'asker': self._speaker(ev), 'channel': ev.get('channel')},
                       refs=[rec['seq'], crec['seq']], urgent=False)

    def _new_task(self, kind, payload, refs, urgent):
        self.counters['task'] += 1
        tid = f'task:{self.counters["task"]:05d}'
        r = self.j.append(self.DRV, 'TASK', {'task': tid, 'op': 'OPEN', 'kind': kind, 'payload': payload,
                                             'urgent': urgent}, refs=refs, step=self._s(), world_t=self.world_t)
        self.tasks[tid] = {'kind': kind, 'status': 'OPEN', 'payload': payload, 'open_seq': r['seq'], 'urgent': urgent,
                           'opened_t': self.world_t, 'history': [('OPEN', r['seq'])], 'asked': False}
        if self.adopting and refs:
            self._adopt_task[int(list(refs)[0])] = tid
        return tid

    def _task_status(self, tid, status, refs=(), note=None):
        t = self.tasks[tid]
        t['status'] = status
        r = self.j.append(self.DRV, 'TASK', {'task': tid, 'op': status, 'note': note}, refs=[t['open_seq']] + list(refs),
                          step=self._s(), world_t=self.world_t)
        t['history'].append((status, r['seq']))
        return r

    # ================================================================== DRIVE
    def _candidates(self, t) -> List[Tuple[float, str, dict]]:
        out = []
        for tid, task in sorted(self.tasks.items()):
            if task['kind'] == 'ANSWER' and task['status'] == 'OPEN' and task['urgent']:
                out.append((100.0, 'ANSWER', {'task': tid}))
        if self.cfg['reactive'] and not any(c[1] == 'ANSWER' for c in out):
            # B0: thinks only while a message is being answered
            pass
        for tid, task in sorted(self.tasks.items()):
            if task['kind'] == 'GOAL' and task['status'] in ('OPEN', 'EXECUTING'):
                out.append((3.0 * self._mult('GOAL', tid), 'GOAL', {'task': tid}))
        for w, wm in sorted(self.worlds.items()):
            if self.world_meta[w]['static']:
                continue
            per = sorted(self.permissions.get(w, {}).keys())
            lp = self.last_percept.get(w)
            if per and lp and lp['t'] == t:
                bonus = self._task_targets(w)
                acts = wm.eig_actions(lp['percept'], per, bonus)
                if acts:
                    v, act = acts[0]
                    if act:                                     # the best action is a real intervention
                        out.append((v * self._mult('EXPERIMENT', w), 'EXPERIMENT', {'world': w, 'action': act,
                                                                                   'value': v, 'alternatives': len(acts)}))
            for val, n, kind in wm.extension_candidates():
                out.append((val * self._mult('EXTEND', f'{w}/{n}'), 'EXTEND', {'world': w, 'target': n, 'kind': kind}))
        ab = self._abstraction_candidates()
        if ab:
            out.append((0.5 * len(ab) * self._mult('ABSTRACT', 'lib'), 'ABSTRACT', {'n': len(ab)}))
        if self.cfg['learner'] == 'W' and self.worlds:
            # value of consolidation = learning progress: expected reduction of prequential code length (bits) over
            # the next 10 observations of every target, from the running mean of the replay-loss reduction per sleep
            ntg = sum(1 for wm in self.worlds.values() for tm in wm.targets.values() if tm.rows)
            if ntg:
                ema = self.drive.get('sleep_gain_ema', 0.05)
                nrows = sum(len(tm.rows) for wm in self.worlds.values() for tm in wm.targets.values())
                n_new = min(200, nrows - self.drive.get('rows_at_last_sleep', 0))
                g = max(0.0, ema) + 0.0005 * n_new / ntg       # unconsolidated new experience can be gained from
                v = g / math.log(2) * ntg * 10
                out.append((v, 'SLEEP', {'gain_ema_nats': round(ema, 6), 'new_rows': n_new, 'targets': ntg}))
        if self.drive['changes_since_review'] > 0:
            out.append((0.4 * self._mult('REVIEW', 'own'), 'REVIEW', {}))
        for tid, task in sorted(self.tasks.items()):
            if task['kind'] == 'ANSWER' and task['status'] == 'OPEN_UNKNOWN':
                out.append((0.6 * self._mult('RESOLVE', tid), 'RESOLVE', {'task': tid}))
                if not task.get('asked') and self._mult('RESOLVE', tid) <= 0.125 and not self.cfg['reactive']:
                    plan = self._ask_plan(tid, task)
                    if plan:
                        a, b = self.ask_stats.get(plan[0], [0, 0])
                        out.append((0.3 * (b + 1) / (a + 2) * self._mult('ASK', tid), 'ASK',
                                    {'task': tid, 'channel': plan[0], 'request': plan[1]}))
            if task['kind'] == 'CORRECTION' and task['status'] == 'OPEN':
                out.append((1.5, 'CORRECT', {'task': tid}))
        if self.adopting:                     # replaying the past: only internal structural work, nothing outward
            out = [c for c in out if c[1] in ('EXTEND', 'ABSTRACT', 'SLEEP')]
        out.sort(key=lambda z: (-z[0], z[1], _sjson(z[2])))
        return out

    def _mult(self, kind, key) -> float:
        return self.drive['mult'].get(f'{kind}|{key}', 1.0)

    def _decay(self, kind, key, progress: bool):
        k = f'{kind}|{key}'
        if progress:
            self.drive['mult'][k] = 1.0
        else:
            self.drive['mult'][k] = self.drive['mult'].get(k, 1.0) * 0.5

    def _task_targets(self, w):
        out = set()
        for task in self.tasks.values():
            if task['status'] in ('OPEN', 'OPEN_UNKNOWN', 'EXECUTING'):
                q = task['payload'].get('q') or task['payload'].get('goal') or {}
                if q.get('world') == w:
                    for k in ('var', 'effect', 'target'):
                        if q.get(k):
                            out.add(q[k])
        return out

    def _drive_loop(self, t, woken: bool):
        cfg = self.cfg
        if cfg['reactive'] and not woken and not any(x['status'] == 'OPEN' and x['urgent'] for x in self.tasks.values()):
            self.cost['rest_ticks'] += 1
            return
        if self.drive['resting'] and not woken and not cfg['always_busy']:
            urgent = any(x['status'] == 'OPEN' and x['urgent'] for x in self.tasks.values())
            timer = self.drive['rest_since'] is not None and t - self.drive['rest_since'] >= WAKE_TIMER
            if not (urgent or self.drive['pending_surprise'] or timer):
                self.cost['rest_ticks'] += 1
                return
            self.cost['wakes'] += 1
            self.j.append(self.DRV, 'WAKE', {'reason': 'URGENT_TASK' if urgent else ('SURPRISE' if self.drive['pending_surprise'] else 'TIMER')},
                          step=self._s(), world_t=t)
            self.drive['resting'] = False
        self.drive['pending_surprise'] = False
        q = 0
        while q < cfg['budget']:
            cands = self._candidates(t)
            if cfg['reactive'] and not woken:
                cands = [c for c in cands if c[1] == 'ANSWER']   # B0: no thinking without an incoming message
            if not cands or (cands[0][0] < THETA_REST and not cfg['always_busy']):
                if not self.drive['resting']:
                    self.j.append(self.DRV, 'REST', {'reason': 'NO_VALUABLE_WORK' if cands or not self.tasks else 'NOTHING_TO_DO',
                                                     'best': [cands[0][0], cands[0][1]] if cands else None,
                                                     'wake_on': ['INBOUND_MESSAGE', 'SURPRISE', f'TIMER_{WAKE_TIMER}']},
                                  step=self._s(), world_t=t)
                    self.drive['resting'] = True
                    self.drive['rest_since'] = t
                return
            val, kind, args = cands[0]
            dec = self.j.append(self.DRV, 'DECISION', {'choice': kind, 'args': args, 'value': round(val, 6),
                                                       'top': [[round(c[0], 6), c[1]] for c in cands[:5]]},
                                step=self._s(), world_t=t)
            self.cost['quanta'] += 1
            self.cost['quanta_by_kind'][kind] = self.cost['quanta_by_kind'].get(kind, 0) + 1
            t0 = time.process_time()
            getattr(self, '_q_' + kind.lower())(dec, args, t)
            self.cost['eval_seconds'] += time.process_time() - t0
            q += 1

    # ---------------------------------------------------------------- quanta
    def _q_answer(self, dec, args, t):
        tid = args['task']
        task = self.tasks[tid]
        ans = self.answer(task['payload']['q'], dec['seq'], at_t=task['opened_t'])
        self._send(dec, task['payload']['channel'], 'ANSWER', {'task': tid, 'question': task['payload']['q'], **ans})
        st = {'UNKNOWN': 'OPEN_UNKNOWN', 'CERTIFIED_PARTIAL': 'ANSWERED_PARTIAL'}.get(ans['basis'], 'ANSWERED')
        self._task_status(tid, st, refs=[dec['seq']])
        self._decay('ANSWER', tid, True)

    def _q_resolve(self, dec, args, t):
        tid = args['task']
        task = self.tasks[tid]
        ans = self.answer(task['payload']['q'], dec['seq'], quiet=True, at_t=task['opened_t'])
        if ans['basis'] != 'UNKNOWN':
            if self.drive['quiet_reports'] < self.cfg['quiet_report_limit']:
                self.drive['quiet_reports'] += 1
                self.cost['initiative_msgs'] += 1
                self._send(dec, task['payload']['channel'], 'REPORT', {'task': tid, 'question': task['payload']['q'],
                                                                      'unsolicited': True, **ans})
                self._task_status(tid, 'ANSWERED_LATER', refs=[dec['seq']])
                self._decay('RESOLVE', tid, True)
                return
        self._decay('RESOLVE', tid, False)

    def _q_correct(self, dec, args, t):
        tid = args['task']
        task = self.tasks[tid]
        if self.drive['quiet_reports'] < self.cfg['quiet_report_limit'] or task['payload'].get('requested'):
            self.drive['quiet_reports'] += 1
            self.cost['initiative_msgs'] += 1
            self._send(dec, task['payload']['channel'], 'CORRECTION', dict(task['payload']['correction'], unsolicited=True))
            self._task_status(tid, 'DONE', refs=[dec['seq']])
        else:
            self._task_status(tid, 'WAITING_FOR_TURN', refs=[dec['seq']])

    def _ask_plan(self, tid, task):
        """Own effort is exhausted: whom to ask for what (once per task).  Permission for an untested cause goes to
        the person who asked; anything else to the teacher, if a teacher channel exists."""
        q = task['payload'].get('q') or {}
        w = q.get('world')
        if q.get('q') == 'CAUSE' and q.get('cause') not in self.permissions.get(w, {}):
            return task['payload']['channel'], {'request': 'PERMISSION', 'world': w, 'switches': [q['cause']],
                                                'why': 'a causal claim needs my own interventions on the cause'}
        if 'TEACHER' in self.channels and q.get('q') in ('PREDICT', 'MECHANISM', 'CAUSE', 'ENTITY'):
            about = q.get('var') or q.get('effect')
            return self.channels['TEACHER'], {'request': 'LESSON', 'world': w, 'about': about,
                                              'why': 'my hypothesis space did not explain it'}
        return None

    def _q_ask(self, dec, args, t):
        tid = args['task']
        task = self.tasks[tid]
        if self.drive['quiet_reports'] >= self.cfg['quiet_report_limit']:
            self._decay('ASK', tid, False)                    # not now: no pestering
            return
        self.drive['quiet_reports'] += 1
        self.cost['initiative_msgs'] += 1
        task['asked'] = True
        st = self.ask_stats.setdefault(args['channel'], [0, 0])
        st[0] += 1
        self._send(dec, args['channel'], 'ASK', {'task': tid, 'question': task['payload']['q'], **args['request'],
                                                 'unsolicited': True})
        self._task_status(tid, 'OPEN_UNKNOWN', refs=[dec['seq']], note='asked ' + args['channel'])

    def _q_experiment(self, dec, args, t):
        w = args['world']
        lp = self.last_percept[w]
        wm = self.worlds[w]
        # recursive step made explicit: hypothesis -> prediction of the test -> action
        preds = {}
        x = wm.vec(lp['percept'])
        for n in sorted(wm.targets):
            p, _ = wm.targets[n].predictive(x, wm.prev2)
            preds[n] = [round(float(v), 4) for v in p]
        pr = self.j.append(self.EVA, 'PREDICTION', {'world': w, 'action': args['action'], 'expected_information_bits':
                                                   round(args['value'], 5), 'next_device_distribution': preds,
                                                   'note': 'prediction of the test; becomes evidence only via the later verified percept'},
                           refs=[dec['seq'], lp['seq']], step=self._s(), world_t=t)
        per = self.permissions.get(w, {})
        sw = list(args['action'])[0]
        self._send(dec, f'actuator:{w}', 'ACTION', {'world': w, 'action': args['action'], 'effective_t': t + 1,
                                                    'permission_seq': per.get(sw), 'prediction_seq': pr['seq']},
                   refs=[per[sw]] if sw in per else [])
        self._decay('EXPERIMENT', w, args['value'] > 0.05)

    def _q_sleep(self, dec, args, t):
        """Replay consolidation for the weighted learner: a weight change is a COMMIT decision with lineage (the
        journal seqs of the observations and lessons that trained it)."""
        targets = [tm for w in sorted(self.worlds) for n, tm in sorted(self.worlds[w].targets.items())]
        res = WL.sleep(self.slow, targets, seed=dec['seq'])
        ev_obs = res['used_percepts']
        ev_les = [s_ for s_ in res['used_lessons'] if self.lessons.get(s_, {}).get('status') == 'ADMITTED']
        self.j.append(self.COM, 'COMMIT_DECISION', {'decision': decide(operation='ADMIT_BELIEF_STATUS', channel_role='SELF',
                                                                     verified_by=None, origin='').to_dict(),
                                                   'subject': 'WEIGHT_UPDATE', 'evidence': ev_obs, 'lessons': ev_les,
                                                   'loss_before': res['loss_before'], 'loss_after': res['loss_after'],
                                                   'steps': res['steps'], 'slow_updates': self.slow.updates},
                      refs=[dec['seq']] + ev_obs[-64:] + ev_les, step=self._s(), world_t=t)
        self.cost['sleep_quanta'] = self.cost.get('sleep_quanta', 0) + 1
        gain = (res['loss_before'] or 0) - (res['loss_after'] or 0)
        self.drive['sleep_gain_ema'] = 0.8 * self.drive.get('sleep_gain_ema', 0.05) + 0.2 * gain
        self.drive['rows_at_last_sleep'] = sum(len(tm.rows) for wm in self.worlds.values() for tm in wm.targets.values())

    def _q_extend(self, dec, args, t):
        w, n, kind = args['world'], args['target'], args['kind']
        wm = self.worlds[w]
        tm0 = wm.targets[n]
        before = tm0.inadequacy()
        names = wm.names if not wm.static else [m for m in wm.names if m != n]
        pre = tm0.mechanism(names)
        res = wm.extend(n, kind)
        self.j.append(self.EVA, 'HYPOTHESIS', {'world': w, 'target': n, 'extension': kind, 'result': res,
                                               'target_n_obs': tm0.n_obs,
                                               'inadequacy_before': round(before, 5),
                                               'map_before': {'program': pre['program'], 'inputs': pre['inputs'],
                                                              'domains': pre['domains'], 'table': pre['map_table']
                                                              if 'map_table' in pre else pre['table']},
                                               'note': 'internal iteration: new specialist hypotheses; credit only from FUTURE verified observations'},
                      refs=[dec['seq']], step=self._s(), world_t=t)
        self._decay('EXTEND', f'{w}/{n}', res.get('new_hypotheses', 0) > 0)
        self.drive['pending_surprise'] = True

    def _abstraction_candidates(self):
        """Operators that are the CERTIFIED MAP mechanism of at least two different targets (design §3.1: 'an
        operator that became MAP in several targets gets a name'), reduced to their essential inputs and
        canonicalised under input permutation, not yet in the library and not trivially short."""
        if self.cfg['learner'] != 'S' or self.cfg.get('no_library'):
            return []
        have = {(tuple(l.in_domains), l.out_domain, l.table.tobytes()) for l in self.space.library}
        out: Dict[tuple, list] = {}
        for (w, n), cert in sorted(self.cert_state.items()):
            if not cert or w not in self.worlds:
                continue
            tm = self.worlds[w].targets[n]
            m = tm.map_hypothesis()
            if m is None:
                continue
            fam, o, e = m
            if fam.private is not None:
                continue                                     # taught tables are the teacher's, not abstractions
            sig = self.space.sigs[fam.sig_key]
            op = int(fam.ops[o])
            dep = sig.op_depends[op]
            ins = [i for i in range(len(sig.in_domains)) if dep[i]]
            if len(ins) < 2 or sig.op_size[op] < 5:
                continue
            reduced, red_doms = _reduce_table(sig, op, ins)
            perm, ctab = _canon(reduced, red_doms)
            key = (tuple(red_doms[i] for i in perm), sig.out_domain, ctab.tobytes())
            if key in have:
                continue
            out.setdefault(key, []).append((w, n, op, sig.op_size[op], fam.sig_key, tuple(perm)))
        good = [(k, v) for k, v in out.items() if len({(u[0], u[1]) for u in v}) >= 2]
        return sorted(good, key=lambda kv: (-len(kv[1]), str(kv[0][0]), kv[0][2]))

    def _q_abstract(self, dec, args, t):
        cands = self._abstraction_candidates()
        if not cands:
            self._decay('ABSTRACT', 'lib', False)
            return
        (in_doms, out_dom, tbytes), users = cands[0]
        w, n, op, size, sig_key, perm = users[0]
        sig = self.space.sigs[sig_key]
        table = np.frombuffer(tbytes, dtype=np.int8).copy()
        prog = _permute_program(_reduced_program(sig, op), perm)
        evidence = []
        for u in users:
            evidence += self._witness(u[0], u[1])[-6:]
        prop = self.j.append(self.EVA, 'PROPOSAL', {'library_operator': {'in_domains': list(in_doms), 'out_domain': out_dom,
                                                                        'table': table.tolist(), 'program': prog_str(prog)},
                                                   'from_certified_mechanisms': [[u[0], u[1]] for u in users]},
                             refs=[dec['seq']], step=self._s(), world_t=t)
        c = self.j.append(self.COM, 'COMMIT_DECISION', {'decision': decide(operation='ADMIT_BELIEF_STATUS', channel_role='SELF',
                                                                         verified_by=None, origin='').to_dict(),
                                                       'subject': 'LIBRARY_OPERATOR', 'proposal': prop['seq'], 'evidence': evidence,
                                                       'scope': 'priors of worlds born AFTER this decision only (no double counting)'},
                          refs=[prop['seq']] + evidence, step=self._s(), world_t=t)
        self.space.add_library_op(in_doms, out_dom, table, prog, {'commit_seq': c['seq'],
                                                                   'from': [[u[0], u[1]] for u in users]})
        self.cost['library_ops'] = self.cost.get('library_ops', 0) + 1
        self._decay('ABSTRACT', 'lib', True)

    def _q_review(self, dec, args, t):
        """Return to own past statements: does anything we asserted contradict what we now know?  Also settle
        the sources' mechanism claims that our certified knowledge can now decide."""
        for (w_, n_) in sorted({(c['claim'].get('world'), c['claim'].get('var')) for c in self.mech_claims
                                if not c['checked']}):
            if self.cert_state.get((w_, n_)):
                self._check_mech_claims(w_, n_)
        found = 0
        for r in list(self.persp.said):
            if not r['own'] or r.get('reviewed_against') == self.drive['changes_since_review']:
                continue
            ans = r.get('answer')
            if not ans or ans.get('basis') in ('UNKNOWN', 'ATTRIBUTED', 'OBSERVED'):
                continue
            q = ans.get('question')
            if not q or q.get('q') not in ('PREDICT', 'MECHANISM', 'CAUSE', 'ENTITY'):
                continue
            if q.get('q') == 'PREDICT':
                continue                                     # predictions are checked when their time comes
            # a statement belongs to the regime it was made in: if the world showed a sign of change after it
            # (memory contradicted / certificate failed), today's model is not a model of THAT time — no correction
            scope_t = q.get('var') if q.get('q') in ('MECHANISM', 'ENTITY') else None
            if any(ev_[0] == q.get('world') and (scope_t is None or ev_[1] == scope_t) and ev_[2] > r['t_said']
                   for ev_ in self.regime_events):
                r['reviewed_against'] = self.drive['changes_since_review']
                continue
            now = self.answer(q, dec['seq'], quiet=True, record=False, at_t=ans.get('asked_t'))
            if now['basis'] != 'UNKNOWN' and _conflict(q, ans, now):
                found += 1
                con = self.j.append(self.EVA, 'CONTRADICTION', {'own_statement_seq': r['seq'], 'was': ans.get('answer'),
                                                               'now': now.get('answer'), 'question': q},
                                    refs=[dec['seq'], r['seq']], step=self._s(), world_t=t)
                tid = self._new_task('CORRECTION', {'channel': ans.get('channel', 'user'),
                                                    'correction': {'question': q, 'previously_said': ans.get('answer'),
                                                                   'now': now.get('answer'), 'basis': now['basis'],
                                                                   'contradiction_seq': con['seq']}},
                                     refs=[con['seq']], urgent=False)
            r['reviewed_against'] = self.drive['changes_since_review']
        self.drive['changes_since_review'] = 0
        self._decay('REVIEW', 'own', found > 0)

    def _q_goal(self, dec, args, t):
        tid = args['task']
        task = self.tasks[tid]
        g = task['payload']['goal']
        w = g['world']
        wm = self.worlds.get(w)
        lp = self.last_percept.get(w)
        if wm is None or lp is None:
            self._decay('GOAL', tid, False)
            return
        if lp['percept'].get(g['var']) == g['value']:
            self._task_status(tid, 'ACHIEVED_VERIFIED', refs=[dec['seq'], lp['seq']])
            self._send(dec, task['payload']['channel'], 'REPORT', {'task': tid, 'goal': g, 'status': 'ACHIEVED',
                                                                   'verified_by_percept': lp['seq']})
            return
        plan = self.plan(w, lp['percept'], g['var'], g['value'], sorted(self.permissions.get(w, {})))
        self.j.append(self.EVA, 'PLAN', {'task': tid, 'plan': plan}, refs=[dec['seq'], lp['seq']], step=self._s(), world_t=t)
        if plan.get('actions'):
            act = plan['actions'][0]
            per = self.permissions.get(w, {})
            sw = list(act)[0]
            self._send(dec, f'actuator:{w}', 'ACTION', {'world': w, 'action': act, 'effective_t': t + 1,
                                                        'permission_seq': per.get(sw), 'for_task': tid},
                       refs=[per[sw]] if sw in per else [])
            if task['status'] != 'EXECUTING':
                self._task_status(tid, 'EXECUTING', refs=[dec['seq']])
            self._decay('GOAL', tid, True)
        elif plan.get('waiting'):
            self._decay('GOAL', tid, True)
        else:
            self._decay('GOAL', tid, False)

    def _send(self, dec, channel, kind, content, refs=()):
        if kind == 'ACTION':
            w = content['world']
            sw = list(content['action'])[0] if content['action'] else None
            if sw is not None and sw not in self.permissions.get(w, {}):
                raise PermissionError(f'MEDIATE: no committed permission for {w}/{sw}')   # desire != permission
        rec = self.j.append(self.MED, 'OUTBOUND', {'channel': channel, 'kind': kind, 'content': content,
                                                   'decision': dec['seq']}, refs=[dec['seq']] + list(refs),
                            step=self._s(), world_t=self.world_t)
        replayed = self.j.last_verified
        self.cost['outbound'] += 1
        if kind in ('ANSWER', 'REPORT', 'CORRECTION'):
            claim = {'op': 'ANSWER', 'content': content}
            r = self.persp.add(speaker=SELF, content=claim, t_said=self.world_t, narrated=None, seq=rec['seq'],
                               channel_role='SELF', own=True)
            r['answer'] = dict(content, channel=channel)
        self.outbox.append({'seq': rec['seq'], 'hash': rec['hash'], 'channel': channel, 'kind': kind,
                            'content': content, 'replayed': replayed})
        return rec

    # ================================================================== EVAL: answers and plans
    def answer(self, q: dict, dec_seq: int, quiet: bool = False, record: bool = True, at_t: Optional[int] = None) -> dict:
        """at_t: the world tick the question was asked at — predictions and causal questions are about the state
        THEN (a later report answers the question that was asked, not a new one)."""
        kind = q.get('q')
        fn = getattr(self, '_a_' + kind.lower(), None)
        self._q_at = at_t
        out = fn(q) if fn else {'answer': None, 'basis': 'UNKNOWN', 'why': 'UNSUPPORTED_QUESTION'}
        self._q_at = None
        if at_t is not None:
            out['asked_t'] = at_t
        if record:
            body = {'question': q, 'result': out}
            if out['basis'] == 'UNKNOWN' and kind == 'PREDICT':
                body['best_guess_not_asserted'] = self._best_guess(q, at_t)
            self.j.append(self.EVA, 'RECALL' if out['basis'] in ('OBSERVED', 'ATTRIBUTED', 'OWN_RECORD') else 'EXPLANATION',
                          body, refs=[dec_seq] + [s for s in out.get('evidence', [])
                                                                             if isinstance(s, int) and s < len(self.j)],
                          step=self._s(), world_t=self.world_t)
        return out

    def _a_state_now(self, q):
        lp = self.last_percept.get(q['world'])
        if not lp:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NOT_OBSERVED'}
        return {'answer': lp['percept'].get(q['var']), 'basis': 'OBSERVED', 'at_t': lp['t'], 'evidence': [lp['seq']]}

    def _a_past_state(self, q):
        w, v, T = q['world'], q['var'], int(q['t'])
        seq = self.percept_log.get(w, {}).get(T)
        if seq is not None:
            return {'answer': self.j.get(seq)['payload']['event']['content']['percept'].get(v), 'basis': 'OBSERVED',
                    'at_t': T, 'evidence': [seq]}
        claims = []
        for r in self.persp.said:
            base, pol = effective(r['content'])
            if r['own'] or base.get('op') != 'STATE' or base.get('world') != w or base.get('var') != v:
                continue
            n = r['narrated']
            if n == T or (isinstance(n, list) and n[0] <= T <= n[1]):
                claims.append({'speaker': r['speaker'], 'said_t': r['t_said'], 'value': base['value'], 'polarity': pol,
                               'narrated': n, 'reliability': round(self.rel.mean(r['speaker']), 3)})
        if claims:
            return {'answer': None, 'basis': 'ATTRIBUTED', 'claims': claims, 'evidence': []}
        return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NEITHER_OBSERVED_NOR_REPORTED'}

    def _best_guess(self, q, at_t):
        """The model's most probable value (argmax of every predictive, certification ignored) — kept in the
        journal as an internal, NON-asserted hypothesis so that a later revision can be audited."""
        w = q.get('world')
        wm = self.worlds.get(w)
        self._q_at = at_t
        lp = self._percept_at(w)
        self._q_at = None
        if wm is None or lp is None:
            return None
        x = wm.vec(lp['percept'])
        xp = None
        held = {sname: x[wm.idx[sname]] for sname in wm.switches}
        held.update({k: int(v) for k, v in (q.get('do') or {}).items()})
        for _ in range(int(q.get('k', 1))):
            nx = list(x)
            for sname, v in held.items():
                nx[wm.idx[sname]] = v
            for n, tm in wm.targets.items():
                p, _ = tm.predictive(x, xp if getattr(tm, 'lag_enabled', False) else None)
                nx[wm.idx[n]] = int(np.argmax(p))
            xp, x = x, nx
        return x[wm.idx[q['var']]]

    def _percept_at(self, w):
        """The verified percept the question refers to: the one at the question's tick if we have it."""
        at = getattr(self, '_q_at', None)
        if at is not None:
            seq = self.percept_log.get(w, {}).get(at)
            if seq is not None:
                return {'t': at, 'seq': seq, 'percept': self.j.get(seq)['payload']['event']['content']['percept']}
        return self.last_percept.get(w)

    def _a_predict(self, q):
        w = q['world']
        wm = self.worlds.get(w)
        lp = self._percept_at(w)
        if wm is None or lp is None:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_MODEL'}
        traj, bases = wm.simulate(lp['percept'], int(q['k']), q.get('do') or None)
        v = traj[-1].get(q['var'])
        if v is None:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NOT_CERTIFIED', 'kind': 'PREDICTION', 'evidence': [lp['seq']]}
        return {'answer': v, 'basis': 'CERTIFIED', 'kind': 'PREDICTION', 'from_t': lp['t'], 'k': q['k'],
                'evidence': [lp['seq']] + self._cert_evidence(w)}

    def _a_cause(self, q):
        w = q['world']
        wm = self.worlds.get(w)
        lp = self._percept_at(w)
        if wm is None or lp is None:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_MODEL'}
        verdict, info = wm.causal(q['cause'], q['effect'], int(q.get('k', 3)), lp['percept'])
        if verdict is None:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NOT_INTERVENTIONALLY_CERTIFIED', 'info': info}
        return {'answer': verdict, 'basis': 'CERTIFIED', 'kind': 'CAUSAL', 'info': info, 'evidence': self._cert_evidence(w)}

    def _a_mechanism(self, q):
        w = q['world']
        wm = self.worlds.get(w)
        if wm is None or q['var'] not in wm.targets:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_MODEL'}
        tm = wm.targets[q['var']]
        names = wm.names if not wm.static else [m for m in wm.names if m != q['var']]
        if not tm.certified():
            d = tm.map_description(names)
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'HYPOTHESIS_NOT_CERTIFIED', 'hypothesis': d.get('map'),
                    'evidence': []}
        mech = tm.mechanism(names)
        if not any(v is not None for v in mech['table']):
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_OBSERVED_CASES_SINCE_CHANGE', 'hypothesis': mech['program'],
                    'evidence': []}
        basis = 'CERTIFIED' if mech['complete'] else 'CERTIFIED_PARTIAL'
        return {'answer': mech['program'], 'basis': basis,
                'mechanism': {'inputs': mech['inputs'], 'domains': mech['domains'], 'table': mech['table'],
                              'support': mech['support'],
                              'family_origin': mech['family_origin'], 'function_mass': (round(mech['function_mass'], 4) if mech.get('function_mass') is not None else None),
                              'unvisited_entries_unknown': not mech['complete']},
                'evidence': self._witness(w, q['var'])[-6:]}

    def _a_entity(self, q):
        w = q['world']
        wm = self.worlds.get(w)
        if wm is None:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_MODEL'}
        v, basis, p = wm.assert_static(q['var'], q['features'])
        if v is None:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NOT_CERTIFIED'}
        return {'answer': v, 'basis': basis, 'evidence': self._witness(w, q['var'])[-6:]}

    def _a_said(self, q):
        key = _key_of(q['about'])
        rows = self.persp.said_about(q['speaker'], key, narrated_t=q.get('narrated_t'))
        if not rows:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NOTHING_SAID', 'evidence': []}
        r = rows[-1]
        base, pol = effective(r['content'])
        ans = {'claim': r['content'], 'effective_value': base.get('value'), 'effective_polarity': pol,
               'said_t': r['t_said'], 'narrated': r['narrated']}
        if q.get('narrated_t') is not None:
            ans['exact_time'] = ('SAID_ABOUT_THIS_TICK' if r['narrated'] == q['narrated_t']
                                 else 'UNKNOWN: said about an interval that contains it')
        return {'answer': ans, 'basis': 'ATTRIBUTED', 'evidence': [r['seq']]}

    def _a_thinks_now(self, q):
        key = _key_of(q['about'])
        rows = self.persp.stances(q['speaker'], key)
        cur = [x for x in rows if q.get('at_t') is None or x['t_said'] <= q['at_t']]
        if not cur:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_STANCE_RECORDED', 'evidence': []}
        r = cur[-1]
        base, pol = self.persp.stance_content(r, q['speaker'])
        hist = []
        for x in rows:
            b2, p2 = self.persp.stance_content(x, q['speaker'])
            hist.append({'t': x['t_said'], 'value': b2.get('value'), 'polarity': p2})
        return {'answer': {'value': base.get('value'), 'polarity': pol, 'as_of': r['t_said'], 'history': hist},
                'basis': 'ATTRIBUTED', 'evidence': [r['seq']]}

    def _a_own_said(self, q):
        rows = []
        for r in self.persp.own_statements():
            a = r.get('answer') or {}
            qq = a.get('question') or {}
            if all(qq.get(k) == v for k, v in q['about'].items()):
                rows.append({'seq': r['seq'], 't': r['t_said'], 'answer': a.get('answer'), 'basis': a.get('basis')})
        if not rows:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'I_SAID_NOTHING_ABOUT_IT', 'evidence': []}
        return {'answer': rows, 'basis': 'OWN_RECORD', 'evidence': [x['seq'] for x in rows]}

    def _a_quote(self, q):
        rows = [r for r in self.persp.quotes_of(q['quoted']) if r['speaker'] == q['speaker']]
        if not rows:
            return {'answer': None, 'basis': 'UNKNOWN', 'why': 'NO_SUCH_QUOTE', 'evidence': []}
        r = rows[-1]
        own = self._a_own_said({'about': q.get('about', {})}) if q['quoted'] == SELF else None
        return {'answer': {'quote': r['content'], 'by': r['speaker'], 't_said': r['t_said'],
                           'what_I_actually_said': own['answer'] if own else None}, 'basis': 'ATTRIBUTED',
                'evidence': [r['seq']]}

    def _a_source_reliability(self, q):
        return {'answer': round(self.rel.mean(q['speaker']), 3), 'basis': 'OWN_RECORD',
                'counts': self.rel.counts.get(q['speaker'], [0, 0]), 'evidence': []}

    def _cert_evidence(self, w):
        out = []
        for (ww, n), cert in sorted(self.cert_state.items()):
            if ww == w and cert:
                out += self._witness(w, n)[-3:]
        return out

    def _witness(self, w, n) -> List[int]:
        """CL-R5 G0.1: the evidence of a certificate = the admitted observations on which the learner's own current
        streak grew (owned by the learner, rebuilt with it)."""
        wm = self.worlds.get(w)
        tm = wm.targets.get(n) if wm is not None else None
        return [int(s) for s in getattr(tm, 'witness', [])] if tm is not None else []

    def _admit_mech(self, key, certified: bool, desc: dict):
        if certified:
            self.cert_mech[key] = desc.get('map')
        else:
            self.cert_mech.pop(key, None)

    def _reconcile_status(self, cause_seq: int, t=None):
        """CL-R5 G0.1: after ANY rebuild of learner state (retraction), the admitted belief status must equal the
        learners' status; every difference is decided again by COMMIT, citing the rebuild's cause and (for a
        certificate) the witnesses of the replayed streak."""
        for w in sorted(self.worlds):
            wm = self.worlds[w]
            for n in sorted(wm.targets):
                key = (w, n)
                was, now = self.cert_state.get(key, False), bool(wm.targets[n].certified())
                names = wm.names if not self.world_meta[w]['static'] else [m for m in wm.names if m != n]
                desc = wm.targets[n].map_description(names)
                # a certificate that survives the rebuild but now rests on ANOTHER mechanism (e.g. the retracted
                # lesson's hypothesis replaced by the learner's own) is a different belief: decided again as well
                moved = now and was and self.cert_mech.get(key) != desc.get('map')
                if now == was and not moved:
                    continue
                self.cert_state[key] = now
                self._admit_mech(key, now, desc)
                self._renew_resolution(w)
                # a certificate cites the replayed streak; a withdrawn certificate needs no observation at all (the
                # rebuild itself, i.e. the retraction decision, is its cause and is cited as such, never as evidence)
                ev_refs = self._witness(w, n)[-12:] if now else []
                self.j.append(self.COM, 'COMMIT_DECISION',
                              {'decision': decide(operation='ADMIT_BELIEF_STATUS', channel_role='SELF', verified_by=None,
                                                  origin='').to_dict(),
                               'subject': 'BELIEF_STATUS', 'world': w, 'target': n,
                               'status': 'CERTIFIED' if now else 'REFUTED', 'reason': 'REBUILD', 'cause_seq': cause_seq,
                               'mechanism_changed': bool(moved),
                               'mechanism': desc.get('map'), 'family_origin': desc.get('family_origin'),
                               'evidence': ev_refs},
                              refs=sorted(set([cause_seq] + ev_refs)), step=self._s(),
                              world_t=self.world_t if t is None else t)
                if now:
                    self._check_mech_claims(w, n)

    def plan(self, w, percept, var, value, permitted, depth=6) -> dict:
        """Breadth-first search over interventions with the CERTIFIED model (SIMULATION, never evidence)."""
        wm = self.worlds[w]
        if not permitted:
            return {'actions': [], 'why': 'NO_PERMISSION'}
        start = dict(percept)
        frontier = [(start, [])]
        seen = {_sjson(start)}
        for d in range(depth):
            nxt = []
            for st, acts in frontier:
                for s in permitted:
                    for v in range(wm.domains[wm.idx[s]]):
                        for do in ([{s: v}] if st[s] != v else [{}]):
                            traj, bases = wm.simulate(st, 1, do or None)
                            ns = traj[0]
                            if any(x is None for k2, x in ns.items() if k2 in wm.targets and k2 == var):
                                continue
                            if ns.get(var) == value:
                                return {'actions': (acts + [do]) if do else acts + [{}], 'depth': d + 1}
                            if any(x is None for x in ns.values()):
                                continue
                            key = _sjson(ns)
                            if key not in seen:
                                seen.add(key)
                                nxt.append((ns, acts + [do]))
            frontier = nxt[:200]
            if not frontier:
                break
        return {'actions': [], 'why': 'NO_CERTIFIED_PLAN', 'waiting': False}

    # ================================================================== CL-R5 G0.4: the CODE_UPGRADE boundary
    def code_upgrade_record(self, subject: str, payload: dict, refs=()):
        """COMMIT of the migration itself (genesis CODE_UPGRADE_BEGIN, closing CODE_UPGRADE); lawful only as
        SYSTEM_MIGRATION after the adoption procedure verified the parent (c4life/adopt.py)."""
        d = decide(operation='ADOPT_LIFE', channel_role='SELF', verified_by='MIGRATION', origin='')
        return self.j.append(self.COM, 'COMMIT_DECISION', dict({'decision': d.to_dict(), 'subject': subject}, **payload),
                             refs=list(refs), step=self._s(), world_t=self.world_t)

    # ================================================================== persistence
    def state_dict(self) -> dict:
        return {'schema': SCHEMA, 'cfg': self.cfg, 'journal_len': len(self.j), 'journal_head': self.j.head(),
                'step': self.step, 'world_t': self.world_t,
                'space': self.space.to_dict(),
                'worlds': {w: wm.to_dict() for w, wm in sorted(self.worlds.items())}, 'world_meta': self.world_meta,
                'persp': self.persp.to_dict(), 'rel': self.rel.to_dict(), 'tasks': self.tasks,
                'permissions': self.permissions, 'lessons': {str(k): v for k, v in self.lessons.items()},
                'interv': {w: {str(k): v for k, v in d.items()} for w, d in self.interv.items()},
                'last_percept': self.last_percept,
                'percept_log': {w: {str(k): v for k, v in d.items()} for w, d in self.percept_log.items()},
                'cert_state': [[w, n, v] for (w, n), v in sorted(self.cert_state.items())],
                'cert_mech': [[w, n, m] for (w, n), m in sorted(self.cert_mech.items())],
                'drive': self.drive, 'cost': self.cost, 'counters': self.counters, 'channels': self.channels,
                'ask_stats': self.ask_stats, 'mech_claims': self.mech_claims, 'regime_events': self.regime_events,
                'slow': self.slow.to_dict() if self.slow is not None else None, 'lineage': self.lineage,
                **({'lang': self.lang.to_dict()} if self.lang is not None else {}),
                **({'external_clock': self.external_clock.to_dict()} if self.external_clock is not None else {}),
                **({'frame_organ': self.frame_organ.to_dict()} if self.frame_organ is not None else {}),
                **({'frame_sim_receipts': self.frame_sim_receipts} if self.frame_sim_receipts else {}),
                **({'frame_teacher_lessons': self.frame_teacher_lessons} if self.frame_teacher_lessons else {}),
                **({'discourse_organ': self.discourse_organ.to_dict()} if self.discourse_organ is not None else {}),
                **({'discourse_teacher_lessons': self.discourse_teacher_lessons} if self.discourse_teacher_lessons else {}),
                **({'weak_discourse_organ': self.weak_discourse_organ.to_dict()} if self.weak_discourse_organ is not None else {}),
                **({'weak_discourse_lessons': self.weak_discourse_lessons} if self.weak_discourse_lessons else {}),
                **({'grounding_organ': self.grounding_organ.to_dict()} if self.grounding_organ is not None else {}),
                **({'grounding_sim_receipts': self.grounding_sim_receipts} if self.grounding_sim_receipts else {}),
                **({'grounding_teacher_lessons': self.grounding_teacher_lessons} if self.grounding_teacher_lessons else {}),
                **({'event_trace_organ': self.event_trace_organ.to_dict()} if self.event_trace_organ is not None else {}),
                **({'event_trace_sim_receipts': self.event_trace_sim_receipts} if self.event_trace_sim_receipts else {}),
                **({'event_trace_surface_vocab': self.event_trace_surface_vocab} if self.event_trace_surface_vocab else {}),
                **({'event_trace_teacher_lessons': self.event_trace_teacher_lessons} if self.event_trace_teacher_lessons else {}),
                **({'relational_organ': self.relational_organ.to_dict()} if self.relational_organ else {}),
                **({'relational_sim_receipts':self.relational_sim_receipts} if self.relational_sim_receipts else {}),
                **({'relational_teacher_lessons':self.relational_teacher_lessons} if self.relational_teacher_lessons else {}),
                **({'temporal_organ':self.temporal_organ.to_dict()} if self.temporal_organ else {}),
                **({'temporal_sim_receipts':self.temporal_sim_receipts} if self.temporal_sim_receipts else {}),
                **({'temporal_teacher_lessons':self.temporal_teacher_lessons} if self.temporal_teacher_lessons else {}),
                **({'metric_organ':self.metric_organ.to_dict()} if self.metric_organ else {}),
                **({'metric_sim_receipts':self.metric_sim_receipts} if self.metric_sim_receipts else {}),
                **({'metric_teacher_lessons':self.metric_teacher_lessons} if self.metric_teacher_lessons else {}),
                **({'joint_organ':self.joint_organ.to_dict()} if self.joint_organ else {}),
                **({'joint_sim_receipts':self.joint_sim_receipts} if self.joint_sim_receipts else {}),
                **({'joint_teacher_lessons':self.joint_teacher_lessons} if self.joint_teacher_lessons else {}),
                **({'story_mind':self.story_mind.to_dict()} if self.story_mind else {}),
                **({'story_questions':self.story_questions.to_dict()} if self.story_questions else {}),
                **({'story_sim_receipts':self.story_sim_receipts} if self.story_sim_receipts else {}),
                **({'story_teacher_lessons':self.story_teacher_lessons} if self.story_teacher_lessons else {}),
                **({'text_story_learner':self.text_story_learner.to_dict()} if self.text_story_learner else {}),
                **({'text_story_teacher_lessons':self.text_story_teacher_lessons} if self.text_story_teacher_lessons else {}),
                **({'text_story_narratives':self.text_story_narratives} if self.text_story_narratives else {}),
                **({'morph_story_learner':self.morph_story_learner.to_dict()} if self.morph_story_learner else {}),
                **({'morph_story_teacher_lessons':self.morph_story_teacher_lessons} if self.morph_story_teacher_lessons else {}),
                **({'morph_story_narratives':self.morph_story_narratives} if self.morph_story_narratives else {}),
                **({'interaction_identity':self.interaction_identity.to_dict()} if self.interaction_identity is not None else {}),
                **({'dialogue_teacher_lessons':self.dialogue_teacher_lessons} if self.dialogue_teacher_lessons else {})}

    def state_hash(self) -> str:
        d = self.state_dict()
        d.pop('cost', None)
        return hashlib.sha256(_sjson(d).encode()).hexdigest()

    def snapshot(self, path: Optional[str] = None) -> str:
        path = path or os.path.join(self.home, 'snapshot.json')
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf8') as f:
            f.write(_sjson(self.state_dict()))
        os.replace(tmp, path)
        return path

    @classmethod
    def resume(cls, home: str) -> 'Life':
        snap = os.path.join(home, 'snapshot.json')
        with open(snap, encoding='utf8') as f:
            d = json.load(f)
        self = cls.__new__(cls)
        self.home = home
        self.cfg = d['cfg']
        self.j = Journal(os.path.join(home, 'journal.jsonl'))
        self.MED, self.EVA, self.COM, self.DRV = (self.j.cap(o) for o in ('MEDIATE', 'EVAL', 'COMMIT', 'DRIVE'))
        self.outbox = []
        self._reset_state()
        self.load_state(d)
        self.j.resume_at(d['journal_len'])
        return self

    def load_state(self, d):
        self.step, self.world_t = d['step'], d['world_t']
        self.space = OperatorSpace.from_dict(d['space'])
        self.world_meta = d['world_meta']
        self.worlds = {}
        self.slow = WL.SlowModules.from_dict(d['slow']) if d.get('slow') else None
        for w, wd in d['worlds'].items():
            if wd.get('kind') == 'S':
                self.worlds[w] = WorldModelS.from_dict(wd, self.space)
            else:
                self.worlds[w] = WL.WorldModelW.from_dict(wd, self.slow)
        self.persp = Perspective.from_dict(d['persp'])
        self.rel = SourceReliability.from_dict(d['rel'])
        self.tasks = d['tasks']
        for t in self.tasks.values():
            t['history'] = [tuple(x) for x in t['history']]
        self.permissions = d['permissions']
        self.lessons = {int(k): v for k, v in d['lessons'].items()}
        self.interv = {w: {int(k): v for k, v in dd.items()} for w, dd in d['interv'].items()}
        self.last_percept = d['last_percept']
        self.percept_log = {w: {int(k): v for k, v in dd.items()} for w, dd in d['percept_log'].items()}
        self.cert_state = {(w, n): v for w, n, v in d['cert_state']}
        self.cert_mech = {(w, n): m for w, n, m in d.get('cert_mech', [])}
        self.lang = LANG.learner_from_dict(d['lang']) if d.get('lang') else None
        self.external_clock = ClockMap.from_dict(d['external_clock']) if d.get('external_clock') else None
        self.frame_organ = GroundedFrameInducer.from_dict(d['frame_organ']) if d.get('frame_organ') else None
        self.frame_sim_receipts = d.get('frame_sim_receipts',{})
        self.frame_teacher_lessons=d.get('frame_teacher_lessons',{})
        self.discourse_organ=DiscourseInducer.from_dict(d['discourse_organ']) if d.get('discourse_organ') else None
        self.discourse_teacher_lessons=d.get('discourse_teacher_lessons',{})
        self.weak_discourse_organ=WeakBoundaryInducer.from_dict(d['weak_discourse_organ']) if d.get('weak_discourse_organ') else None
        self.weak_discourse_lessons=d.get('weak_discourse_lessons',{})
        self.grounding_organ=SituatedLexicon.from_dict(d['grounding_organ']) if d.get('grounding_organ') else None
        self.grounding_sim_receipts=d.get('grounding_sim_receipts',{})
        self.grounding_teacher_lessons=d.get('grounding_teacher_lessons',{})
        self.event_trace_organ=EventMeaningInducer.from_dict(d['event_trace_organ']) if d.get('event_trace_organ') else None
        self.event_trace_sim_receipts=d.get('event_trace_sim_receipts',{})
        self.event_trace_surface_vocab=d.get('event_trace_surface_vocab',[])
        self.event_trace_teacher_lessons=d.get('event_trace_teacher_lessons',{})
        self.relational_organ=RelationalInducer.from_dict(d['relational_organ']) if d.get('relational_organ') else None
        self.relational_sim_receipts=d.get('relational_sim_receipts',{})
        self.relational_teacher_lessons=d.get('relational_teacher_lessons',{})
        self.temporal_organ=TemporalInducer.from_dict(d['temporal_organ']) if d.get('temporal_organ') else None
        self.temporal_sim_receipts=d.get('temporal_sim_receipts',{})
        self.temporal_teacher_lessons=d.get('temporal_teacher_lessons',{})
        self.metric_organ=MetricInducer.from_dict(d['metric_organ']) if d.get('metric_organ') else None
        self.metric_sim_receipts=d.get('metric_sim_receipts',{})
        self.metric_teacher_lessons=d.get('metric_teacher_lessons',{})
        self.joint_organ=JointUtteranceInducer.from_dict(d['joint_organ']) if d.get('joint_organ') else None
        self.joint_sim_receipts=d.get('joint_sim_receipts',{})
        self.joint_teacher_lessons=d.get('joint_teacher_lessons',{})
        self.story_mind=StoryMind.from_dict(d['story_mind']) if d.get('story_mind') else None
        self.story_questions=MeaningQuestionLearner.from_dict(d['story_questions']) if d.get('story_questions') else None
        self.story_sim_receipts=d.get('story_sim_receipts',{})
        self.story_teacher_lessons=d.get('story_teacher_lessons',{})
        self.text_story_learner=PatternInducer.from_dict(d['text_story_learner']) if d.get('text_story_learner') else None
        self.text_story_teacher_lessons=d.get('text_story_teacher_lessons',{})
        self.text_story_narratives=d.get('text_story_narratives',{})
        self.morph_story_learner=MorphStory.from_dict(d['morph_story_learner']) if d.get('morph_story_learner') else None
        self.morph_story_teacher_lessons=d.get('morph_story_teacher_lessons',{})
        self.morph_story_narratives=d.get('morph_story_narratives',{})
        self.interaction_identity=InteractionIdentity.from_dict(d['interaction_identity']) if d.get('interaction_identity') else None
        self.dialogue_teacher_lessons=d.get('dialogue_teacher_lessons',{})
        self.drive, self.cost, self.counters = d['drive'], d['cost'], d['counters']
        self.channels, self.ask_stats = d.get('channels', {}), d.get('ask_stats', {})
        self.mech_claims = d.get('mech_claims', [])
        self.regime_events = d.get('regime_events', [])
        self.lineage = d.get('lineage')

    def close(self):
        self.j.close()


# ---------------------------------------------------------------------- helpers
def prog_size_names(prog) -> int:
    if not isinstance(prog, (list, tuple)) or not prog:
        return 1
    if prog[0] in ('V', 'C', 'SELF'):
        return 1
    return 1 + sum(prog_size_names(a) for a in prog[1:])


def _rename_self(prog, tgt):
    if isinstance(prog, (list, tuple)):
        if len(prog) and prog[0] == 'SELF':
            return ('V', '__SELF__')
        return tuple(_rename_self(p, tgt) for p in prog)
    return prog


def _mech_eval(mech, assign):
    """Value a reported mechanism asserts for a full assignment {input name: value}, or None."""
    if not mech or 'table' not in mech:
        return None
    idx = 0
    doms = mech.get('domains') or [2] * len(mech['inputs'])
    for nme, d in zip(mech['inputs'], doms):
        if nme not in assign:
            return None
        idx = idx * d + int(assign[nme])
    v = mech['table'][idx] if idx < len(mech['table']) else None
    return v


def _conflict(q, old, new) -> bool:
    """Does a new assertion contradict an old one?  For mechanisms: some full assignment of the union of their
    inputs gets two different ASSERTED values (unknown entries never conflict)."""
    import itertools
    if q.get('q') != 'MECHANISM':
        return new.get('answer') != old.get('answer')
    a, b = old.get('mechanism') or {}, new.get('mechanism') or {}
    names = sorted(set(a.get('inputs', [])) | set(b.get('inputs', [])))
    if len(names) > 12:
        return new.get('answer') != old.get('answer')
    for combo in itertools.product([0, 1], repeat=len(names)):
        asg = dict(zip(names, combo))
        va, vb = _mech_eval(a, asg), _mech_eval(b, asg)
        if va is not None and vb is not None and va != vb:
            return True
    return False


def _tuplify(x):
    if isinstance(x, list):
        return tuple(_tuplify(v) for v in x)
    return x


def _key_of(about: dict) -> tuple:
    op = about.get('op', 'STATE')
    if op == 'STATE':
        return ('STATE', about.get('world'), about.get('var'))
    if op == 'CAUSES':
        return ('CAUSES', about.get('world'), about.get('cause'), about.get('effect'))
    if op == 'MECH':
        return ('MECH', about.get('world'), about.get('var'))
    return (op,)


def _reduce_table(sig, op, ins):
    """Restrict an operator table to its essential inputs (others fixed at 0: irrelevant by construction)."""
    from .operators import configs
    doms = [sig.in_domains[i] for i in ins]
    st = strides(sig.in_domains)
    rows = []
    for c in configs(tuple(doms)):
        full = np.zeros(len(sig.in_domains), dtype=np.int64)
        for j, i in enumerate(ins):
            full[i] = c[j]
        rows.append(sig.op_tables[op, int((full * st).sum())])
    return np.array(rows, dtype=np.int8), doms


def _canon(table: np.ndarray, doms):
    """Canonical form of a table under permutation of its inputs: (perm, permuted table) with the smallest bytes.
    perm[j] = which original input becomes input j."""
    import itertools
    from .operators import configs
    best = None
    k = len(doms)
    st = strides(tuple(doms))
    for perm in itertools.permutations(range(k)):
        nd = tuple(doms[i] for i in perm)
        rows = []
        for c in configs(nd):
            orig = np.zeros(k, dtype=np.int64)
            for j, i in enumerate(perm):
                orig[i] = c[j]
            rows.append(table[int((orig * st).sum())])
        tb = np.array(rows, dtype=np.int8)
        if best is None or tb.tobytes() < best[1].tobytes():
            best = (perm, tb)
    return list(best[0]), best[1]


def _permute_program(prog, perm):
    """Renumber IN(i) so that original input perm[j] becomes IN(j)."""
    inv = {i: j for j, i in enumerate(perm)}

    def rn(p):
        if p[0] == 'IN':
            return ('IN', inv.get(p[1], p[1]))
        if p[0] == 'C':
            return p
        if p[0] == 'LIB':
            return ('LIB', p[1]) + tuple(rn(a) for a in p[2:])
        return (p[0],) + tuple(rn(a) for a in p[1:])
    return rn(prog)


def _reduced_program(sig, op):
    """The operator's program with inputs renumbered to the essential inputs (a library body)."""
    dep = sig.op_depends[op]
    ins = [i for i in range(len(sig.in_domains)) if dep[i]]
    ren = {i: j for j, i in enumerate(ins)}

    def rn(p):
        if p[0] == 'IN':
            return ('IN', ren.get(p[1], 0))
        if p[0] == 'C':
            return p
        if p[0] == 'LIB':
            return ('LIB', p[1]) + tuple(rn(a) for a in p[2:])
        return (p[0],) + tuple(rn(a) for a in p[1:])
    return rn(sig.op_progs[op])
