"""C4/G1.4: weakly grounded discovery of two-event boundaries.

No clause spans, boundary markers, Russian terms, pronoun/case rules or
answers are supplied to the learner during paired training. A separate
*atomic* organ is trained from verified single-event demonstrations. For each
unaligned pair, the model enumerates surface partitions and retains only
those whose two atomic interpretations agree with the independent host's
node witnesses. It then learns connector/graph relation correspondences.

This is WEAKLY SUPERVISED, not unsupervised speech segmentation. The host
provides typed event witnesses and scene names; its ontology is inherited.
A useful minimal stepping stone, not proof of spontaneous natural language.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from typing import Any

from .frame_induction import GroundedFrameInducer, _tokens, _json, _mentions, _features_role, _features_attr
from .temporal import Interval, order


def _hash(x):
    return hashlib.sha256(_json(x).encode('utf8')).hexdigest()


def _expected(receipt: dict):
    w = receipt['witness']
    attrs = {str(k): str(v) for k,v in w['attributes'].items()}
    if w.get('event_time') is not None:
        if w.get('time_axis') not in {'SIM_UTC', 'UTC'}:
            raise ValueError('unknown event clock')
        t = receipt.get('utterance_time')
        if not t:
            raise ValueError('missing host utterance clock')
        rel = order(Interval(**w['event_time']), Interval(**t))
        if rel != 'UNKNOWN_OR_OVERLAP':
            attrs['temporal_relation'] = rel
    return {'roles':{str(k):str(v) for k,v in w['roles'].items()}, 'attributes':attrs}


class WeakBoundaryInducer:
    VERSION = 1

    def __init__(self, atomic: GroundedFrameInducer | None = None, *, max_gap=3, min_support=3):
        if not 1 <= max_gap <= 5:
            raise ValueError('bounded gap required')
        self.atomic = atomic or GroundedFrameInducer()
        self.max_gap = max_gap
        self.min_support = min_support
        self.examples: list[dict] = []
        self.verified_roots: set[str] = set()
        self.lexicon: dict[str,dict[str,dict[str,int]]] = {}
        self.ellipsis: dict[str,dict[str,dict[str,int]]] = {}
        self.alignment_ledger: list[dict] = []
        self.rejected_alignments: list[dict] = []
        self.trained = False

    def observe_atomic(self, example: dict, *, verified_receipts: dict[str,dict]):
        """Atomic teaching remains separately attested, never invented from an utterance."""
        return self.atomic.observe(example, verified_receipts=verified_receipts)

    def observe_pair(self, ex: dict, *, verified_receipts: dict[str,dict]):
        """NO ex['clauses'], ex['boundary'], or oracle substring labels allowed."""
        if any(k in ex for k in ('clauses','boundary','aligned_spans','subutterances')):
            raise ValueError('paired training may not supply clause alignment')
        if ex.get('origin') not in {'SIMULATION','HOST_OBSERVED'}:
            raise PermissionError('not an independently supplied simulated/observed episode')
        if not ex.get('teacher_source'):
            raise ValueError('teacher provenance missing')
        root = str(ex.get('graph_root',''))
        graph = verified_receipts.get(root)
        if not graph:
            raise PermissionError('unattested episode root')
        roots = [str(x) for x in graph.get('node_roots',[])]
        if len(roots)!=2 or len(set(roots))!=2 or root in roots:
            raise ValueError('invalid graph node roots')
        if _json(ex.get('link_witness')) != _json(graph.get('witness')):
            raise PermissionError('graph semantics modified by teacher')
        link = graph['witness']
        if not isinstance(link,dict) or set(link) != {'relation','attribution'}:
            raise ValueError('graph requires typed link witness')
        if not all(r in verified_receipts for r in roots):
            raise PermissionError('missing independently attested world nodes')
        # A teacher must not be able to redefine the available objects by
        # attaching a legitimate root to a doctored scene inventory.
        entities = {str(k):str(v) for k,v in ex.get('entities',{}).items()}
        for r in roots:
            rec=verified_receipts[r]
            if 'witness' not in rec or 'entities' not in rec:
                raise ValueError('invalid independent receipt')
            for eid,name in rec['entities'].items():
                if entities.get(str(eid)) != str(name):
                    raise PermissionError('scene does not match independent node receipt')
        witness0 = verified_receipts[roots[0]]['witness']
        if link['attribution']!='@NARRATOR' and link['attribution'] not in witness0['roles']:
            raise ValueError('quoted role not in first event')
        if not _tokens(ex.get('utterance','')):
            raise ValueError('empty teacher surface')
        if root in self.verified_roots:
            return False
        if any(r in self.verified_roots for r in roots):
            raise PermissionError('node receipt reused as new independent episode')
        # Freeze the semantic content at intake rather than retaining a mutable
        # pointer to the host dict. This is evidence provenance, NOT an answer key
        # supplied to the inference method.
        self.examples.append({'surface': str(ex['utterance']), 'entities':entities,
                              'graph_root':root, 'node_roots':roots,
                              'node_witnesses':[_expected(verified_receipts[r]) for r in roots],
                              'relation':str(link['relation']),
                              'attribution':str(link['attribution']),
                              'teacher_source':str(ex['teacher_source'])})
        self.verified_roots.update([root,*roots])
        self.trained=False
        return True

    def _partial_event(self, text: str, entities: dict[str,str]):
        """Obtain a conservative 1-role-missing interpretation from atomic skills.

        No pronoun, Russian suffix or role name is coded. Evidence for mapping
        any overt mention to a role comes from previously learned cue/role
        contrasts of the atomic learner. The missing referent is UNBOUND.
        """
        toks,mentions,problem=_mentions(text,entities)
        if problem or not mentions:return None
        if len(self.atomic.role_binders)!=1:return None
        schema=next(iter(self.atomic.role_binders))
        binder=self.atomic.role_binders[schema]
        roles=sorted(binder.seen_roles)
        if len(roles)!=len(mentions)+1:return None
        nonmentions=[t for i,t in enumerate(toks) if i not in {m['index'] for m in mentions}]
        if set(nonmentions)-self.atomic.seen_surface_tokens:return None
        # Demand an unambiguous, repeatedly witnessed role cue for each overt
        # mention. A missing role is NOT inferred from sentence position alone.
        assigned={}
        for rank,m in enumerate(mentions):
            f=_features_role(toks,m,rank,len(mentions))
            options=[]
            for role in roles:
                strongest=0
                for feat in f:
                    c=binder.cue_roles.get(feat)
                    if c and sum(c.values())>=3 and c[role]/sum(c.values())>=.95:
                        strongest=max(strongest,c[role])
                if strongest:options.append((strongest,role))
            options.sort(reverse=True)
            if len(options)!=1 and (not options or options[0][0]==options[1][0]):
                return None
            role=options[0][1]
            if role in assigned:return None
            assigned[role]=m['entity_id']
        missed=list(set(roles)-set(assigned))
        if len(missed)!=1:return None
        attrs={}
        features=_features_attr(toks,mentions,self.atomic.attr_vocab)
        for field,head in self.atomic.cues.items():
            value,_,why=head.predict(features)
            if value is None:return None
            attrs[field]=value
        return {'roles':assigned,'attributes':attrs,'missing_role':missed[0]}

    def _splits(self, surface: str, entities: dict[str,str], *, require_known_connector=False,
                allow_ellipsis=False):
        tokens=_tokens(surface)
        # Name overlap cannot be used as a connective; better UNKNOWN than
        # dropping one of the participants as a syntactic cue.
        entity_tokens={t for n in entities.values() for t in _tokens(n)}
        out=[]
        for k in range(1,len(tokens)-1):
            for length in range(1,self.max_gap+1):
                if k+length >= len(tokens): continue
                marker=tokens[k:k+length]
                if set(marker)&entity_tokens:continue
                key=' '.join(marker)
                if require_known_connector and key not in self.lexicon: continue
                left=' '.join(tokens[:k]);right=' '.join(tokens[k+length:])
                # Parse with same generic single-event grammar in both clauses.
                pa=self.atomic.predict(left,entities,speaker='quoted',source_root='analysis')
                pb=self.atomic.predict(right,entities,speaker='quoted',source_root='analysis')
                if pa.get('status')!='CANDIDATE':continue
                left_h=pa['hypothesis']
                if pb.get('status')=='CANDIDATE':
                    right_h=pb['hypothesis']
                elif allow_ellipsis:
                    right_h=self._partial_event(right,entities)
                    if right_h is None:continue
                else:continue
                out.append({'split':k,'gap':length,'connector':key,
                            'left':left_h,'right':right_h})
        return out

    def fit(self):
        if not self.atomic.trained:self.atomic.fit()
        tally=defaultdict(lambda:{'relation':Counter(),'attribution':Counter()})
        ellipsis=defaultdict(lambda:defaultdict(Counter))
        self.alignment_ledger=[];self.rejected_alignments=[]
        for e in self.examples:
            alignments=self._splits(e['surface'],e['entities'],allow_ellipsis=True)
            matching=[]
            for a in alignments:
                gold_l,gold_r=e['node_witnesses']
                if {'roles':a['left']['roles'],'attributes':a['left']['attributes']} != gold_l:
                    continue
                child=a['right']
                if child['attributes']!=gold_r['attributes']:
                    continue
                if any(gold_r['roles'].get(r)!=v for r,v in child['roles'].items()):
                    continue
                missing=child.get('missing_role')
                if missing is None:
                    if child['roles'] == gold_r['roles']:
                        matching.append((a,None))
                else:
                    referent=gold_r['roles'].get(missing)
                    antecedents=[r for r,v in a['left']['roles'].items() if v==referent]
                    if len(antecedents)==1:
                        matching.append((a,(missing,antecedents[0])))
            if len(matching)!=1:
                self.rejected_alignments.append({'root':e['graph_root'],'reason':
                    'AMBIGUOUS_WORLD_ALIGNMENT' if len(matching)>1 else 'NO_WORLD_ALIGNMENT',
                    'valid_partitions':len(matching)})
                continue
            a,anaphora=matching[0];key=a['connector']
            tally[key]['relation'][e['relation']]+=1
            tally[key]['attribution'][e['attribution']]+=1
            if anaphora:
                child_role,parent_role=anaphora
                ellipsis[key][child_role][parent_role]+=1
            self.alignment_ledger.append({'root':e['graph_root'],'connector':key,
                                          'split':a['split'],'gap':a['gap'],
                                          'elided_reference':list(anaphora) if anaphora else None})
        self.lexicon={k:{kk:dict(sorted(vv.items())) for kk,vv in v.items()}
                      for k,v in sorted(tally.items())}
        self.ellipsis={key:{role:dict(sorted(v.items())) for role,v in mp.items()}
                       for key,mp in sorted(ellipsis.items())}
        self.trained=True

    def predict(self, surface: str, entities:dict[str,str], *, speaker:str,
                source_root:str, world:str, predicate_slot:str, polarity_slot:str,
                utterance_time:dict|None=None):
        if not self.trained:
            return {'status':'UNKNOWN','reason':'NOT_TRAINED'}
        if not predicate_slot or not polarity_slot:
            return {'status':'UNKNOWN','reason':'MISSING_WORLD_SCHEMA'}
        toks=_tokens(surface)
        names={t for s in entities.values() for t in _tokens(s)}
        # Scene ambiguity suppresses learned lexical boundary rather than
        # silently moving an entity from event content to connective.
        if any(tok in names for cue in self.lexicon for tok in cue.split() if tok in toks):
            return {'status':'UNKNOWN','reason':'CONNECTIVE_OR_ENTITY_AMBIGUOUS'}
        candidates=[]
        for a in self._splits(surface,entities,require_known_connector=True,allow_ellipsis=True):
            votes=self.lexicon[a['connector']]
            labels={}
            for k,counts in votes.items():
                if sum(counts.values())<self.min_support or len(counts)!=1:
                    break
                labels[k]=next(iter(counts))
            if len(labels)==2:
                candidates.append((a,labels))
        if len(candidates)!=1:
            return {'status':'UNKNOWN', 'reason':
                    'AMBIGUOUS_PARTITION' if candidates else 'UNRESOLVED_PARTITION',
                    'candidate_count':len(candidates)}
        a,labels=candidates[0]
        missing=a['right'].get('missing_role')
        if missing:
            options=self.ellipsis.get(a['connector'],{}).get(missing,{})
            if len(options)!=1 or sum(options.values())<self.min_support:
                return {'status':'UNKNOWN','reason':'ELLIPSIS_UNGROUNDED_OR_AMBIGUOUS'}
            antecedent=next(iter(options))
            eid=a['left']['roles'].get(antecedent)
            if eid is None or eid in a['right']['roles'].values():
                return {'status':'UNKNOWN','reason':'ELLIPSIS_REFERENT_UNAVAILABLE'}
            a['right']['roles']={**a['right']['roles'],missing:eid}
        frames=[]
        for idx,which in enumerate(('left','right')):
            h=a[which]; attrs=dict(h['attributes'])
            pred=attrs.get(predicate_slot)
            if not pred:
                return {'status':'UNKNOWN','reason':'NO_PREDICATE_FIELD'}
            pol=attrs.get(polarity_slot,'UNSET')
            frame={'episode_id':f'{source_root}:{idx}','world':world,
                   'predicate':pred,'bindings':sorted(h['roles'].items()),
                   'semantic_attributes':sorted(attrs.items()),
                   'polarity':pol if pol in {'POS','NEG','UNSET'} else 'UNSET',
                   'status':'REPORTED','source':'language:inference',
                   'source_root':source_root,'speaker':speaker,
                   'event_time':None,'utterance_time':utterance_time,
                   'quote_scope':[]}
            frames.append(frame)
        if labels['attribution']!='@NARRATOR':
            role=labels['attribution'];values=dict(frames[0]['bindings'])
            if role not in values:return {'status':'UNKNOWN','reason':'UNBOUND_ATTRIBUTION'}
            frames[1]['speaker']=values[role]
            frames[1]['quote_scope']=[frames[0]['episode_id']]
        return {'status':'CANDIDATE','confidence':min(.8, .5+len(self.alignment_ledger)/200),
                'frames':frames,'link':{'relation':labels['relation'],
                    'attribution':labels['attribution'],'source_root':source_root,
                    'status':'REPORTED'},'trace':{'induced_split':a['split'],
                    'connector_token_length':a['gap'],'support':
                    sum(self.lexicon[a['connector']]['relation'].values()),
                    'aligned_training_pairs':len(self.alignment_ledger),
                    'anaphoric_role_filled':missing}}

    def retract_teacher(self, source: str):
        before=len(self.examples)
        self.examples=[e for e in self.examples if e['teacher_source']!=source]
        self.verified_roots=set(r for e in self.examples for r in [e['graph_root'],*e['node_roots']])
        self.fit()
        return before-len(self.examples)

    def to_dict(self):
        return {'version':self.VERSION,'max_gap':self.max_gap,'min_support':self.min_support,
                'examples':self.examples,'verified_roots':sorted(self.verified_roots),
                'lexicon':self.lexicon,'ellipsis':self.ellipsis,'aligned':self.alignment_ledger,
                'rejected':self.rejected_alignments,'trained':self.trained,
                'atomic':self.atomic.to_dict()}

    @classmethod
    def from_dict(cls,d):
        if d.get('version')!=cls.VERSION:raise ValueError('state version mismatch')
        s=cls(GroundedFrameInducer.from_dict(d['atomic']),max_gap=d['max_gap'],min_support=d['min_support'])
        s.examples=d['examples'];s.verified_roots=set(d['verified_roots'])
        if d['trained']:
            s.fit()
        return s

    def digest(self): return _hash(self.to_dict())
