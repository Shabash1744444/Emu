"""C4 G1.2: learn event *descriptions* from grounded paired demonstrations.

Research prototype, not a Russian parser or an assertion of real-world truth.
Generic computable biases: segment supplied text at whitespace, identify scene names,
learn sparse cue->attribute associations, learn role->mention binding by perceptron,
and compare independently time-stamped event / utterance intervals.

No built-in words, named grammatical cases, actor/recipient slots, polarity tokens,
or rules about a particular language.  Scene/entity IDs and attribute keys are
arbitrary symbols.  A teacher's linguistic association is not a world receipt.

This module never executes inferred action, COMMITs its output to world truth or
mints receipt roots.  A host must attest roots independently, and must confirm
that the witness structure comes from the world rather than teacher claims.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from itertools import permutations
import hashlib
import json
import re
from typing import Any
from .temporal import Interval, order
from .event_frames import Frame


def _tokens(surface: str) -> list[str]:
    """Minimal supplied-text splitter: NOT a learned audio/word segmenter."""
    return [t.strip('.,!?;:«»()[]{}"“”').casefold() for t in str(surface).split() if t.strip('.,!?;:«»()[]{}"“”')]


def _mentions(surface: str, entities: dict[str, str]):
    """Find lexical mentions using scene-provided names; identify unknown inflection by leftover form.

    This is an explicit observation bootstrap, not autonomous object-name discovery.
    The learned meaning is *which role* each mention bears.
    """
    toks = _tokens(surface)
    out = []
    for i, t in enumerate(toks):
        cand = []
        for eid, name in entities.items():
            base = name.casefold()
            common = 0
            for ca, cb in zip(t, base):
                if ca != cb: break
                common += 1
            # Generic bounded edit alignment. This learns the *role value*
            # from changed endings; it does not contain a Russian inflection table.
            if (t == base or (len(base) >= 3 and common >= max(2 if len(base)<=3 else 3, int(.6*len(base)))
                             and len(base)-common <= 2 and len(t)-common <= 3)):
                form = base[common:]+'>'+t[common:]
                cand.append((common, str(eid), form))
        if cand:
            cand.sort(reverse=True)
            longest = cand[0][0]
            if sum(x[0] == longest for x in cand) != 1:
                return toks, [], 'AMBIGUOUS_ALIAS'
            _n, eid, residual = cand[0]
            out.append({'index': i, 'entity_id': eid, 'surface': t, 'residual': residual})
    if len(set(x['entity_id'] for x in out)) != len(out):
        return toks, [], 'DUPLICATE_MENTION'
    return toks, out, None


def _features_role(toks: list[str], m: dict, rank: int, count: int) -> set[str]:
    i = m['index']
    suffix = m['residual']
    fs = {f'end:{suffix}', f'position:{rank}', f'from_end:{count-rank-1}',
          'first' if i == 0 else 'not_first', 'last' if i == len(toks)-1 else 'not_last'}
    if i:
        fs.add('prev:'+toks[i-1])
    if i+1 < len(toks):
        fs.add('next:'+toks[i+1])
    return fs


def _features_attr(toks: list[str], mentions: list[dict], observed_vocabulary=()) -> set[str]:
    idx = {m['index'] for m in mentions}
    present = {tok for i,tok in enumerate(toks) if i not in idx}
    # Absence is a general logical feature of a sequence, not a hardcoded
    # negation word. Only absences of previously observed tokens can be used.
    return {'word:'+tok for tok in present} | {'missing:'+tok for tok in observed_vocabulary if tok not in present}


def _json(d):
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


class CueClassifier:
    """Contrasted examples, not a hardcoded lexicon or output default.

    A feature only licenses a result if it is exclusive for this label on
    recorded contrasting examples. Unseen or conflicting cues yield UNKNOWN.
    """
    def __init__(self):
        self.counts = defaultdict(Counter)
        self.labels = Counter()

    def observe(self, feats: set[str], label: str):
        self.labels[label] += 1
        for f in feats:
            self.counts[f][label] += 1

    def predict(self, feats: set[str]):
        if len(self.labels) < 2:
            return None, 0., 'NO_CONTRAST'
        support = defaultdict(float)
        for f in feats:
            c = self.counts.get(f)
            if not c or sum(c.values()) < 2:
                continue
            total = sum(c.values())
            for v, n in c.items():
                if n == total:
                    # weight rare/specific cues above ubiquitous words
                    support[v] += min(4.0, n**.5)
        if not support:
            return None, 0., 'UNSUPPORTED'
        items = sorted(support.items(), key=lambda z: (-z[1], z[0]))
        if len(items) > 1 and items[0][1] <= items[1][1]+0.0001:
            return None, 0., 'CONFLICT'
        return items[0][0], min(.8, .5 + items[0][1]/20), 'LEARNED_CUE'

    def to_dict(self):
        return {'labels': dict(self.labels),'counts': {k:dict(v) for k,v in sorted(self.counts.items())}}

    @classmethod
    def from_dict(cls, d):
        s = cls(); s.labels = Counter(d['labels'])
        for k, v in d['counts'].items(): s.counts[k] = Counter(v)
        return s


class RoleBinder:
    """Shared structural model over all arbitrary role IDs; no actor/recipient code.

    Learns which *slot* mention fills. Uses constrained assignment to prevent
    two roles silently binding to the same object. Equal scoring alternatives
    are UNKNOWN instead of guessed by entity order.
    """
    def __init__(self, epochs: int = 14):
        self.epochs = epochs
        self.weights = defaultdict(Counter)
        self.seen_roles = set()
        self.n_examples = 0
        self.cue_roles = defaultdict(Counter)

    def _decode(self, toks, mentions, roles, weights=None):
        w = self.weights if weights is None else weights
        if len(mentions) < len(roles) or len(mentions)>7 or len(roles)>5:
            return None, 0., 'CARDINALITY'
        fs = [_features_role(toks, m, k, len(mentions)) for k, m in enumerate(mentions)]
        scored = []
        for choice in permutations(range(len(mentions)), len(roles)):
            score = sum(sum(w[r].get(f,0.) for f in fs[i]) for r,i in zip(roles,choice))
            scored.append((score, choice))
        scored.sort(key=lambda z: (-z[0], z[1]))
        if not scored:
            return None, 0., 'NO_ASSIGNMENT'
        margin = scored[0][0]-(scored[1][0] if len(scored)>1 else scored[0][0]-1)
        return {r: mentions[i]['entity_id'] for r,i in zip(roles,scored[0][1])}, margin, 'RANKED_ASSIGNMENT'

    def fit(self, examples):
        for e in examples:
            self.seen_roles.update(e['roles'])
        roles = sorted(self.seen_roles)
        for e in examples:
            for k,m in enumerate(e['mentions']):
                matching=[r for r,v in e['roles'].items() if v == m['entity_id']]
                if not matching: continue
                for f in _features_role(e['toks'],m,k,len(e['mentions'])):
                    self.cue_roles[f][matching[0]] += 1
        for ep in range(self.epochs):
            for e in examples:
                toks, ms = e['toks'], e['mentions']
                tgt = e['roles']
                relevant = sorted(tgt)
                if set(relevant) != set(roles):
                    continue  # partial role families have different assignment space
                p, _, _ = self._decode(toks, ms, relevant)
                if p == tgt:
                    continue
                for role in relevant:
                    pos = next((i for i,m in enumerate(ms) if m['entity_id']==tgt[role]),None)
                    neg = next((i for i,m in enumerate(ms) if m['entity_id']==p[role]),None) if p else None
                    if pos is None or neg is None or pos == neg:
                        continue
                    for f in _features_role(toks,ms[pos],pos,len(ms)):
                        self.weights[role][f] += 1.
                    for f in _features_role(toks,ms[neg],neg,len(ms)):
                        self.weights[role][f] -= 1.
        self.n_examples += len(examples)

    def predict(self, toks, mentions):
        roles = sorted(self.seen_roles)
        if not roles:
            return None, 0., 'NO_ROLES'
        pred, margin, reason = self._decode(toks,mentions,roles)
        if pred is None or margin <= 0.:
            return None, 0., 'NON_UNIQUE_BINDING'
        # A positive perceptron score is not evidence of a learned association.
        # Demand a repeatable, discriminative cue for EVERY predicted slot.
        for role, eid in pred.items():
            rank=next(i for i,m in enumerate(mentions) if m['entity_id']==eid)
            fs=_features_role(toks,mentions[rank],rank,len(mentions))
            good=False
            for f in fs:
                c=self.cue_roles.get(f)
                if c and sum(c.values())>=3 and c[role]/sum(c.values())>=.85:
                    good=True;break
            if not good:
                return None, 0., 'ROLE_NOT_SUPPORTED_BY_DISCRIMINATIVE_CUE'
        return pred, min(.8, .4 + margin/15), reason

    def to_dict(self):
        return {'epochs':self.epochs,'n_examples':self.n_examples,'seen_roles':sorted(self.seen_roles),
                'weights':{k:dict(v) for k,v in sorted(self.weights.items())},
                'cue_roles':{k:dict(v) for k,v in sorted(self.cue_roles.items())}}

    @classmethod
    def from_dict(cls,d):
        s=cls(d['epochs']);s.n_examples=d['n_examples'];s.seen_roles=set(d['seen_roles'])
        for r,w in d['weights'].items():s.weights[r]=Counter(w)
        for f,c in d['cue_roles'].items():s.cue_roles[f]=Counter(c)
        return s


class GroundedFrameInducer:
    """An explicitly non-canonical experimental organ; outputs only CANDIDATE frames.

    World receipt is supplied from a trusted host, not the teacher message.
    `trusted_roots` is an attestation set the caller obtained through MEDIATE.
    The caller must keep the teacher linguistic demonstration and observation
    independent. Reject exact replay of training events as evidence multiplication.
    """
    def __init__(self):
        self.examples=[];self.seen_roots=set();self.cues={};self.role_binders={};self.schema_head=CueClassifier()
        self.trained=False;self.attestations=[];self.attr_vocab=[];self.seen_surface_tokens=set();self.repeated_surface_tokens=set()

    def observe(self, ex: dict, *, verified_receipts: dict[str,dict]):
        if ex.get('origin') in {'REPLAY','DERIVED','SELF_OUTPUT','LLM_SYNTHETIC_RECEIPT'}:
            raise ValueError('not a new grounded demonstration')
        if not ex.get('teacher_source') or ex.get('world_receipt_root') not in verified_receipts:
            raise PermissionError('teacher cannot mint a world receipt')
        # Roots are *addresses*, not evidence of arbitrary content. Bind exact
        # witness and scene bytes to the independent MEDIATE-host record.
        receipt = verified_receipts[ex['world_receipt_root']]
        if _json(receipt.get('witness')) != _json(ex.get('witness')) or _json(receipt.get('entities')) != _json(ex.get('entities')):
            raise PermissionError('world witness/content does not match its attested root')
        root = str(ex['world_receipt_root'])
        if root in self.seen_roots:
            return False
        spec=ex.get('witness')
        if not isinstance(spec,dict) or not isinstance(spec.get('roles'),dict) or not isinstance(spec.get('attributes'),dict):
            raise ValueError('no typed world witness')
        es={str(k):str(v) for k,v in ex.get('entities',{}).items()}
        roles={str(k):str(v) for k,v in spec['roles'].items()}
        if not roles or set(roles.values())-set(es):
            raise ValueError('unbound roles')
        if len(set(roles.values())) != len(roles):
            raise ValueError('duplicate world referent')
        toks, mentions, problem = _mentions(ex.get('utterance',''),es)
        if problem or set(roles.values())-set(m['entity_id'] for m in mentions):
            raise ValueError('world witness participant not mentioned or ambiguous: '+str(problem))
        if spec.get('event_time') is not None:
            # Time must be a physical timestamp on a comparable axis, not a
            # computation tick masquerading as microseconds. The host attests
            # the utterance time independently of what the teacher writes.
            axis=spec.get('time_axis')
            if not axis or axis not in {'SIM_UTC','UTC'} or ex.get('time_axis') != axis:
                raise ValueError('mixed or unknown clock axis')
            if _json(receipt.get('utterance_time')) != _json(ex.get('utterance_time')):
                raise PermissionError('teacher utterance timestamp not independently attested')
            when = Interval(**spec['event_time']); at = Interval(**ex['utterance_time'])
            if when.status not in {'MEASURED','ESTIMATED','SIMULATED'} or at.status not in {'MEASURED','ESTIMATED','SIMULATED'}:
                raise ValueError('clock not independently witnessed')
            if when.status != at.status and 'SIMULATED' in {when.status,at.status}:
                raise ValueError('cannot compare simulated and real wall clocks')
            rel = order(when,at)
        else:
            rel = None
        attrs = {str(k):str(v) for k,v in spec['attributes'].items()}
        if rel is not None and rel != 'UNKNOWN_OR_OVERLAP':
            attrs['temporal_relation'] = rel
        observed={'toks':toks,'mentions':mentions,'roles':roles,'attrs':attrs,'root':root, 'schema':_json(sorted(roles))}
        self.examples.append(observed);self.seen_roots.add(root)
        self.attestations.append({'world_root':root,'teacher_source':str(ex['teacher_source'])})
        self.trained=False
        return True

    def retract_teacher(self, teacher_source: str):
        # Teacher false/retracted examples must cease influencing model and do
        # not erase any actual world event or receipt in the external journal.
        roots={a['world_root'] for a in self.attestations if a['teacher_source']==teacher_source}
        if not roots:return 0
        self.examples=[e for e in self.examples if e['root'] not in roots]
        self.attestations=[a for a in self.attestations if a['teacher_source']!=teacher_source]
        self.seen_roots.difference_update(roots)
        self.fit()
        return len(roots)

    def fit(self):
        self.cues={}; self.role_binders={}; self.schema_head=CueClassifier()
        tokcounts=Counter()
        self.seen_surface_tokens=set()
        self.repeated_surface_tokens=set()
        for ex in self.examples:
            present=[t for i,t in enumerate(ex['toks']) if i not in {m['index'] for m in ex['mentions']}]
            self.seen_surface_tokens.update(present)
            self.repeated_surface_tokens.update(t for t,n in Counter(present).items() if n>1)
            tokcounts.update(_features_attr(ex['toks'], ex['mentions']))
        self.attr_vocab=sorted(f[5:] for f,n in tokcounts.items() if f.startswith('word:') and n>=3)
        grouped=defaultdict(list)
        for ex in self.examples:
            grouped[ex['schema']].append(ex)
        for schema, exs in grouped.items():
            binder=RoleBinder();binder.fit(exs);self.role_binders[schema]=binder
        for ex in self.examples:
            feats=_features_attr(ex['toks'], ex['mentions'], self.attr_vocab)
            self.schema_head.observe(feats,ex['schema'])
            for field,label in ex['attrs'].items():
                self.cues.setdefault(field,CueClassifier()).observe(feats,label)
        self.trained=True

    def predict(self, utterance:str, entities:dict[str,str], *, speaker:str, source_root:str,
                world:str='unknown', utterance_time:dict|None=None):
        if not self.trained or not self.examples:
            return {'status':'UNKNOWN','reason':'NOT_TRAINED'}
        toks,mentions,problem=_mentions(utterance,entities)
        if problem:
            return {'status':'UNKNOWN','reason':problem}
        feats=_features_attr(toks,mentions,self.attr_vocab)
        if len(self.role_binders)==1:
            schema=next(iter(self.role_binders))
        else:
            schema,_,reason=self.schema_head.predict(feats)
            if schema is None:
                return {'status':'UNKNOWN','reason':'UNKNOWN_ROLE_SCHEMA:'+reason}
        nonmentions=[t for i,t in enumerate(toks) if i not in {m['index'] for m in mentions}]
        unfamiliar=set(nonmentions)-self.seen_surface_tokens
        if unfamiliar:
            return {'status':'UNKNOWN','reason':'UNSEEN_SURFACE_OPERATOR',
                    'unfamiliar_count':len(unfamiliar)}
        if any(n>1 and t not in self.repeated_surface_tokens for t,n in Counter(nonmentions).items()):
            return {'status':'UNKNOWN','reason':'UNSEEN_REPETITION_PATTERN'}
        roles,rc,reason=self.role_binders[schema].predict(toks,mentions)
        if roles is None:
            return {'status':'UNKNOWN','reason':reason}

        attrs={}; conf=[rc]; gaps=[]
        for name,cls in sorted(self.cues.items()):
            v,c,why=cls.predict(feats)
            if v is None:gaps.append(f'{name}:{why}')
            else:attrs[name]=v;conf.append(c)
        if gaps:
            return {'status':'UNKNOWN','reason':'UNRESOLVED_ATTRIBUTES','gaps':gaps,'candidate_roles':roles}
        # Teacher/source claim: no amount of training converts a sentence into OBSERVED world state.
        # Even if it describes a receipt, the interpretation is attributed to *speaker*.
        return {'status':'CANDIDATE', 'confidence':round(min(conf),3),
                'hypothesis':{'world':world,'roles':roles,'attributes':attrs,'utterance':utterance,
                              'speaker':speaker,'source_root':source_root,'modality':'REPORTED',
                              'utterance_time':utterance_time},
                'trace':{'training_examples':len(self.examples),'role_margin':round((rc-.4)*15,3),
                         'witness_roots_count':len(self.seen_roots),'reason':reason}}

    def propose_frame(self, utterance: str, entities: dict[str,str], *,
                      episode_id: str, world: str, speaker: str, source: str,
                      source_root: str, predicate_slot: str, polarity_slot: str,
                      listener: str|None=None, utterance_time: dict|None=None,
                      quote_scope: tuple[str,...]=()):
        """Produce an EventFrame about *what the speaker said*, not what happened.

        Slot mappings are explicit WORLD SCHEMA keys, NOT lexical word rules.
        No actual event timestamp can be invented from learned BEFORE/AFTER.
        """
        candidate=self.predict(utterance,entities,speaker=speaker,source_root=source_root,
                               world=world,utterance_time=utterance_time)
        if candidate['status']!='CANDIDATE':return candidate
        hyp=candidate['hypothesis'];attrs=hyp['attributes']
        pred=attrs.get(predicate_slot)
        if not pred:
            return {'status':'UNKNOWN','reason':'NO_PREDICATE_FIELD'}
        pol=attrs.get(polarity_slot,'UNSET')
        if pol not in {'POS','NEG','UNSET'}:
            pol='UNSET'
        when=Interval(**utterance_time) if utterance_time else None
        frame=Frame(episode_id,world,pred,tuple(sorted(hyp['roles'].items())),None,
                    source,source_root,'REPORTED',pol,speaker,listener,when,
                    None,quote_scope,tuple(sorted(attrs.items())))
        return {'status':'CANDIDATE','confidence':candidate['confidence'],
                'frame':frame,'trace':candidate['trace']}

    def to_dict(self):
        return {'version':2,'trained':self.trained,'attr_vocab':self.attr_vocab,'seen_surface_tokens':sorted(self.seen_surface_tokens),
                'repeated_surface_tokens':sorted(self.repeated_surface_tokens),'examples':self.examples,'seen_roots':sorted(self.seen_roots),
                'attestations':self.attestations,'cues':{k:v.to_dict() for k,v in sorted(self.cues.items())},
                'role_binders':{k:v.to_dict() for k,v in sorted(self.role_binders.items())},
                'schema_head':self.schema_head.to_dict()}

    @classmethod
    def from_dict(cls,d):
        if d['version']!=2: raise ValueError('unknown model version')
        s=cls();s.examples=d['examples'];s.seen_roots=set(d['seen_roots']);s.attestations=d['attestations'];s.attr_vocab=d['attr_vocab'];s.seen_surface_tokens=set(d['seen_surface_tokens']);s.repeated_surface_tokens=set(d['repeated_surface_tokens'])
        s.cues={k:CueClassifier.from_dict(v) for k,v in d['cues'].items()}
        s.role_binders={k:RoleBinder.from_dict(v) for k,v in d['role_binders'].items()}
        s.schema_head=CueClassifier.from_dict(d['schema_head']);s.trained=bool(d.get('trained',True))
        return s

    def digest(self):
        return hashlib.sha256(_json(self.to_dict()).encode()).hexdigest()
