"""G2.5: prelinguistic event/claim composition in a *simulated* world.

Typed, epistemically scoped, event sourced. A quote is evidence that someone
uttered a proposition, NOT evidence that the proposition holds. A plan is NOT
an achieved effect. Nothing here interprets Russian text; lesson/query language
is learned separately. Simulator receipts are not claims about the real world.
"""
from __future__ import annotations
import hashlib, json
from copy import deepcopy


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def event_root(event):
    return 'story:' + hashlib.sha256(canon(event).encode('utf-8')).hexdigest()


def validate(event):
    if not isinstance(event, dict): raise ValueError('NOT_EVENT')
    need=('story_id','event_id','time_ns','kind')
    if any(not isinstance(event.get(k), str) or not event[k] for k in need if k != 'time_ns'):
        raise ValueError('INVALID_ID_OR_KIND')
    if type(event.get('time_ns')) is not int or event['time_ns'] < 0:
        raise ValueError('INVALID_TIME')
    k=event['kind']
    if k == 'OBSERVE':
        if not isinstance(event.get('state'), dict): raise ValueError('BAD_STATE')
    elif k in ('INTENT', 'ACTION'):
        if not isinstance(event.get('actor'), str) or not event['actor']: raise ValueError('BAD_ACTOR')
        if not isinstance(event.get('changes'), dict) or not event['changes']: raise ValueError('BAD_CHANGES')
        if k == 'ACTION':
            if event.get('outcome') not in ('SUCCEEDED','FAILED'): raise ValueError('BAD_OUTCOME')
            if not isinstance(event.get('before'), dict) or not isinstance(event.get('after'), dict):
                raise ValueError('MISSING_BEFORE_AFTER')
            if (event['outcome']=='FAILED') != (event['before']==event['after']):
                raise ValueError('OUTCOME_DOES_NOT_MATCH_EFFECT')
            if event['outcome']=='SUCCEEDED' and event['after']==event['before']:
                raise ValueError('NO_CHANGE')
    elif k=='REPORT':
        if not isinstance(event.get('speaker'), str) or not event['speaker']: raise ValueError('BAD_SPEAKER')
        validate_statement(event.get('content'))
    else:raise ValueError('UNKNOWN_EVENT_KIND')
    return True


def validate_statement(node, depth=0):
    if depth>5 or not isinstance(node,dict):raise ValueError('INVALID_STATEMENT')
    if node.get('kind')=='STATE':
        if not isinstance(node.get('key'),str) or not node['key']:raise ValueError('BAD_KEY')
        if not isinstance(node.get('value'),str) or not node['value']:raise ValueError('BAD_VALUE')
    elif node.get('kind')=='REPORT':
        if not isinstance(node.get('speaker'),str) or not node['speaker']:raise ValueError('BAD_REPORTED_SPEAKER')
        validate_statement(node.get('content'), depth+1)
    else:raise ValueError('UNKNOWN_STATEMENT_KIND')


class StoryMind:
    """A stream of partial world states, intentions, actions, and nested reports.

    Evidence is per-story, per-event-id, one host origin; no cross-world leakage.
    Unknown observations remain UNKNOWN, not FALSE. All transitions are append-only.
    """
    def __init__(self):
        self.stories={}
        self.roots={}

    def observe(self, event, root):
        validate(event)
        if root != event_root(event):raise PermissionError('ROOT_MISMATCH')
        if root in self.roots:return False
        s=self.stories.setdefault(event['story_id'], {'state':{},'state_support':{},'events':[], 'ids':{}})
        if event['event_id'] in s['ids']:raise ValueError('EVENT_ID_CONFLICT')
        if s['events'] and event['time_ns'] < s['events'][-1]['event']['time_ns']:
            raise ValueError('TIME_REORDER')
        k=event['kind']
        if k == 'OBSERVE':
            # A full host snapshot is allowed, but its scope never escapes SIMULATION.
            s['state']=deepcopy(event['state'])
            s['state_support']={key:root for key in event['state']}
        elif k == 'ACTION':
            if event['before'] != s['state']:raise ValueError('ACTION_PRESTATE_CONFLICT')
            if event['outcome']=='SUCCEEDED':
                expected={**s['state'],**event['changes']}
                if event['after'] != expected:raise ValueError('ACTION_EFFECT_MISMATCH')
                s['state']=deepcopy(event['after'])
                for key in event['changes']:s['state_support'][key]=root
            else:
                if event['after'] != s['state']:raise ValueError('FAILED_ACTION_CHANGED_STATE')
        # INTENT and REPORT have no world-state side effects.
        node={'event':deepcopy(event),'root':root,'state_after':deepcopy(s['state']),
              'support_after':deepcopy(s['state_support'])}
        s['events'].append(node);s['ids'][event['event_id']]=len(s['events'])-1
        self.roots[root]=event['story_id']
        return True

    def ask(self, story_id, query):
        s=self.stories.get(story_id)
        if s is None:return {'status':'UNKNOWN','reason':'NO_STORY'}
        kind=query.get('kind')
        key=query.get('key')
        when=query.get('as_of')
        if when is None:ix=len(s['events'])-1
        elif when in s['ids']:ix=s['ids'][when]
        else:return {'status':'UNKNOWN','reason':'UNKNOWN_EVENT_TIME'}
        if kind == 'WORLD':
            if not isinstance(key,str) or key not in s['events'][ix]['state_after']:
                return {'status':'UNKNOWN','reason':'UNOBSERVED_STATE'}
            e=s['events'][ix]
            return {'status':'KNOWN','value':e['state_after'][key],
                    'scope':'SIMULATED_WORLD','as_of':e['event']['event_id'],
                    'support':e['support_after'][key]}
        if kind in ('INTENT','ACTION'):
            actor=query.get('actor')
            cand=[e for e in s['events'][:ix+1] if e['event']['kind']==kind and
                   e['event'].get('actor')==actor and key in e['event'].get('changes',{})]
            if not cand:return {'status':'UNKNOWN','reason':'NO_'+kind+'_RECEIPT'}
            e=cand[-1];v=e['event']
            return {'status':'KNOWN','value':v['changes'][key],
                    'outcome':v.get('outcome','INTENDED_NOT_EXECUTED'),
                    'scope':'SIMULATED_'+kind,'support':e['root']}
        if kind=='REPORTED':
            speaker=query.get('speaker');path=query.get('path',[])
            if not isinstance(path,list) or len(path)>5:return {'status':'UNKNOWN','reason':'BAD_QUOTE_PATH'}
            cand=[]
            for e in s['events'][:ix+1]:
                v=e['event']
                if v['kind']!='REPORT' or v.get('speaker')!=speaker:continue
                frame=v['content']
                for name in path:
                    if frame.get('kind')=='REPORT' and frame.get('speaker')==name:frame=frame['content']
                    else:break
                else:
                    if frame.get('kind')=='STATE' and frame.get('key')==key:cand.append((e,frame))
            if not cand:return {'status':'UNKNOWN','reason':'NO_MATCHING_REPORTED_CONTENT'}
            e,v=cand[-1]
            return {'status':'KNOWN','value':v['value'], 'scope':'REPORTED_ONLY',
                    'speaker':speaker,'quote_path':path,'support':e['root']}
        if kind=='ORDER':
            a=s['ids'].get(query.get('a'));b=s['ids'].get(query.get('b'))
            if a is None or b is None:return {'status':'UNKNOWN','reason':'MISSING_EVENT'}
            t1=s['events'][a]['event']['time_ns'];t2=s['events'][b]['event']['time_ns']
            return {'status':'KNOWN','value':'BEFORE' if t1<t2 else 'AFTER' if t1>t2 else 'SIMULTANEOUS',
                    'scope':'SIMULATED_EVENT_TIME',
                    'support':[s['events'][a]['root'],s['events'][b]['root']]}
        return {'status':'UNKNOWN','reason':'UNSUPPORTED_QUERY_TYPE'}

    def to_dict(self):return {'stories':deepcopy(self.stories),'roots':deepcopy(self.roots)}
    @classmethod
    def from_dict(cls,d):
        x=cls()
        for sid,v in sorted(d['stories'].items()):
            for node in v['events']:
                assert x.observe(node['event'],node['root'])
        if canon(x.to_dict())!=canon(d):raise ValueError('STORY_RESTORE_MISMATCH')
        return x
    def digest(self):return hashlib.sha256(canon(self.to_dict()).encode()).hexdigest()

class MeaningQuestionLearner:
    """Infer which *existing* semantic question operation a surface question denotes.

    Grounded feedback is the answer to the query in a simulator story. No Russian
    vocabulary or known word forms live here. The available query operators are
    an architectural prior; this does NOT create new primitives or parse prose.
    Names are mapped from independently furnished simulated scene aliases.
    """
    OPS=('WORLD','INTENT','ACTION','REPORTED')
    def __init__(self, min_support=6, precision=.96):
        self.min_support=min_support;self.precision=precision;self.examples=[]
        self.lexicon=set();self.rules={};self.fitted=False

    @staticmethod
    def words(line):
        import re
        return re.findall(r'[^\W_]+',line.casefold(),re.UNICODE)

    def _parse(self,utterance, aliases, key):
        if not isinstance(aliases,dict) or not isinstance(key,str):return None
        words=self.words(utterance)
        if not words:return None
        entities=[];used=set()
        for name,uid in aliases.items():
            span=self.words(name)
            hits=[i for i in range(len(words)-len(span)+1) if words[i:i+len(span)]==span]
            if len(hits)>1:return None
            if hits:
                start=hits[0];finish=start+len(span)
                if used.intersection(range(start,finish)):return None
                used.update(range(start,finish));entities.append(uid)
        if len(entities)>1:return None
        # The grounded artifact alias is given by the independent scene, not
        # guessed from language. Remove it as a referent, just as for actors.
        object_alias=key.split(':',1)[-1]
        objwords=self.words(object_alias)
        hits=[i for i in range(len(words)-len(objwords)+1) if words[i:i+len(objwords)]==objwords]
        if len(hits)!=1:return None
        if used.intersection(range(hits[0],hits[0]+len(objwords))):return None
        used.update(range(hits[0],hits[0]+len(objwords)))
        residue=[w for i,w in enumerate(words) if i not in used]
        feats={' '.join(residue[i:i+n]) for n in (1,2) for i in range(len(residue)-n+1)}
        return {'words':words,'residue':residue,'feats':feats,'who':entities[0] if entities else None}

    def observe(self,mind,story,utterance,aliases,key,answer,source):
        if not isinstance(source,str) or not source:raise ValueError('SOURCE_REQUIRED')
        parsed=self._parse(utterance,aliases,key)
        if parsed is None:raise ValueError('AMBIGUOUS_SURFACE_REFERENT')
        candidates=[]
        for op in self.OPS:
            if op !='WORLD' and parsed['who'] is None:continue
            query={'kind':op,'key':key}
            if op in ('INTENT','ACTION'):query['actor']=parsed['who']
            if op=='REPORTED':query['speaker']=parsed['who']
            pred=mind.ask(story,query)
            val=pred.get('outcome') if op=='ACTION' else pred.get('value')
            if pred['status']=='KNOWN' and val==answer:candidates.append(op)
        ex={'sentence':utterance,'residue':parsed['residue'],'candidates':candidates,
            'feats':sorted(parsed['feats']),'source':source}
        self.examples.append(ex);self.fitted=False
        return {'possible_programs':candidates,'identifiable':len(candidates)==1}

    def fit(self):
        from collections import Counter
        self.lexicon={w for e in self.examples for w in e['residue']}
        freq=Counter(f for e in self.examples for f in e['feats'])
        forms=[f for f,n in freq.items() if n>=self.min_support]
        self.rules={op:[] for op in self.OPS}
        # Learn both presence and absence evidence, and avoid overinterpreting
        # a feature that was never contrasted against competing meanings.
        for op in self.OPS:
            scored=[]
            for f in forms:
                for absent in [None]+forms:
                    if f==absent:continue
                    subset=[e for e in self.examples if f in e['feats'] and
                            (absent is None or absent not in e['feats'])]
                    if len(subset)<self.min_support:continue
                    if len({x['sentence'] for x in subset})<2:continue
                    # Ambiguous supervisory answers cannot establish meaning.
                    positives=sum(op in e['candidates'] for e in subset)
                    uniquely_identified=sum(e['candidates']==[op] for e in subset)
                    if positives/len(subset)<self.precision or uniquely_identified<2:continue
                    score=(positives/len(subset),len(subset), -int(absent is not None),-len(f))
                    scored.append((score,f,absent))
            scored.sort(reverse=True)
            self.rules[op]=[{'requires':f,'forbids':neg} for _,f,neg in scored[:8]]
        self.fitted=True

    def predict(self,mind,story,utterance,aliases,key):
        if not self.fitted:self.fit()
        parsed=self._parse(utterance,aliases,key)
        if parsed is None:return {'status':'UNKNOWN','reason':'AMBIGUOUS_REFERENTS'}
        if any(w not in self.lexicon for w in parsed['residue']):
            return {'status':'UNKNOWN','reason':'UNSEEN_SURFACE_CONSTRUCTION'}
        votes=[]
        for op,rules in self.rules.items():
            if op!='WORLD' and parsed['who'] is None:continue
            if any(r['requires'] in parsed['feats'] and
                   (r['forbids'] is None or r['forbids'] not in parsed['feats']) for r in rules):
                votes.append(op)
        if len(votes)!=1:return {'status':'UNKNOWN','reason':'NO_UNIQUE_LEARNED_MEANING','candidates':votes}
        op=votes[0];q={'kind':op,'key':key}
        if op in ('INTENT','ACTION'):q['actor']=parsed['who']
        if op=='REPORTED':q['speaker']=parsed['who']
        answer=mind.ask(story,q)
        return {**answer,'learned_operation':op}

    def revoke(self,source):
        self.examples=[e for e in self.examples if e['source']!=source]
        self.fitted=False
        self.fit()

    def to_dict(self):
        if not self.fitted:self.fit()
        return {'min_support':self.min_support,'precision':self.precision,
        'examples':deepcopy(self.examples),'rules':deepcopy(self.rules),'lexicon':sorted(self.lexicon)}
    @classmethod
    def from_dict(cls,d):
        m=cls(d['min_support'],d['precision']);m.examples=deepcopy(d['examples']);m.fit()
        if canon(m.to_dict())!=canon(d):raise ValueError('QUESTION_LEARNER_RESTORE_MISMATCH')
        return m
    def digest(self):return hashlib.sha256(canon(self.to_dict()).encode()).hexdigest()
