"""G2.9 research: grounded, defeasible linguistic anaphora induction.

The host supplies independently attested candidate referents, not an answer
at inference. A teacher provides surface form in an actual witnessed turn,
paired with an independently attested target. The learner induces which
*structural* candidate selectors are consistent across contrasting episodes.
No Russian pronouns, gender endings, or world truths are in this code.

Scopes: an utterance about a person is not proof of that person's physical
identity. Resolving a reference never makes narrated text a world fact.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib,json,re


def words(text):
    return re.findall(r'[^\W_]+',text.casefold(),re.UNICODE)


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


# These operators are GENERAL feature tests; none contains a natural word.
# An absent or non-unique selector abstains; tie-breaking by name is forbidden.
def programs(candidates):
    groups=defaultdict(list)
    for c in candidates:
        groups[('KIND',c['kind'])].append(c)
        if c.get('agreement') is not None:
            groups[('AGREEMENT',c['agreement'])].append(c)
            groups[('KIND_CLASS',c['kind'],c['agreement'])].append(c)
        groups[('ROLE',c['role'])].append(c)
        groups[('KIND_ROLE',c['kind'],c['role'])].append(c)
    results={}
    for p,arr in groups.items():
        if len(arr)==1:results[canonical(p)]=arr[0]['ref']
        # Allow a structurally grounded recency relation, but only when one
        # candidate has *strictly* highest recency, never on equal times.
        if len(arr)>1:
            arr=sorted(arr,key=lambda a:a['age'])
            if arr[0]['age']<arr[1]['age']:
                results[canonical(('LATEST',)+p)]=arr[0]['ref']
    if len(candidates)==1:results[canonical(('UNIQUE_CONTEXT',))]=candidates[0]['ref']
    return results


class ContextReferenceLearner:
    def __init__(self,min_support=3):
        self.min_support=int(min_support)
        self.lessons=[]

    @staticmethod
    def candidates_ok(candidates):
        if not isinstance(candidates,list) or len(candidates)>24:return False
        for c in candidates:
            if not isinstance(c,dict) or not isinstance(c.get('ref'),str) or not c['ref']:
                return False
            if c.get('kind') not in ('PERSON','OBJECT','EVENT') or c.get('role') not in (
                'ACTOR','PATIENT','RECIPIENT','TOPIC','POSSESSOR'):return False
            if type(c.get('age')) is not int or c['age']<1:return False
            a=c.get('agreement')
            if a is not None and (not isinstance(a,str) or not a or len(a)>32):return False
        return len({c['ref'] for c in candidates})==len(candidates)

    def teach(self,utterance,surface,candidates,target_ref,source,grounding_root,turn_key):
        if not all(isinstance(s,str) and s for s in (utterance,surface,target_ref,source,turn_key)):
            raise ValueError('INVALID_REFERENCE_DEMONSTRATION')
        toks=words(utterance);term=words(surface)
        if len(term)!=1 or toks.count(term[0])!=1:
            raise ValueError('REFERENCE_MUST_APPEAR_ONCE_AS_FULL_TOKEN')
        if not self.candidates_ok(candidates):raise ValueError('INVALID_CONTEXT_CANDIDATES')
        if target_ref not in [c['ref'] for c in candidates]:raise ValueError('TARGET_NOT_IN_PREVIOUS_ATTESTED_CONTEXT')
        if type(grounding_root) is not int or grounding_root<0:raise ValueError('NO_ATTESTED_GROUNDING_ROOT')
        x={'word':term[0],'candidates':candidates,'target_ref':target_ref,
           'source':source,'grounding_root':grounding_root,'turn_key':turn_key,'active':True}
        if any(e==x for e in self.lessons):raise ValueError('DUPLICATE_REFERENCE_LESSON')
        self.lessons.append(x)
        return {'status':'LANGUAGE_HYPOTHESIS_ADMITTED','surface':term[0],'candidates':len(candidates)}

    def retract(self,source):
        count=0
        for e in self.lessons:
            if e['source']==source and e['active']:e['active']=False;count+=1
        return count

    def hypotheses(self):
        groups=defaultdict(list)
        for e in self.lessons:
            if e['active']:groups[e['word']].append(e)
        out={}
        for word,examples in groups.items():
            if len({e['turn_key'] for e in examples})<self.min_support:continue
            possible=None
            for e in examples:
                selectors={k for k,v in programs(e['candidates']).items() if v==e['target_ref']}
                possible=selectors if possible is None else possible.intersection(selectors)
            if possible:
                # Important: matching one training object name isn't support;
                # only structural selector programs survive multiple contexts.
                out[word]=sorted(possible)
        return out

    def resolve(self,utterance,candidates):
        if not isinstance(utterance,str) or len(utterance)>3000:return {'status':'UNKNOWN','reason':'INVALID_TEXT'}
        if not self.candidates_ok(candidates):return {'status':'UNKNOWN','reason':'INVALID_CONTEXT'}
        tokens=words(utterance)
        # Quoted or nested speech has its own narrator. The parser must not
        # resolve it in the outer speaker's perspective without separate proof.
        if any(m in utterance for m in ('«','»','"','“','”')):
            return {'status':'UNKNOWN','reason':'NESTED_ATTRIBUTION_NOT_LEARNED'}
        learned=self.hypotheses();recognized=[(i,w) for i,w in enumerate(tokens) if w in learned]
        if len({w for _,w in recognized})<len(recognized):
            return {'status':'UNKNOWN','reason':'REPEATED_UNSCOPED_REFERENCE'}
        if not recognized:return {'status':'UNKNOWN','reason':'NO_LEARNED_REFERENCE_SURFACES'}
        current=programs(candidates);links=[]
        for i,w in recognized:
            predictions={current[p] for p in learned[w] if p in current}
            if len(predictions)!=1:
                return {'status':'UNKNOWN','reason':'CONTEXT_AMBIGUOUS_OR_UNSUPPORTED','word':w,
                        'candidate_count':len(candidates)}
            ref=next(iter(predictions))
            # A contradictory corpus might still have a selector surviving by
            # chance on the current query; reject identical training contexts
            # carrying different targets rather than majority-voting a person.
            lessons=[e for e in self.lessons if e['active'] and e['word']==w]
            by_context=defaultdict(set)
            for e in lessons:
                signature=canonical([(c['kind'],c['agreement'],c['role'],c['age']) for c in e['candidates']])
                pos=next(j for j,c in enumerate(e['candidates']) if c['ref']==e['target_ref'])
                by_context[signature].add(pos)
            if any(len(v)>1 for v in by_context.values()):
                return {'status':'UNKNOWN','reason':'CONTRADICTORY_GROUNDED_LESSONS'}
            links.append({'token_index':i,'surface':w,'referent':ref,'scope':'NARRATED_ONLY',
                          'confidence':'LEARNED_CONTEXTUAL_REFERENCE_NOT_PERSON_VERIFICATION'})
        return {'status':'LINKED_REFERENCES','links':links,'world_fact':False,
                'candidate_count':len(candidates)}

    def to_dict(self):return {'min_support':self.min_support,'lessons':self.lessons}
    @classmethod
    def from_dict(cls,data):
        o=cls(data.get('min_support',3));o.lessons=list(data.get('lessons',[]));return o
    def digest(self):return hashlib.sha256(canonical(self.to_dict()).encode()).hexdigest()
