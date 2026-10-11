"""G2.6 exploratory meaning-from-text induction.

NOT a Russian parser. Learns schematic fragment patterns from paired atomic
utterances and typed simulator scenes, then segments whole unpunctuated stories
by global unique covering. No clauses/event boundaries supplied at inference.
Runtime vocabulary has no hard-coded Russian markers or names.
Every parsed event stays inside NARRATED, never SIMULATED_WORLD/OBSERVED.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import re


def words(text):
    return re.findall(r'[^\W_]+', str(text).casefold(), re.UNICODE)


def stable(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

SCHEMAS = {
    'INITIAL': ('holder','object'),
    'INTENT': ('actor','recipient','object'),
    'SUCCESS': ('actor','recipient','object'),
    'FAILURE': ('actor','recipient','object'),
    'REPORT': ('speaker','claim_holder','object'),
    'NESTED_REPORT': ('outer','inner','claim_holder','object'),
}
PERSON_ROLES = {'holder','actor','recipient','speaker','claim_holder','outer','inner'}


def _inventory(persons, objects):
    """Surface aliases grounded by external scene, distinct from utterance meaning."""
    if not isinstance(persons, dict) or not isinstance(objects, dict):
        raise ValueError('INVENTORY_REQUIRED')
    result={}
    for typ, d in [('P',persons),('O',objects)]:
        for alias,value in d.items():
            span=tuple(words(alias))
            if not span or len(span)>5 or not isinstance(value,str) or not value:
                raise ValueError('INVALID_ALIAS')
            if span in result and result[span] != (typ,value):
                raise ValueError('AMBIGUOUS_ALIAS')
            result[span]=(typ,value)
    return result


class PatternInducer:
    """Induces slot-bearing constructions; no lexical meaning is preinstalled.

    Semantic targets (INITIAL/INTENT/... 6 program classes) are priors and
    paired with atomic phrases during teaching. The interesting transfer is
    to multi-event, unsegmented, unpunctuated stories with new entities.
    """
    def __init__(self, min_support=3):
        self.min_support=min_support
        self.examples=[]
        self.patterns={}
        self.blocked=[]

    @staticmethod
    def _slots_for(target):
        if not isinstance(target,dict) or target.get('kind') not in SCHEMAS:
            raise ValueError('UNKNOWN_SEMANTIC_KIND')
        names=SCHEMAS[target['kind']]
        if any(not isinstance(target.get(k),str) or not target[k] for k in names):
            raise ValueError('INVALID_SEMANTIC_TARGET')
        return names

    def teach(self, utterance, target, persons, objects, source='teacher:grounded', context=None):
        if not isinstance(source,str) or not source:raise ValueError('SOURCE_REQUIRED')
        names=self._slots_for(target)
        inv=_inventory(persons,objects)
        toks=words(utterance)
        if not toks or len(toks)>30:raise ValueError('EMPTY_OR_LONG_UTTERANCE')
        # Find candidate surface references and align with target values.
        hits=[]
        for span,(typ,value) in inv.items():
            for i in range(len(toks)-len(span)+1):
                if tuple(toks[i:i+len(span)])==span:
                    roles=[r for r in names if target[r]==value and
                           (('P' if r in PERSON_ROLES else 'O') == typ)]
                    for role in roles:hits.append((i,i+len(span),role))
        # A missing person role may be deictic (speaker/addressee), but never
        # assume that for names that are visibly grounded by scene aliases.
        context=context or {}
        defaults={}
        active=[]
        for role in names:
            if any(r==role for _,_,r in hits):
                active.append(role)
            elif role in PERSON_ROLES:
                options=[tag for tag in ('speaker','addressee') if target[role]==context.get(tag)]
                if len(options)!=1:raise ValueError('UNGROUNDED_MISSING_ROLE')
                defaults[role]=options[0]
            else:raise ValueError('MISSING_OBJECT_GROUNDING')
        # Unique, total alignment is necessary. Ambiguous names/roles -> abstain.
        choices=[]
        def walk(remaining, used, picked):
            if not remaining:
                choices.append(picked.copy());return
            role=remaining[0]
            for a,b,r in hits:
                if r==role and not any(k in used for k in range(a,b)):
                    walk(remaining[1:], used.union(range(a,b)), picked+[(a,b,role)])
                    if len(choices)>2:return
        walk(active,set(),[])
        def make_pattern(choice):
            loc={a:(b,role) for a,b,role in choice}
            pat=[];i=0
            while i<len(toks):
                if i in loc:
                    b,role=loc[i];pat.append('@'+role);i=b
                else:pat.append(toks[i]);i+=1
            return pat
        if len(choices)!=1:
            # Unidentifiable role aliases may be resolved ONLY by previously
            # *contrasted* acquired patterns, never by fixed word order.
            supported=[ch for ch in choices
                       if (tuple(make_pattern(ch)) in self.patterns and
                           self.patterns[tuple(make_pattern(ch))][0]==target['kind'])]
            if len(supported)!=1:raise ValueError('AMBIGUOUS_SLOT_ALIGNMENT')
            choices=supported
        pattern=make_pattern(choices[0])
        # Meaning is never inferred from names (which are variable slots).
        self.examples.append({'kind':target['kind'],'pattern':list(pattern),'defaults':defaults,
            'source':source,'utterance':utterance})
        self._rebuild()
        return {'status':'ADMITTED','pattern':pattern,'kind':target['kind']}

    def _rebuild(self):
        counts=Counter((e['kind'],tuple(e['pattern']),tuple(sorted(e.get('defaults',{}).items())))
                       for e in self.examples)
        bypattern=defaultdict(set)
        for kind,pat,defaults in counts:bypattern[pat].add((kind,defaults))
        self.patterns={}
        for pat, interpretations in bypattern.items():
            if len(interpretations)!=1:continue
            kind,defaults=next(iter(interpretations))
            support=counts[(kind,pat,defaults)]
            if support>=self.min_support:
                self.patterns[pat]=(kind,support,dict(defaults))
        self.blocked=[list(p) for p,k in bypattern.items() if len(k)>1]

    def retract(self,source):
        self.examples=[e for e in self.examples if e['source']!=source]
        self._rebuild()

    def _matches_from(self, tokens, start, inv, context):
        """Exact learned word scaffold, typed multi-token slot spans."""
        for pat,(kind,support,defaults) in self.patterns.items():
            bindings={};pos=start;valid=True
            for elem in pat:
                if elem.startswith('@'):
                    role=elem[1:]
                    typ='P' if role in PERSON_ROLES else 'O'
                    choices=[]
                    for span,(t,val) in inv.items():
                        if t==typ and tuple(tokens[pos:pos+len(span)])==span:
                            choices.append((len(span),val))
                    if len(choices)!=1:
                        valid=False;break
                    n,val=choices[0];bindings[role]=val;pos+=n
                elif pos<len(tokens) and tokens[pos]==elem:
                    pos+=1
                else:valid=False;break
            if valid and pos>start:
                for role,channel in defaults.items():
                    if not isinstance(context.get(channel),str) or not context[channel]:
                        valid=False;break
                    bindings[role]=context[channel]
                if valid:yield pos, {'kind':kind,**bindings},support

    def parse(self, paragraph, persons, objects, max_events=12, context=None):
        toks=words(paragraph)
        if not toks or len(toks)>120:return {'status':'UNKNOWN','reason':'LENGTH'}
        inv=_inventory(persons,objects)
        context=context or {}
        # Unique global segmentation. Do not privilege punctuation, length,
        # parser order, or high-scoring readings if alternatives coexist.
        candidates={0:[[]]}
        for pos in range(len(toks)):
            if pos not in candidates:continue
            for end,meaning,support in self._matches_from(toks,pos,inv,context):
                for seq in candidates[pos]:
                    if len(seq)>=max_events:continue
                    proposed=seq+[meaning]
                    bucket=candidates.setdefault(end,[])
                    if proposed not in bucket:bucket.append(proposed)
                    if len(bucket)>1:bucket[:]=bucket[:2]
        final=candidates.get(len(toks),[])
        if len(final)==0:return {'status':'UNKNOWN','reason':'UNSUPPORTED_SURFACE'}
        if len(final)>1:return {'status':'UNKNOWN','reason':'AMBIGUOUS_COMPOSITION'}
        return {'status':'PARSED','scope':'NARRATED_ONLY','events':final[0],
                'tokens':len(toks),'boundaries_supplied':False}

    def to_dict(self):
        return {'min_support':self.min_support,'examples':self.examples}
    @classmethod
    def from_dict(cls,d):
        m=cls(d['min_support']);m.examples=list(d['examples']);m._rebuild();return m
    def digest(self):
        return hashlib.sha256(stable(self.to_dict()).encode()).hexdigest()


class NarrativeMind:
    """Counterfactual reading of *reported text*, NEVER authenticated observation."""
    def __init__(self):
        self.frames=[];self.states=[];self.reports=[];self.intentions=[]
        self.known=False
    def consume(self, parsed, source='utterance:external'):
        # Transactional: an invalid later event must never leave partial belief.
        if parsed.get('status')!='PARSED':return {'status':'UNKNOWN'}
        if not isinstance(source,str) or not source:raise ValueError('SOURCE_REQUIRED')
        state={};origin={};frames=[];states=[];reports=[];intentions=[]
        for i,frame in enumerate(parsed['events']):
            kind=frame['kind'];who=frame.get('actor');obj=frame['object'];root=f'{source}:narrated:{i}'
            if kind=='INITIAL':state[obj]=frame['holder'];origin[obj]=root
            elif kind=='INTENT':intentions.append({'actor':who,'object':obj,'recipient':frame['recipient'],'support':root})
            elif kind=='SUCCESS':
                if obj not in state:return {'status':'UNKNOWN','reason':'UNANCHORED_ACTION'}
                state[obj]=frame['recipient'];origin[obj]=root
            elif kind=='FAILURE':
                if obj not in state:return {'status':'UNKNOWN','reason':'UNANCHORED_ACTION'}
            elif kind=='REPORT':reports.append({'speaker':frame['speaker'],
                  'holder':frame['claim_holder'],'object':obj,'support':root,'scope':'REPORTED_ONLY'})
            elif kind=='NESTED_REPORT':reports.append({'speaker':frame['outer'],
                  'quoted_speaker':frame['inner'],'holder':frame['claim_holder'],
                  'object':obj,'support':root,'scope':'NESTED_REPORTED_ONLY'})
            frames.append({'frame':frame,'support':root,'source_scope':'NARRATED_ONLY'})
            states.append({'holder':state.copy(),'support':origin.copy()})
        self.frames=frames;self.states=states;self.reports=reports;self.intentions=intentions
        self.known=True
        return {'status':'ADMITTED_NARRATIVE','events':len(self.frames)}
    def ask_holder(self,obj,as_of=None):
        if not self.known:return {'status':'UNKNOWN'}
        ix=len(self.states)-1 if as_of is None else as_of
        if not isinstance(ix,int) or ix<0 or ix>=len(self.states):return {'status':'UNKNOWN'}
        val=self.states[ix]['holder'].get(obj)
        if val is None:return {'status':'UNKNOWN'}
        return {'status':'KNOWN','value':val,'scope':'NARRATED_ONLY',
                'support':self.states[ix]['support'][obj]}
    def to_dict(self):return {'frames':self.frames,'states':self.states,'reports':self.reports,
                               'intentions':self.intentions,'known':self.known}
    @classmethod
    def from_dict(cls,d):
        o=cls();o.frames=d['frames'];o.states=d['states'];o.reports=d['reports'];
        o.intentions=d['intentions'];o.known=d['known'];return o


def attested_atomic_story(mind, story_id, target):
    """Return existing SIM_HOST story roots matching the language lesson."""
    if not mind or story_id not in mind.stories:return []
    PatternInducer._slots_for(target)
    key='holder:'+target['object'];matches=[]
    for rec in mind.stories[story_id]['events']:
        ev=rec['event'];kind=target['kind'];match=False
        if kind=='INITIAL' and ev['kind']=='OBSERVE':
            match=ev['state'].get(key)==target['holder']
        elif kind=='INTENT' and ev['kind']=='INTENT':
            match=ev['actor']==target['actor'] and ev['changes'].get(key)==target['recipient']
        elif kind in ('SUCCESS','FAILURE') and ev['kind']=='ACTION':
            match=(ev['actor']==target['actor'] and ev['changes'].get(key)==target['recipient']
                   and ev['outcome']==('SUCCEEDED' if kind=='SUCCESS' else 'FAILED'))
        elif kind=='REPORT' and ev['kind']=='REPORT':
            c=ev['content'];match=(ev['speaker']==target['speaker'] and c.get('kind')=='STATE'
                   and c.get('key')==key and c.get('value')==target['claim_holder'])
        elif kind=='NESTED_REPORT' and ev['kind']=='REPORT':
            c=ev['content'];nested=c.get('content',{})
            match=(ev['speaker']==target['outer'] and c.get('kind')=='REPORT'
                   and c.get('speaker')==target['inner'] and nested.get('kind')=='STATE'
                   and nested.get('key')==key and nested.get('value')==target['claim_holder'])
        if match:matches.append(rec['root'])
    return matches
