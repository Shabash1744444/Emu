"""G3.0D ISOLATED dialogue pragmatics and provisional conversational clarification.

NO profanity polarity dictionaries, Russian question grammars, pretrained LLM,
world fact admission, false independent evidence. A teacher supplies *speaker*
intent labels for verified user intent reports; this is not world grounding.
Generalization is conservative and source-qualified.
"""
from __future__ import annotations
import copy, hashlib, json, re
from collections import defaultdict

SCHEMA='G30D_PROVISIONAL_DIALOGUE_V1'

def sha(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def pieces(x):
    if not isinstance(x,str) or not 0<len(x)<=4000:raise ValueError('INVALID_UTTERANCE')
    # Unicode-letter oriented, no Russian-specific word/slang table.
    return re.findall(r'[^\W_]+',x.casefold(),flags=re.UNICODE)

def features(x):
    t=pieces(x)
    f=set('tok:'+w for w in t)
    f|={'pair:'+a+'|'+b for a,b in zip(t,t[1:])}
    for w in t:
        if len(w)>=4:
            f.update('chr:'+w[i:i+3] for i in range(len(w)-2))
    return f

class PragmaticLearner:
    def __init__(self):
        self.lessons=[]
        self.explanations=[]
        self.pending=None
        self.turn_index=0

    def teach(self,utterance,move,intent,*,speaker,source,root):
        """Explicitly witnessed speaker-intent demonstration (not fact of world).
        Originating host must verify that intent came from speaker feedback.
        This function cannot itself authenticate that speaker in Android.
        """
        if not all(isinstance(k,str) and k.strip() for k in (move,intent,speaker,source,root)):
            raise ValueError('MISSING_ATTRIBUTION')
        p=pieces(utterance)
        if not p:raise ValueError('EMPTY_WORD_SEQUENCE')
        if len(intent)>100 or len(move)>100:raise ValueError('INVALID_LABEL')
        if any(e['root']==root for e in self.lessons):raise ValueError('DUPLICATE_WITNESS')
        row={'utterance':utterance,'move':move,'intent':intent,'speaker':speaker,
             'source':source,'root':root,'active':True,
             'status':'SPEAKER_REPORTED_INTENT_NOT_WORLD_FACT'}
        self.lessons.append(row)
        return {'status':'ATTRIBUTED_INTENT_LESSON','root':root}

    def infer(self,utterance,move,*,speaker='user'):
        target=features(utterance)
        lessons=[e for e in self.lessons if e['active'] and e['move']==move and e['speaker']==speaker]
        if not lessons:return {'status':'UNKNOWN','intent':None,'support':[]}
        grouped=defaultdict(list)
        for e in lessons:
            f=features(e['utterance'])
            score=len(target & f)/max(1,len(target|f))
            if pieces(utterance)==pieces(e['utterance']):score=1.
            if score>=0.30:grouped[e['intent']].append((score,e))
        if not grouped:return {'status':'UNKNOWN','intent':None,'support':[]}
        ranked=[]
        for intent,matches in grouped.items():
            # Deduplicate origins: repeats of one example cannot gain weight.
            best_by_root={}
            for score,e in matches:
                best_by_root[e['root']]=max(score,best_by_root.get(e['root'],0))
            ranked.append((sum(sorted(best_by_root.values(),reverse=True)[:3]),intent,matches))
        ranked.sort(reverse=True)
        if len(ranked)>1 and (ranked[0][0]-ranked[1][0]<0.18):
            return {'status':'AMBIGUOUS','intent':None,'possible':sorted(grouped),'support':[]}
        score,intent,matches=ranked[0]
        direct=any(pieces(utterance)==pieces(e['utterance']) for _,e in matches)
        roots=sorted({e['root'] for s,e in matches if s>=0.30})
        # Novel combinations require at least two independent testimony episodes.
        if not direct and len(roots)<2:
            return {'status':'INSUFFICIENT_EVIDENCE','intent':None,'support':roots}
        if not direct and ranked[0][0]<0.86:
            return {'status':'LOW_TRANSFER_CONFIDENCE','intent':None,'support':roots}
        return {'status':'SPEAKER_INTENT_PROPOSAL','intent':intent,'support':roots,
                'is_world_fact':False,'exact_seen':direct,'scope':move}

    def ask_clarification(self,utterance,*,speaker,move):
        if self.pending:return False
        self.turn_index+=1
        self.pending={'original':utterance,'speaker':speaker,'move':move,'turn':self.turn_index}
        return True

    def receive_followup(self,text,*,speaker,source):
        """A next utterance is only a POSSIBLE explanation. Never admit as truth.
        A new speaker does not resolve another speaker's question.
        """
        if not self.pending or speaker!=self.pending['speaker']:return None
        p=self.pending;self.pending=None
        self.turn_index+=1
        e={'surface':p['original'],'speaker':speaker,'move':p['move'],
           'explanation':text,'source':source,'root':sha({'pending':p,'text':text,'source':source}),
           'active':True,'status':'UNCONFIRMED_FOLLOWUP_SELF_REPORT'}
        self.explanations.append(e)
        return {'status':'TENTATIVE_FOLLOWUP_STORED','root':e['root'],'not_semantic_proof':True}

    def recall(self,utterance,*,speaker,move):
        rows=[e for e in self.explanations if e['active'] and e['surface'].casefold()==utterance.casefold()
              and e['speaker']==speaker]
        if not rows:return None
        texts={e['explanation'] for e in rows}
        if len(texts)>1:return {'status':'CONFLICTING_FOLLOWUPS','explanations':sorted(texts)}
        if not any(e['move']==move for e in rows):
            return {'status':'OTHER_DIALOGUE_CONTEXT_UNVERIFIED','explanation':rows[-1]['explanation'],
                    'original_move':rows[-1]['move'],'not_verified_intent':True}
        return {'status':'TENTATIVE_RECALLED_EXPLANATION','explanation':rows[-1]['explanation'],
                'roots':[e['root'] for e in rows],'not_verified_intent':True}

    def retract(self,source):
        n=0
        for row in self.lessons+self.explanations:
            if row['source']==source and row['active']:
                row['active']=False;n+=1
        return n

    def state(self):
        return {'schema':SCHEMA,'lessons':copy.deepcopy(self.lessons),
                'explanations':copy.deepcopy(self.explanations),
                'pending':copy.deepcopy(self.pending),'turn_index':self.turn_index}

    @classmethod
    def restore(cls,obj):
        if not isinstance(obj,dict) or obj.get('schema')!=SCHEMA:raise ValueError('INVALID_G30D_SCHEMA')
        a=cls();a.lessons=copy.deepcopy(obj['lessons']);a.explanations=copy.deepcopy(obj['explanations']);
        a.pending=copy.deepcopy(obj.get('pending'));a.turn_index=int(obj.get('turn_index',0))
        seen=set()
        for e in a.lessons+a.explanations:
            if e['root'] in seen or not e['source'] or not e['speaker']:raise ValueError('DUPLICATE_OR_UNSOURCED_CLAIM')
            seen.add(e['root'])
        return a
