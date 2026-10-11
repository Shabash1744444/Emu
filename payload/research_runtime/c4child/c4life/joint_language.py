"""G2.4 experimental *joined* event utterance induction.

Train from whole utterances + independently SIM_HOST-attested event receipts.
Learns lexical operations, event phase, speech-relative time, and actor/target
reference assignment in one provenance-preserving candidate. No Russian tokens
are built into the learner. Closed and limited: single witnessed event, two
host-grounded participant aliases, no audio / case inflection / nested speech.
A teacher's linguistic choice is NEVER an independent world observation.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from .grounded_language import tokenize
from .event_semantics import measured_trace, content_root


def _j(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',',':'))


def joint_root(witness,scene):
    measured_trace(witness)
    if not isinstance(scene,list) or len(scene)!=2:
        raise ValueError('joint witness scene must have 2 entities')
    return 'joint:'+hashlib.sha256(_j({'trace':witness,'scene':scene}).encode('utf8')).hexdigest()

def _mention_spans(words,scene):
    if not isinstance(scene,list) or len(scene)!=2:
        raise ValueError('exactly two independently known participants required')
    out=[]; occupied=set()
    for item in scene:
        ident=item.get('id'); name=item.get('name'); kind=item.get('kind')
        if not isinstance(ident,str) or not ident or not isinstance(kind,str) or not kind:
            raise ValueError('missing entity id or sensor-grounded type')
        phrase=tokenize(name)
        if not phrase:raise ValueError('unnamed scene entity')
        hits=[i for i in range(len(words)-len(phrase)+1) if tuple(words[i:i+len(phrase)])==phrase]
        if len(hits)!=1:raise ValueError('entity name absent or multiply mentioned')
        span=set(range(hits[0],hits[0]+len(phrase)))
        if occupied & span:raise ValueError('overlapping aliases')
        occupied.update(span)
        out.append({'id':ident,'kind':kind,'start':hits[0],'end':hits[0]+len(phrase),'name':name})
    out.sort(key=lambda x:x['start'])
    if out[0]['id']==out[1]['id']:raise ValueError('duplicate scene ID')
    residue=[w for i,w in enumerate(words) if i not in occupied]
    return out, tuple(residue)


def _feats(residue):
    return {(' '.join(residue[i:i+n])) for n in (1,2) for i in range(len(residue)-n+1)}


class JointUtteranceInducer:
    """Weakly supervised supervised by WHOLE traces; no gold token spans/roles.

    All semantic axes are contrasted factorially. An unseen word or cue order
    causes abstention. A failed or unsupported syntax is never treated as false.
    """
    def __init__(self,min_support=6,precision=.94):
        self.min_support=min_support;self.precision=precision
        self.examples=[];self.roots=set();self.programs={};self.role_cases={}
        self.lexicon=set();self.order_shapes=set();self.axis_orders={};self.fitted=False

    def observe(self,utterance,root,witness,scene,source):
        if not isinstance(source,str) or not source:raise ValueError('teacher channel required')
        if root!=joint_root(witness,scene):raise PermissionError('not a jointly attested trace and scene')
        if root in self.roots:return False
        meaning=measured_trace(witness)
        trace=witness['trace']
        words=tokenize(utterance)
        mentions,residue=_mention_spans(words,scene)
        if not 3<=len(words)<=20:raise ValueError('utterance length')
        if {trace['actor_id'],trace['target_id']}!={mentions[0]['id'],mentions[1]['id']}:
            raise ValueError('scene does not match trace participants')
        if not residue:raise ValueError('no lexical content')
        roles=('ACTOR','TARGET') if mentions[0]['id']==trace['actor_id'] else ('TARGET','ACTOR')
        e={'root':root,'source':source,'utterance':utterance,'residue':list(residue),
           'features':sorted(_feats(residue)),
           'meaning':{'phase':meaning['phase'],'chronology':meaning['chronology'],'operation':trace['operation_id']},
           'kinds':[m['kind'] for m in mentions], 'roles':list(roles),
           'witness':deepcopy(witness),'scene':deepcopy(scene)}
        self.examples.append(e);self.roots.add(root);self.fitted=False
        return True

    def fit(self):
        self.lexicon={w for e in self.examples for w in e['residue']}
        self.programs={};self.role_cases={};self.order_shapes=set();self.axis_orders={}
        for axis in ('phase','chronology','operation'):
            freq=Counter(f for e in self.examples for f in e['features'])
            # For each surface cue, also try its absence as an independent
            # counterexample. No language-specific negation tokens.
            by=defaultdict(Counter)
            for e in self.examples:
                for f in e['features']:by[f][e['meaning'][axis]]+=1
            candidates=defaultdict(list)
            cues=sorted(f for f,c in freq.items() if c>=self.min_support)
            for req in cues:
                for forbidden in (None,*cues):
                    if req==forbidden:continue
                    covered=[e for e in self.examples if req in e['features'] and
                             (forbidden is None or forbidden not in e['features'])]
                    if len(covered)<self.min_support:continue
                    counts=Counter(e['meaning'][axis] for e in covered)
                    for label,k in counts.items():
                        if k/len(covered)<self.precision:continue
                        distinct={tuple(e['meaning'][z] for z in ('phase','chronology','operation') if z!=axis)
                                  for e in covered}
                        if len(distinct)<2:continue
                        candidates[label].append({'requires':req,'forbids':forbidden,
                           'support':len(covered),'precision':round(k/len(covered),6)})
            self.programs[axis]={}
            for label,items in sorted(candidates.items()):
                # Greedy minimum-description-length covering: prefer a rule
                # which explains many yet-uncovered witnesses with fewer
                # literals. This removes hundreds of accidental conjunctions.
                remaining={e['root'] for e in self.examples if e['meaning'][axis]==label}
                chosen=[]
                while remaining:
                    options=[]
                    for r in items:
                        covered={e['root'] for e in self.examples
                                 if e['meaning'][axis]==label and
                                 r['requires'] in e['features'] and
                                 (r['forbids'] is None or r['forbids'] not in e['features'])}
                        gain=len(remaining & covered)
                        if gain:
                            complexity=1+int(r['forbids'] is not None)+.1*(len(r['requires'].split())-1)
                            options.append((gain/complexity,gain,r['forbids'] is not None,
                                            len(r['requires'].split()),r['requires'],r['forbids'] or '',r,covered))
                    if not options:break
                    options.sort(key=lambda x:(-x[0],-x[1],x[2],x[3],x[4],x[5]))
                    best=options[0]
                    chosen.append(best[6]);remaining-=best[7]
                    if len(chosen)>=16:break
                self.programs[axis][label]=chosen
            vocabulary={word for group in self.programs[axis].values() for rule in group
                       for cue in (rule['requires'],rule['forbids']) if cue is not None
                       for word in cue.split()}
            self.axis_orders[axis]=sorted({tuple(w for w in e['residue'] if w in vocabulary)
                                           for e in self.examples})
        role=defaultdict(Counter)
        for e in self.examples:
            key=tuple(e['kinds']);role[key][e['roles'][0]]+=1
        self.role_cases={_j(list(k)):dict(v) for k,v in role.items()}
        # Induce role/phase/operation/chronology CUE ORDER constraints without
        # requiring any exact full sentence to be repeated during testing.
        for e in self.examples:
            shape=self._shape(e['residue'])
            if shape:self.order_shapes.add(shape)
        self.fitted=True
        return {'examples':len(self.examples),'operators':{k:len(v) for k,v in self.programs.items()},
                'order_shapes':len(self.order_shapes),'role_contexts':len(self.role_cases)}

    def _choose(self,axis,feats):
        wins={lab for lab,rules in self.programs.get(axis,{}).items()
              if any(r['requires'] in feats and
                     (r['forbids'] is None or r['forbids'] not in feats) for r in rules)}
        return next(iter(wins)) if len(wins)==1 else None

    def _shape(self,residue):
        # Discover which positions are informative by which axis-exclusive
        # cues are supported, not from Russian morphology dictionaries.
        labels=[]
        for token in residue:
            flags=[]
            for axis in ('phase','chronology','operation'):
                for rules in self.programs.get(axis,{}).values():
                    if any(token in r['requires'].split() for r in rules):flags.append(axis)
            if len(set(flags))==1:labels.append(flags[0])
        compact=[]
        for label in labels:
            if not compact or compact[-1]!=label:compact.append(label)
        return tuple(compact)

    def predict(self,utterance,scene,speaker,utterance_utc_ns):
        if not self.fitted:self.fit()
        if not self.examples:return {'status':'ASK','reason':'NO_GROUNDED_JOINT_EXPERIENCE'}
        if not isinstance(speaker,str) or not speaker:
            return {'status':'UNKNOWN','reason':'UNATTRIBUTED_SPEAKER'}
        if type(utterance_utc_ns) is not int or utterance_utc_ns<0:
            return {'status':'UNKNOWN','reason':'NO_EXTERNAL_UTTERANCE_CLOCK'}
        try:
            words=tokenize(utterance);mentions,residue=_mention_spans(words,scene)
        except (ValueError,TypeError,AttributeError):
            return {'status':'UNKNOWN','reason':'REFERENT_IDENTIFICATION_UNRESOLVED'}
        unknown=sorted(set(residue)-self.lexicon)
        if unknown:
            return {'status':'ASK','reason':'UNLEARNED_TEXT','unknown':unknown}
        feats=_feats(residue)
        found={axis:self._choose(axis,feats) for axis in ('phase','chronology','operation')}
        if None in found.values():
            return {'status':'UNKNOWN','reason':'JOINT_MEANING_AMBIGUOUS','resolved_axes':found}
        for axis,orders in self.axis_orders.items():
            vocabulary={w for sequence in orders for w in sequence}
            if tuple(w for w in residue if w in vocabulary) not in orders:
                return {'status':'UNKNOWN','reason':'UNTRAINED_AXIS_SCOPE_ORDER','axis':axis}
        if self._shape(residue) not in self.order_shapes:
            return {'status':'UNKNOWN','reason':'UNTRAINED_CUE_SCOPE_ORDER'}
        key=_j([m['kind'] for m in mentions]);counts=self.role_cases.get(key,{})
        total=sum(counts.values());ranked=sorted(counts.items(),key=lambda it:-it[1])
        if total<self.min_support or not ranked or ranked[0][1]/total<self.precision:
            return {'status':'UNKNOWN','reason':'ROLE_DIRECTION_UNRESOLVED'}
        pattern=ranked[0][0]
        actor=mentions[0 if pattern=='ACTOR' else 1]['id']
        target=mentions[1 if pattern=='ACTOR' else 0]['id']
        return {'status':'CANDIDATE_REPORTED_EVENT','source_status':'SPEAKER_REPORTED_NOT_WORLD_OBSERVED',
                'speaker':speaker,'utterance_utc_ns':utterance_utc_ns,'actor':actor,'target':target,
                'operation':found['operation'],'phase':found['phase'],'chronology':found['chronology'],
                'evidence_kind':'TEACHER_CONVENTION_WITH_SIMULATED_CONTRAST','sandbox_only':True,
                'matched_training_roots':len(self.roots),'world_fact':False}

    def revoke(self,source):
        before=len(self.examples)
        self.examples=[x for x in self.examples if x['source']!=source]
        self.roots={x['root'] for x in self.examples};self.fit()
        return before-len(self.examples)

    def to_dict(self):
        if not self.fitted:self.fit()
        return {'version':'G2.4','min_support':self.min_support,'precision':self.precision,
                'examples':self.examples,'programs':self.programs,'role_cases':self.role_cases,
                'lexicon':sorted(self.lexicon),'order_shapes':[list(x) for x in sorted(self.order_shapes)],
                'axis_orders':self.axis_orders}

    @classmethod
    def from_dict(cls,d):
        z=cls(d['min_support'],d['precision']);z.examples=deepcopy(d['examples']);z.roots={x['root'] for x in z.examples}
        z.fit()
        expected=dict(d)
        if _j(z.to_dict())!=_j(expected):raise ValueError('G2.4 deterministic state restoration mismatch')
        return z

    def digest(self):return hashlib.sha256(_j(self.to_dict()).encode()).hexdigest()
