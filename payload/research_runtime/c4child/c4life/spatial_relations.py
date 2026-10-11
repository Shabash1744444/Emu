"""Research G1.7: learn *unnamed* spatial relations from witnessed pairs.

The program provides general computable numeric comparison primitives. It does
NOT contain Russian relation names, a noun-to-role rule, or an English gloss.

The teaching simulator supplies a witnessed performed action and a separately
pointed reference object. This is still supervised grounding: it is NOT raw
vision, automatic object correspondence or the induction of unrestricted logic.

Each lexical surface acquires an axis/direction predicate and a learned ordering
of argument mentions; contradictory / insufficient evidence => abstain.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import hashlib,json
from .grounded_language import tokenize,_features,_canon


def _coord(obj):
    xs=obj.get('position')
    if not isinstance(xs,(list,tuple)) or not 2<=len(xs)<=8 or not all(type(x) in (float,int) for x in xs):
        raise ValueError('missing typed numeric position')
    if any(abs(x)>1e8 or x!=x for x in xs):raise ValueError('invalid position')
    return tuple(xs)


def _rel_candidates(target,anchor,epsilon=.25):
    a,b=_coord(target),_coord(anchor)
    if len(a)!=len(b):raise ValueError('coordinate dimensionality mismatch')
    return frozenset(f'axis:{i}:positive' if a[i]>b[i] else f'axis:{i}:negative'
       for i in range(len(a)) if abs(a[i]-b[i])>epsilon)


def _objects(scene):
    if not isinstance(scene,list) or len(scene)<3:raise ValueError('scene missing contrasts')
    found={}
    for o in scene:
        if not isinstance(o,dict) or 'id' not in o: raise ValueError('invalid object')
        k=str(o['id'])
        if k in found:raise ValueError('duplicate ID')
        _coord(o);_features(o)
        found[k]=o
    return found


class SpatialInducer:
    def __init__(self,min_support=12,precision=.95,contrast=.35):
        self.min_support=min_support;self.precision=precision;self.contrast=contrast
        self.examples=[];self.roots=set();self.hypotheses={};self.unresolved={}
        self.trained=False
        self.coordinate_frame=None

    def observe(self,phrase,root,witness,teacher,base_lexicon):
        if not isinstance(root,str) or not root.startswith('sandbox:') or root in self.roots:
            return False
        if not isinstance(teacher,str) or not teacher:raise ValueError('missing teacher identity')
        if witness.get('origin')!='SIMULATION':raise PermissionError('simulator receipt required')
        objs=_objects(witness['scene'])
        frames={o.get('coordinate_frame') for o in objs.values()}
        if len(frames)!=1 or not all(isinstance(x,str) and x for x in frames):
            raise ValueError('no single verified spatial coordinate frame')
        frame=next(iter(frames))
        if self.coordinate_frame is not None and self.coordinate_frame!=frame:
            raise ValueError('independent coordinate frames require a learned transform')
        tar,anc=str(witness['target']),str(witness['anchor'])
        if tar not in objs or anc not in objs or tar==anc:raise ValueError('bad scene pair')
        # The host independently points to the reference entity when demonstrating.
        if witness['operation'] not in [json.loads(x['atom'][len('operation:'):]) for x in base_lexicon.associations.values() if x['atom'].startswith('operation:')]:
            raise ValueError('unlearned operation demonstration')
        toks=tokenize(phrase)
        if len(toks)!=4 or len(set(toks))!=4:raise ValueError('research stage uses four nonrepeated symbols')
        known=[(i,t,base_lexicon.associations[t]['atom']) for i,t in enumerate(toks) if t in base_lexicon.associations]
        unknown=[(i,t) for i,t in enumerate(toks) if t not in base_lexicon.associations]
        if len(known)!=3 or len(unknown)!=1:raise ValueError('need known action/two referents and one unknown relation')
        operations=[x for x in known if x[2].startswith('operation:')]
        nouns=sorted([x for x in known if x[2].startswith('feature:')])
        if len(operations)!=1 or len(nouns)!=2:raise ValueError('invalid lexical slot inventory')
        if json.loads(operations[0][2][len('operation:'):])!=witness['operation']:
            raise ValueError('demo action vs utterance mismatch')
        target_feature=_features(objs[tar]);anchor_feature=_features(objs[anc])
        slots=[]
        for order in ('first_is_target','last_is_target'):
            ts,an=(nouns[0],nouns[1]) if order=='first_is_target' else (nouns[1],nouns[0])
            if ts[2] in target_feature and an[2] in anchor_feature:
                slots.append(order)
        if len(slots)!=1:
            raise ValueError('role mapping not independently identifiable')
        rel=unknown[0][1]
        candidates=_rel_candidates(objs[tar],objs[anc])
        if not candidates:raise ValueError('no measured relation')
        self.examples.append({'utterance':str(phrase),'relation':rel,'root':root,'teacher':teacher,
                              'role_order':slots[0],'candidates':sorted(candidates),
                              'witness':json.loads(_canon(witness))})
        self.roots.add(root);self.coordinate_frame=frame;self.trained=False
        return True

    def fit(self):
        byrel=defaultdict(list)
        for e in self.examples:byrel[e['relation']].append(e)
        hypo={};bad={}
        for word,examples in sorted(byrel.items()):
            if len(examples)<self.min_support:
                bad[word]='INSUFFICIENT_SUPPORT';continue
            roles=Counter(e['role_order'] for e in examples)
            if len(roles)!=1:
                bad[word]='INCONSISTENT_ROLE_ORDER';continue
            cand_all=Counter(c for e in examples for c in e['candidates'])
            candidates=[]
            for cand,n in cand_all.items():
                p=n/len(examples)
                # Candidate must ALSO be absent from different learned relation
                # demonstrations (negative contrast); otherwise "all targets
                # happened to the right" is not learnable as a unique relation.
                negative=[e for e in self.examples if e['relation']!=word]
                bg=sum(cand in e['candidates'] for e in negative)/len(negative) if negative else 1.
                if p>=self.precision and p-bg>=self.contrast:
                    candidates.append((cand,p,bg))
            if len(candidates)!=1:
                bad[word]='NO_UNIQUE_CONTRASTIVE_RELATION' if candidates else 'INSUFFICIENT_CONTRAST'
                continue
            c,p,bg=candidates[0]
            hypo[word]={'relation':c,'role_order':next(iter(roles)),'support':len(examples),
                        'precision':round(p,5),'background':round(bg,5),
                        'roots':[e['root'] for e in examples]}
        self.hypotheses=hypo;self.unresolved=bad;self.trained=True
        return {'learned_relations':len(hypo),'unresolved_relations':len(bad),'examples':len(self.examples)}

    def predict(self,utterance,scene,base_lexicon):
        if not self.trained:self.fit()
        toks=tokenize(utterance)
        if len(toks)!=4 or len(set(toks))!=4:
            return {'status':'UNKNOWN','reason':'SPATIAL_SEQUENCE_UNSUPPORTED'}
        unknown=[w for w in toks if w not in base_lexicon.associations]
        if len(unknown)!=1 or unknown[0] not in self.hypotheses:
            return {'status':'ASK','reason':'RELATION_NOT_LEARNED','unresolved_tokens':unknown}
        hyp=self.hypotheses[unknown[0]]
        mapped=[(i,t,base_lexicon.associations[t]['atom']) for i,t in enumerate(toks) if t in base_lexicon.associations]
        acts=[m[2] for m in mapped if m[2].startswith('operation:')]
        nouns=sorted((m for m in mapped if m[2].startswith('feature:')))
        if len(acts)!=1 or len(nouns)!=2:
            return {'status':'UNKNOWN','reason':'SPATIAL_ARGUMENTS_UNSUPPORTED'}
        if hyp['role_order']=='last_is_target':nouns.reverse()
        objs=_objects(scene)
        frames={o.get('coordinate_frame') for o in objs.values()}
        if frames!={self.coordinate_frame}:
            return {'status':'UNKNOWN','reason':'UNESTABLISHED_COORDINATE_FRAME'}
        tfeat,afeat=nouns[0][2],nouns[1][2]
        pairs=[]
        for a in objs.values():
            if tfeat not in _features(a):continue
            for b in objs.values():
                if a['id']==b['id'] or afeat not in _features(b):continue
                if hyp['relation'] in _rel_candidates(a,b):pairs.append((str(a['id']),str(b['id'])))
        if len(pairs)!=1:
            return {'status':'UNKNOWN','reason':'AMBIGUOUS_RELATIONAL_REFERENCE' if pairs else 'NO_RELATION_MATCH',
                    'candidate_pairs':len(pairs)}
        op=json.loads(acts[0][len('operation:'):])
        return {'status':'ACTION_PROPOSAL','sandbox_only':True,'operation':op,
                'target':pairs[0][0],'reference':pairs[0][1],
                'relation_evidence_count':hyp['support'],'language_evidence':'LEARNED_SPATIAL_RELATION_SIMULATION_ONLY',
                'evidence_roots':[]}

    def revoke(self,teacher):
        before=len(self.examples)
        self.examples=[e for e in self.examples if e['teacher']!=teacher]
        self.roots={e['root'] for e in self.examples}
        self.coordinate_frame=(self.examples[0]['witness']['scene'][0]['coordinate_frame'] if self.examples else None)
        self.trained=False;self.fit()
        return before-len(self.examples)

    def to_dict(self):
        if not self.trained:self.fit()
        return {'version':1,'min_support':self.min_support,'precision':self.precision,
                'contrast':self.contrast,'examples':self.examples,'coordinate_frame':self.coordinate_frame,
                'hypotheses':self.hypotheses,'unresolved':self.unresolved}

    @classmethod
    def from_dict(cls,record):
        m=cls(record['min_support'],record['precision'],record['contrast'])
        m.examples=record['examples'];m.roots={e['root'] for e in m.examples}
        m.coordinate_frame=record['coordinate_frame']
        m.fit()
        if m.hypotheses!=record['hypotheses'] or m.unresolved!=record['unresolved']:
            raise ValueError('spatial learning checksum / reproducibility violation')
        return m

    def digest(self):
        return hashlib.sha256(_canon(self.to_dict()).encode()).hexdigest()
