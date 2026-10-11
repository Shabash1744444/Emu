"""Emu typed API: one G2.9 living journal, isolated G3.0C diagnostic language lane.
No hidden LLM, no generic Russian text QA, no free-chat language learning.
"""
from .c4life.kernel import Life
from .language_live import LanguageLab
from .dialogue_learning import PragmaticLearner

class C4ChildDialogue:
    def __init__(self,g):
        self.g=g
        self.life=Life.resume(g.home)
        self.lab=LanguageLab(*g.lab_payload)
        self.pragmatics=PragmaticLearner.restore(g.pragmatics_state)
        g.life=self.life;g.lab=self.lab;g.pragmatics=self.pragmatics

class C4LivingRuntime:
    def __init__(self,dialogue):
        self.dialogue=dialogue;self.life=dialogue.life;self.lab=dialogue.lab
        self.pragmatics=dialogue.pragmatics;self._events=[];self._id=0;self._last_event_move="OPEN";self._session='g29-g30c-live-lab';self._channel='user:android'
    def load_runtime_state(self,rs):
        if rs and rs.get('schema') not in (None,'C4M_G29_G30C_G30D_DIALOGUE_LAB_V1'):
            raise ValueError('INCOMPATIBLE_RUNTIME_STATE')
        return self.runtime_state()
    def runtime_state(self):
        return {'state':'RUNNING','runtimeId':'C4_G29_G30C_G30D_PROVENANCE_DIALOGUE_RESEARCH_V1',
           'organismSchema':'C4M_G29_G30C_G30D_DIALOGUE_LAB_V1',
           'world_t':self.life.world_t,'step':self.life.step,
           'journal_len':len(self.life.j),'journal_head':self.life.j.head(),
           'language_lessons':len(self.lab.lex.lessons),
           'language_learning_from_raw_chat':False,'provisional_dialogue_explanations':len(self.pragmatics.explanations),
           'supported_typed_intent_lessons':len(self.pragmatics.lessons),
           'capabilities':['USER_MESSAGE_RAW','G30C_LEXICAL_DIAGNOSTIC','G30D_TENTATIVE_FOLLOWUP',
             'G30D_TYPED_SPEAKER_INTENT_DEMONSTRATION','TICK','POLL','CHECKPOINT'],
           'unsupported':['GENERAL_RUSSIAN_QA','GENERAL_LANGUAGE_TRAIN_FROM_FREE_TEXT',
                          'G30C_CANONICAL_MERGE','SENSORY_SESSION','ANDROID_BODY_ACTION'],
           'researchOnly':True}
    def _advance(self,events):
        originals=self.life.tick(int(self.life.world_t)+1,events)
        for e in originals:
            if e.get('replayed'):continue
            content=e.get('content') or {}
            kind=e.get('kind')
            if kind=='ASK':
                s=content.get('question') if isinstance(content,dict) else None
                if s:self._last_event_move='AFTER_NATIVE_ASK';self._events.append({'type':'ASK','eventId':'c4g29-'+str(e['seq']),
                    'text':s,'journalSeq':e['seq'],'origin':'NATIVE_G29_ASK'})
            elif kind in ('ANSWER','REPORT','CORRECTION'):
                self._events.append({'type':'STATUS','eventId':'c4g29-'+str(e['seq']),
                    'state':'STRUCTURED_'+str(kind),'journalSeq':e['seq'],'content':content})
        return originals
    def teach_dialogue(self,utterance,move,intent,*,source,root,speaker='user:android'):
        # Research-only explicit witness. Host must obtain verified speaker feedback
        # rather than infer the intent label from text with another model.
        if not root or not source:raise ValueError('ATTRIBUTED_FEEDBACK_REQUIRED')
        return self.pragmatics.teach(utterance,move,intent,speaker=speaker,source=source,root=root)

    def user_message(self,text):
        if not isinstance(text,str) or not text.strip():
            return {'accepted':False,'error':'EMPTY_UTTERANCE'}
        if len(text)>4000:
            return {'accepted':False,'error':'CHAT_UTTERANCE_TOO_LONG_USE_SOURCE_STREAM'}
        self._id+=1
        m_id='live-g29g30d-'+str(self._id)
        move=self._last_event_move
        pending_before=bool(self.pragmatics.pending)
        # Genuine C4 journal event: speaker said this string. Not a semantic lesson.
        out_before=len(self._events)
        self._advance([{'type':'DIALOGUE_TURN','role':'USER','channel':self._channel,
              'verified_by':'TRANSPORT','host_routed_to':'SELF_C4',
              'content':{'session':self._session,'message_id':m_id,'utterance':text}},
            {'type':'UTTERANCE','role':'USER','channel':self._channel,
              'verified_by':'TRANSPORT','content':{'op':'RAW_TEXT','text':text,
              'interpretation_status':'G30D_RESEARCH_CANDIDATE_NOT_WORLD_FACT'}}])
        msg,lex=self.lab.diagnostic(text)
        intent=self.pragmatics.infer(text,move,speaker=self._channel)
        recall=self.pragmatics.recall(text,speaker=self._channel,move=move)
        followup=None
        if pending_before:
            followup=self.pragmatics.receive_followup(text,speaker=self._channel,source=m_id)
        text_parts=['[АНАЛИЗ C4/G3.0D: адаптер, НЕ свободная речь] '+msg]
        if intent.get('intent') is not None:
            text_parts.append('Из уроков о намерениях: '+str(intent['intent'])+' (только гипотеза о смысле говорящего).')
        else:text_parts.append('Коммуникативный смысл: '+intent['status']+'.')
        if recall:
            if recall['status'] in ('TENTATIVE_RECALLED_EXPLANATION','OTHER_DIALOGUE_CONTEXT_UNVERIFIED'):
                text_parts.append('Раньше ты пояснил эту реплику так: «'+recall['explanation']+'». '+('Сейчас контекст ДРУГОЙ; перенос не подтверждён.' if recall['status']=='OTHER_DIALOGUE_CONTEXT_UNVERIFIED' else 'Это лишь предположение.'))
            else:text_parts.append('Твои предыдущие пояснения противоречат друг другу.')
        if followup:
            text_parts.append('Твоё пояснение сохранено как НЕПОДТВЕРЖДЁННАЯ гипотеза, не как факт или правило русского.')
        self._events.append({'type':'REPLY','text':' '.join(text_parts),
                'eventId':'g30d-analysis-'+str(self._id),'origin':'ADAPTER_DIAGNOSTIC',
                'isNativeGeneratedSpeech':False,'learningOccurred':bool(followup),
                'learningKind':'UNCONFIRMED_SPEAKER_FOLLOWUP' if followup else 'NONE',
                'lexical':lex,'pragmatics':intent})
        native_ask_on_this_turn=any(e.get('origin')=='NATIVE_G29_ASK' for e in self._events[out_before:])
        if not pending_before and not native_ask_on_this_turn and (not recall or recall['status']=='OTHER_DIALOGUE_CONTEXT_UNVERIFIED') and not intent.get('intent') and len(text)<=200:
            # Explicit adapter-owned clarification. Never masquerade as C4 own language.
            if self.pragmatics.ask_clarification(text,speaker=self._channel,move=move):
                self._events.append({'type':'ASK','eventId':'g30d-coach-'+str(self._id),
                   'text':'[УТОЧНЕНИЕ ОТ УЧЕБНОГО АДАПТЕРА] Что ты хотел сказать этой репликой? Можно объяснить своими словами.',
                   'origin':'ADAPTER_COACH_NOT_LEARNER_GENERATION','isNativeGeneratedSpeech':False})
        self._last_event_move='AFTER_USER_MESSAGE'
        return {'accepted':True,'stored_as':'ATTRIBUTED_USER_UTTERANCE',
                'native_dialogue_response':False,'lexical':lex,'intent':intent,
                'unconfirmed_followup':followup,'adapterClarification':self.pragmatics.pending is not None}
    def tick(self,n=1):
        for _ in range(max(0,min(int(n),20))):self._advance([])
        return {'accepted':True,'ticks':max(0,min(int(n),20))}
    def poll(self,limit=100):
        limit=max(0,min(int(limit),100));r=self._events[:limit];del self._events[:limit];return r
