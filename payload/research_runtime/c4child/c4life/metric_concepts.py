"""G2.3: contrastive metric-comparison induction from externally timestamped traces.

This learns which of a finite, generic family of cross-channel comparisons a
teacher's *one-word label* denotes. No semantic class / Russian word is built in.
This is NOT a universal concept inventor, speech interpreter, or causal learner.
Timing is from witnessed timestamps, never the internal C4 tick counter.
"""
from __future__ import annotations
from collections import defaultdict
from itertools import combinations
import hashlib,json,math
from .grounded_language import tokenize


def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def metric_root(w):return 'sandbox:metric:'+hashlib.sha256(canon(w).encode()).hexdigest()


def measured(w):
    if not isinstance(w,dict) or w.get('origin')!='SIMULATION':raise ValueError('simulator witness required')
    if any(x in w for x in ('gold','truth','meaning','target','concept','program','label','relation')):raise ValueError('semantic leakage')
    channels=w.get('channels')
    if not isinstance(channels,list) or len(channels)!=2:raise ValueError('exactly two independently measured channels')
    out=[];ids=set()
    for c in channels:
        if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'] or c['id'] in ids:raise ValueError('duplicate/bad channels')
        ids.add(c['id'])
        r=c.get('readings')
        if not isinstance(r,list) or not 4<=len(r)<=9:raise ValueError('4..9 readings per channel')
        vals=[];ts=[]
        for e in r:
            if not isinstance(e,dict) or set(e)!={'t','value'}:raise ValueError('raw timestamp and value only')
            t=e['t'];v=e['value']
            if type(t)!=int or abs(t)>10**15 or (ts and t<=ts[-1]):raise ValueError('invalid/nonmonotone event time')
            if (type(v) not in (str,int,float,bool) or (type(v)==str and not v) or
                (type(v)==float and not math.isfinite(v))):raise ValueError('malformed sensor observation')
            ts.append(t);vals.append((type(v).__name__,v))
        changes=[i for i in range(1,len(r)) if vals[i]!=vals[i-1]]
        if len(changes)<2:raise ValueError('at least two observed transitions required')
        out.append((ts,changes))
    return out


def measurements(w):
    streams=measured(w);features=[]
    for ts,changes in streams:
        gaps=[b-a for a,b in zip(ts,ts[1:])]
        # The same algebra is applied to *every* channel. Label names are
        # unknown to this feature constructor; all features come from times.
        d={'start':ts[0],'end':ts[-1], 'span':ts[-1]-ts[0],
           'change_first':ts[changes[0]],'change_last':ts[changes[-1]],
           'change_span':ts[changes[-1]]-ts[changes[0]],
           'gap_first':gaps[0], 'gap_last':gaps[-1],
           'gap_min':min(gaps),'gap_max':max(gaps),
           'changes':len(changes)}
        features.append(d)
    return features


def comparator_values(w):
    f0,f1=measurements(w)
    # Role positions are supplied by the measuring host. For every available
    # *same* numeric descriptor compare its values without semantic labels.
    # This naturally yields duration comparisons AND timing synchrony.
    result={}
    for key in sorted(f0.keys()&f1.keys()):
        a,b=f0[key],f1[key]
        result[key]= -1 if a<b else (1 if a>b else 0)
    return result


class MetricInducer:
    def __init__(self,min_lessons=18,min_worlds=2):
        self.min_lessons=min_lessons;self.min_worlds=min_worlds
        self.examples=[];self.roots=set();self.programs={};self.unresolved={}

    def observe(self,label,posroot,negroot,receipts,source):
        tt=tokenize(label)
        if len(tt)!=1:raise ValueError('label must be exactly one token; free text not supported')
        if not isinstance(source,str) or not source:raise ValueError('attributable teacher required')
        if posroot==negroot or posroot in self.roots or negroot in self.roots:raise ValueError('replayed receipt')
        if posroot not in receipts or negroot not in receipts:raise PermissionError('independent simulator receipt missing')
        rows=[]
        for root in (posroot,negroot):
            w=receipts[root]
            if metric_root(w)!=root:raise PermissionError('content-addressed witness mismatch')
            rows.append({'root':root,'witness':json.loads(canon(w)), 'features':comparator_values(w)})
        if rows[0]['features']==rows[1]['features']:
            raise ValueError('no distinguishable measurement contrast')
        self.examples.append({'label':tt[0],'positive':rows[0],'negative':rows[1],'source':source})
        self.roots.update([posroot,negroot]);self.fit()
        return True

    def fit(self):
        self.programs={};self.unresolved={};grouped=defaultdict(list)
        for row in self.examples:grouped[row['label']].append(row)
        for label,lessons in sorted(grouped.items()):
            worlds={row[side]['witness'].get('world') for row in lessons for side in ('positive','negative')}
            if len(lessons)<self.min_lessons or len(worlds)<self.min_worlds:
                self.unresolved[label]='INSUFFICIENT_DIVERSE_LESSONS';continue
            names=set(lessons[0]['positive']['features'])
            candidates=[]
            for size in (1,2):
                for name in sorted(names):
                    for allowed in combinations((-1,0,1),size):
                        if all(row['positive']['features'][name] in allowed and row['negative']['features'][name] not in allowed for row in lessons):
                            candidates.append([name,list(allowed)])
                if candidates:break  # minimum complexity, disjunction only when necessary
            if candidates:self.programs[label]={'candidates':candidates,'lessons':len(lessons),'worlds':sorted(map(str,worlds))}
            else:self.unresolved[label]='NO_CONSISTENT_MEASURED_COMPARISON'
        return len(self.programs)

    def predict(self,label,w):
        tt=tokenize(label)
        if len(tt)!=1:return {'status':'UNKNOWN','reason':'FREE_SYNTAX_NOT_LEARNED'}
        label=tt[0]
        if label not in self.programs:return {'status':'ASK','reason':self.unresolved.get(label,'UNKNOWN_LABEL')}
        vals=comparator_values(w)
        prog=self.programs[label]
        choices={vals[k] in allowed for k,allowed in prog['candidates']}
        if len(choices)!=1:return {'status':'UNKNOWN','reason':'UNRESOLVED_COMPARISONS','candidate_count':len(prog['candidates'])}
        return {'status':'CANDIDATE_METRIC_RELATION','holds':choices.pop(),'support':prog['lessons'],
                'scope':'SIMULATION','note':'linguistic hypothesis, not real-world fact'}

    def revoke(self,source):
        before=len(self.examples)
        self.examples=[e for e in self.examples if e['source']!=source]
        self.roots={e[side]['root'] for e in self.examples for side in ('positive','negative')}
        self.fit();return before-len(self.examples)

    def to_dict(self):
        return {'version':'G2.3','min_lessons':self.min_lessons,'min_worlds':self.min_worlds,
                'examples':self.examples,'programs':self.programs,'unresolved':self.unresolved}

    @classmethod
    def from_dict(cls,d):
        m=cls(d['min_lessons'],d['min_worlds']);m.examples=d['examples'];roots=set()
        for e in m.examples:
            if not isinstance(e['label'],str) or not isinstance(e['source'],str):raise ValueError('corrupt source label')
            for side in ('positive','negative'):
                row=e[side];root=row['root']
                if root in roots or root!=metric_root(row['witness']) or row['features']!=comparator_values(row['witness']):
                    raise ValueError('replay or forged/changed metric witness')
                roots.add(root)
        m.roots=roots;m.fit()
        if canon(m.programs)!=canon(d['programs']) or canon(m.unresolved)!=canon(d['unresolved']):
            raise ValueError('corrupt learned program state')
        return m

    def digest(self):return hashlib.sha256(canon(self.to_dict()).encode()).hexdigest()
