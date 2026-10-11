"""Emu typed API: one G2.9 living journal, isolated G3.0C diagnostic language lane.
No hidden LLM, no generic Russian text QA, no free-chat language learning.
"""
from .c4life.kernel import Life
from .language_live import LanguageLab
from .dialogue_learning import PragmaticLearner
from .dialogue_binding import OpenQuestionLedger

class C4ChildDialogue:
    def __init__(self,g):
        self.g=g
        self.life=Life.resume(g.home)
        self.lab=LanguageLab(*g.lab_payload)
        self.pragmatics=PragmaticLearner.restore(g.pragmatics_state)
        self.binding=OpenQuestionLedger.restore(g.binding_state)
        g.life=self.life;g.lab=self.lab;g.pragmatics=self.pragmatics;g.binding=self.binding

class C4LivingRuntime:
    def __init__(self,dialogue):
        self.dialogue=dialogue;self.life=dialogue.life;self.lab=dialogue.lab
        self.pragmatics=dialogue.pragmatics;self.binding=dialogue.binding;self._events=[];self._id=0;self._last_event_move="OPEN";self._session='g29-g30c-live-lab';self._channel='user:android'
    def load_runtime_state(self,rs):
        if rs and rs.get('schema') not in (None,'C4M_G29_G30C_G30D_G30G_BINDING_LIVE_LAB_V1'):
            raise ValueError('INCOMPATIBLE_RUNTIME_STATE')
        return self.runtime_state()
    def runtime_state(self):
        return {'state':'RUNNING','runtimeId':'C4_G29_G30C_G30D_G30G_BINDING_RESEARCH_V1',
           'organismSchema':'C4M_G29_G30C_G30D_G30G_BINDING_LIVE_LAB_V1',
           'world_t':self.life.world_t,'step':self.life.step,
           'journal_len':len(self.life.j),'journal_head':self.life.j.head(),
           'language_lessons':len(self.lab.lex.lessons),
           'language_learning_from_raw_chat':False,'provisional_dialogue_explanations':len(self.pragmatics.explanations),
           'supported_typed_intent_lessons':len(self.pragmatics.lessons),
           'g30g_inquiry_lessons':len(self.binding.extractor.lessons),
           'g30g_questions':len(self.binding.questions),'g30g_unresolved':sum(q['status']=='OPEN' for q in self.binding.questions),
           'g30g_self_reports':len([c for c in self.binding.claims if c['status']=='PROVISIONAL_SELF_REPORT_NOT_PERSON_VERIFICATION']),
           'capabilities':['USER_MESSAGE_RAW','G30C_LEXICAL_DIAGNOSTIC','G30D_TENTATIVE_FOLLOWUP',
             'G30D_TYPED_SPEAKER_INTENT_DEMONSTRATION','G30G_TYPED_INQUIRY_BINDING_DIAGNOSTIC','TICK','POLL','CHECKPOINT'],
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
                if s:
                    self._last_event_move='AFTER_NATIVE_ASK'
                    self._events.append({'type':'ASK','eventId':'c4g29-'+str(e['seq']),
                        'text':s,'journalSeq':e['seq'],'origin':'NATIVE_G29_ASK'})
                    # Typed provenance bridge ONLY: G29 exported identity-inquiry marker.
                    # No text-based parsing of question, no claim that the learner
                    # discovered question type from ordinary Russian.
                    if content.get('not_a_verified_identity') is True and content.get('uncertainty'):
                        self.binding.asked(question_id='c4g29-'+str(e['seq']),
                            slot='participant-claimed-label',channel=self._channel,
                            question_root='native-life-journal-seq:'+str(e['seq']),at=self.life.world_t)
            elif kind in ('ANSWER','REPORT','CORRECTION'):
                self._events.append({'type':'STATUS','eventId':'c4g29-'+str(e['seq']),
                    'state':'STRUCTURED_'+str(kind),'journalSeq':e['seq'],'content':content})
        return originals
    def teach_dialogue(self,utterance,move,intent,*,source,root,speaker='user:android'):
        # Research-only explicit witness. Host must obtain verified speaker feedback
        # rather than infer the intent label from text with another model.
        if not root or not source:raise ValueError('ATTRIBUTED_FEEDBACK_REQUIRED')
        return self.pragmatics.teach(utterance,move,intent,speaker=speaker,source=source,root=root)

    def _speaker_continuity(self):
        # Read G29's real interaction-hypothesis state; Android channel is
        # not proof of unique human speaker. Never mint verified identity.
        ii=self.life.interaction_identity
        if ii is None:return None
        st=ii.sessions.get(ii._key(self._session,self._channel))
        if not st or st.get('uncertainty'):return None
        return st.get('last_speaker')

    def user_message(self,text):
        if not isinstance(text,str) or not text.strip():
            return {'accepted':False,'error':'EMPTY_UTTERANCE'}
        if len(text)>4000:return {'accepted':False,'error':'CHAT_UTTERANCE_TOO_LONG_USE_SOURCE_STREAM'}
        # The original journal is the source of the evidence root and actor
        # continuity. No hardcoded text match or silent teacher gold label.
        self._id+=1
        before_head=self.life.j.head()
        m_id='g30g-'+str(self.life.step)+'-'+before_head[:14]
        move=self._last_event_move
        pending_before=bool(self.pragmatics.pending)
        original_questions=[q['question_id'] for q in self.binding.questions if q['status']=='OPEN']
        original_event_count=len(self._events)
        self._advance([{'type':'DIALOGUE_TURN','role':'USER','channel':self._channel,
              'verified_by':'TRANSPORT','host_routed_to':'SELF_C4',
              'content':{'session':self._session,'message_id':m_id,'utterance':text}},
            {'type':'UTTERANCE','role':'USER','channel':self._channel,
              'verified_by':'TRANSPORT','content':{'op':'RAW_TEXT','text':text,
              'interpretation_status':'G30G_RESEARCH_CANDIDATE_NOT_WORLD_FACT'}}])
        # G30G can use only a question opened PRIOR to this same utterance.
        binding_result={'status':'NO_PREVIOUS_OPEN_NATIVE_QUESTION'}
        if original_questions:
            binding_result=self.binding.received(text=text,channel=self._channel,
                speaker_track=self._speaker_continuity(),
                root='native-turn-head:'+self.life.j.head(),at=self.life.world_t)
        msg,lex=self.lab.diagnostic(text)
        intent=self.pragmatics.infer(text,move,speaker=self._channel)
        recall=self.pragmatics.recall(text,speaker=self._channel,move=move)
        followup=self.pragmatics.receive_followup(text,speaker=self._channel,source=m_id) if pending_before else None
        notes=['[ДИАГНОСТИКА G3.0C / G3.0D / G3.0G — НЕ СВОБОДНАЯ РЕЧЬ C4] '+msg]
        notes.append('Вопрос→ответ: '+binding_result['status']+'.')
        if binding_result.get('status')=='ANSWER_CANDIDATE':
            c=binding_result['claim']
            notes.append('По ДВУМ освоенным конструкциям предполагаемое самоописание: «'+str(c['value'])+'». Личность НЕ подтверждена.')
        elif binding_result.get('status')=='UNCONFIRMED_SLOT_HYPOTHESIS':
            notes.append('Одна возможная форма ответа; пока это неподтверждённая гипотеза.')
        if intent.get('intent') is not None:
            notes.append('Гипотеза о намерении: '+str(intent['intent'])+'.')
        else:notes.append('Прагматика: '+intent['status']+'.')
        if recall and recall['status']=='TENTATIVE_RECALLED_EXPLANATION':
            notes.append('Прежнее пояснение: «'+recall['explanation']+'» (непроверенное).')
        if followup:notes.append('Пояснение сохранено как предположение, не как истина.')
        self._events.append({'type':'REPLY','text':' '.join(notes),
             'eventId':'g30g-analysis-'+str(self.life.step),
             'origin':'ADAPTER_DIAGNOSTIC_NOT_NATIVE_SPEECH',
             'isNativeGeneratedSpeech':False,'binding':binding_result,
             'learningOccurred':bool(followup),
             'learningKind':'TENTATIVE_SPEAKER_EXPLANATION' if followup else 'NONE',
             'lexical':lex,'pragmatics':intent})
        native_ask_on_this_turn=any(e.get('origin')=='NATIVE_G29_ASK' for e in self._events[original_event_count:])
        open_questions=any(q['status']=='OPEN' for q in self.binding.questions)
        if not pending_before and not native_ask_on_this_turn and not open_questions and not intent.get('intent') and len(text)<=200:
            if self.pragmatics.ask_clarification(text,speaker=self._channel,move=move):
                self._events.append({'type':'ASK','eventId':'g30d-coach-'+str(self.life.step),
                   'text':'[УТОЧНЕНИЕ ОТ УЧЕБНОГО АДАПТЕРА, НЕ C4] Что ты хотел сказать?',
                   'origin':'ADAPTER_COACH_NOT_LEARNER_GENERATION','isNativeGeneratedSpeech':False})
        self._last_event_move='AFTER_USER_MESSAGE'
        return {'accepted':True,'stored_as':'ATTRIBUTED_USER_UTTERANCE',
                'native_dialogue_response':False,'lexical':lex,
                'binding':binding_result,'intent':intent,
                'unconfirmed_followup':followup}
    def tick(self,n=1):
        for _ in range(max(0,min(int(n),20))):self._advance([])
        return {'accepted':True,'ticks':max(0,min(int(n),20))}
    def poll(self,limit=100):
        limit=max(0,min(int(limit),100));r=self._events[:limit];del self._events[:limit];return r
