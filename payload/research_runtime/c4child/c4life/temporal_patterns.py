"""G2.2: bounded relational *feature construction* over raw, opaque sensor sequences.

No predefined concept for return / alternation / nesting etc.  A generic
program grammar enumerates equality/inequality constraints among sampled values
in a four-observation temporal window. Learns teacher's convention from
content-addressed independent simulator traces and negative contrasts.

Honest boundary: finite 4-step windows, symbol equality and sequential-order
primitives are BUILT IN. This does NOT invent raw sensor physics or arbitrary
semantics, nor imply understanding Russian utterances.
"""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
from itertools import combinations, product
import hashlib, json, math
from .grounded_language import tokenize


def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def trace_root(w):
    return 'sandbox:temporal:'+hashlib.sha256(canonical(w).encode()).hexdigest()


def _key(v):
    # Distinguish numeric, boolean and string sensor symbols (without hardcoding labels).
    if isinstance(v,bool):return ('boolean',int(v))
    if isinstance(v,int):return ('integer',v)
    if isinstance(v,str) and v:return ('symbol',v)
    if isinstance(v,float) and math.isfinite(v):return ('real',v)
    raise ValueError('invalid finite sensor value')


def signature(values):
    """Canonical partition code; invariant to arbitrary renaming of sensor values."""
    seen={};out=[]
    for v in values:
        k=_key(v)
        if k not in seen:seen[k]=len(seen)
        out.append(seen[k])
    return tuple(out)


def validate_trace(w):
    if not isinstance(w,dict) or w.get('origin')!='SIMULATION':raise ValueError('simulator witness required')
    if any(k in w for k in ('gold','meaning','target','concept','program','relation','truth')):
        raise ValueError('semantic label leakage')
    readings=w.get('readings');focus=w.get('focus_sensor')
    if not isinstance(readings,list) or not (4<=len(readings)<=12):raise ValueError('4..12 time ordered sensor readings required')
    if not isinstance(focus,str) or not focus:raise ValueError('unidentified focal sensor')
    keys=None;prev=None;seq=[]
    for frame in readings:
        if not isinstance(frame,dict) or not isinstance(frame.get('t'),int) or isinstance(frame['t'],bool):raise ValueError('event timestamps required')
        if prev is not None and frame['t']<=prev:raise ValueError('nonmonotone external timestamp')
        prev=frame['t']
        sensors=frame.get('sensors')
        if not isinstance(sensors,dict) or focus not in sensors or not (1<=len(sensors)<=8):raise ValueError('sensor dictionary incomplete')
        if not all(isinstance(n,str) and n for n in sensors):raise ValueError('malformed sensor names')
        if keys is None:keys=set(sensors)
        if keys!=set(sensors):raise ValueError('changing sensor topology')
        for v in sensors.values():_key(v)
        seq.append(sensors[focus])
    return seq


def patterns(w):
    seq=validate_trace(w)
    return tuple(sorted({signature(seq[i:i+4]) for i in range(len(seq)-3)}))


def _all_partitions(n=4):
    if n==0:return [()]
    out=[(0,)]
    for _ in range(n-1):
        out=[p+(new,) for p in out for new in range(max(p)+2)]
    return sorted(out)


PAIRS=tuple(combinations(range(4),2))
PARTITIONS=tuple(_all_partitions())
_PART_INDEX={p:i for i,p in enumerate(PARTITIONS)}


@lru_cache(maxsize=4)
def candidate_programs(max_lits=4):
    """Blind enumerator: no class names; generic low-complexity equality predicates."""
    out=[]
    for count in range(1,max_lits+1):
        for edge_ids in combinations(range(len(PAIRS)),count):
            for bits in product([0,1],repeat=count):
                clause=tuple((edge_id,bit) for edge_id,bit in zip(edge_ids,bits))
                truth=0
                for ix,p in enumerate(PARTITIONS):
                    if all((p[PAIRS[edge][0]]==p[PAIRS[edge][1]])==bool(bit) for edge,bit in clause):
                        truth|=1<<ix
                if truth:out.append((clause,truth))
    return tuple(out)


def witness_bits(w):
    mask=0
    for p in patterns(w):mask|=1<<_PART_INDEX[p]
    return mask


class TemporalInducer:
    def __init__(self,min_examples=12,max_lits=4):
        self.min_examples=min_examples;self.max_lits=max_lits
        self.examples=[];self.roots=set();self.programs={};self.unknown={}

    def observe(self,word,positive_root,negative_root,receipts,source):
        t=tokenize(word)
        if len(t)!=1:raise ValueError('one label per contrasted lesson; free Russian not supported')
        if not isinstance(source,str) or not source:raise ValueError('unknown teacher source')
        if positive_root==negative_root or positive_root in self.roots or negative_root in self.roots:
            raise ValueError('receipt replay cannot multiply evidence')
        if positive_root not in receipts or negative_root not in receipts:raise PermissionError('not host witnessed')
        rows=[]
        for root in (positive_root,negative_root):
            w=receipts[root]
            if trace_root(w)!=root:raise PermissionError('witness hash does not match')
            mask=witness_bits(w)
            rows.append({'root':root,'witness':json.loads(canonical(w)),'pattern_bits':mask})
        if rows[0]['pattern_bits']==rows[1]['pattern_bits']:
            raise ValueError('no sensor difference measurable with current representation')
        self.examples.append({'word':t[0],'positive':rows[0], 'negative':rows[1], 'source':source})
        self.roots.update([positive_root,negative_root])
        self.fit()
        return True

    def fit(self):
        self.programs={};self.unknown={}
        groups=defaultdict(list)
        for e in self.examples:groups[e['word']].append(e)
        for word,ex in sorted(groups.items()):
            pos=[e['positive']['pattern_bits'] for e in ex]
            neg=[e['negative']['pattern_bits'] for e in ex]
            worlds={e[s]['witness'].get('world') for e in ex for s in ('positive','negative')}
            if len(ex)<self.min_examples or len(worlds)<2:
                self.unknown[word]='INSUFFICIENT_WORLD_DIVERSITY_OR_CONTRAST';continue
            candidates=[];mincomplexity=None
            for clause,mask in candidate_programs(self.max_lits):
                size=len(clause)
                if mincomplexity and size>mincomplexity:break
                if all(mask & p for p in pos) and all(not (mask & n) for n in neg):
                    candidates.append([[int(idx),int(bit)] for idx,bit in clause])
                    mincomplexity=size
            if not candidates:
                self.unknown[word]='NO_DISCRIMINATIVE_TEMPORAL_PROGRAM';continue
            self.programs[word]={'hypotheses':candidates,'complexity':mincomplexity,
                                 'lessons':len(ex),'domains':sorted(str(x) for x in worlds)}
        return {'learned':len(self.programs),'unresolved':dict(self.unknown)}

    @staticmethod
    def program_mask(clause):
        m=0
        for ix,p in enumerate(PARTITIONS):
            if all((p[PAIRS[idx][0]]==p[PAIRS[idx][1]])==bool(eq) for idx,eq in clause):
                m|=1<<ix
        return m

    def predict(self,word,w):
        t=tokenize(word)
        if len(t)!=1:return {'status':'UNKNOWN','reason':'FREE_SYNTAX_NOT_LEARNED'}
        if t[0] not in self.programs:return {'status':'ASK','reason':self.unknown.get(t[0],'UNKNOWN_LABEL')}
        mask=witness_bits(w);p=self.programs[t[0]]
        choices={bool(mask & self.program_mask(c)) for c in p['hypotheses']}
        if len(choices)!=1:return {'status':'UNKNOWN','reason':'UNRESOLVED_PROGRAMS','hypotheses':len(p['hypotheses'])}
        return {'status':'CANDIDATE_TEMPORAL_RELATION','holds':choices.pop(),
                'scope':'SIMULATION','hypotheses':len(p['hypotheses']),
                'support':p['lessons'],'note':'teacher usage hypothesis, not world fact'}

    def revoke(self,source):
        before=len(self.examples)
        self.examples=[e for e in self.examples if e['source']!=source]
        self.roots={row['root'] for e in self.examples for row in (e['positive'],e['negative'])}
        self.fit()
        return before-len(self.examples)

    def to_dict(self):
        return {'version':'G2.2','min_examples':self.min_examples,'max_lits':self.max_lits,
                'examples':self.examples,'programs':self.programs,'unknown':self.unknown}

    @classmethod
    def from_dict(cls,d):
        m=cls(d['min_examples'],d['max_lits'])
        m.examples=d['examples']
        roots=set()
        for e in m.examples:
            if not isinstance(e.get('word'),str) or not isinstance(e.get('source'),str):
                raise ValueError('corrupt lesson attribution')
            for side in ('positive','negative'):
                x=e[side];root=x['root']
                if root in roots or trace_root(x['witness'])!=root or witness_bits(x['witness'])!=x['pattern_bits']:
                    raise ValueError('corrupt, replayed, or ungrounded temporal evidence')
                roots.add(root)
        m.roots=roots
        m.fit()
        if canonical(m.programs)!=canonical(d['programs']) or canonical(m.unknown)!=canonical(d['unknown']):
            raise ValueError('temporal induction state altered or corrupt')
        return m

    def digest(self):return hashlib.sha256(canonical(self.to_dict()).encode()).hexdigest()
