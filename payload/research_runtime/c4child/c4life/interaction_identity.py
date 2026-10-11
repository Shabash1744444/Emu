"""G2.8: channel != acoustic stream != speaking person != claimed identity.

No Russian word rules or face recognition are embedded here. An optional linguistic
teacher may align *surface forms* to one of the deictic roles relative to an
attested turn. A turn without sensory evidence inherits a provisional dialogue
continuity hypothesis, NEVER identity verification.

The speaker's farewell is a claim of intended departure, not host-certified
absence; no farewell is not proof they stayed. Dialogue is scoped to a (session,
channel), and one channel can contain multiple acoustic clusters/participants.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
from .context_reference import ContextReferenceLearner


def canonical(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


class InteractionIdentity:
    def __init__(self, min_teacher_sources=2):
        self.sessions={}
        self.turns={}
        self.sensor_receipts={}
        self.groundings={}  # simulated/world sensor referent in a particular witnessed turn
        self.lessons=[]
        self.min_teacher_sources=int(min_teacher_sources)
        self._cached_deictic=None
        self.reference_learner=ContextReferenceLearner()

    @staticmethod
    def _key(session,channel):
        if not isinstance(session,str) or not session or not isinstance(channel,str) or not channel:
            raise ValueError('SESSION_AND_CHANNEL_REQUIRED')
        return canonical([session,channel])

    @staticmethod
    def _msg_id(mid):
        if not isinstance(mid,str) or not mid or len(mid)>200:raise ValueError('INVALID_MESSAGE_ID')
        return mid

    def sensor(self,session,channel,message_id,clusters=None,authenticated_principal=None,root=None):
        """ONLY caller's host boundary may authenticate this call as SENSOR.

        clusters: non-empty list of diarization/acoustic IDs (NOT human identities).
        authenticated_principal: a host-certified ACCOUNT / access principal,
        never proof of the physical person using that account.
        """
        key=self._key(session,channel);mid=self._msg_id(message_id)
        pair=canonical([key,mid])
        if pair in self.sensor_receipts:raise ValueError('DUPLICATE_SENSOR_ROOT')
        if clusters is None:clusters=[]
        if not isinstance(clusters,list) or len(clusters)>12 or len(set(clusters))!=len(clusters):
            raise ValueError('INVALID_CLUSTERS')
        if not all(isinstance(t,str) and 0<len(t)<128 for t in clusters):
            raise ValueError('INVALID_CLUSTERS')
        if authenticated_principal is not None and (not isinstance(authenticated_principal,str) or not authenticated_principal):
            raise ValueError('INVALID_HOST_IDENTITY')
        receipt={'key':key,'message_id':mid,'clusters':clusters,'authenticated_principal':authenticated_principal,
                 'root':str(root or 'HOST_SENSOR'),'used':False}
        self.sensor_receipts[pair]=receipt
        return {'status':'SENSOR_ROOT_RECORDED','root':receipt['root']}

    def observe(self,session,channel,message_id,utterance='',claimed_name=None,
                farewell=False,addressed_to=None,host_routed=False):
        """Record a claimed utterance, never promote its content to world truth.

        `claimed_name` and `farewell` are UNTRUSTED semantic claims. A host sensor
        binding is consumed when present. `addressed_to` is explicit routing,
        *not* inferred from a pronoun, and may be absent in group conversations.
        """
        k=self._key(session,channel);mid=self._msg_id(message_id)
        tk=canonical([k,mid])
        if tk in self.turns:raise ValueError('REPLAYED_TURN')
        if not isinstance(utterance,str) or len(utterance)>10000:raise ValueError('INVALID_UTTERANCE')
        if claimed_name is not None and (not isinstance(claimed_name,str) or not claimed_name):
            raise ValueError('INVALID_SELF_CLAIM')
        if not isinstance(addressed_to,(str,type(None))):raise ValueError('INVALID_ADDRESSEE')
        if not isinstance(farewell,bool):raise ValueError('FAREWELL_MUST_BE_BOOLEAN')
        st=self.sessions.setdefault(k,{'last_speaker':None,'last_status':None,'last_farewell':False,
             'voice_clusters':[],'unique_speakers':[],'last_message_id':None,'uncertainty':False,
             'epoch':0,'last_identity_ask_epoch':-1,'last_claimed_name':None})
        old_speaker=st['last_speaker']
        old_uncertainty=st['uncertainty']
        conflicting_self_claim=bool(claimed_name and st['last_claimed_name'] and claimed_name!=st['last_claimed_name'])
        receipt=self.sensor_receipts.get(tk)
        if receipt and receipt['used']:raise ValueError('SENSOR_REPLAY')
        speaker=None;confidence='UNKNOWN';basis=[];clusters=[]
        if receipt:
            receipt['used']=True;clusters=receipt['clusters']
            for cluster in clusters:
                if cluster not in st['voice_clusters']:st['voice_clusters'].append(cluster)
            if len(st['voice_clusters'])>1:st['uncertainty']=True
            if len(clusters)>1:
                confidence='MULTIPLE_SIMULTANEOUS_VOICES'
                st['uncertainty']=True
            elif len(clusters)==1:
                speaker='voice-cluster:'+k+':'+clusters[0]
                confidence='SENSOR_TRACKED_VOICE_NOT_PERSON'
                basis=[receipt['root']]
            elif st['last_speaker'] is not None and not st['last_farewell'] and len(st['voice_clusters'])<2:
                speaker=st['last_speaker'];confidence='ASSUMED_CONTINUITY';basis=['PRIOR_TURN_HYPOTHESIS']
        elif st['uncertainty'] or len(st['voice_clusters'])>1:
            confidence='UNKNOWN_SHARED_CHANNEL_MULTISPEAKER'
        elif st['last_speaker'] is not None and not st['last_farewell']:
            speaker=st['last_speaker'];confidence='ASSUMED_CONTINUITY';basis=['PRIOR_TURN_HYPOTHESIS']
        elif st['last_speaker'] is None and st['last_message_id'] is None:
            speaker='unknown-first-speaker:'+k
            confidence='UNVERIFIED_SINGLE_SPEAKER_HYPOTHESIS';basis=['NO_INDIVIDUAL_SENSOR']
        else:
            confidence='UNKNOWN_AFTER_DEPARTURE_CLAIM'
        # Never use surface name claim to assign/overwrite sensor identity.
        # Two conflicting self-naming claims from one text channel are grounds
        # for SUSPECTING a switch, not evidence that a second human appeared.
        if conflicting_self_claim and confidence != 'SENSOR_TRACKED_VOICE_NOT_PERSON':
            speaker=None;confidence='SUSPECTED_SWITCH_FROM_CONFLICTING_SELF_CLAIMS';basis=['CONFLICTING_SOURCE_CLAIMS']
            st['uncertainty']=True
        if speaker is not None:
            if speaker not in st['unique_speakers']:st['unique_speakers'].append(speaker)
            st['last_speaker']=speaker;st['last_status']=confidence
        elif confidence in ('MULTIPLE_SIMULTANEOUS_VOICES','UNKNOWN_SHARED_CHANNEL_MULTISPEAKER',
                            'UNKNOWN_AFTER_DEPARTURE_CLAIM','SUSPECTED_SWITCH_FROM_CONFLICTING_SELF_CLAIMS'):
            st['last_speaker']=None;st['last_status']=confidence
        if (old_speaker is not None and speaker is not None and speaker != old_speaker) or (not old_uncertainty and st['uncertainty']) or farewell:
            st['epoch']+=1
        st['last_message_id']=mid;st['last_farewell']=bool(farewell)
        if claimed_name:st['last_claimed_name']=claimed_name
        if addressed_to == 'SELF_C4': addressee='SELF_C4';addressee_status='DIRECT_HOST_ROUTING' if host_routed else 'CLAIMED_ROUTING'
        elif addressed_to is not None: addressee='unverified-addressee:'+addressed_to;addressee_status='CLAIMED_ROUTING'
        else:addressee=None;addressee_status='NOT_RESOLVED'
        item={'session':session,'channel':channel,'message_id':mid,'utterance':utterance,
              'speaker':speaker,'speaker_status':confidence,'basis':basis,
              'voice_clusters':clusters,'claimed_name':claimed_name,'farewell_claim':bool(farewell),
              'authenticated_principal':receipt.get('authenticated_principal') if receipt else None,
              'addressee':addressee,'addressee_status':addressee_status,
              'scope':'SOURCE_UTTERANCE_ONLY'}
        self.turns[tk]=item
        return self.inspect(session,channel,mid)

    def inspect(self,session,channel,message_id):
        k=self._key(session,channel);tk=canonical([k,self._msg_id(message_id)])
        if tk not in self.turns:return {'status':'UNKNOWN','reason':'NO_ATTESTED_TURN'}
        r=self.turns[tk]
        return {'status':'TRACKED_TURN','speaker':r['speaker'], 'speaker_status':r['speaker_status'],
                'identity_confirmed':False,
                'authenticated_principal':r.get('authenticated_principal'),
                'claimed_name':r['claimed_name'],'named_identity_verified':False,
                'addressee':r['addressee'],'addressee_status':r['addressee_status'],
                'channel':r['channel'],'session':r['session'],'message_id':r['message_id'],
                'voice_clusters':list(r['voice_clusters']), 'evidence_basis':list(r['basis']),
                'scope':'SOURCE_UTTERANCE_ONLY'}

    def ground(self,session,channel,message_id,grounding_id,target_ref,argument_slot,root,kind=None,agreement=None):
        """Independent host observation links event role to concrete referent.

        A linguistic tutor will NOT specify SPEAKER/ADDRESSEE. The learning
        algorithm derives that role by comparing the target to a recorded turn.
        """
        key=self._key(session,channel);mid=self._msg_id(message_id)
        tk=canonical([key,mid])
        if tk not in self.turns:raise ValueError('NO_WITNESSED_TURN')
        if not isinstance(grounding_id,str) or not grounding_id:raise ValueError('BAD_GROUNDING_ID')
        if not isinstance(target_ref,str) or not target_ref:raise ValueError('BAD_REFERENCE')
        if argument_slot not in ('ACTOR','PATIENT','RECIPIENT','TOPIC','POSSESSOR'):
            raise ValueError('INVALID_ARGUMENT_SLOT')
        gk=canonical([tk,grounding_id]);
        if gk in self.groundings:raise ValueError('DUPLICATE_WORLD_ROOT')
        if kind is not None and kind not in ('PERSON','OBJECT','EVENT'):
            raise ValueError('INVALID_SEMANTIC_KIND')
        if agreement is not None and (not isinstance(agreement,str) or not agreement or len(agreement)>32):
            raise ValueError('INVALID_AGREEMENT_OBSERVATION')
        self.groundings[gk]={'turn_key':tk,'target_ref':target_ref,
                              'argument_slot':argument_slot,'root':str(root),
                              'kind':kind,'agreement':agreement}
        return gk

    def previous_referents(self,turn_key,window=4):
        """Only PREVIOUS host-witnessed mentions in the same channel/session.

        The current turn's own grounding (the label) is never an inference input;
        using it would turn an exam into an answer leak.
        """
        keys=list(self.turns)
        if turn_key not in self.turns:raise ValueError('UNWITNESSED_REFERENCE_TURN')
        pos=keys.index(turn_key)
        turn=self.turns[turn_key]
        scoped=[key for key in keys[:pos] if self.turns[key]['session']==turn['session']
                and self.turns[key]['channel']==turn['channel']]
        prior=[(key,len(scoped)-idx) for idx,key in enumerate(scoped[-window:],
             start=len(scoped)-len(scoped[-window:]))]
        results={}
        for past_key,age in prior:
            for g in self.groundings.values():
                if g['turn_key']!=past_key or g.get('kind') is None:continue
                ref=g['target_ref']
                record={'ref':ref,'kind':g['kind'],'agreement':g.get('agreement'),
                        'role':g['argument_slot'],'age':age,'support_root':int(g['root'])}
                if ref not in results or age<results[ref]['age']:
                    results[ref]=record
        return list(results.values())

    def teach_reference(self,word,source,grounding_key):
        if grounding_key not in self.groundings:raise ValueError('NO_INDEPENDENT_REFERENCE_GROUNDING')
        g=self.groundings[grounding_key]
        turn_key=g['turn_key']
        turn=self.turns[turn_key]
        previous=self.previous_referents(turn_key)
        return self.reference_learner.teach(turn['utterance'],word,previous,
            g['target_ref'],source,int(g['root']),turn_key)

    def resolve_references(self,session,channel,message_id):
        # The surface parser makes no assumptions about Russian pronoun tables.
        # It merges TWO previously acquired skills: situated I/YOU deixis and
        # contextual third-person/event references. It does not parse events.
        from .context_reference import words
        tk=canonical([self._key(session,channel),self._msg_id(message_id)])
        if tk not in self.turns:return {'status':'UNKNOWN','reason':'NO_WITNESSED_TURN'}
        utterance=self.turns[tk]['utterance']
        if any(x in utterance for x in ('«','»','"','“','”')):
            return {'status':'UNKNOWN','reason':'NESTED_ATTRIBUTION_NOT_LEARNED'}
        toks=words(utterance);relative_forms=self.learned_roles()
        self_forms={form for form,slot in relative_forms}
        if self_forms.intersection(self.reference_learner.hypotheses()):
            return {'status':'UNKNOWN','reason':'COLLIDING_DEICTIC_AND_DISCOURSE_MEANING'}
        links=[]
        for i,word in enumerate(toks):
            slots=[slot for form,slot in relative_forms if form==word]
            if not slots:continue
            if toks.count(word)>1:return {'status':'UNKNOWN','reason':'REPEATED_UNSCOPED_REFERENCE'}
            results=[self.resolve_word(word,slot,session,channel,message_id) for slot in slots]
            refs={z.get('referent') for z in results if z['status']=='RESOLVED_DEICTIC'}
            if len(refs)!=1 or len(results)!=len(refs) and not all(z['status']=='RESOLVED_DEICTIC' for z in results):
                return {'status':'UNKNOWN','reason':'UNRESOLVED_CONTEXTUAL_DEIXIS'}
            links.append({'token_index':i,'surface':word,'referent':next(iter(refs)),
                          'scope':'SOURCE_UTTERANCE_ONLY','confidence':'CONTEXTUAL_DEIXIS_UNVERIFIED_PERSON'})
        if set(toks).intersection(self.reference_learner.hypotheses()):
            response=self.reference_learner.resolve(utterance,self.previous_referents(tk))
            if response['status']!='LINKED_REFERENCES':return response
            links+=response['links']
        if not links:return {'status':'UNKNOWN','reason':'NO_LEARNED_REFERENCE_SURFACES'}
        links.sort(key=lambda x:x['token_index'])
        return {'status':'LINKED_REFERENCES','links':links,'world_fact':False,
                'physical_identity_verified':False,'scope':'NARRATED_ONLY'}

    def learn_from_grounding(self,word,source,grounding_key):
        if grounding_key not in self.groundings:raise ValueError('MISSING_WORLD_GROUNDING')
        g=self.groundings[grounding_key];r=self.turns[g['turn_key']]
        candidates=[]
        if r['speaker']==g['target_ref']:candidates.append('SPEAKER')
        if r['addressee']==g['target_ref']:candidates.append('ADDRESSEE')
        # No guessing 'THIRD' from absence of a match to a known participant.
        if len(candidates)!=1:raise ValueError('UNRESOLVED_RELATIVE_ROLE')
        return self.learn_deixis(word,candidates[0],g['argument_slot'],source,g['turn_key'])

    def learn_deixis(self,word,relative_role,argument_slot,source,turn_key):
        """Teacher's LANGUAGE CONVENTION about an attested turn; no hardcoded RU map.

        Two independent turn demonstrations per surface/slot required. Sources
        cannot be promoted to independent persons by changing IDs on one channel.
        """
        if not all(isinstance(v,str) and v for v in (word,relative_role,argument_slot,source,turn_key)):
            raise ValueError('INVALID_LESSON')
        if relative_role not in ('SPEAKER','ADDRESSEE','THIRD'):raise ValueError('INVALID_DEICTIC_ROLE')
        if argument_slot not in ('ACTOR','PATIENT','RECIPIENT','TOPIC','POSSESSOR'):raise ValueError('INVALID_ARGUMENT_SLOT')
        if turn_key not in self.turns:raise ValueError('TURN_NOT_WITNESSED')
        r=self.turns[turn_key]
        if relative_role=='SPEAKER' and r['speaker'] is None:raise ValueError('NO_SPEAKER_GROUND')
        if relative_role=='ADDRESSEE' and r['addressee'] is None:raise ValueError('NO_ADDRESSEE_GROUND')
        item={'word':word.casefold(),'role':relative_role,'slot':argument_slot,
              'source':source,'turn_key':turn_key,'active':True}
        # Prevent a single teacher's duplicate reassertions from counting as new independent examples.
        if any(e==item for e in self.lessons):raise ValueError('DUPLICATE_LESSON')
        self.lessons.append(item);self._cached_deictic=None
        return {'status':'LANGUAGE_HYPOTHESIS_ADMITTED','surface':word.casefold()}

    def retract_source(self,source):
        n=0
        for e in self.lessons:
            if e['source']==source and e['active']:
                e['active']=False;n+=1
        self._cached_deictic=None
        n+=self.reference_learner.retract(source)
        return n

    def learned_roles(self):
        counts=defaultdict(set)
        for e in self.lessons:
            if e['active']:counts[(e['word'],e['slot'],e['role'])].add(e['turn_key'])
        grouped=defaultdict(dict)
        for (w,slot,role),turns in counts.items():
            if len(turns)>=self.min_teacher_sources:grouped[(w,slot)][role]=len(turns)
        out={}
        for key,poss in grouped.items():
            # conflicting teaching does not turn into majority-vote identity.
            if len(poss)==1:out[key]=next(iter(poss))
        return out

    def resolve_word(self,word,argument_slot,session,channel,message_id,antecedents=None,perspective=None):
        k=self._key(session,channel);tk=canonical([k,self._msg_id(message_id)])
        if tk not in self.turns:return {'status':'UNKNOWN','reason':'NO_TURN'}
        role=self.learned_roles().get((word.casefold(),argument_slot))
        if role is None:return {'status':'UNKNOWN','reason':'UNLEARNED_OR_CONTRADICTED_FORM'}
        item=self.turns[tk]
        # A quoted «я» belongs to the *quoted source*, never automatically
        # to whoever uttered the outer sentence. Quoted attribution itself
        # remains narrated / claimed, not an observed speaking identity.
        if perspective:
            if not isinstance(perspective,dict):return {'status':'UNKNOWN','reason':'INVALID_PERSPECTIVE'}
            ptype=perspective.get('kind')
            if ptype=='INDIRECT_REPORT':
                return {'status':'UNKNOWN','reason':'INDIRECT_DEIXIS_NOT_LEARNED'}
            if ptype!='QUOTE':return {'status':'UNKNOWN','reason':'UNKNOWN_PERSPECTIVE_KIND'}
            if role in ('SPEAKER','ADDRESSEE'):
                pk='speaker_ref' if role=='SPEAKER' else 'addressee_ref'
                ref=perspective.get(pk)
                if not isinstance(ref,str) or not ref:
                    return {'status':'UNKNOWN','reason':'UNATTRIBUTED_NESTED_VOICE'}
                return {'status':'RESOLVED_DEICTIC','referent':ref,
                        'confidence':'NARRATED_QUOTATION_ONLY','role':role,
                        'slot':argument_slot,'scope':'NARRATED_ONLY'}
        if role=='SPEAKER':
            if item['speaker'] is None:return {'status':'UNKNOWN','reason':'UNRESOLVED_SPEAKER'}
            return {'status':'RESOLVED_DEICTIC','referent':item['speaker'],
                    'confidence':'PROVISIONAL_SPEAKER_NOT_PERSON_VERIFIED',
                    'role':role,'slot':argument_slot}
        if role=='ADDRESSEE':
            if item['addressee'] is None:return {'status':'UNKNOWN','reason':'UNRESOLVED_ADDRESSEE'}
            return {'status':'RESOLVED_DEICTIC','referent':item['addressee'],
                    'confidence':item['addressee_status'],'role':role,'slot':argument_slot}
        # Third person is only determinable if context already selected exactly
        # one referent. Gender/agreement/anaphora remain OPEN.
        antecedents=list(dict.fromkeys(antecedents or []))
        if len(antecedents)!=1:return {'status':'UNKNOWN','reason':'AMBIGUOUS_THIRD_PERSON'}
        return {'status':'RESOLVED_DEICTIC','referent':antecedents[0],
                'confidence':'CONTEXT_ONLY','role':role,'slot':argument_slot}

    def should_ask_identity(self,session,channel,high_stakes=False,turn_id=None):
        """One question per uncertainty epoch; no repeated identification nagging."""
        k=self._key(session,channel)
        st=self.sessions.get(k)
        if st is None:return {'ask':False,'reason':'NO_INBOUND_TURN'}
        if st['last_identity_ask_epoch']==st['epoch']:
            return {'ask':False,'reason':'ALREADY_ASKED_IN_THIS_CONTEXT'}
        changed=st['uncertainty'] or st['last_farewell'] or st['last_status']=='UNKNOWN_AFTER_DEPARTURE_CLAIM'
        need=changed or high_stakes or (
            st['last_status']=='UNVERIFIED_SINGLE_SPEAKER_HYPOTHESIS' and not st['last_claimed_name'])
        return {'ask':bool(need),'reason':('MULTIPLE_POSSIBLE_SPEAKERS' if st['uncertainty'] else
            'SPEAKER_CHANGE_UNCONFIRMED' if changed else
            'HIGH_STAKES_UNVERIFIED_PERSON' if high_stakes else
            'FIRST_CONTACT_IDENTITY_UNKNOWN' if need else 'CONTINUITY_SUFFICIENT_FOR_LOW_STAKES')}

    def mark_asked(self,session,channel):
        k=self._key(session,channel)
        if k not in self.sessions:raise ValueError('NO_CONVERSATION_TO_ASK_ABOUT')
        self.sessions[k]['last_identity_ask_epoch']=self.sessions[k]['epoch']

    def to_dict(self):
        return {'sessions':self.sessions,'turns':self.turns,'sensor_receipts':self.sensor_receipts,
                'lessons':self.lessons,'groundings':self.groundings,'min_teacher_sources':self.min_teacher_sources,
                'reference_learner':self.reference_learner.to_dict()}

    @classmethod
    def from_dict(cls,d):
        x=cls(d.get('min_teacher_sources',2));x.sessions=d.get('sessions',{});x.turns=d.get('turns',{});
        x.sensor_receipts=d.get('sensor_receipts',{});x.lessons=d.get('lessons',[]);x.groundings=d.get('groundings',{});
        x.reference_learner=ContextReferenceLearner.from_dict(d.get('reference_learner',{}));return x

    def digest(self):
        return hashlib.sha256(canonical(self.to_dict()).encode('utf8')).hexdigest()
