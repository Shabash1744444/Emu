"""G1.1 opt-in contrastive learner for unknown temporal words, no Russian rules.

Experiences consist of a language utterance and a *referential demonstration*
selected from independently timestamped events.  The teacher may establish a
linguistic convention, never the occurrence/time of the event.  Weights are
updated from contrasts, never from hidden expected answers at evaluation.
"""
from __future__ import annotations
from collections import defaultdict
import json
import math
import re
from typing import Sequence
from .temporal import TimedEvent, Interval, reference_features


def tokens(s: str) -> tuple[str,...]:
    # Surface segmentation deliberately language agnostic. This is NOT a
    # phoneme or word-boundary learner for raw audio; it is a text prototype.
    return tuple(re.findall(r'[^\W_]+|[^\s]', s.casefold(), flags=re.UNICODE))


class ContrastiveTimeGrounder:
    """Sparse online pairwise ranking over (utterance token x temporal feature).

    No hardcoded lexical items, tense forms, pronouns, yesterday/tomorrow,
    calendar vocabulary, weekday words, or rules for a particular language.
    Computational bias: events may be compared via order, duration, and
    local-calendar relation supplied by the host. A word is learned from
    repeated examples varying the world objects, timestamps and speakers.
    """
    def __init__(self, *, learning_rate: float = 0.3, epochs: int = 30, margin: float = 0.1):
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.margin = margin
        self.weights: dict[str, float] = defaultdict(float)
        self.vocab: set[str] = set()
        self.training_count = 0
        self.provenance_roots: set[str] = set()

    def _vector(self, utterance: str, event: TimedEvent, at: Interval, zone: str) -> dict[str,float]:
        feat = reference_features(event, at, zone)
        out: dict[str,float] = {}
        for token in set(tokens(utterance)):
            if token not in self.vocab:
                continue
            for key, val in feat.items():
                if val and key != 'bias':
                    out[f'{token}|{key}'] = val
        return out

    def _score(self, v: dict[str,float]) -> float:
        return sum(self.weights.get(k, 0.0)*x for k,x in v.items())

    def fit(self, examples: Sequence[dict], *, verified_roots: set[str]):
        """Each example has: utterance, events, chosen_id, at, zone,
        convention_source, receipt_roots (per observed event).
        The caller must validate event receipt roots against its journal.
        This method rejects non-attested events, replay/self-origin and absent
        language-convention source. No self-certified evidence roots.
        """
        good = []
        for ex in examples:
            evs = ex['events']
            if not isinstance(evs, (list, tuple)) or len(evs) < 2:
                raise ValueError('need independently described contrast candidates')
            ids = [e.event_id for e in evs]
            if len(set(ids)) != len(ids) or ex['chosen_id'] not in ids:
                raise ValueError('invalid event references')
            if not ex.get('convention_source') or ex.get('origin') in {'SIM_FEED', 'REPLAY', 'SELF_OUTPUT', 'DERIVED'}:
                raise ValueError('a real linguistic demonstration source is required')
            for ev in evs:
                if (ev.when.status not in {'MEASURED', 'ESTIMATED'} or not ev.source_root
                    or ev.simulation != bool(ex.get('simulation', False))):
                    raise ValueError('event observation or simulated receipt must be explicit')
                if ev.source_root not in verified_roots:
                    raise ValueError('event root not attested by the external verifier')
            if ex['at'].status not in {'MEASURED','ESTIMATED'}:
                raise ValueError('time of utterance is not a clock measurement')
            good.append(ex)
        for ex in good:
            self.vocab.update(tokens(ex['utterance']))
            self.provenance_roots.update(e.source_root for e in ex['events'])
        # Deterministic optimization over the *same* recorded training examples.
        # No private-test information is accessed, and no new roots are minted.
        for _ in range(self.epochs):
            for ex in good:
                feats = {e.event_id: self._vector(ex['utterance'], e, ex['at'], ex['zone'])
                         for e in ex['events']}
                pos = feats[ex['chosen_id']]
                for eid in sorted(feats):
                    if eid == ex['chosen_id']:
                        continue
                    neg = feats[eid]
                    p, n = self._score(pos), self._score(neg)
                    if p-n < self.margin:
                        for k in pos.keys() | neg.keys():
                            self.weights[k] += self.learning_rate*(pos.get(k,0)-neg.get(k,0))
        self.training_count += len(good)

    def predict(self, utterance: str, events: Sequence[TimedEvent], at: Interval, zone: str) -> dict:
        if not self.training_count:
            return {'status':'UNKNOWN', 'reason':'NO_EXPERIENCE'}
        active = set(tokens(utterance)) & self.vocab
        if not active:
            return {'status':'UNKNOWN','reason':'UNSEEN_LANGUAGE'}
        # If evidence learned from a word mainly supports a *calendar-day* distinction,
        # an event interval crossing a civil day is unresolvable with this evidence.
        # Do not let a correlated distance/order feature turn this into a false answer.
        calendar_signal = any(self.weights.get(f'{w}|civil:day:{d}',0.0) > self.margin
                              for w in active for d in range(-7,8))
        if calendar_signal and any('civil:uncertain' in reference_features(e,at,zone) for e in events):
            return {'status':'UNKNOWN','reason':'AMBIGUOUS_CIVIL_DAY_BOUNDARY'}
        scored = [(self._score(self._vector(utterance,e,at,zone)),e.event_id) for e in events]
        scored.sort(key=lambda x:(-x[0],x[1]))
        if len(scored)<2:
            return {'status':'UNKNOWN','reason':'NO_CONTRAST'}
        diff = scored[0][0]-scored[1][0]
        if diff <= self.margin or scored[0][0] <= 0:
            return {'status':'UNKNOWN','reason':'NO_DISCRIMINATING_SUPPORT', 'margin':round(diff,6)}
        return {'status':'CANDIDATE','event_id':scored[0][1], 'margin':round(diff,6),
                'note':'language-convention hypothesis, not certified world fact'}

    def to_dict(self):
        return {'version':1,'learning_rate':self.learning_rate,'epochs':self.epochs,'margin':self.margin,
                'weights':dict(sorted(self.weights.items())), 'vocab':sorted(self.vocab),
                'training_count':self.training_count,'provenance_roots':sorted(self.provenance_roots)}

    @classmethod
    def from_dict(cls, d):
        x=cls(learning_rate=d['learning_rate'],epochs=d['epochs'],margin=d['margin'])
        x.weights=defaultdict(float,d['weights']);x.vocab=set(d['vocab'])
        x.training_count=d['training_count'];x.provenance_roots=set(d['provenance_roots'])
        return x
