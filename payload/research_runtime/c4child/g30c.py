"""G3.0C additive, explicitly limited research organs.

Learnable surface->many-grounded-senses; witnessed orthographic span grouping;
conservative discourse-reference rule induction. No Russian lexicon, spellchecker,
semantic oracle, identity recognition, or general free-text parser is embedded.

World observation proves a referent was observed, NOT that a speaker's proposed
word denotes it. Language demonstrations remain source-qualified claims.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any
import copy
import unicodedata
from .g30b import VirtualWorld, Receipt, digest, token


def form(raw: str) -> str:
    """A *single* lexical form may include punctuation. Preserve exact raw elsewhere.

    This is not a language-specific tokenizer. It only validates a bounded span.
    """
    if not isinstance(raw, str) or not (1 <= len(raw) <= 120) or raw.strip() != raw:
        raise ValueError('INVALID_SURFACE')
    if any(unicodedata.category(ch).startswith('C') for ch in raw):
        raise ValueError('INVALID_SURFACE')
    if not any(unicodedata.category(ch).startswith('L') for ch in raw):
        raise ValueError('INVALID_SURFACE')
    return raw.casefold()


def context_units(words) -> tuple[str, ...]:
    if not isinstance(words, (list, tuple)) or len(words) > 40:
        raise ValueError('INVALID_CONTEXT')
    return tuple(sorted({form(w) for w in words}))


class SenseLedger:
    """Surface-form candidates backed by an observed referent + language testimony.

    The parent dictionary is immutable and local additions never overwrite it.
    No second sense can silently displace an old sense.  A missing/tied context
    returns AMBIGUOUS. Revocation is restricted by source ID.
    """
    def __init__(self, host: VirtualWorld, parent_lexicon: dict[str, str]):
        self.host = host
        self.parent = {form(w): str(sense) for w, sense in parent_lexicon.items()}
        self.lessons: list[dict] = []

    def teach(self, raw_word, observed_atom, receipt: Receipt, *, source, context=(), scope='LOCAL_LANGUAGE'):
        w = form(raw_word)
        if not isinstance(source, str) or not source or not isinstance(scope, str) or not scope:
            raise ValueError('SOURCE_SCOPE_REQUIRED')
        context = context_units(context)
        r = self.host.verify(receipt, 'OBSERVED_OBJECT')
        if r['atom'] != observed_atom:
            raise ValueError('UNWITNESSED_REFERENT')
        if any(e['root'] == receipt.root and e['source'] == source and e['word'] == w for e in self.lessons):
            raise ValueError('REPLAYED_LANGUAGE_LESSON')
        self.lessons.append({'word': w, 'sense': str(observed_atom), 'root': receipt.root,
                             'source': source, 'scope': scope, 'context': list(context), 'active': True,
                             'epistemic': 'ATTESTED_REFERENT_PLUS_TEACHER_LANGUAGE_CLAIM'})
        return 'ADDED_SENSE_WITNESS'

    def candidates(self, raw_word):
        w = form(raw_word)
        found = set()
        if w in self.parent:
            found.add(self.parent[w])
        found.update(e['sense'] for e in self.lessons if e['active'] and e['word'] == w)
        return sorted(found)

    def resolve(self, raw_word, *, context=()):
        w = form(raw_word)
        c = self.candidates(w)
        if not c:
            return {'status': 'UNKNOWN', 'senses': [], 'chosen': None}
        if len(c) == 1:
            return {'status': 'SINGLE_CANDIDATE_NOT_WORLD_TRUTH', 'senses': c, 'chosen': c[0]}
        cues = set(context_units(context))
        scores = defaultdict(int)
        support = defaultdict(set)
        for e in self.lessons:
            if not e['active'] or e['word'] != w:
                continue
            overlap = cues.intersection(e['context'])
            if overlap:
                scores[e['sense']] += len(overlap)
                support[e['sense']].add(e['root'])
        best = max((scores[x] for x in c), default=0)
        winner = [x for x in c if scores[x] == best]
        if not cues or best == 0 or len(winner) != 1:
            return {'status': 'AMBIGUOUS', 'senses': c, 'chosen': None}
        chosen = winner[0]
        # At least two separate host observations for contextual sense claim.
        if len(support[chosen]) < 2:
            return {'status': 'INSUFFICIENT_CONTEXT_EVIDENCE', 'senses': c, 'chosen': None}
        return {'status': 'CONTEXTUAL_SENSE_PROPOSAL', 'senses': c,
                'chosen': chosen, 'support_roots': sorted(support[chosen])}

    def retract(self, source):
        count = 0
        for e in self.lessons:
            if e['source'] == source and e['active']:
                e['active'] = False
                count += 1
        return count

    def state(self):
        return {'schema': 'G30C_SENSE_LEDGER_V1', 'parent_hash': digest(self.parent),
                'lessons': copy.deepcopy(self.lessons)}

    def restore(self, state):
        if state.get('schema') != 'G30C_SENSE_LEDGER_V1' or state.get('parent_hash') != digest(self.parent):
            raise ValueError('INVALID_PARENT_OR_SCHEMA')
        for e in state['lessons']:
            r = self.host._log.get(e['root'])
            if r is None or r.kind != 'OBSERVED_OBJECT' or r.data['atom'] != e['sense']:
                raise ValueError('MISSING_OBSERVED_WITNESS')
        self.lessons = copy.deepcopy(state['lessons'])


def raw_spans(raw: str) -> list[dict]:
    """Lossless orthographic spans, not a Russian segmentation oracle."""
    if not isinstance(raw, str) or len(raw) > 4096:
        raise ValueError('INVALID_UTTERANCE')
    out = []
    start = 0
    current = None
    def bucket(ch):
        cat = unicodedata.category(ch)
        if ch.isspace(): return 'SPACE'
        if cat[0] in ('L', 'M'): return 'LETTER'
        if cat[0] == 'N': return 'NUMBER'
        return 'PUNCTUATION'
    for i, ch in enumerate(raw):
        key = bucket(ch)
        if key != current and current is not None:
            out.append({'raw': raw[start:i], 'start': start, 'end': i, 'kind': current})
            start = i
        current = key
    if current is not None:
        out.append({'raw': raw[start:], 'start': start, 'end': len(raw), 'kind': current})
    return out


class BoundaryInducer:
    """Learn how written spans can be grouped from language demonstrations.

    The punctuation *character* used to join items is induced, not hardcoded.
    Its use never implies a meaning, a known word, or a spelling correction.
    """
    def __init__(self, host: VirtualWorld, min_examples=2, min_sources=2):
        self.host = host
        self.min_examples, self.min_sources = min_examples, min_sources
        self.lessons = []

    @staticmethod
    def separator(raw, parts):
        if len(parts) != 2 or not all(isinstance(p, str) and p for p in parts):
            raise ValueError('TWO_PARTS_REQUIRED')
        a, b = parts
        if not raw.startswith(a) or not raw.endswith(b):
            raise ValueError('UNALIGNED_PARTS')
        sep = raw[len(a):len(raw)-len(b)]
        if not sep or any(unicodedata.category(x)[0] in ('L','N') for x in sep):
            raise ValueError('NO_PUNCTUATION_BOUNDARY')
        return sep

    def teach(self, raw, parts, receipt: Receipt, *, source):
        d = self.host.verify(receipt, 'ORTHOGRAPHIC_DEMONSTRATION')
        if d != {'raw': raw, 'parts': list(parts), 'source': source}:
            raise ValueError('MISMATCHED_DEMONSTRATION')
        sep = self.separator(raw, parts)
        if any(x['root'] == receipt.root for x in self.lessons):
            raise ValueError('REPLAYED_DEMONSTRATION')
        self.lessons.append({'raw': raw, 'parts': list(parts), 'separator': sep,
                             'root': receipt.root, 'source': source, 'active': True})

    def known_separators(self):
        grouped = defaultdict(list)
        for x in self.lessons:
            if x['active']:
                grouped[x['separator']].append(x)
        return sorted(sep for sep, ex in grouped.items()
                      if len({x['raw'] for x in ex}) >= self.min_examples
                      and len({x['source'] for x in ex}) >= self.min_sources)

    def analyze(self, raw):
        spans = raw_spans(raw)
        comps = []
        seps = self.known_separators()
        for i in range(1, len(spans)-1):
            mid = spans[i]
            if mid['raw'] in seps and spans[i-1]['kind'] == 'LETTER' and spans[i+1]['kind'] == 'LETTER':
                comps.append({'surface': ''.join(x['raw'] for x in spans[i-1:i+2]),
                              'parts': [spans[i-1]['raw'], spans[i+1]['raw']],
                              'status': 'LEARNED_GROUPING_NOT_SEMANTICALLY_VALIDATED'})
        return {'raw': raw, 'spans': spans, 'compound_proposals': comps}

    def retract(self, source):
        out = 0
        for e in self.lessons:
            if e['source'] == source and e['active']:
                e['active'] = False
                out += 1
        return out


@dataclass(frozen=True)
class Mention:
    entity: str
    event_number: int
    quoted: bool = False
    is_topic: bool = False


@dataclass(frozen=True)
class ReferenceScene:
    """Semantically presegmented context. NOT an end-to-end Russian parser."""
    utterance: str
    surface: str
    eligible: tuple[str, ...]
    mentions: tuple[Mention, ...]

    def key(self):
        return digest({'utterance': self.utterance, 'surface': self.surface,
                       'eligible': list(self.eligible),
                       'mentions': [vars(m) for m in self.mentions]})

    def features(self, candidate):
        if candidate not in self.eligible:
            return set()
        mentions = [m for m in self.mentions if m.entity == candidate]
        if not mentions:
            return {'NOT_MENTIONED'}
        all_unquoted = [m for m in self.mentions if not m.quoted]
        recent = max((m.event_number for m in self.mentions), default=0)
        recent_unquoted = max((m.event_number for m in all_unquoted), default=-1)
        top = [m for m in self.mentions if m.is_topic]
        features = {'MENTIONED'}
        if max(m.event_number for m in mentions) == recent:
            features.add('LATEST_MENTION')
        if max((m.event_number for m in mentions if not m.quoted), default=-1) == recent_unquoted:
            features.add('LATEST_UNQUOTED_MENTION')
        if any(m.is_topic for m in mentions):
            features.add('CURRENT_TOPIC')
        if len(mentions) >= 2:
            features.add('REPEATED_MENTION')
        if all(m.quoted for m in mentions):
            features.add('ONLY_QUOTED')
        if top and top[-1].entity == candidate:
            features.add('LATEST_TOPIC')
        return features


class ReferenceInducer:
    """Discover *positive unique-reference clues* from language demonstrations.

    Requires a presegmented reference scene and already eligible referents;
    explicit ref classes are NOT silently inferred from arbitrary text.
    Leaves tied or unsupported questions UNKNOWN.
    """
    def __init__(self, host: VirtualWorld, min_support=3):
        self.host = host
        self.min_support = min_support
        self.lessons = []

    def teach(self, case: ReferenceScene, target, receipt: Receipt, *, source):
        d = self.host.verify(receipt, 'LANGUAGE_REFERENCE_DEMONSTRATION')
        if not source or d != {'case': case.key(), 'target': target, 'source': source}:
            raise ValueError('MISALIGNED_LANGUAGE_REFERENCE')
        if target not in case.eligible:
            raise ValueError('TARGET_NOT_ELIGIBLE')
        if any(e['root'] == receipt.root for e in self.lessons):
            raise ValueError('REPLAYED_REFERENCE_LESSON')
        self.lessons.append({'root': receipt.root, 'source': source,
                             'surface': form(case.surface), 'target': target,
                             'case_frame':{'utterance':case.utterance,'surface':case.surface,
                                           'eligible':list(case.eligible),
                                           'mentions':[vars(m) for m in case.mentions]},
                             'positive': sorted(case.features(target)),
                             'negative': sorted(set().union(*(case.features(x) for x in case.eligible if x != target))
                                                - case.features(target)),
                             'active': True})

    def rules(self, raw_surface):
        f = form(raw_surface)
        lessons = [x for x in self.lessons if x['active'] and x['surface'] == f]
        good = Counter()
        bad = Counter()
        sources = defaultdict(set)
        for e in lessons:
            for k in e['positive']:
                good[k] += 1
                sources[k].add(e['source'])
            for k in e['negative']:
                bad[k] += 1
        return sorted(k for k, n in good.items() if n >= self.min_support and
                      len(sources[k]) >= 2 and bad[k] == 0)

    def resolve(self, case: ReferenceScene):
        if not case.eligible:
            return {'status': 'UNKNOWN', 'chosen': None}
        if len(set(case.eligible)) != len(case.eligible):
            raise ValueError('DUPLICATE_ELIGIBLE')
        if len(case.eligible) == 1:
            return {'status': 'SINGLE_ELIGIBLE_FROM_EXTERNAL_CONTEXT', 'chosen': case.eligible[0]}
        # Unresolved nested quotation/viewpoint: a fresh quoted candidate can
        # compete with a fresh outer-narration candidate. Until quote-scope
        # language is *learned* rather than assumed, do not elevate one to fact.
        if case.mentions:
            newest = max(m.event_number for m in case.mentions)
            latest = [m for m in case.mentions if m.event_number == newest and m.entity in case.eligible]
            if len({m.entity for m in latest}) > 1 and any(m.quoted for m in latest):
                return {'status': 'AMBIGUOUS_QUOTE_VIEWPOINT', 'chosen': None}
        rules = self.rules(case.surface)
        if not rules:
            return {'status': 'UNKNOWN', 'chosen': None}
        winners = set()
        used = []
        for rule in rules:
            has = [x for x in case.eligible if rule in case.features(x)]
            if len(has) == 1:
                winners.add(has[0])
                used.append(rule)
        if len(winners) != 1:
            return {'status': 'AMBIGUOUS' if winners else 'UNKNOWN', 'chosen': None}
        return {'status': 'LEARNED_REFERENCE_PROPOSAL', 'chosen': next(iter(winners)),
                'rules': sorted(used), 'not_full_text_comprehension': True}

    def retract(self, source):
        count = 0
        for e in self.lessons:
            if e['active'] and e['source'] == source:
                e['active'] = False
                count += 1
        return count


def frozen_state(lex: SenseLedger, ortho: BoundaryInducer, refs: ReferenceInducer, parent_index_hash, operators=None):
    return {'schema': 'G30C_RESEARCH_V1', 'parent_index_hash': parent_index_hash,
            'parent_lexicon_hash': digest(lex.parent), 'sense_ledger': lex.state(),
            'orthography': copy.deepcopy(ortho.lessons), 'reference': copy.deepcopy(refs.lessons),
            'scope_operator': copy.deepcopy(operators.examples) if operators is not None else []}


def restore_state(state, lex: SenseLedger, ortho: BoundaryInducer, refs: ReferenceInducer, parent_index_hash, operators=None):
    if state.get('schema') != 'G30C_RESEARCH_V1' or state.get('parent_index_hash') != parent_index_hash:
        raise ValueError('INVALID_ARCHIVAL_LINEAGE')
    lex.restore(state['sense_ledger'])
    for x in state['orthography']:
        r = ortho.host._log.get(x['root'])
        if not r or r.kind != 'ORTHOGRAPHIC_DEMONSTRATION' or r.data != {'raw':x['raw'],'parts':x['parts'],'source':x['source']}:
            raise ValueError('ORTHO_WITNESS_UNAVAILABLE')
    for x in state['reference']:
        r = refs.host._log.get(x['root'])
        if not r or r.kind != 'LANGUAGE_REFERENCE_DEMONSTRATION' or r.data['source'] != x['source'] or r.data['target'] != x['target']:
            raise ValueError('REFERENCE_WITNESS_UNAVAILABLE')
        frozen=x.get('case_frame')
        if not frozen:
            raise ValueError('REFERENCE_FRAME_MISSING')
        case=ReferenceScene(frozen['utterance'],frozen['surface'],tuple(frozen['eligible']),
                            tuple(Mention(**m) for m in frozen['mentions']))
        if (case.key()!=r.data['case'] or x['surface']!=form(case.surface) or
            x['positive']!=sorted(case.features(x['target'])) or
            x['negative']!=sorted(set().union(*(case.features(v) for v in case.eligible if v!=x['target']))
                                  -case.features(x['target']))):
            raise ValueError('REFERENCE_FRAME_OR_FEATURES_TAMPERED')
    ortho.lessons = copy.deepcopy(state['orthography'])
    refs.lessons = copy.deepcopy(state['reference'])
    operator_entries = state.get('scope_operator', [])
    if operator_entries and operators is None:
        raise ValueError('MISSING_OPERATOR_REPLAY_ORGAN')
    if operators is not None:
        for e in operator_entries:
            r=operators.host._log.get(e['root'])
            if not r or r.kind!='OBSERVED_OBJECT':
                raise ValueError('MISSING_OPERATOR_WITNESS')
            words=[part['raw'].casefold() for part in raw_spans(e['sentence']) if part['kind']=='LETTER']
            recomputed=set()
            for i in range(1,len(words)):
                cue=operators.witnessed_cue_sense(lex,e['surface'],words[i])
                if cue and cue!=r.data['atom']:
                    recomputed.add(words[i-1])
            if sorted(recomputed)!=e['candidates']:
                raise ValueError('OPERATOR_CANDIDATES_TAMPERED')
        operators.examples=copy.deepcopy(operator_entries)


def export_host_evidence(host: VirtualWorld):
    """Cold-replay in-process simulator log; NOT a remotely signed attestation."""
    return [{'kind': r.kind, 'data': copy.deepcopy(r.data), 'root': r.root}
            for r in host._log.values()]


def import_host_evidence(entries):
    host = VirtualWorld()
    for e in entries:
        r = host.record(e['kind'], **e['data'])
        if r.root != e['root']:
            raise ValueError('CORRUPT_HOST_EVENT_CHAIN')
        if r.kind == 'OBSERVED_OBJECT':
            obj, atom = r.data['object'], r.data['atom']
            if obj in host.objects and host.objects[obj] != atom:
                raise ValueError('CONFLICTING_OBSERVED_OBJECT')
            host.objects[obj] = atom
    return host


def interpret_utterance(raw: str, lex: SenseLedger, orth: BoundaryInducer,
                        refs: ReferenceInducer | None = None,
                        semantic_reference: ReferenceScene | None = None):
    """Compose research organ predictions into an *unverified interpretation*.

    No arbitrary Russian sentence parsing, word-role extraction, or scene creation.
    A supplied semantic_reference is an external PRESEGMENTED annotation whose
    raw utterance must match; it is not inferred by this function.
    """
    tokenized = orth.analyze(raw)
    word_spans = [s for s in tokenized['spans'] if s['kind'] == 'LETTER']
    wordforms = [s['raw'] for s in word_spans]
    lexical = []
    for i,w in enumerate(wordforms):
        choices = lex.candidates(w)
        if choices:
            context = [v for j,v in enumerate(wordforms) if j != i]
            lexical.append({'raw': w, 'result': lex.resolve(w, context=context)})
    answer = {'raw': raw,
              'raw_sha256': digest(raw),
              'epistemic': 'UNVERIFIED_TEXT_INTERPRETATION_NOT_WORLD_FACT',
              'lexical_candidates': lexical,
              'orthographic_compounds': tokenized['compound_proposals'],
              'reference': None}
    if semantic_reference is not None:
        if semantic_reference.utterance != raw or refs is None:
            raise ValueError('EXTERNAL_CONTEXT_MISMATCH')
        answer['reference'] = refs.resolve(semantic_reference)
        answer['reference_provided_as_external_structure'] = True
    return answer


class ContextOperatorInducer:
    """Induce an immediately-following-cue suppression operator from
    independently witnessed CONTRASTING utterances.

    No specific Russian negator or spelling is built in. The generic hypothesis
    class is small: a learned marker suppresses only the next *single* context
    cue. This DOES NOT solve natural-language negation scope, polarity, or
    compositional grammar; such claims require further experiments.
    """
    def __init__(self, host: VirtualWorld, min_examples=4, min_surfaces=2,
                 min_sources=2):
        self.host=host
        self.min_examples=min_examples
        self.min_surfaces=min_surfaces
        self.min_sources=min_sources
        self.examples=[]

    @staticmethod
    def witnessed_cue_sense(lex: SenseLedger, surface, cue):
        # Derive cue->sense using previous lexical grounding. A teacher cannot
        # assert an arbitrary cue without at least two host receipts.
        w=form(surface)
        supports=defaultdict(set)
        for e in lex.lessons:
            if e['active'] and e['word']==w and cue in e['context']:
                supports[e['sense']].add(e['root'])
        eligible=[sense for sense,roots in supports.items() if len(roots)>=2]
        return eligible[0] if len(eligible)==1 else None

    def teach(self, utterance, ambiguous_form, observed_sense, receipt: Receipt,
              lex: SenseLedger, *, source):
        r=self.host.verify(receipt,'OBSERVED_OBJECT')
        if r['atom']!=observed_sense:
            raise ValueError('CONTRADICTORY_WORLD_WITNESS')
        if not source:
            raise ValueError('SOURCE_REQUIRED')
        if any(e['root']==receipt.root for e in self.examples):
            raise ValueError('REPLAYED_OPERATOR_EVIDENCE')
        words=[s['raw'].casefold() for s in raw_spans(utterance) if s['kind']=='LETTER']
        if form(ambiguous_form) not in words or len(lex.candidates(ambiguous_form))<2:
            raise ValueError('NO_AMBIGUOUS_TARGET')
        candidates=set()
        for i in range(1,len(words)):
            cue=words[i]
            cue_sense=self.witnessed_cue_sense(lex,ambiguous_form,cue)
            if cue_sense is not None and cue_sense!=observed_sense:
                # The generic hypothesis is learnt from the opposite-sense cue
                # being immediately preceded by a candidate scope marker.
                candidates.add(words[i-1])
        if not candidates:
            return 'NO_OPERATOR_EVIDENCE'
        self.examples.append({'root':receipt.root,'source':source,
                              'surface':form(ambiguous_form),
                              'sentence':utterance,'candidates':sorted(candidates),
                              'active':True})
        return 'CONTRASTIVE_OPERATOR_EVIDENCE'

    def operators(self):
        by=defaultdict(list)
        for e in self.examples:
            if e['active']:
                for marker in e['candidates']:
                    by[marker].append(e)
        return sorted(marker for marker, es in by.items()
                      if len({e['root'] for e in es})>=self.min_examples
                      and len({e['source'] for e in es})>=self.min_sources
                      and len({e['surface'] for e in es})>=self.min_surfaces)

    def filter_context(self, words, target_index, lex: SenseLedger):
        if not isinstance(words,(list,tuple)) or not (0<=target_index<len(words)):
            raise ValueError('INVALID_WORD_POSITION')
        marker_set=set(self.operators())
        kept=[]
        suppressed=[]
        for i,w in enumerate(words):
            if i==target_index:
                continue
            # Only exclude a cue if it is known for the TARGET word, and the
            # observed preceding marker was learned from contrasting scenes.
            if i>0 and words[i-1] in marker_set and self.witnessed_cue_sense(lex,words[target_index],w):
                suppressed.append(w)
            else:
                kept.append(w)
        return {'context':kept,'suppressed_cues':suppressed,
                'learned_operators':sorted(marker_set)}

    def retract(self,source):
        count=0
        for e in self.examples:
            if e['active'] and e['source']==source:
                e['active']=False
                count+=1
        return count


def interpret_with_operators(raw, lex: SenseLedger, orth: BoundaryInducer,
                             ops: ContextOperatorInducer):
    """Limited raw-text -> candidate senses, incorporating acquired local scopes."""
    spans=orth.analyze(raw)
    words=[s['raw'].casefold() for s in spans['spans'] if s['kind']=='LETTER']
    found=[]
    for i,w in enumerate(words):
        if lex.candidates(w):
            filtered=ops.filter_context(words,i,lex)
            found.append({'raw':w,'result':lex.resolve(w,context=filtered['context']),
                          'operator_evidence':filtered})
    return {'raw':raw, 'raw_sha256':digest(raw),
            'epistemic':'UNVERIFIED_COMPOSITION_NO_WORLD_FACT_PROMOTION',
            'lexical_candidates':found, 'orthographic_compounds':spans['compound_proposals']}
