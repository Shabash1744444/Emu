"""G3.0B: small, evidence-led experiments on a private/shared lexicon.

NOT an implementation of Russian language acquisition. Host-sensor attestations,
partner private lexicons, and C4's beliefs are deliberately separate. Morphology
and character/audio mappings acquire operations from demonstrations, not rules
for Russian words. No imported LLM, spelling dictionary, or external answer oracle.
"""
from __future__ import annotations

from collections import defaultdict
import copy
from dataclasses import dataclass, field
import hashlib
import json
import random
import re
from typing import Optional


def serial(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(obj):
    return hashlib.sha256(serial(obj).encode('utf-8')).hexdigest()


def token(raw):
    if not isinstance(raw,str) or not 1 <= len(raw) <= 60 or not raw.isalpha():
        raise ValueError('INVALID_SURFACE')
    return raw.casefold()


@dataclass(frozen=True)
class Receipt:
    kind: str
    data: dict
    root: str


class VirtualWorld:
    """Only world-side code can create grounded receipts; not a security boundary.

    A receipt is cross-checked against an append-only host log by its digest.
    This is an *in-process simulated authority*, NOT cryptographic host security.
    """
    def __init__(self):
        self._log: dict[str, Receipt] = {}
        self._serial = 0
        self.objects: dict[str,str] = {}
        self._trials: dict[str,dict] = {}

    def record(self, kind, **data):
        self._serial += 1
        entry={'seq':self._serial,'kind':kind,'data':data}
        r=Receipt(kind, copy.deepcopy(data), digest(entry))
        self._log[r.root]=r
        return Receipt(kind, copy.deepcopy(data), r.root)

    def verify(self, receipt, expected):
        if not isinstance(receipt,Receipt) or self._log.get(receipt.root)!=receipt or receipt.kind!=expected:
            raise ValueError('UNATTESTED_EVIDENCE')
        return receipt.data

    def introduce(self, obj_id, atom):
        if obj_id in self.objects: raise ValueError('DUPLICATE_OBJECT')
        self.objects[obj_id]=atom
        return self.record('OBSERVED_OBJECT', object=obj_id, atom=atom)

    def show(self, obj_id):
        if obj_id not in self.objects: raise ValueError('OBJECT_UNKNOWN')
        return self.record('OBSERVED_OBJECT', object=obj_id, atom=self.objects[obj_id])

    def demonstration(self, listener, word, obj_id):
        """Listener sees physical pointing + text; C4 only gets an event receipt."""
        if obj_id not in self.objects: raise ValueError('UNKNOWN_OBJECT')
        return self.record('POINTED_LABEL', listener=listener, word=token(word),
                           object=obj_id, atom=self.objects[obj_id])

    def start_trial(self, listener, word, scene_ids, target, *, trial_id):
        if trial_id in self._trials:raise ValueError('DUPLICATE_TRIAL_ID')
        if target not in scene_ids or len(scene_ids)<2 or len(scene_ids)!=len(set(scene_ids)):
            raise ValueError('INVALID_TARGET_SCENE')
        if any(o not in self.objects for o in scene_ids):raise ValueError('UNKNOWN_OBJECT')
        self._trials[trial_id]={'listener':listener,'word':token(word),
                                'scene':list(scene_ids),'target':target,'assessed':False}

    def verify_trial_target(self, trial_id, target, listener, word):
        t=self._trials.get(trial_id)
        if t is None or t['target']!=target or t['listener']!=listener or t['word']!=token(word):
            raise ValueError('UNCOMMITTED_TRIAL_TARGET')

    def assess(self, listener, word, scene_ids, answer, *, trial_id):
        if not scene_ids or len(scene_ids)!=len(set(scene_ids)) or len(scene_ids)<2:
            raise ValueError('INVALID_SCENE')
        if any(x not in self.objects for x in scene_ids):raise ValueError('UNKNOWN_OBJECT')
        if answer is not None and answer not in scene_ids:raise ValueError('ANSWER_OUT_OF_SCENE')
        trial=self._trials.get(trial_id)
        if not trial or trial['listener']!=listener or trial['word']!=token(word) or trial['scene']!=list(scene_ids) or trial['assessed']:
            raise ValueError('UNCOMMITTED_OR_REPLAYED_TRIAL')
        trial['assessed']=True
        # Raw observed response; target intentionally absent from receipt.
        return self.record('PARTNER_RESPONSE',listener=listener,word=token(word),
                           scene=list(scene_ids),choice=answer,trial_id=trial_id)


class SpeakerLexicon:
    """Words bind to sensed meanings; lexeme origin is not an authority claim."""
    def __init__(self, host, old_lexicon):
        self.host=host
        self.words={token(k):str(v) for k,v in old_lexicon.items()}
        self.additional:dict[str,dict]={}
        self.conflicts=[]

    def learn(self,word,atom,receipt,*,source):
        w=token(word)
        if not source:raise ValueError('SOURCE_REQUIRED')
        x=self.host.verify(receipt,'OBSERVED_OBJECT')
        if x['atom']!=atom: raise ValueError('UNWITNESSED_MEANING')
        if w in self.words and self.words[w]==atom:
            return 'KNOWN_PREEXISTING_MAPPING'
        if w in self.words and self.words[w]!=atom:
            self.conflicts.append({'word':w,'claimed':atom,'existing':self.words[w],
                                   'source':source,'root':receipt.root})
            return 'CONFLICT_NO_COMMIT'
        if w in self.additional and self.additional[w]['active'] and self.additional[w]['atom']!=atom:
            self.conflicts.append({'word':w,'claimed':atom,'existing':self.additional[w]['atom'],
                                   'source':source,'root':receipt.root})
            return 'CONFLICT_NO_COMMIT'
        if w in self.additional and self.additional[w]['active']:return 'KNOWN_SAME_MAPPING'
        self.additional[w]={'atom':atom,'source':source,'root':receipt.root,
                            'scope':'LOCAL_CONVENTION_UNVERIFIED_WITH_OTHERS', 'active':True}
        return 'LOCAL_MAPPING_GROUNDED'

    def lookup(self,w):
        w=token(w)
        if w in self.additional and self.additional[w]['active']:
            return self.additional[w]['atom']
        return self.words.get(w)

    def retract(self,source):
        count=0
        for entry in self.additional.values():
            if entry['active'] and entry['source']==source:
                entry['active']=False;count+=1
        return count


class OpaquePhonographicLearner:
    """Only learns from positionally ALIGNED character/discrete-sound examples.

    Does not infer segmentation, phonemes from waveform, stress, or orthography
    of natural Russian. It must reject ambiguous letter-sound correspondences.
    """
    def __init__(self, support=3):
        self.support=support
        self.evidence:dict[str,dict[str,set[str]]] = defaultdict(lambda:defaultdict(set))

    def observe(self, surface, sound_units, root):
        w=token(surface)
        if len(w)!=len(sound_units) or not root:raise ValueError('SEGMENT_ALIGNMENT_REQUIRED')
        if any(not isinstance(s,str) or not s for s in sound_units):raise ValueError('BAD_SOUND_UNIT')
        for a,b in zip(w,sound_units):self.evidence[a][b].add(root)

    def correspondences(self):
        found={}
        for ch, choices in self.evidence.items():
            supported=[sound for sound,roots in choices.items() if len(roots)>=self.support]
            if len(supported)==1 and len(choices)==1:found[ch]=supported[0]
        return found

    def encode(self,w):
        mapping=self.correspondences()
        w=token(w)
        if any(ch not in mapping for ch in w):return None
        return [mapping[ch] for ch in w]

    def fragments(self):
        """Known sound-producing graphemes can be reused in new syllables."""
        return sorted(self.correspondences())


class SyllableBoundaryLearner:
    """Induce a narrow, revisable segmentation convention from chunk examples.

    The code does not contain Cyrillic vowel/consonant classes. It needs
    explicitly segmented teaching samples; it does NOT discover phonetic
    syllabification from audio or solve complex Russian syllabification.
    """
    def __init__(self,min_contexts=3):
        self.min_contexts=min_contexts
        self.end_evidence=defaultdict(set)
        self.start_evidence=defaultdict(set)
        self.chunk_length_evidence=defaultdict(set)
        self.lessons=[]

    def teach(self,whole,chunks,source_root):
        w=token(whole)
        if not source_root or not chunks or any(not isinstance(s,str) for s in chunks):
            raise ValueError('MISSING_SEGMENT_EVIDENCE')
        normalized=[token(x) for x in chunks]
        if ''.join(normalized)!=w or len(normalized)<2:
            raise ValueError('NOT_A_VALID_SPLIT')
        if any(e['root']==source_root for e in self.lessons):
            raise ValueError('REPLAYED_SPLIT')
        self.lessons.append({'word':w,'chunks':normalized,'root':source_root})
        for i,c in enumerate(normalized):
            self.chunk_length_evidence[len(c)].add(source_root)
            if i<len(normalized)-1:self.end_evidence[c[-1]].add(source_root)
            if i>0:self.start_evidence[c[0]].add(source_root)

    def induced_classes(self):
        end={x for x,roots in self.end_evidence.items() if len(roots)>=self.min_contexts}
        start={x for x,roots in self.start_evidence.items() if len(roots)>=self.min_contexts}
        lengths=sorted(x for x,roots in self.chunk_length_evidence.items() if len(roots)>=self.min_contexts)
        return {'possible_chunk_ends':sorted(end),'possible_chunk_starts':sorted(start),
                'observed_chunk_lengths':lengths}

    def split(self,raw):
        w=token(raw);classes=self.induced_classes()
        ends=set(classes['possible_chunk_ends']);starts=set(classes['possible_chunk_starts'])
        if not ends or not starts:return {'status':'UNKNOWN'}
        boundaries=[i+1 for i in range(len(w)-1) if w[i] in ends and w[i+1] in starts]
        if not boundaries:return {'status':'UNKNOWN'}
        b=[0]+boundaries+[len(w)]
        chunks=[w[x:y] for x,y in zip(b,b[1:])]
        # No plausible reading if a piece lacks evidence for its ending
        # or its starting context. Mark heuristic not phonetic truth.
        supported_lengths=set(classes['observed_chunk_lengths'])
        if any(len(x) not in supported_lengths or x[-1] not in ends for x in chunks):
            return {'status':'UNKNOWN'}
        return {'status':'LEARNED_SEGMENTATION_PROPOSAL','chunks':chunks,
                'not_phonetic_certainty':True}


class ContrastiveMorphLearner:
    """Induces reusable tail substitutions from paired witnessed forms.

    Category keys (e.g. TO, FROM) are opaque semantic relations from scenes.
    No categories, Cyrillic endings, or Russian rules are hardcoded here.
    Requires independent distinct stems and independent source roots.
    """
    def __init__(self, min_stems=3, min_sources=2):
        self.min_stems=min_stems
        self.min_sources=min_sources
        self.pairs=[]

    @staticmethod
    def candidates(base,form):
        base=token(base);form=token(form)
        # Common prefix must remain nonempty; ambiguous tail lengths learned
        # by cross-stem support, not by memorizing one full word transformation.
        shared=0
        for a,b in zip(base,form):
            if a!=b:break
            shared+=1
        if shared==0:return []
        return [(base[i:],form[i:]) for i in range(1,shared+1)]

    def observe(self,base,form,role,root,source):
        if not isinstance(role,str) or not role or not root or not source:raise ValueError('INCOMPLETE_EVIDENCE')
        c=self.candidates(base,form)
        if not c:raise ValueError('NO_SHARABLE_STRUCTURE')
        e={'base':token(base),'form':token(form),'role':role,'root':root,'source':source,'active':True}
        if any(x['root']==root for x in self.pairs):raise ValueError('REPLAYED_WITNESS')
        self.pairs.append(e)

    def retract(self,source):
        count=0
        for p in self.pairs:
            if p['source']==source and p['active']:
                p['active']=False;count+=1
        return count

    def rules(self,role):
        examples=[p for p in self.pairs if p['role']==role and p['active']]
        rules=defaultdict(list)
        for e in examples:
            for before,after in self.candidates(e['base'],e['form']):
                rules[(before,after)].append(e)
        eligible={}
        for rule,es in rules.items():
            distinct={x['base'] for x in es}
            sources={x['source'] for x in es}
            if len(distinct)>=self.min_stems and len(sources)>=self.min_sources:
                eligible[rule]=len(distinct)
        return eligible

    def predict(self,base,role):
        base=token(base)
        rules=self.rules(role)
        possibilities=[]
        for (old,new),support in rules.items():
            if old and base.endswith(old) and len(base)>len(old):
                possibilities.append((base[:-len(old)]+new, old, new, support))
        if not possibilities:return {'status':'UNKNOWN','candidate':None}
        # Prefer most specific generalization that survives cross-stem support.
        longest=max(len(x[1]) for x in possibilities)
        survivors=[x for x in possibilities if len(x[1])==longest]
        forms={x[0] for x in survivors}
        if len(forms)!=1:
            return {'status':'AMBIGUOUS','candidate':None,'options':sorted(forms)}
        return {'status':'LEARNED_FORM_PROPOSAL','candidate':survivors[0][0],
                'support_stems':max(x[3] for x in survivors),
                'not_dictionary_certainty':True}


class PrivatePartner:
    """Independent simulated listener; cannot be inspected by C4 in a trial."""
    def __init__(self, partner_id, misses_remaining=0):
        self.partner_id=partner_id
        self.misses_remaining=misses_remaining
        self._meanings:dict[str,set[str]]=defaultdict(set)

    def witness_demonstration(self,receipt,host):
        d=host.verify(receipt,'POINTED_LABEL')
        if d['listener']!=self.partner_id:raise ValueError('WRONG_LISTENER')
        if self.misses_remaining>0:
            self.misses_remaining-=1
            return 'MISSED_DEMONSTRATION'
        self._meanings[d['word']].add(d['atom'])
        return 'LEARNED_SIMULATED_LABEL'

    def respond(self,word,scene,host):
        atoms=self._meanings.get(token(word),set())
        candidates=[o for o in scene if host.objects[o] in atoms]
        # Abstain if another object shares the same concept or conflicting senses.
        return candidates[0] if len(candidates)==1 else None


class PartnerBeliefs:
    """C4 only sees outward host-observed behavior. Not the partner's mind."""
    def __init__(self,host,min_successes=3):
        self.host=host
        self.min_successes=min_successes
        self.observations=defaultdict(list)
        self.told=set()  # evidence of explanation, not evidence of understanding
        self.allowed_observations=set()
        self.learning_epoch_start={}  # evidence since latest independently observed explanation

    def noted_explanation(self,partner,word,receipt):
        d=self.host.verify(receipt,'POINTED_LABEL')
        if d['listener']!=partner or d['word']!=token(word):raise ValueError('NOT_THE_SAME_EXPLANATION')
        self.told.add((partner,token(word),d['atom']))
        self.learning_epoch_start[(partner,token(word),d['atom'])]=len(self.observations.get((partner,token(word),d['atom']),[]))

    def record_trial(self,partner,word,target_obj,receipt):
        d=self.host.verify(receipt,'PARTNER_RESPONSE')
        if d['listener']!=partner or d['word']!=token(word) or target_obj not in d['scene']:
            raise ValueError('MISMATCHED_OBSERVATION')
        self.host.verify_trial_target(d['trial_id'],target_obj,partner,word)
        # Target must have been chosen before trial and is NOT carried in receipt.
        # Require unique trial id per observed partner word.
        key=(partner,token(word))
        if d['trial_id'] in self.allowed_observations:
            raise ValueError('REPLAYED_TRIAL')
        self.allowed_observations.add(d['trial_id'])
        target_atom=self.host.objects[target_obj]
        correct=(d['choice']==target_obj)
        self.observations[(partner,token(word),target_atom)].append({
            'correct':correct,'target_obj':target_obj,
            'scene_atoms':tuple(sorted(self.host.objects[x] for x in d['scene'])),
            'root':receipt.root,'trial':d['trial_id']})
        return correct

    def status(self,partner,word,atom):
        k=(partner,token(word),atom)
        evidence=self.observations.get(k,[])[self.learning_epoch_start.get(k,0):]
        successes=[e for e in evidence if e['correct']]
        failures=[e for e in evidence if not e['correct']]
        distinct={e['scene_atoms'] for e in successes}
        different_referents={e['target_obj'] for e in successes}
        # Any recent failure invalidates supported competence; no silent forgiveness.
        if failures:return 'UNRELIABLE_OR_UNKNOWN'
        if (len(successes)>=self.min_successes and len(distinct)>=self.min_successes
            and len(different_referents)>=self.min_successes):
            return 'BEHAVIORALLY_SUPPORTED_NOT_MIND_READ'
        if successes:return 'PROVISIONAL_SINGLE_OR_REPEATED_CONTEXT'
        if (partner,token(word),atom) in self.told:return 'EXPLAINED_NOT_CONFIRMED'
        return 'NO_EVIDENCE_OF_PARTNER_UNDERSTANDING'

    def next_action(self,partner,word,atom):
        status=self.status(partner,word,atom)
        if status=='BEHAVIORALLY_SUPPORTED_NOT_MIND_READ':return 'USE_WORD_WITH_MONITORING'
        if status=='PROVISIONAL_SINGLE_OR_REPEATED_CONTEXT':return 'TEST_IN_NEW_CONTEXT'
        if status=='UNRELIABLE_OR_UNKNOWN':return 'CLARIFY_OR_EXPLAIN'
        return 'INTRODUCE_AND_DEMONSTRATE_MEANING'


class WordCoiner:
    """Generate novel pronounceable-looking strings from witnessed letter parts.

    Candidate *form* is invented; its *meaning* still requires grounding.
    No assumption others understand it, and no Russian phonotactic oracle.
    """
    def __init__(self, phonographic, lexicon):
        self.phonographic=phonographic
        self.existing={token(x) for x in lexicon}

    def candidates(self, seed, min_length=4, max_length=7):
        alphabet=self.phonographic.fragments()
        if not alphabet:return []
        rng=random.Random(seed)
        out=set()
        for _ in range(200):
            n=rng.randrange(min_length,max_length+1)
            w=''.join(rng.choice(alphabet) for i in range(n))
            if w not in self.existing and self.phonographic.encode(w):out.add(w)
        return sorted(out)


def snapshot(lx,phon,morph,bel,syllables=None):
    return {'local_words':lx.additional,'conflicts':lx.conflicts,
            'syllable_examples':syllables.lessons if syllables is not None else [],
            'letter_sounds':{a:{b:sorted(r) for b,r in x.items()} for a,x in phon.evidence.items()},
            'morph_pairs':morph.pairs,
            'partner_evidence':[{ 'partner':k[0],'word':k[1],'atom':k[2],'trials':v}
                for k,v in sorted(bel.observations.items())],
            'explanations':sorted(map(list,bel.told)),
            'epoch_start':[{'partner':a,'word':b,'atom':c,'start':n}
                           for (a,b,c),n in sorted(bel.learning_epoch_start.items())]}
