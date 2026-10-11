"""CL-R5 G1 — the language organ: a learnable mechanism for symbol sequences grounded in experienced events.

No lexicon of any language is built in.  An utterance is a UTF-8 symbol sequence; meaning is acquired from experience
events (utterance + context + scene + an observed / teacher demonstration, a typed record such as
{"type": "ACTION", "action": ..., "object_id": ...}).

Each field of a demonstration is learned as one of:
  FEATURE  the value is the id of an entity of the scene/context that the utterance does NOT name: tokens are bound to
           FEATURES of the referent (colour, shape, its role in the context: speaker / addressee / pointed at; its time
           relative to the moment of speech), never to the id itself; a new scene with new ids is resolved by
           intersecting the constraints of the query's tokens
  MENTION  the value is named by a token of the utterance (a person's name, possibly inflected; a new file name): the
           organ learns WHICH token fills the field (neighbouring tokens, ending, order, side of the predicate word);
           cues that are not shared by all examples (e.g. word order in a life with two orders) drop out by themselves
  LABEL    a categorical value (action, act, status, temporal reference, the type of the answer): a decision list by
           precision over situation features (tokens, context keys present/absent, speaker features, pairs)
  NONE     null, learned conditionally on the label values (e.g. no object when the action is NO_ACTION)
Composition: the answer to a new utterance is assembled field by field from these parts.  An entity field with more
than one candidate is a request for clarification (if that answer occurred in experience), with none — UNKNOWN.

Three learners with the same input and the same single pass over the experience (`make_learner`):
  S  structural: consistency / precision over symbolic features (this module's main organ)
  H  trainable weights: perceptrons over the same features (5 epochs over the same events)
  N  whole-utterance memorizer: nearest training utterance, entity re-found by its old features
Confidence never exceeds 0.8: an interpretation induced from a few examples is not an observation of the world.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import combinations, permutations
from typing import Any, Dict, List, Optional, Tuple

CAP = 0.8
EDGE = set(',.!?;:«»"“”()[]{}…')
ID_KEYS = ('id', 'object_id', 'entity_id', 'person_id', 'event_id', 'file_id', 'uid')
TIME_KEYS = ('t', 'time', 'tick', 'at', 'when_t', 'event_time', 'timestamp', 'step')
NOW_KEYS = ('now', 'speech_time', 'current_time', 'utterance_time', 'time', 't', 'tick')
SPEAKER_KEYS = ('speaker', 'source', 'from', 'by', 'author', 'sender', 'utterer')
DEMO_KEYS = ('observed_demonstration', 'demonstration', 'receipt', 'world_receipt', 'receipts', 'observed', 'outcome',
             'teacher_demonstration', 'demo', 'answer', 'target_answer')
ANSWER_FIELDS = {'ACTION': ('action', 'object_id'), 'EVENT_ROLES': ('actor', 'recipient', 'act'),
                 'TEMPORAL_REFERENCE': ('reference',), 'REFERENCE': ('referent',), 'ASK_CLARIFICATION': ('target',),
                 'FILE_ACTION': ('action', 'arg1', 'arg2'), 'KNOWLEDGE_STATUS': ('claim', 'status'), 'UNKNOWN': ()}
TYPE_BY_FIELD = (('actor', 'EVENT_ROLES'), ('recipient', 'EVENT_ROLES'), ('referent', 'REFERENCE'),
                 ('reference', 'TEMPORAL_REFERENCE'), ('target', 'ASK_CLARIFICATION'), ('arg1', 'FILE_ACTION'),
                 ('status', 'KNOWLEDGE_STATUS'), ('claim', 'KNOWLEDGE_STATUS'), ('object_id', 'ACTION'),
                 ('action', 'ACTION'))


# ------------------------------------------------------------------ segmentation
def tokenize(s: Any) -> List[Tuple[str, str]]:
    """(normalized, raw) tokens: whitespace chunks; edge punctuation as separate tokens; inner symbols kept."""
    out: List[Tuple[str, str]] = []
    for chunk in str(s or '').split():
        lead, trail = [], []
        while chunk and chunk[0] in EDGE:
            lead.append(chunk[0])
            chunk = chunk[1:]
        while chunk and chunk[-1] in EDGE:
            trail.insert(0, chunk[-1])
            chunk = chunk[:-1]
        out += [(p, p) for p in lead]
        if chunk:
            out.append((chunk.lower(), chunk))
        out += [(p, p) for p in trail]
    return out


def similar(a: str, b: str) -> bool:
    """Surface identity up to a learned-free 'stem': same string, or a common beginning of >= 3 symbols that covers
    >= 60 % of the shorter one (inflected names, case endings) — no list of endings of any language."""
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n >= 3 and n >= 0.6 * min(len(a), len(b)) and min(len(a), len(b)) >= 3


def _norm(v) -> str:
    return str(v).strip().lower()


def _scalar(v) -> bool:
    return isinstance(v, (str, int, float, bool))


# ------------------------------------------------------------------ the situation: entities and features
def extract_entities(scene: Any, context: Any) -> Dict[str, dict]:
    ents: Dict[str, dict] = {}

    def add(eid, kind: str, d: dict):
        e = ents.setdefault(str(eid), {'kind': kind, 'feat': set(), 'strings': set(), 'num': {}})
        e['strings'].add(str(eid).lower())
        for k, v in d.items():
            if k in ID_KEYS:
                continue
            if _scalar(v) and not isinstance(v, bool) and isinstance(v, (int, float)):
                e['num'][k] = float(v)
                e['feat'].add(f'{k}={_norm(v)}')
            elif _scalar(v):
                e['feat'].add(f'{k}={_norm(v)}')
                if isinstance(v, str):
                    e['strings'].add(v.lower())
            elif isinstance(v, list) and all(_scalar(x) for x in v):
                for x in v:
                    e['feat'].add(f'{k}={_norm(x)}')
        e['feat'].add(f'kind={kind}')

    def walk(x, key: str):
        if isinstance(x, dict):
            eid = next((x[k] for k in ID_KEYS if k in x and _scalar(x[k])), None)
            if eid is not None:
                add(eid, key, x)
            elif x and all(isinstance(v, dict) and not any(i in v for i in ID_KEYS)
                           and all(_scalar(y) or isinstance(y, list) for y in v.values()) for v in x.values()) \
                    and key not in ('scene', 'context'):
                for k, v in x.items():                   # {id: {attributes}} under a collection key
                    add(k, key, v)
                return
            for k, v in x.items():
                if isinstance(v, dict):
                    walk(v, k)
                elif isinstance(v, list):
                    if all(isinstance(y, dict) for y in v):
                        for y in v:
                            walk(y, k)
                    elif eid is None and all(isinstance(y, str) for y in v) and k not in ('tokens', 'utterance', 'text'):
                        for y in v:
                            add(y, k, {'name': y})
        elif isinstance(x, list):
            for y in x:
                walk(y, key)

    walk(scene or {}, 'scene')
    walk(context or {}, 'context')
    # relational features from the context: who speaks, to whom, what is pointed at; time against the moment of speech
    if isinstance(context, dict):
        for k, v in _flat(context):
            vals = v if isinstance(v, list) else [v]
            for x in vals:
                if _scalar(x) and str(x) in ents:
                    ents[str(x)]['feat'].add(f'ctx:{k}')
                elif isinstance(x, str) and k.split('.')[-1] in SPEAKER_KEYS + ('addressee', 'listener', 'to', 'pointing',
                                                                                 'pointed', 'pointer', 'target'):
                    add(x, 'context', {'name': x})
                    ents[str(x)]['feat'].add(f'ctx:{k}')
        now = next((float(context[k]) for k in NOW_KEYS if isinstance(context.get(k), (int, float))
                    and not isinstance(context.get(k), bool)), None)
        if now is not None:
            # G1.1 compatibility guard: G1 historically compared any numeric 'tick',
            # 'timestamp' and 'now' as if they shared a physical unit.  When a
            # typed external-time context is supplied, allow comparison ONLY
            # for entities declaring the exact same axis and unit. Older
            # untyped G1 experiments remain unchanged (not a new time claim).
            ctx_axis = context.get('now_time_domain')
            ctx_unit = context.get('now_time_unit')
            timed = [(e['num'][tk], eid) for eid, e in ents.items() for tk in TIME_KEYS
                     if tk in e['num']
                     and (not ctx_axis or f'time_domain={str(ctx_axis).lower()}' in e['feat'])
                     and (not ctx_unit or f'time_unit={str(ctx_unit).lower()}' in e['feat'])]
            for tv, eid in timed:
                ents[eid]['feat'].add('rel=' + ('past' if tv < now else 'now' if tv == now else 'future'))
            past = [x for x in timed if x[0] < now]
            if past:
                ents[max(past)[1]]['feat'].add('rel=latest_past')
                ents[min(past)[1]]['feat'].add('rel=earliest_past')
    return ents


def _flat(d: dict, prefix: str = '', depth: int = 0):
    for k, v in d.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict) and depth < 1:
            yield from _flat(v, key + '.', depth + 1)
        else:
            yield key, v


def situation(toks: List[str], context: Any, ents: Dict[str, dict], known_ctx: set) -> set:
    F = {'w:' + t for t in toks}
    present = set()
    if isinstance(context, dict):
        for k, v in _flat(context):
            if v is None or v == '' or v == [] or v is False:
                continue
            present.add(k)
            F.add('c:' + k)
            if _scalar(v) and str(v) not in ents:
                F.add(f'cv:{k}={_norm(v)}')
        for k in SPEAKER_KEYS:
            sp = context.get(k)
            if _scalar(sp) and str(sp) in ents:
                F |= {'spk:' + f for f in ents[str(sp)]['feat'] if not f.startswith('ctx:')
                      and sum(1 for e in ents.values() if f in e['feat']) > 1}
    F |= {'nc:' + k for k in known_ctx - present}
    for t in toks:
        if any(t in e['strings'] for e in ents.values()):
            F.add('tok_is_entity')
        elif any(ch.isdigit() for ch in t) or '.' in t or '_' in t:
            F.add('tok_new_identifier')
    return F


def pairs(F: set) -> set:
    """Conjunctions of an utterance token with another token or with a context flag (what was said, in what
    situation) — e.g. a demonstrative WITHOUT pointing."""
    w = sorted(f for f in F if f.startswith('w:'))
    other = sorted(f for f in F if f.startswith(('w:', 'c:', 'nc:', 'cv:', 'tok_')))
    return {a + '&' + b if a < b else b + '&' + a for a in w for b in other if a != b}


def cues(toks: List[str], i: int, anchors: List[int]) -> set:
    t = toks[i]
    c = {'prev=' + (toks[i - 1] if i > 0 else '^'), 'next=' + (toks[i + 1] if i + 1 < len(toks) else '$'),
         'suf1=' + t[-1:]}
    if len(t) > 3:
        c.add('suf2=' + t[-2:])
    for a in anchors:
        c.add('before_anchor' if i < a else 'after_anchor')
    return c


def form_cue(tok: str, strings) -> Optional[str]:
    """How a mention token relates to the string of the entity it names: identical, or the same beginning with a
    different / added ending — a learned-free morphological cue (no list of endings)."""
    best = None
    for st in sorted(strings):
        if len(st) < 3 and st != tok:
            continue
        if tok == st:
            return 'form=exact'
        if similar(tok, st):
            n = 0
            for x, y in zip(tok, st):
                if x != y:
                    break
                n += 1
            c = 'form=+' + tok[n:] if len(tok) > len(st) and tok.startswith(st) else 'form=~' + tok[n:]
            best = best or c
    return best


def demo_of(ev: dict) -> Tuple[Optional[dict], Optional[str]]:
    for k in DEMO_KEYS:
        d = ev.get(k)
        if isinstance(d, list):
            d = next((x for x in d if isinstance(x, dict) and x), None)
        if isinstance(d, dict) and d:
            d = dict(d)
            if 'type' not in d:
                d['type'] = next((t for f, t in TYPE_BY_FIELD if f in d), 'UNKNOWN')
            if d['type'] in ANSWER_FIELDS:
                d = {'type': d['type'], **{f: d.get(f) for f in ANSWER_FIELDS[d['type']]}}
            return d, ('TEACHER' if 'teacher' in k else 'WORLD')
    return None, None


def prepare(ev: dict, known_ctx: set) -> dict:
    tk = tokenize(ev.get('utterance', ev.get('text', '')))
    toks = [n for n, _ in tk]
    ents = extract_entities(ev.get('scene'), ev.get('context'))
    return {'toks': toks, 'raw': [r for _, r in tk], 'ents': ents, 'context': ev.get('context'),
            'F': situation(toks, ev.get('context'), ents, known_ctx)}


def _key(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


# ------------------------------------------------------------------ S: the structural organ
class SLearner:
    kind = 'S'

    def __init__(self):
        self.n = 0
        self.known_ctx: set = set()
        self.type_lab = DecisionList()
        self.types: Dict[str, List[str]] = {}                 # type -> field order
        self.mode: Dict[str, Counter] = defaultdict(Counter)  # 'T|f' -> MENTION/FEATURE/LABEL/NONE counts
        self.lab: Dict[str, DecisionList] = defaultdict(DecisionList)
        self.none_ctx: Dict[str, Counter] = defaultdict(Counter)
        self.mode_ctx: Dict[str, Dict[tuple, Counter]] = defaultdict(lambda: defaultdict(Counter))
        self.label_ctx: Dict[str, Counter] = defaultdict(Counter)
        self.tokfeat: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))   # 'T|f' -> tok -> feat
        self.tokn: Dict[str, Counter] = defaultdict(Counter)
        self.discr: Dict[str, Counter] = defaultdict(Counter)  # 'T|f' -> feature seen absent on a same-kind distractor
        self.refkind: Dict[str, Counter] = defaultdict(Counter)
        self.cue_obs: Dict[str, List[list]] = defaultdict(list)   # 'T|f' -> [tokens, mention position]
        self.mention_toks: set = set()
        self.templates: Dict[str, Counter] = defaultdict(Counter)
        self.plain_toks: Counter = Counter()

    # ---------------------------------------------------------------- learning
    def observe(self, ev: dict):
        demo, _src = demo_of(ev)
        if demo is None:
            return
        if isinstance(ev.get('context'), dict):
            self.known_ctx |= {k for k, _ in _flat(ev['context'])}
        x = prepare(ev, self.known_ctx)
        self.learn(x, demo)

    def learn(self, x: dict, demo: dict):
        self.n += 1
        T = str(demo['type'])
        fields = [f for f in demo if f != 'type']
        self.types.setdefault(T, fields)
        FF = x['F'] | pairs(x['F'])
        self.type_lab.add(FF, T)
        toks, ents = x['toks'], x['ents']
        labels = tuple(sorted((f, _key(demo[f])) for f in fields if self._is_label(demo[f], ents, toks)))
        mention_pos = set()
        for f in fields:
            key = f'{T}|{f}'
            v = demo[f]
            if v is None:
                self.mode[key]['NONE'] += 1
                self.mode_ctx[key][labels]['NONE'] += 1
                self.none_ctx[key][labels] += 1
                continue
            pos = self._mention_positions(v, toks, ents)
            tmpl = None
            if not pos and str(v) not in ents:
                tp = self._template(v, toks)
                if tp is not None:
                    pos, tmpl = [tp[0]], tp[1]
            if pos:
                self.mode[key]['MENTION'] += 1
                self.mode_ctx[key][labels]['MENTION'] += 1
                i = pos[0]
                mention_pos.add(i)
                fc = form_cue(toks[i], ents[str(v)]['strings'] if str(v) in ents else {str(v).lower()})
                self.cue_obs[key].append([list(toks), i, fc])
                self.templates[key][tmpl or '{}'] += 1
                if str(v) in ents:
                    self.refkind[key][ents[str(v)]['kind']] += 1
            elif str(v) in ents:
                self.mode[key]['FEATURE'] += 1
                self.mode_ctx[key][labels]['FEATURE'] += 1
                ref = ents[str(v)]
                self.refkind[key][ref['kind']] += 1
                same = [e for eid, e in ents.items() if eid != str(v) and e['kind'] == ref['kind']]
                for ph in ref['feat']:
                    if any(ph not in e['feat'] for e in same):
                        self.discr[key][ph] += 1
                for t in set(toks):
                    self.tokn[key][t] += 1
                    for ph in ref['feat']:
                        self.tokfeat[key][t][ph] += 1
            else:
                self.mode[key]['LABEL'] += 1
                self.mode_ctx[key][labels]['LABEL'] += 1
                self.lab[key].add(FF, _key(v))
            self.label_ctx[key][labels] += 1
        for i, t in enumerate(toks):
            (self.mention_toks.add(t) if i in mention_pos else self.plain_toks.update([t]))

    def _is_label(self, v, ents, toks) -> bool:
        return v is not None and not self._mention_positions(v, toks, ents) and str(v) not in ents \
            and self._template(v, toks) is None

    @staticmethod
    def _template(v, toks) -> Optional[Tuple[int, str]]:
        if not isinstance(v, str):
            return None
        lv = v.lower()
        for i, t in enumerate(toks):
            if len(t) >= 3 and t in lv and t != lv:
                j = lv.index(t)
                return i, v[:j] + '{}' + v[j + len(t):]
        return None

    def _mention_positions(self, v, toks, ents) -> List[int]:
        if not _scalar(v) or isinstance(v, bool):
            return []
        sv = str(v).lower()
        strings = {sv}
        if str(v) in ents:
            strings |= ents[str(v)]['strings']
        out = []
        for i, t in enumerate(toks):
            if t == sv or (str(v) in ents and any(similar(t, s) for s in strings if len(s) >= 3)):
                out.append(i)
        return out

    def _anchors(self, toks, T) -> List[int]:
        return [i for f in self.types.get(T, []) for i in [self._anchor(toks, f, T)] if i is not None
                and self.mode[f'{T}|{f}'].most_common(1)[0][0] == 'LABEL']

    def _anchor(self, toks, f, T) -> Optional[int]:
        """Position of the token that best predicts a label field (the predicate word): the side of it is a cue."""
        dl = self.lab.get(f'{T}|{f}')
        if dl is None:
            return None
        best, bp = None, 0.0
        for i, t in enumerate(toks):
            p = dl.purity('w:' + t)
            if p > bp:
                best, bp = i, p
        return best if bp >= 0.99 else None

    # ---------------------------------------------------------------- answering
    def predict(self, ev: dict) -> Tuple[dict, float, dict]:
        x = prepare(ev, self.known_ctx)
        FF = x['F'] | pairs(x['F'])
        T, tconf, tsup = self.type_lab.predict(FF)
        trace = {'type': [T, tconf, tsup]}
        if T is None or T not in self.types:
            return {'type': 'UNKNOWN'}, 0.0, trace
        pred = {'type': T}
        confs = [tconf]
        fields = self.types[T]
        labels = []
        for f in fields:
            key = f'{T}|{f}'
            if self.mode[key].most_common(1)[0][0] == 'LABEL':
                v, c, s = self.lab[key].predict(FF)
                trace[f] = ['LABEL', v, c, s]
                if v is None:
                    return {'type': 'UNKNOWN'}, 0.0, trace
                pred[f] = json.loads(v)
                confs.append(c)
                labels.append((f, v))
        labels = tuple(sorted(labels))
        anchors = self._anchors(x['toks'], T)
        mslots = []
        for f in fields:
            key = f'{T}|{f}'
            mc = self.mode_ctx[key].get(labels)
            m = (mc or self.mode[key]).most_common(1)[0][0]
            nc = self.none_ctx[key].get(labels, 0)
            if m == 'NONE' or (nc > 0 and self.label_ctx[key].get(labels, 0) == 0):
                pred[f] = None
                continue
            if m == 'LABEL':
                continue
            if m == 'MENTION':
                mslots.append(f)
                continue
            v, c, why = self._feature_slot(key, x)
            trace[f] = ['FEATURE', v, c, why]
            if v == 'AMBIGUOUS':
                return self._ask(x, FF, trace, f)
            if v is None:
                return {'type': 'UNKNOWN'}, 0.0, trace
            pred[f] = v
            confs.append(c)
        if mslots:
            res, c, why = self._mention_slots(T, mslots, x, anchors)
            trace['mentions'] = [res, c, why]
            if res is None:
                return {'type': 'UNKNOWN'}, 0.0, trace
            pred.update(res)
            confs.append(c)
        return pred, round(min(CAP, min(confs)), 3), trace

    def _ask(self, x, FF, trace, f):
        if 'ASK_CLARIFICATION' in self.types:
            key = 'ASK_CLARIFICATION|target'
            v, c, s = self.lab[key].predict(FF) if key in self.lab else (None, 0, 0)
            tgt = json.loads(v) if v is not None else f
            return {'type': 'ASK_CLARIFICATION', 'target': tgt}, round(min(CAP, 0.6), 3), trace
        return {'type': 'UNKNOWN'}, 0.0, trace

    def _constraints(self, key, toks) -> Dict[str, Tuple[str, int]]:
        """token -> its consistent, discriminative features (precision 1 over its occurrences with this field);
        a feature claimed by several tokens stays only with the best-supported ones (mutual exclusivity)."""
        cand: Dict[str, set] = {}
        for t in self.tokn[key]:                     # over the whole vocabulary: mutual exclusivity is global
            n = self.tokn[key][t]
            fs = {ph for ph, c in self.tokfeat[key][t].items() if c == n and self.discr[key].get(ph, 0) > 0}
            if fs:
                cand[t] = fs
        owner: Dict[str, int] = {}
        for t, fs in cand.items():
            for ph in fs:
                owner[ph] = max(owner.get(ph, 0), self.tokn[key][t])
        q = set(toks)
        out = {t: {ph for ph in fs if self.tokn[key][t] >= owner[ph]} for t, fs in cand.items() if t in q}
        return {t: fs for t, fs in out.items() if fs}

    def _feature_slot(self, key, x):
        cons = self._constraints(key, x['toks'])
        need = set().union(*cons.values()) if cons else set()
        kinds = set(self.refkind[key])
        pool = [(eid, e) for eid, e in x['ents'].items() if e['kind'] in kinds] or list(x['ents'].items())
        if not need:
            return ('AMBIGUOUS' if len(pool) > 1 else (pool[0][0] if pool else None)), 0.4, {'constraints': {}}
        hit = [eid for eid, e in pool if need <= e['feat']]
        why = {'constraints': {t: sorted(v) for t, v in cons.items()}, 'candidates': hit}
        if len(hit) == 1:
            sup = min(self.tokn[key][t] for t in cons)
            return hit[0], 0.55 + 0.25 * min(1.0, sup / 3), why
        if hit:
            return 'AMBIGUOUS', 0.0, why
        ident = {ph for ph in need if ph.split('=')[0] in ('name', 'label', 'title')}
        if ident and need - ident:
            h = [eid for eid, e in pool if (need - ident) <= e['feat']]
            if len(h) == 1:
                why['relaxed'] = 'identity features dropped'
                return h[0], 0.5, why
        # no entity satisfies everything: some constraint was a coincidence of few examples.  Keep the largest
        # subsets of constraints that single out one entity; answer only if all of them agree (lower confidence).
        need_l = sorted(need)
        for k in range(len(need_l) - 1, 0, -1):
            found = set()
            for keep in combinations(need_l, k):
                h = [eid for eid, e in pool if set(keep) <= e['feat']]
                if len(h) == 1:
                    found.add(h[0])
            if found:
                why['relaxed_to'] = k
                return (sorted(found)[0], 0.5, why) if len(found) == 1 else ('AMBIGUOUS', 0.0, why)
        why['unsatisfiable'] = True
        return 'AMBIGUOUS', 0.0, why

    def _mention_slots(self, T, slots, x, anchors):
        toks, ents = x['toks'], x['ents']
        cand = [i for i, t in enumerate(toks) if t not in EDGE and (
            any(similar(t, s) for e in ents.values() for s in e['strings'] if len(s) >= 3)
            or t in self.mention_toks or t not in self.plain_toks)]
        if len(cand) < len(slots):
            return None, 0.0, {'candidates': cand}
        cons = {}
        for f in slots:
            sets = [cues(o[0], o[1], self._anchors(o[0], T)) | ({o[2]} if len(o) > 2 and o[2] else set())
                    for o in self.cue_obs[f'{T}|{f}']]
            cons[f] = set.intersection(*sets) if sets else set()
        ccues = {}
        for i in cand:
            fcs = {form_cue(toks[i], e['strings']) for e in ents.values()} - {None}
            ccues[i] = cues(toks, i, anchors) | ({sorted(fcs)[0]} if len(fcs) == 1 else set()) | \
                ({'form=exact'} if 'form=exact' in fcs else set())
        best, ties = None, []
        for perm in permutations(cand, len(slots)):
            sc = sum(len(ccues[i] & cons[f]) for f, i in zip(slots, perm))
            # order of mention among the candidates is a cue of last resort (stable in a fixed-order life)
            sc2 = -sum(abs(cand.index(i) - k) for k, i in enumerate(perm)) * 0.001
            s = sc + sc2
            if best is None or s > best[0] + 1e-9:
                best, ties = (s, perm), []
            elif abs(s - best[0]) <= 1e-9:
                ties.append(perm)
        s, perm = best
        out = {}
        for f, i in zip(slots, perm):
            key = f'{T}|{f}'
            kinds = {k for k, _ in self.refkind[key].most_common(1)}
            match = [eid for eid, e in ents.items() if (not kinds or e['kind'] in kinds)
                     and any(similar(toks[i], st) for st in e['strings'] if len(st) >= 3 or st == toks[i])]
            tm = self.templates[key].most_common(1)[0][0] if self.templates.get(key) else '{}'
            out[f] = match[0] if len(match) == 1 and tm == '{}' else tm.replace('{}', x['raw'][i])
        conf = 0.75 if (s >= 1 and not ties) else 0.5 if not ties else 0.3
        return out, conf, {'cons': {f: sorted(c) for f, c in cons.items()}, 'positions': list(perm), 'ties': len(ties)}

    # ---------------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {'kind': 'S', 'n': self.n, 'known_ctx': sorted(self.known_ctx), 'type_lab': self.type_lab.to_dict(),
                'types': self.types, 'mode': {k: dict(v) for k, v in sorted(self.mode.items())},
                'mode_ctx': {k: [[list(map(list, a)), dict(c)] for a, c in v.items()] for k, v in sorted(self.mode_ctx.items())},
                'lab': {k: v.to_dict() for k, v in sorted(self.lab.items())},
                'none_ctx': {k: [[list(map(list, a)), b] for a, b in v.items()] for k, v in sorted(self.none_ctx.items())},
                'label_ctx': {k: [[list(map(list, a)), b] for a, b in v.items()] for k, v in sorted(self.label_ctx.items())},
                'tokfeat': {k: {t: dict(c) for t, c in sorted(d.items())} for k, d in sorted(self.tokfeat.items())},
                'tokn': {k: dict(v) for k, v in sorted(self.tokn.items())},
                'discr': {k: dict(v) for k, v in sorted(self.discr.items())},
                'refkind': {k: dict(v) for k, v in sorted(self.refkind.items())},
                'cue_obs': {k: v for k, v in sorted(self.cue_obs.items())},
                'mention_toks': sorted(self.mention_toks), 'plain_toks': dict(self.plain_toks),
                'templates': {k: dict(v) for k, v in sorted(self.templates.items())}}

    @classmethod
    def from_dict(cls, d: dict) -> 'SLearner':
        s = cls()
        s.n, s.known_ctx = d['n'], set(d['known_ctx'])
        s.type_lab = DecisionList.from_dict(d['type_lab'])
        s.types = d['types']
        for k, v in d['mode'].items():
            s.mode[k] = Counter(v)
        for k, v in d['lab'].items():
            s.lab[k] = DecisionList.from_dict(v)
        for k, v in d.get('mode_ctx', {}).items():
            for a, c in v:
                s.mode_ctx[k][tuple(tuple(p) for p in a)] = Counter(c)
        for k, v in d['none_ctx'].items():
            s.none_ctx[k] = Counter({tuple(tuple(p) for p in a): b for a, b in v})
        for k, v in d['label_ctx'].items():
            s.label_ctx[k] = Counter({tuple(tuple(p) for p in a): b for a, b in v})
        for k, dd in d['tokfeat'].items():
            for t, c in dd.items():
                s.tokfeat[k][t] = Counter(c)
        for name in ('tokn', 'discr', 'refkind'):
            for k, v in d[name].items():
                getattr(s, name)[k] = Counter(v)
        for k, v in d['cue_obs'].items():
            s.cue_obs[k] = [list(x) for x in v]
        s.mention_toks, s.plain_toks = set(d['mention_toks']), Counter(d['plain_toks'])
        for k, v in d.get('templates', {}).items():
            s.templates[k] = Counter(v)
        return s


class DecisionList:
    """feature -> value counts; prediction by the purest (then best supported) feature present."""

    def __init__(self):
        self.c: Dict[str, Counter] = defaultdict(Counter)
        self.co: Dict[str, set] = defaultdict(set)      # feature -> utterance tokens it co-occurred with
        self.prior: Counter = Counter()

    def add(self, feats, value: str):
        self.prior[value] += 1
        ws = {f for f in feats if f.startswith('w:')}
        for f in feats:
            self.c[f][value] += 1
            if '&' not in f:
                self.co[f] |= ws - {f}

    def purity(self, f) -> float:
        c = self.c.get(f)
        if not c:
            return 0.0
        return c.most_common(1)[0][1] / sum(c.values())

    def predict(self, feats) -> Tuple[Optional[str], float, int]:
        if len(self.prior) == 1:
            v, n = next(iter(self.prior.items()))
            return v, 0.5 + 0.3 * min(1.0, n / 3), n
        best = None
        for f in sorted(feats):
            c = self.c.get(f)
            if not c:
                continue
            v, k = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            tot = sum(c.values())
            score = (k / tot, len(self.co.get(f, ())), k)
            if best is None or score > best[0]:
                best = (score, v)
        if best is None:
            return None, 0.0, 0
        (p, _div, k), v = best
        if p < 0.5:
            return None, 0.0, k
        return v, round(p * (0.5 + 0.3 * min(1.0, k / 3)), 3), k

    def to_dict(self):
        return {'c': {f: dict(v) for f, v in sorted(self.c.items())}, 'prior': dict(self.prior),
                'co': {f: sorted(v) for f, v in sorted(self.co.items())}}

    @classmethod
    def from_dict(cls, d):
        x = cls()
        for f, v in d['c'].items():
            x.c[f] = Counter(v)
        for f, v in d.get('co', {}).items():
            x.co[f] = set(v)
        x.prior = Counter(d['prior'])
        return x


# ------------------------------------------------------------------ H: trainable weights on the same features
class HLearner:
    kind = 'H'
    EPOCHS = 5

    def __init__(self):
        self.data: List[Tuple[dict, dict]] = []
        self.known_ctx: set = set()
        self.W: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.types: Dict[str, List[str]] = {}
        self.mode: Dict[str, str] = {}
        self.refkind: Dict[str, str] = {}
        self.trained = False

    def observe(self, ev: dict):
        demo, _ = demo_of(ev)
        if demo is None:
            return
        if isinstance(ev.get('context'), dict):
            self.known_ctx |= {k for k, _ in _flat(ev['context'])}
        self.data.append((ev, demo))
        self.trained = False

    def _w(self, slot):
        return self.W.setdefault(slot, {})

    @staticmethod
    def _score(w, feats, val):
        return sum(w.get(val, {}).get(f, 0.0) for f in feats)

    @staticmethod
    def _upd(w, feats, val, d):
        row = w.setdefault(val, {})
        for f in feats:
            row[f] = row.get(f, 0.0) + d

    def _ent_feats(self, x, eid, anchors):
        e = x['ents'][eid]
        fs = {f'{t}|{ph}' for t in x['toks'] for ph in e['feat']}
        for i, t in enumerate(x['toks']):
            if any(similar(t, s) for s in e['strings'] if len(s) >= 3):
                fs |= {'M|' + c for c in cues(x['toks'], i, anchors)}
                fs.add('M|named')
        return fs

    def _copy_feats(self, x, i, anchors):
        return {'C|' + c for c in cues(x['toks'], i, anchors)} | {'C|new' if x['toks'][i] not in self._seen else 'C|old'}

    def train(self):
        self._seen = Counter(t for ev, _ in self.data for t, _r in tokenize(ev.get('utterance', '')))
        xs = [(prepare(ev, self.known_ctx), demo) for ev, demo in self.data]
        modes: Dict[str, Counter] = defaultdict(Counter)
        for x, demo in xs:
            T = str(demo['type'])
            self.types.setdefault(T, [f for f in demo if f != 'type'])
            for f in self.types[T]:
                v = demo.get(f)
                key = f'{T}|{f}'
                if v is None:
                    m = 'NONE'
                elif str(v) in x['ents']:
                    m = 'ENTITY'
                    self.refkind.setdefault(key, x['ents'][str(v)]['kind'])
                elif any(t == str(v).lower() for t in x['toks']):
                    m = 'COPY'
                else:
                    m = 'LABEL'
                    self._w(key).setdefault(_key(v), {})
                modes[key][m] += 1
        self.mode = {k: c.most_common(1)[0][0] for k, c in sorted(modes.items())}
        for _ in range(self.EPOCHS):
            for x, demo in xs:
                T = str(demo['type'])
                F = x['F']
                w = self._w('TYPE')
                p = max(self.types, key=lambda t: (self._score(w, F, t), t))
                if p != T:
                    self._upd(w, F, T, 1.0)
                    self._upd(w, F, p, -1.0)
                for f in self.types[T]:
                    key, v = f'{T}|{f}', demo.get(f)
                    m = self.mode.get(key)
                    if m == 'LABEL' and v is not None:
                        w = self._w(key)
                        vals = list(w.keys()) or [_key(v)]
                        p = max(vals + [_key(v)], key=lambda t: (self._score(w, F, t), t))
                        if p != _key(v):
                            self._upd(w, F, _key(v), 1.0)
                            self._upd(w, F, p, -1.0)
                    elif m == 'ENTITY' and v is not None and str(v) in x['ents']:
                        w = self._w(key).setdefault('_', {})
                        pool = [eid for eid, e in x['ents'].items() if e['kind'] == self.refkind.get(key)]
                        sc = {eid: sum(w.get(f2, 0.0) for f2 in self._ent_feats(x, eid, [])) for eid in pool}
                        p = max(pool, key=lambda e: (sc[e], e))
                        if p != str(v):
                            for f2 in self._ent_feats(x, str(v), []):
                                w[f2] = w.get(f2, 0.0) + 1.0
                            for f2 in self._ent_feats(x, p, []):
                                w[f2] = w.get(f2, 0.0) - 1.0
                    elif m == 'COPY' and v is not None:
                        w = self._w(key).setdefault('_', {})
                        pos = [i for i, t in enumerate(x['toks']) if t == str(v).lower()]
                        if not pos:
                            continue
                        sc = {i: sum(w.get(f2, 0.0) for f2 in self._copy_feats(x, i, [])) for i in range(len(x['toks']))}
                        p = max(sc, key=lambda i: (sc[i], -i))
                        if p != pos[0]:
                            for f2 in self._copy_feats(x, pos[0], []):
                                w[f2] = w.get(f2, 0.0) + 1.0
                            for f2 in self._copy_feats(x, p, []):
                                w[f2] = w.get(f2, 0.0) - 1.0
        self.trained = True

    def predict(self, ev: dict):
        if not self.trained:
            self.train()
        if not self.types:
            return {'type': 'UNKNOWN'}, 0.0, {}
        x = prepare(ev, self.known_ctx)
        F = x['F']
        w = self._w('TYPE')
        sc = sorted(((self._score(w, F, t), t) for t in self.types), reverse=True)
        T = sc[0][1]
        margin = sc[0][0] - (sc[1][0] if len(sc) > 1 else 0.0)
        pred, margins = {'type': T}, [margin if len(sc) > 1 else 3.0]
        used = set()
        for f in self.types[T]:
            key = f'{T}|{f}'
            m = self.mode.get(key)
            if m == 'NONE' or m is None:
                pred[f] = None
            elif m == 'LABEL':
                ww = self._w(key)
                vals = sorted(((self._score(ww, F, v), v) for v in ww), reverse=True)
                if not vals:
                    return {'type': 'UNKNOWN'}, 0.0, {}
                pred[f] = json.loads(vals[0][1])
                margins.append(vals[0][0] - (vals[1][0] if len(vals) > 1 else 0.0))
            elif m == 'ENTITY':
                ww = self._w(key).get('_', {})
                pool = [eid for eid, e in x['ents'].items() if e['kind'] == self.refkind.get(key) and eid not in used]
                if not pool:
                    return {'type': 'UNKNOWN'}, 0.0, {}
                s = sorted(((sum(ww.get(f2, 0.0) for f2 in self._ent_feats(x, eid, [])), eid) for eid in pool), reverse=True)
                pred[f] = s[0][1]
                used.add(s[0][1])
                margins.append(s[0][0] - (s[1][0] if len(s) > 1 else 0.0))
            elif m == 'COPY':
                ww = self._w(key).get('_', {})
                s = sorted(((sum(ww.get(f2, 0.0) for f2 in self._copy_feats(x, i, [])), -i) for i in range(len(x['toks']))
                            if -i not in used), reverse=True)
                if not s:
                    return {'type': 'UNKNOWN'}, 0.0, {}
                i = -s[0][1]
                used.add(-i)
                pred[f] = x['raw'][i]
                margins.append(s[0][0] - (s[1][0] if len(s) > 1 else 0.0))
        m = min(margins)
        conf = 0.0 if m <= 0 else round(min(CAP, 1 - math.exp(-m / 2)), 3)
        return pred, conf, {'margins': margins}

    def to_dict(self):
        return {'kind': 'H', 'data': [[ev, demo] for ev, demo in self.data]}

    @classmethod
    def from_dict(cls, d):
        h = cls()
        for ev, demo in d['data']:
            h.observe(ev)
        return h


# ------------------------------------------------------------------ N: whole-utterance memorizer
class NLearner:
    kind = 'N'

    def __init__(self):
        self.mem: List[Tuple[set, dict, dict]] = []

    def observe(self, ev: dict):
        demo, _ = demo_of(ev)
        if demo is None:
            return
        ents = extract_entities(ev.get('scene'), ev.get('context'))
        refs = {f: sorted(ents[str(v)]['feat']) for f, v in demo.items() if f != 'type' and v is not None and str(v) in ents}
        self.mem.append(({t for t, _ in tokenize(ev.get('utterance', ''))}, demo, refs))

    def predict(self, ev: dict):
        if not self.mem:
            return {'type': 'UNKNOWN'}, 0.0, {}
        q = {t for t, _ in tokenize(ev.get('utterance', ''))}
        sim = lambda a: len(a & q) / max(1, len(a | q))
        toks, demo, refs = max(self.mem, key=lambda m: sim(m[0]))
        out = dict(demo)
        ents = extract_entities(ev.get('scene'), ev.get('context'))
        for f, feats in refs.items():
            fs = {ph for ph in feats if not ph.startswith('kind=')}
            same = [eid for eid, e in ents.items() if fs <= e['feat']]
            if len(same) == 1:
                out[f] = same[0]
        return out, round(min(CAP, sim(toks)), 3), {'similarity': sim(toks)}

    def to_dict(self):
        return {'kind': 'N', 'mem': [[sorted(a), b, c] for a, b, c in self.mem]}

    @classmethod
    def from_dict(cls, d):
        n = cls()
        n.mem = [(set(a), b, c) for a, b, c in d['mem']]
        return n


LEARNERS = {'S': SLearner, 'H': HLearner, 'N': NLearner}


def make_learner(kind: str):
    return LEARNERS[kind]()


def learner_from_dict(d: dict):
    return LEARNERS[d['kind']].from_dict(d)
