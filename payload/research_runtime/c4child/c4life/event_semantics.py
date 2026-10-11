"""G1.8 research: learning utterance -> independently witnessed event TRACE distinctions.

The learner does not know Russian words or temporal markers. It receives a
speaker's utterance plus a simulator action trace with plan/attempt/actuator
receipts, before/after sensor measurements, and an external UTC clock sample.
An axis-specific, small Boolean decision program is induced from contrasting
surface ngrams; no direct `word -> gold meaning` records are consumed.

This is NOT general semantic parsing, mental-state reading, or proof of a
speaker's truth. 'Planned' only means a recorded plan, never an unobserved wish.
Similarly, a failure receipt is evidence of failure of THAT attempt, not proof
that no action happened at another time.
"""
from __future__ import annotations
from collections import Counter
import copy
import hashlib
import json
import math
import re
from .grounded_language import tokenize


def canonical(d):
    return json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def content_root(witness):
    return 'sandbox:'+hashlib.sha256(canonical(witness).encode('utf8')).hexdigest()


def measured_trace(w):
    """Convert raw receipts into generic event constraints; no language labels."""
    if not isinstance(w,dict) or w.get('origin')!='SIMULATION':
        raise PermissionError('only independent sandbox world traces')
    if w.get('world_family')!='event_trace' or not isinstance(w.get('trace'),dict):
        raise ValueError('malformed trace witness')
    t=w['trace']
    if set(t)<{'plan','attempt','actuator','state_before','state_after','event_utc_ns','speech_utc_ns','actor_id','target_id','operation_id'}:
        raise ValueError('incomplete trace')
    plan,attempt=t['plan'],t['attempt']
    actuator=t['actuator']
    if type(plan) is not bool or type(attempt) is not bool or actuator not in ('NONE','REJECTED','EXECUTED'):
        raise ValueError('invalid trace stages')
    if not isinstance(t['state_before'],dict) or not isinstance(t['state_after'],dict):
        raise ValueError('trace requires observed object states')
    if plan and not attempt and actuator=='NONE' and t['state_before']==t['state_after']:
        phase='PLANNED_ONLY'
    elif plan and attempt and actuator=='REJECTED' and t['state_before']==t['state_after']:
        phase='ATTEMPT_FAILED'
    elif plan and attempt and actuator=='EXECUTED' and t['state_before']!=t['state_after']:
        phase='EXECUTED_EFFECT'
    else:
        raise ValueError('unsupported/contradictory stage combination')
    en,sp=t['event_utc_ns'],t['speech_utc_ns']
    if type(en) is not int or type(sp) is not int or en<0 or sp<0:
        raise ValueError('timestamps must be externally reported integer UTC nanoseconds')
    # Explicitly do not infer event order from Life ticks.
    delta=en-sp
    if abs(delta)<1_000_000_000:
        raise ValueError('two clock samples too close to distinguish')
    chronology='BEFORE_SPEECH' if delta<0 else 'AFTER_SPEECH'
    if not all(isinstance(t[k],str) and t[k] for k in ('actor_id','target_id','operation_id')):
        raise ValueError('missing event participants')
    return {'phase':phase,'chronology':chronology}


def surface_features(utterance,max_ngram=2):
    words=tokenize(utterance)
    if not 3<=len(words)<=16:
        raise ValueError('unsupported utterance size')
    return words, frozenset(' '.join(words[i:i+n]) for n in range(1,max_ngram+1)
                              for i in range(len(words)-n+1))


def _induce_rules(examples,field,min_support,min_confidence):
    """Conservative one-vs-rest bounded program induction (AND, NOT, OR-of-rules).

    Exhaustive search over surface ngrams and simple exceptions; concepts and
    words are *never* specified by a language-specific rule. Distinct roots
    count once. Failing or uncovered utterances yield UNKNOWN, not a fallback.
    """
    labels=sorted({e['meaning'][field] for e in examples})
    words=Counter(f for e in examples for f in e['features'])
    available=sorted(f for f,c in words.items() if c>=min_support)
    candidates=[]
    for required in available:
        for forbidden in (None,*available):
            if forbidden==required:continue
            matched=[e for e in examples if required in e['features'] and
                     (forbidden is None or forbidden not in e['features'])]
            if len(matched)<min_support:continue
            hist=Counter(e['meaning'][field] for e in matched)
            for label in labels:
                conf=hist[label]/len(matched)
                if conf<min_confidence:continue
                candidates.append({'requires':[required],
                                   'forbids':([forbidden] if forbidden else []),
                                   'label':label,'support':len(matched),
                                   'precision':round(conf,6),
                                   'roots':[e['root'] for e in matched]})
    rules=[]
    for label in labels:
        still={e['root'] for e in examples if e['meaning'][field]==label}
        eligible=[c for c in candidates if c['label']==label]
        while still:
            ranked=sorted(eligible,key=lambda c:(
                -len(still.intersection(c['roots'])),
                len(c['forbids']),len(c['requires'][0].split()),
                len(c['requires'][0]),c['requires'][0],','.join(c['forbids'])))
            if not ranked:break
            winner=ranked[0]
            gain=len(still.intersection(winner['roots']))
            if gain<min_support:break
            rules.append(winner)
            still.difference_update(winner['roots'])
            eligible=[c for c in eligible if c is not winner]
    return sorted(rules,key=lambda r:(r['label'],r['requires'],r['forbids']))


def _rule_predict(rules,features,min_support,min_confidence):
    active=[]
    for r in rules:
        if all(w in features for w in r['requires']) and all(w not in features for w in r['forbids']):
            active.append(r)
    labels={r['label'] for r in active}
    if len(labels)!=1:
        return None,active
    if min(r['support'] for r in active)<min_support or min(r['precision'] for r in active)<min_confidence:
        return None,active
    return next(iter(labels)),active


class EventMeaningInducer:
    """Cross-situational trace grounding with conservative abstention."""
    def __init__(self,min_support=10,min_confidence=.95):
        self.min_support=int(min_support)
        self.min_confidence=float(min_confidence)
        self.examples=[]
        self.roots=set()
        self.rules={}
        self.fitted=False
        self.cue_vocabulary=[]
        self.axis_cues={}
        self.seen_signatures={}
        self.seen_ordered_signatures={}

    def observe(self,utterance,root,receipt,teacher):
        if not isinstance(root,str) or root!=content_root(receipt):
            raise PermissionError('unverified or mismatched content-addressed receipt root')
        if root in self.roots:return False
        if not isinstance(teacher,str) or not teacher:raise ValueError('teacher source required')
        meaning=measured_trace(receipt)
        words,features=surface_features(utterance)
        # Factor known participants and operation references OUT of the semantic
        # stage/timeline learner. This layer has no authority to learn or test
        # the identity of those referents; a separate sensor/lexicon does so.
        aliases=receipt['trace'].get('surface_aliases')
        if not isinstance(aliases,dict) or set(aliases)<{'actor','target','operation'}:
            raise ValueError('missing independently situated referent labels')
        ref_tokens=set()
        for v in aliases.values():
            if not isinstance(v,str):raise ValueError('invalid referent surface')
            ref_tokens.update(tokenize(v))
        features=frozenset(f for f in features if not set(f.split()).intersection(ref_tokens))
        self.examples.append({'utterance':str(utterance),'root':root,'teacher':teacher,
                              'meaning':meaning,'features':sorted(features),
                              'witness':copy.deepcopy(receipt)})
        self.roots.add(root)
        self.fitted=False
        return True

    def fit(self):
        if not self.examples:
            self.rules={};self.cue_vocabulary=[];self.axis_cues={};self.seen_signatures={};self.seen_ordered_signatures={};self.fitted=True
            return {'examples':0,'programs':0}
        self.rules={field:_induce_rules(self.examples,field,self.min_support,self.min_confidence)
                    for field in ('phase','chronology')}
        cues=set();self.axis_cues={};self.seen_signatures={};self.seen_ordered_signatures={}
        for axis,rules in self.rules.items():
            axis_words=set()
            for r in rules:
                for f in r['requires']+r['forbids']:
                    axis_words.add(f)
                    cues.update(f.split())
            self.axis_cues[axis]=sorted(axis_words)
            self.seen_signatures[axis]=sorted({tuple(f for f in sorted(axis_words) if f in e['features'])
                                               for e in self.examples})
            axis_surface_words={w for f in axis_words for w in f.split()}
            self.seen_ordered_signatures[axis]=sorted({tuple(w for w in tokenize(e['utterance'])
                if w in axis_surface_words) for e in self.examples})
        self.cue_vocabulary=sorted(cues)
        self.fitted=True
        return {'examples':len(self.examples),'programs':sum(len(x) for x in self.rules.values()),
                'learned_surface_cues':len(cues),'cue_vocabulary':self.cue_vocabulary}

    def predict(self,utterance,*,speaker,utterance_utc_ns,grounded_surface_tokens=()):
        if not self.fitted:self.fit()
        words,features=surface_features(utterance)
        if not self.rules:return {'status':'ASK','reason':'NO_EVENT_EXPERIENCE'}
        # Queries need positive, learned evidence for EACH independently predicted axis.
        decisions={};paths={};counts={}
        for field,rules in self.rules.items():
            signature=tuple(f for f in self.axis_cues[field] if f in features)
            cuewords={w for f in self.axis_cues[field] for w in f.split()}
            ordered=tuple(w for w in words if w in cuewords)
            if ordered not in self.seen_ordered_signatures[field]:
                return {'status':'UNKNOWN','reason':'UNSEEN_MARKER_ORDER_OR_SCOPE','axis':field}
            if signature not in self.seen_signatures[field]:
                return {'status':'UNKNOWN','reason':'UNSEEN_MARKER_COMPOSITION','axis':field,
                        'seen_signatures':len(self.seen_signatures[field])}
            label,matched=_rule_predict(rules,features,self.min_support,self.min_confidence)
            if label is None:
                return {'status':'UNKNOWN','reason':'INSUFFICIENT_DISCRIMINATING_EVIDENCE',
                        'axis':field,'matched_rules':len(matched)}
            decisions[field]=label
            paths[field]=[{'required':r['requires'],'forbidden':r['forbids']} for r in matched]
            counts[field]=sum(r['support'] for r in matched)
        # Crucial open-vocabulary safety: unknown clauses/markers must not be silently
        # ignored. Entity/operation words have to be supplied from a separate learned
        # reference layer; this organ does NOT claim it learned them.
        lexical=set(self.cue_vocabulary)|set(w for item in grounded_surface_tokens for w in tokenize(str(item)))
        unknown=sorted(set(words)-lexical)
        if unknown:
            return {'status':'ASK','reason':'UNCOVERED_SURFACE_SYMBOL',
                    'unresolved_tokens':unknown,'needs':'lexical_reference_or_new_demonstration'}
        if type(utterance_utc_ns) is not int or utterance_utc_ns<0:
            return {'status':'UNKNOWN','reason':'NO_EXTERNAL_SPEECH_CLOCK'}
        if not isinstance(speaker,str) or not speaker:
            return {'status':'UNKNOWN','reason':'NO_ATTRIBUTABLE_SPEAKER'}
        return {'status':'EVENT_HYPOTHESIS','source_status':'REPORTED_NOT_OBSERVED',
                'phase':decisions['phase'],'chronology':decisions['chronology'],
                'speaker':speaker,'claimed_utterance_utc_ns':utterance_utc_ns,
                'speech_clock_status':'USER_REPORTED_UNVERIFIED',
                'evidence_kind':'TEACHER_LANGUAGE_CONVENTIONS_PLUS_SIMULATION_TRACES',
                'support':counts,'learned_rules':paths,
                'event_utc_ns':None,'physical_world_fact':False}

    def revoke(self,source):
        previous=len(self.examples)
        self.examples=[e for e in self.examples if e['teacher']!=source]
        self.roots={e['root'] for e in self.examples}
        self.fitted=False;self.fit()
        return previous-len(self.examples)

    def to_dict(self):
        if not self.fitted:self.fit()
        return {'version':'G1.8','min_support':self.min_support,'min_confidence':self.min_confidence,
                'examples':self.examples,'rules':self.rules,'cue_vocabulary':self.cue_vocabulary,
                'axis_cues':self.axis_cues,'seen_signatures':self.seen_signatures,
                'seen_ordered_signatures':self.seen_ordered_signatures}

    @classmethod
    def from_dict(cls,d):
        s=cls(d['min_support'],d['min_confidence'])
        s.examples=copy.deepcopy(d['examples'])
        s.roots={e['root'] for e in s.examples}
        s.fit()
        if canonical({'rules':s.rules,'cue_vocabulary':s.cue_vocabulary,'axis_cues':s.axis_cues,'seen_signatures':s.seen_signatures,'seen_ordered_signatures':s.seen_ordered_signatures}) != canonical({'rules':d['rules'],'cue_vocabulary':d['cue_vocabulary'],'axis_cues':d['axis_cues'],'seen_signatures':d['seen_signatures'],'seen_ordered_signatures':d['seen_ordered_signatures']}):
            raise ValueError('non-reproducible event-learning checkpoint')
        return s

    def digest(self):return hashlib.sha256(canonical(self.to_dict()).encode()).hexdigest()
