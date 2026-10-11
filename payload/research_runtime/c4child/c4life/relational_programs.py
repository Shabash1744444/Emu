"""G2.1 bounded *relational program induction*, without word-specific branches.

Teacher supplies language USE with paired positive/negative pointed episodes.
SIM_HOST independently attests two raw graph states. It supplies no relation name,
truth vector, or target operator. The learner generates generic feature programs
and infers a conjunction of <=2 literals. Programs are proposals about teacher
usage, not certificates of real-world facts. This is NOT unrestricted semantics.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib, itertools, json
from .grounded_language import tokenize


def canonical(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def witness_root(witness):
    return 'sandbox:rel:'+hashlib.sha256(canonical(witness).encode()).hexdigest()


def reach(edges,a,b):
    seen={a}; front=[a]; adj=defaultdict(list)
    for x,y in edges:adj[x].append(y)
    for p in front:
        for nxt in adj[p]:
            if nxt==b:return True
            if nxt not in seen:
                seen.add(nxt);front.append(nxt)
    return False


def features(w):
    if not isinstance(w,dict) or w.get('origin')!='SIMULATION':raise ValueError('no simulator witness')
    if 'meaning' in w or 'relation' in w or 'gold' in w or 'program' in w:
        raise ValueError('semantic target leakage in sensor witness')
    nodes=w.get('nodes');focus=w.get('focus');pre=w.get('before');post=w.get('after')
    if not isinstance(nodes,list) or len(nodes)<4 or len(set(nodes))!=len(nodes) or not isinstance(focus,list) or len(focus)!=2:
        raise ValueError('invalid graph nodes / paired referents')
    if len(set(focus))!=2 or not set(focus).issubset(nodes):raise ValueError('invalid referents')
    if not isinstance(pre,list) or not isinstance(post,list):raise ValueError('states required')
    a,b=focus;result={};nset=set(nodes)
    for suffix,elist in [('before',pre),('after',post)]:
        if any(not isinstance(e,list) or len(e)!=2 or e[0] not in nset or e[1] not in nset or e[0]==e[1] for e in elist):
            raise ValueError('malformed measured edges')
        if len({tuple(e) for e in elist})!=len(elist):raise ValueError('duplicate edges')
        edge_set={tuple(e) for e in elist}
        result['reachable_'+suffix]=reach(edge_set,a,b)
        result['direct_'+suffix]=(a,b) in edge_set
        result['two_hop_'+suffix]=any((a,m) in edge_set and (m,b) in edge_set for m in nodes if m not in (a,b))
        result['shared_out_'+suffix]=any((a,m) in edge_set and (b,m) in edge_set for m in nodes if m not in (a,b))
    result['edge_count_grew']=len(post)>len(pre)
    result['edge_count_shrank']=len(post)<len(pre)
    # The generic primitive vocabulary is designed before selecting a new word.
    # New *compositions* of these primitives are the learned predicates.
    return result


class RelationalInducer:
    def __init__(self,min_positive=18,min_negative=18,max_lits=2):
        self.min_positive=min_positive;self.min_negative=min_negative;self.max_lits=max_lits
        self.examples=[];self.roots=set();self.programs={};self.unknown={}

    def observe(self,word,positive_root,negative_root,receipts,source):
        toks=tokenize(word)
        if len(toks)!=1:raise ValueError('one unknown surface label per lesson; general sentence parsing NOT learned')
        if not source:raise ValueError('teacher source missing')
        if positive_root==negative_root or positive_root in self.roots or negative_root in self.roots:
            raise ValueError('reused/aliased witness')
        if positive_root not in receipts or negative_root not in receipts:raise PermissionError('missing host witnesses')
        pair=[]
        for root in (positive_root,negative_root):
            witness=receipts[root]
            if witness_root(witness)!=root:raise PermissionError('content-address witness mismatch')
            ff=features(witness)
            pair.append({'root':root,'witness':json.loads(canonical(witness)),'features':ff})
        if pair[0]['features']==pair[1]['features']:
            raise ValueError('no observable distinction in pointed contrast')
        self.examples.append({'word':toks[0],'source':source,'positive':pair[0],'negative':pair[1]})
        self.roots.update((positive_root,negative_root))
        self.fit()
        return True

    @staticmethod
    def _literal_match(ff,lit):
        return ff[lit[1:]] is False if lit.startswith('!') else ff[lit] is True

    @classmethod
    def _matches(cls,ff,prog):
        return all(cls._literal_match(ff,s) for s in prog)

    def fit(self):
        self.programs={};self.unknown={}
        groups=defaultdict(list)
        for e in self.examples:groups[e['word']].append(e)
        for w,ex in sorted(groups.items()):
            pos=[e['positive']['features'] for e in ex];neg=[e['negative']['features'] for e in ex]
            worlds={e['positive']['witness'].get('world') for e in ex}
            worlds|={e['negative']['witness'].get('world') for e in ex}
            if len(pos)<self.min_positive or len(neg)<self.min_negative or len(worlds)<2:
                self.unknown[w]='INSUFFICIENT_CONTRAST_OR_DOMAINS';continue
            fkeys=sorted(pos[0]);candidates=[]
            for size in range(1,self.max_lits+1):
                for dims in itertools.combinations(fkeys,size):
                    for signs in itertools.product([False,True],repeat=size):
                        prog=tuple(('' if sign else '!')+dim for dim,sign in zip(dims,signs))
                        if all(self._matches(f,prog) for f in pos) and not any(self._matches(f,prog) for f in neg):
                            candidates.append(prog)
                if candidates:break
            if not candidates:self.unknown[w]='NO_DISCRIMINATIVE_PROGRAM';continue
            # NO arbitrary tiebreak on incompatible hypotheses. They must all have
            # identical predictions on a query or learner returns UNKNOWN.
            self.programs[w]={'hypotheses':[list(p) for p in candidates],
                'complexity':len(candidates[0]),'positive':len(pos),'negative':len(neg),
                'domains':sorted(str(x) for x in worlds),
                'sources':sorted({e['source'] for e in ex})}
        return {'learned':len(self.programs),'unresolved':self.unknown.copy()}

    def predict(self,word,w):
        toks=tokenize(word)
        if len(toks)!=1:return {'status':'UNKNOWN','reason':'COMPOUND_EXPRESSION_UNSUPPORTED'}
        label=toks[0]
        if label not in self.programs:return {'status':'ASK','reason':self.unknown.get(label,'UNKNOWN_WORD'),
                  'question':{'intent':'REQUEST_RELATIONAL_CONTRAST','symbol':label}}
        ff=features(w)
        prog=self.programs[label]
        opinions={self._matches(ff,p) for p in prog['hypotheses']}
        if len(opinions)!=1:return {'status':'UNKNOWN','reason':'MULTIPLE_UNRESOLVED_PROGRAMS','hypotheses':len(prog['hypotheses'])}
        return {'status':'CANDIDATE_RELATION','holds':opinions.pop(),'scope':'SIMULATION',
            'kind':'LEARNED_LINGUISTIC_RELATION','program_hypotheses':len(prog['hypotheses']),
            'positive_support':prog['positive'],'negative_support':prog['negative'],
            'note':'not independently certified about real-world facts'}

    def revoke(self,source):
        count=len(self.examples)
        self.examples=[e for e in self.examples if e['source']!=source]
        self.roots={x['root'] for e in self.examples for x in (e['positive'],e['negative'])}
        self.fit()
        return count-len(self.examples)

    def to_dict(self):
        return {'version':'G2.1','min_positive':self.min_positive,'min_negative':self.min_negative,
                'max_lits':self.max_lits,'examples':self.examples,'programs':self.programs,'unknown':self.unknown}

    @classmethod
    def from_dict(cls,d):
        m=cls(d['min_positive'],d['min_negative'],d['max_lits'])
        m.examples=d['examples'];m.roots={x['root'] for e in m.examples for x in (e['positive'],e['negative'])}
        m.fit()
        if canonical(m.programs)!=canonical(d['programs']) or canonical(m.unknown)!=canonical(d['unknown']):
            raise ValueError('relational-state integrity error')
        return m

    def digest(self):return hashlib.sha256(canonical(self.to_dict()).encode()).hexdigest()
