"""G30G RESEARCH ONLY: learn conversational slot filling from anchored contrasts.

No Russian morphemes or named greeting phrases, no person verification, and
no generated REPLY or ASK.  Distinct speaker, source, witnessed span, and
question root.  Native G29's ASK is the only owner of the open question.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re

SCHEMA = 'G30G_RESEARCH_DIALOGUE_BIND_V1'
_TOKEN = re.compile(r'[^\W_]+', re.UNICODE)

def tokenize(text):
    return [(m.group(0).casefold(),m.start(),m.end()) for m in _TOKEN.finditer(text)]

def stable_id(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
       separators=(',',':')).encode('utf-8')).hexdigest()

class ContrastiveSlotBinder:
    """Synthesizes wildcard utterance operators conditioned on *typed* inquiry.
    Training context/target span are externally witnessed *speaker reports*, not
    statements of real-world truth.  No inference-time target span supplied.
    """
    def __init__(self,min_witness=2):
        self.lessons=[]; self.min_witness=min_witness

    def observe(self, *,slot,utterance,source,root,span=None,negative=False):
        if not all(isinstance(x,str) and x for x in (slot,utterance,source,root)):
            raise ValueError('MISSING_ROOT_OR_CONTEXT')
        if any(e['root']==root for e in self.lessons):
            raise ValueError('DUPLICATE_ROOT')
        toks=tokenize(utterance)
        if not toks:raise ValueError('EMPTY_UTTERANCE')
        if not isinstance(negative,bool):raise ValueError('INVALID_NEGATIVE')
        if negative:
            if span is not None:raise ValueError('NEGATIVE_HAS_NO_TARGET')
            item={'slot':slot,'utterance':utterance,'surface':None,
                'left':None,'right':None,'width':None,'negative':True}
        else:
            if not (isinstance(span,(tuple,list)) and len(span)==2
                    and all(type(t)==int for t in span)):
                raise ValueError('WITNESSED_SPAN_REQUIRED')
            a,b=span
            if a<0 or b>len(utterance) or a>=b:raise ValueError('BAD_SPAN')
            idx=[i for i,(_,s,e) in enumerate(toks) if s>=a and e<=b]
            if not idx or idx!=list(range(idx[0],idx[-1]+1)):
                raise ValueError('NOT_FULL_TOKENS')
            if toks[idx[0]][1]!=a or toks[idx[-1]][2]!=b:
                raise ValueError('SPAN_NOT_TOKEN_ALIGNED')
            item={'slot':slot,'utterance':utterance,
                'surface':utterance[a:b],
                'left':[w for w,_,_ in toks[:idx[0]]],
                'right':[w for w,_,_ in toks[idx[-1]+1:]],
                'width':len(idx),'negative':False}
        self.lessons.append({**item,'source':source,'root':root,'active':True,
            'origin':'ATTRIBUTED_SPEAKER_CONVENTION_NOT_IDENTIFICATION'})
        return {'status':'LESSON_STORED','root':root}

    @staticmethod
    def _pattern_matches(pattern,tokens):
        left,right,width=pattern
        n=len(tokens)
        if n!=len(left)+width+len(right):return False
        return tokens[:len(left)]==list(left) and (not right or tokens[-len(right):]==list(right))

    def operators(self,slot):
        active=[x for x in self.lessons if x['active'] and x['slot']==slot]
        groups=defaultdict(list)
        for e in active:
            if e['negative']:continue
            k=(tuple(e['left']),tuple(e['right']),e['width'])
            groups[k].append(e)
        good=[];rejected=[]
        for pattern,rows in sorted(groups.items()):
            # Different labelled values, different witness roots. Two examples
            # of the same lexical target are NOT evidence of a variable slot.
            roots={e['root'] for e in rows}
            fillers={tuple(w for w,_,_ in tokenize(e['surface'])) for e in rows}
            if (len(roots)<self.min_witness or len(fillers)<2 or
                len({e['source'] for e in rows})<self.min_witness):continue
            # All active negative counterexamples matching the same template
            # falsify this template regardless of positives count.
            negatives=[e for e in active if e['negative'] and
                        self._pattern_matches(pattern,[t for t,_,_ in tokenize(e['utterance'])])]
            if negatives:
                rejected.append({'pattern':pattern,'counterexamples':[n['root'] for n in negatives]})
                continue
            if not pattern[0] and not pattern[1]:
                # A single bare token could mean anything; no reliable
                # language-based extraction rule can be learned from form alone.
                rejected.append({'pattern':pattern,'reason':'UNANCHORED_WILDCARD'})
                continue
            good.append({'pattern':pattern,'roots':sorted(roots)})
        return good,rejected

    def propose(self,*,slot,utterance):
        toks=tokenize(utterance);words=[w for w,_,_ in toks]
        if not words:return {'status':'UNKNOWN','reason':'EMPTY_INPUT'}
        good,_=self.operators(slot)
        matches=[]
        for r in good:
            pat=r['pattern']
            if not self._pattern_matches(pat,words):continue
            a=len(pat[0]);b=a+pat[2]
            value=utterance[toks[a][1]:toks[b-1][2]]
            matches.append({'value':value,'roots':r['roots'],
               'pattern':{'left':list(pat[0]),'right':list(pat[1]),'width':pat[2]}})
        if not matches:return {'status':'UNKNOWN','reason':'NO_TRANSFERABLE_WITNESSED_OPERATOR'}
        meanings={m['value'].casefold() for m in matches}
        if len(meanings)!=1:return {'status':'AMBIGUOUS','reason':'INCOMPATIBLE_MATCHES','matches':matches}
        roots=sorted({root for m in matches for root in m['roots']})
        return {'status':'CANDIDATE_SPEAKER_SELF_REPORT','value':matches[0]['value'],
            'support':roots,'not_verified_person':True,'not_world_fact':True,
            'matched_operators':[m['pattern'] for m in matches]}

    def retract(self,source):
        n=0
        for e in self.lessons:
            if e['source']==source and e['active']:e['active']=False;n+=1
        return n

    def state(self):return {'schema':SCHEMA,'lessons':deepcopy(self.lessons),'min_witness':self.min_witness}
    @classmethod
    def restore(cls,obj):
        if obj.get('schema')!=SCHEMA:raise ValueError('BAD_SCHEMA')
        x=cls(obj['min_witness']);x.lessons=deepcopy(obj['lessons'])
        if len({r['root'] for r in x.lessons})!=len(x.lessons):raise ValueError('DUPLICATE_ROOT')
        return x

class OpenQuestionLedger:
    """Tracks a native question. Never invents speech/verification. Single channel
    isn't certified single human; scope is a hypothesis about continuity only.
    """
    def __init__(self,extractor=None):
        self.extractor=extractor or ContrastiveSlotBinder()
        self.questions=[];self.turns=[];self.claims=[];self.hypotheses=[]

    def asked(self, *,question_id,slot,channel,question_root,at):
        if not all(isinstance(x,str) and x for x in (question_id,slot,channel,question_root)):
            raise ValueError('INVALID_QUESTION')
        if any(q['question_id']==question_id for q in self.questions):raise ValueError('DUPLICATE_QUESTION')
        self.questions.append({'question_id':question_id,'slot':slot,'channel':channel,
              'root':question_root,'created_at':at,'status':'OPEN','claim_roots':[]})

    def received(self, *,text,channel,speaker_track,root,at):
        if any(t['root']==root for t in self.turns):raise ValueError('REPLAYED_TURN')
        if not isinstance(text,str) or not text.strip():raise ValueError('EMPTY_TURN')
        turn={'text':text,'channel':channel,'speaker_track':speaker_track,
              'root':root,'at':at,'scope':'USER_SAID_NOT_WORLD_FACT'}
        self.turns.append(turn)
        open_q=[q for q in self.questions if q['status']=='OPEN' and q['channel']==channel and q['created_at']<at]
        if len(open_q)!=1:return {'status':'NO_UNIQUE_OPEN_QUESTION','pending':len(open_q)}
        q=open_q[0]
        guess=self.extractor.propose(slot=q['slot'],utterance=text)
        if guess['status']!='CANDIDATE_SPEAKER_SELF_REPORT':
            return {'status':'PENDING_UNRESOLVED','reason':guess.get('reason',guess['status']),
                    'question_id':q['question_id']}
        if not speaker_track:
            return {'status':'PENDING_NO_SPEAKER_CONTINUITY', 'question_id':q['question_id']}
        # A single language template may produce a spurious filler (e.g.
        # an unseen negator). Retain only a candidate until the same speaker
        # provides a convergent value through a different learned structure.
        pattern_keys=sorted({stable_id(p) for p in guess['matched_operators']})
        hypothesis={'question_id':q['question_id'],'slot':q['slot'],
          'value':guess['value'],'speaker_track':speaker_track,'root':root,
          'pattern_keys':pattern_keys,'status':'PROPOSAL_NOT_COMMITTED'}
        self.hypotheses.append(hypothesis)
        relevant=[h for h in self.hypotheses if h['question_id']==q['question_id'] and
                  h['speaker_track']==speaker_track and h['status']=='PROPOSAL_NOT_COMMITTED']
        values={h['value'].casefold() for h in relevant}
        if len(values)>1:
            return {'status':'CONFLICTING_SLOT_HYPOTHESES','question_id':q['question_id'],
                    'roots':[h['root'] for h in relevant]}
        structures={p for h in relevant for p in h['pattern_keys']}
        if len(structures)<2 or len({h['root'] for h in relevant})<2:
            return {'status':'UNCONFIRMED_SLOT_HYPOTHESIS','question_id':q['question_id'],
                    'candidate_root':root,'not_verified_person':True}
        claim={'question_id':q['question_id'],'slot':q['slot'],
            'value':guess['value'],'claimant_track':speaker_track,'channel':channel,
            'utterance_root':root,'corroborating_turn_roots':sorted({h['root'] for h in relevant}),
            'question_root':q['root'],'method_roots':sorted({r for r in guess['support']}),
            'status':'PROVISIONAL_SELF_REPORT_NOT_PERSON_VERIFICATION'}
        self.claims.append(claim);q['claim_roots'].extend(claim['corroborating_turn_roots']);q['status']='ANSWER_CANDIDATE'
        return {'status':'ANSWER_CANDIDATE','claim':claim}

    def claimed_value(self,*,slot,channel,speaker_track):
        rows=[c for c in self.claims if c['slot']==slot and c['channel']==channel and
              c['claimant_track']==speaker_track and c['status']=='PROVISIONAL_SELF_REPORT_NOT_PERSON_VERIFICATION']
        if not rows:return {'status':'UNKNOWN'}
        vals={c['value'].casefold() for c in rows}
        if len(vals)>1:return {'status':'CONFLICTING_SELF_REPORTS','roots':[c['utterance_root'] for c in rows]}
        return {'status':'PROVISIONAL_SELF_REPORT','value':rows[-1]['value'],
           'roots':sorted({r for c in rows for r in c.get('corroborating_turn_roots',[c['utterance_root']])}),
           'identity_verified':False}

    def retract_turn(self,root):
        for h in self.hypotheses:
            if h['root']==root:h['status']='RETRACTED'
        for c in self.claims:
            if root in c.get('corroborating_turn_roots',[c['utterance_root']]):
                c['status']='RETRACTED'
        for q in self.questions:
            if root in q['claim_roots']:q['status']='OPEN';q['claim_roots'].remove(root)

    def state(self):return {'schema':SCHEMA,'extractor':self.extractor.state(),
        'questions':deepcopy(self.questions),'turns':deepcopy(self.turns),
        'claims':deepcopy(self.claims),'hypotheses':deepcopy(self.hypotheses)}
    @classmethod
    def restore(cls,obj):
        if obj.get('schema')!=SCHEMA:raise ValueError('BAD_SCHEMA')
        x=cls(ContrastiveSlotBinder.restore(obj['extractor']))
        x.questions=deepcopy(obj['questions']);x.turns=deepcopy(obj['turns']);
        x.claims=deepcopy(obj['claims']);x.hypotheses=deepcopy(obj.get('hypotheses',[]))
        roots=[t['root'] for t in x.turns]
        if len(roots)!=len(set(roots)):raise ValueError('DUPLICATE_TURN_ROOT')
        return x
