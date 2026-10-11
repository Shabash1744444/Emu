"""G1.5: acquire open-class lexical meaning from attested situated demonstrations.

NO built-in Russian words, parts of speech, or grammar. Bootstraps from a *typed*
perception/action interface: observed attributes for seen entities, target entity
and operation of a performed demonstration. A teacher merely supplies a surface
utterance associated with that witnessed action, not its interpretation.

This is cross-situational lexical grounding, NOT unsupervised world-object discovery,
free speech understanding, or independent proof that a teacher's words are true.
All proposed actions are sandbox-only and require independent DRIVE authorization.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import json
import re


def _canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',',':'))


def tokenize(utterance):
    if not isinstance(utterance,str): raise TypeError('utterance must be text')
    # Supplied space-delimited symbols. Not audio segmentation or Russian grammar.
    return tuple(x for x in (t.strip('.,!?;:«»()[]{}"“”').casefold() for t in utterance.split()) if x)


def _features(obj):
    attrs=obj.get('features')
    if not isinstance(attrs,dict) or not attrs: raise ValueError('missing sensor features')
    return {f'feature:{_canon([str(k),v])}' for k,v in attrs.items()}


def _atoms(receipt):
    scene=receipt['scene']; target=str(receipt['target']); op=str(receipt['operation'])
    obj=next((x for x in scene if str(x['id'])==target),None)
    if obj is None: raise ValueError('receipt target not present in sensor scene')
    return frozenset(_features(obj)|{'operation:'+_canon(op)})


class SituatedLexicon:
    """Conservative cross-situational token -> observed atom learner.

    For each token, compute its empirical conditional precision on distinct
    attested demonstration roots. Contexts must vary: multiple distinct target
    feature/action signatures required. A token can be associated with at most
    one atom. A hidden unknown token cannot silently become an ignored filler.
    """
    def __init__(self,min_support=8,precision=.94,background_margin=.35):
        self.min_support=int(min_support)
        self.precision=float(precision)
        self.background_margin=float(background_margin)
        self.examples=[]
        self.roots=set()
        self.associations={}
        self.ambiguous={}
        self.trained=False
        from .spatial_relations import SpatialInducer
        self.spatial=SpatialInducer()

    def observe(self,utterance,receipt_root,verified_receipts,teacher_source):
        if not isinstance(teacher_source,str) or not teacher_source:raise ValueError('missing attributable teacher')
        if not isinstance(receipt_root,str) or receipt_root not in verified_receipts:
            raise PermissionError('missing independently attested simulator receipt')
        if receipt_root in self.roots:
            return False
        receipt=verified_receipts[receipt_root]
        if not isinstance(receipt,dict) or receipt.get('origin')!='SIMULATION':
            raise PermissionError('not a sandbox receipt')
        if 'scene' not in receipt or 'target' not in receipt or 'operation' not in receipt:
            raise ValueError('malformed sensor-action witness')
        if 'anchor' in receipt:
            # G1.7: verified two-referent demonstration; do not contaminate the
            # old unary noun/action contingency learner with reference nouns.
            if not self.trained:self.fit()
            return self.spatial.observe(utterance,receipt_root,receipt,teacher_source,self)
        scene=receipt['scene']
        if not isinstance(scene,list) or len(scene)<2:raise ValueError('need a contrasting scene')
        if len({str(o['id']) for o in scene})!=len(scene):raise ValueError('duplicate scene IDs')
        toks=tokenize(utterance)
        if not toks or len(set(toks))!=len(toks):raise ValueError('empty/repeated token')
        atoms=_atoms(receipt)
        # Keep immutable copies of the *verified* witness, not caller-supplied gold.
        witness=json.loads(_canon(receipt))
        self.examples.append({'utterance':str(utterance),'tokens':list(toks),'root':receipt_root,
                              'teacher':teacher_source,'witness':witness,'atoms':sorted(atoms)})
        self.roots.add(receipt_root);self.trained=False
        return True

    def fit(self):
        word_count=Counter(); atom_count=Counter(); both=defaultdict(Counter)
        contexts=defaultdict(set); examples=self.examples
        for e in examples:
            words=set(e['tokens']); atoms=set(e['atoms'])
            for a in atoms:atom_count[a]+=1
            for w in words:
                word_count[w]+=1
                contexts[w].add(tuple(sorted(atoms)))
                for a in atoms:both[w][a]+=1
        n=len(examples); mapping={}; ambiguity={}
        for w,total in sorted(word_count.items()):
            if total<self.min_support or len(contexts[w])<3:
                ambiguity[w]='INSUFFICIENT_CONTRAST';continue
            candidates=[]
            for atom,joint in both[w].items():
                precision=joint/total
                # Difference between present-token and absent-token conditional rates.
                absent=n-total
                background=(atom_count[atom]-joint)/absent if absent else 1.0
                if precision>=self.precision and precision-background>=self.background_margin:
                    candidates.append((atom,precision,background,joint))
            if len(candidates)==1:
                atom,p,b,j=candidates[0]
                mapping[w]={'atom':atom,'support':total,'precision':round(p,5),
                            'background':round(b,5),'joint':j}
            else:ambiguity[w]='NO_UNIQUE_GROUNDED_ATOM' if candidates else 'UNSUPPORTED'
        self.associations=mapping;self.ambiguous=ambiguity;self.trained=True
        return {'examples':n,'learned_tokens':len(mapping),'unresolved_tokens':len(ambiguity)}

    def predict(self,utterance,scene):
        if not self.trained:self.fit()
        toks=tokenize(utterance)
        if not self.spatial.trained:self.spatial.fit()
        if any(w in self.spatial.hypotheses for w in toks):
            return self.spatial.predict(utterance,scene,self)
        if not toks:return {'status':'UNKNOWN','reason':'EMPTY'}
        if not isinstance(scene,list) or not scene:
            return {'status':'UNKNOWN','reason':'NO_SCENE'}
        if len(set(toks))!=len(toks):
            return {'status':'UNKNOWN','reason':'REPETITION_UNSUPPORTED'}
        unknown=[w for w in toks if w not in self.associations]
        if unknown:
            return {'status':'ASK','reason':'MEANING_UNRESOLVED',
                    'question':{'intent':'REQUEST_GROUNDED_EXAMPLE','symbol':unknown[0]},
                    'unresolved_tokens':unknown}
        atoms=[self.associations[w]['atom'] for w in toks]
        acts={a for a in atoms if a.startswith('operation:')}
        feature_atoms={a for a in atoms if a.startswith('feature:')}
        if len(acts)!=1 or not feature_atoms:
            return {'status':'UNKNOWN','reason':'UNSUPPORTED_COMPOSITION'}
        if len(atoms)!=len(set(atoms)):
            return {'status':'UNKNOWN','reason':'REDUNDANT_MEANING_UNVERIFIED'}
        matches=[]
        for obj in scene:
            if feature_atoms.issubset(_features(obj)):
                matches.append(str(obj['id']))
        if len(matches)!=1:
            return {'status':'UNKNOWN','reason':'AMBIGUOUS_REFERENT' if len(matches)>1 else 'NO_GROUNDED_REFERENT',
                    'candidates':len(matches)}
        return {'status':'ACTION_PROPOSAL','sandbox_only':True,'operation':json.loads(next(iter(acts))[len('operation:'):]),
                'target':matches[0],'evidence_roots':[], 'learning_support':min(self.associations[w]['support'] for w in toks),
                'language_evidence':'OBSERVED_DEMONSTRATIONS_NOT_WORLD_TRUTH'}

    def revoke(self,teacher_source):
        before=len(self.examples)
        self.examples=[e for e in self.examples if e['teacher']!=teacher_source]
        self.roots={e['root'] for e in self.examples}
        rel_removed=self.spatial.revoke(teacher_source)
        self.trained=False;self.fit()
        return before-len(self.examples)+rel_removed

    def to_dict(self):
        if not self.trained:self.fit()
        return {'version':'G1.5','min_support':self.min_support,'precision':self.precision,
                'background_margin':self.background_margin,'examples':self.examples,
                'associations':self.associations,'ambiguous':self.ambiguous,
                'spatial':self.spatial.to_dict()}

    @classmethod
    def from_dict(cls,d):
        m=cls(d['min_support'],d['precision'],d['background_margin'])
        m.examples=d['examples'];m.roots={e['root'] for e in m.examples}
        if d.get('spatial'):
            from .spatial_relations import SpatialInducer
            m.spatial=SpatialInducer.from_dict(d['spatial'])
        m.fit()
        if m.associations!=d['associations'] or m.ambiguous!=d['ambiguous']:
            raise ValueError('grounding checkpoint failed deterministic restoration')
        return m

    def digest(self):
        return hashlib.sha256(_canon(self.to_dict()).encode('utf-8')).hexdigest()
