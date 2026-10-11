"""C4 G1.3 experimental two-event discourse construction.

Learns reusable *boundary positions*, discourse-link labels and attribution
of a second event to an arbitrary role in the first event.  It DOES NOT
contain a lexicon, Russian negation/tense rules, or encoded conjunctions.

The training host independently attests finite sandbox event and graph
receipts; the human/LLM teacher supplies the language correspondence.  A
successful linguistic interpretation is a REPORTED hypothesis, NEVER a
verified event or a verified statement by the quoted speaker.

Limitations are deliberate: no recursive parsing, no elided referents,
no raw-audio segmentation, and no autonomous invention of role ontology.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from typing import Any

from .frame_induction import GroundedFrameInducer, _tokens, _json


def _hash(obj: Any) -> str:
    return hashlib.sha256(_json(obj).encode('utf-8')).hexdigest()


class DiscourseInducer:
    """Learn a two-node episode graph from witnessed paired demonstrations.

    `clauses` and `link_witness` exist only on teaching input; inference receives
    one uninterrupted surface string and a scene inventory, but no boundaries.
    The boundary marker is discovered by exact contrastive alignment of the
    composite surface against taught clause surfaces. This is an *explicitly
    supervised* initial boundary learner, not autonomous raw segmentation.
    """
    VERSION = 1

    def __init__(self):
        self.atomic = GroundedFrameInducer()
        self.examples: list[dict] = []
        self.teacher_attribution: list[dict] = []
        self.markers: dict[str, dict[str, Counter]] = {}
        self.roots: set[str] = set()
        self.trained = False

    def observe(self, example: dict, *, verified_receipts: dict[str, dict]):
        if example.get('origin') not in ('SIMULATION', 'HOST_OBSERVED'):
            raise PermissionError('the teacher is not an independent physical/simulation witness')
        if not example.get('teacher_source'):
            raise ValueError('missing teacher lineage')
        graph_root = str(example.get('graph_root') or '')
        if graph_root not in verified_receipts:
            raise PermissionError('graph root not verified by MEDIATE')
        graph = verified_receipts[graph_root]
        link = example.get('link_witness')
        clause_data = example.get('clauses')
        if not isinstance(clause_data, list) or len(clause_data) != 2:
            raise ValueError('exactly two training clauses required')
        if not isinstance(link, dict) or _json(link) != _json(graph.get('witness')):
            raise PermissionError('forged or mismatched graph relation witness')
        roots = [str(c.get('world_receipt_root') or '') for c in clause_data]
        if roots != graph.get('node_roots') or len(set(roots)) != 2:
            raise PermissionError('graph did not attest exactly these event roots')
        if not graph_root or graph_root in roots or graph_root in self.roots or any(r in self.roots for r in roots):
            return False if graph_root in self.roots else _raise_duplicate()
        if not all(r in verified_receipts for r in roots):
            raise PermissionError('unattested clause root')
        if set(link) != {'relation', 'attribution'}:
            raise ValueError('link shape invalid')
        relation = str(link['relation']); attribution = str(link['attribution'])
        if not relation or not attribution:
            raise ValueError('empty graph operator')
        witness0 = verified_receipts[roots[0]].get('witness', {})
        if attribution != '@NARRATOR' and attribution not in witness0.get('roles', {}):
            raise ValueError('attribution role is not in left event schema')

        tokens = _tokens(example.get('utterance', ''))
        left = _tokens(clause_data[0].get('utterance', ''))
        right = _tokens(clause_data[1].get('utterance', ''))
        if not left or not right or len(tokens) != len(left) + len(right) + 1:
            raise ValueError('no single-token learnable boundary alignment')
        if tokens[:len(left)] != left or tokens[len(left)+1:] != right:
            raise ValueError('teacher clause alignment does not explain surface')
        marker = tokens[len(left)]
        if not marker or marker in left or marker in right:
            raise ValueError('ambiguous boundary marker')

        # Validate *all* pieces before storing any learned experience.
        normalized = []
        for c,root in zip(clause_data, roots):
            receipt = verified_receipts[root]
            if _json(receipt.get('witness')) != _json(c.get('witness')) or _json(receipt.get('entities')) != _json(c.get('entities')):
                raise PermissionError('teacher cannot change event witness or scene')
            normalized.append({'utterance': c['utterance'], 'entities': c['entities'], 'teacher_source': str(example['teacher_source']),
                               'world_receipt_root': root, 'origin': 'SIMULATION', 'witness': c['witness'],
                               'utterance_time': receipt.get('utterance_time'),
                               'time_axis': c['witness'].get('time_axis')})
        for atomic_ex in normalized:
            self.atomic.observe(atomic_ex, verified_receipts={atomic_ex['world_receipt_root']: verified_receipts[atomic_ex['world_receipt_root']]})
        self.examples.append({'root':graph_root, 'node_roots':roots, 'marker':marker, 'relation':relation,
                              'attribution':attribution, 'teacher_source':str(example['teacher_source'])})
        self.roots.update([graph_root]+roots)
        self.trained = False
        return True

    def fit(self):
        self.atomic.fit()
        tally = defaultdict(lambda:{'relation': Counter(), 'attribution': Counter()})
        for e in self.examples:
            tally[e['marker']]['relation'][e['relation']] += 1
            tally[e['marker']]['attribution'][e['attribution']] += 1
        self.markers = {k:{kk: Counter(cc) for kk,cc in v.items()} for k,v in tally.items()}
        self.trained = True

    def predict(self, utterance: str, entities: dict[str,str], *, speaker: str,
                source_root: str, world: str, utterance_time: dict|None=None,
                predicate_slot: str|None=None, polarity_slot: str|None=None):
        if not self.trained or not self.examples:
            return {'status':'UNKNOWN','reason':'NOT_TRAINED'}
        if not predicate_slot or not polarity_slot:
            return {'status':'UNKNOWN','reason':'MISSING_EXPLICIT_WORLD_FRAME_SCHEMA'}
        tokens = _tokens(utterance)
        # A learned boundary token may also be a name in another scene.
        # Without contextual disambiguation, abstain instead of consuming the
        # participant as syntax.  No lexical hardcoded exceptions are used.
        surface_names={str(v).casefold() for v in entities.values()}
        if any(t in surface_names for t in tokens if t in self.markers):
            return {'status':'UNKNOWN','reason':'BOUNDARY_OR_ENTITY_AMBIGUOUS'}
        known = [i for i,t in enumerate(tokens) if t in self.markers]
        if len(known)!=1:
            return {'status':'UNKNOWN','reason':'UNRESOLVED_OR_AMBIGUOUS_EVENT_BOUNDARY'}
        boundary = known[0]
        if boundary==0 or boundary==len(tokens)-1:
            return {'status':'UNKNOWN','reason':'EMPTY_EVENT_CLAUSE'}
        marker = tokens[boundary]
        labels = {}
        for key,counts in self.markers[marker].items():
            count=sum(counts.values())
            if count<4 or len(counts)!=1:
                return {'status':'UNKNOWN','reason':'UNCERTAIN_DISCOURSE_CONNECTOR'}
            labels[key] = next(iter(counts))
        slices = [' '.join(tokens[:boundary]), ' '.join(tokens[boundary+1:])]
        out = []
        for idx,phrase in enumerate(slices):
            # Both clauses come from the same externally received utterance.
            q = self.atomic.propose_frame(phrase, entities,
                episode_id=f'{source_root}:{idx}',world=world,
                speaker=speaker,source='discourse:received',source_root=source_root,
                predicate_slot=predicate_slot,polarity_slot=polarity_slot, utterance_time=utterance_time)
            if q['status'] != 'CANDIDATE':
                return {'status':'UNKNOWN','reason':f'CLAUSE_{idx}_UNRESOLVED', 'detail':q.get('reason')}
            out.append(asdict(q['frame']))
        attribution = labels['attribution']
        if attribution!='@NARRATOR':
            parent_roles = dict(out[0]['bindings'])
            if attribution not in parent_roles:
                return {'status':'UNKNOWN','reason':'UNBOUND_QUOTED_SPEAKER_ROLE'}
            # An inferred quote speaker is only attributed by the original
            # narrator; the original source_root remains the same.
            out[1]['speaker'] = parent_roles[attribution]
            out[1]['quote_scope'] = [out[0]['episode_id']]
        return {'status':'CANDIDATE', 'confidence':min(.8, .5+sum(self.markers[marker]['relation'].values())/50),
                'frames':out,
                'link':{'from':out[0]['episode_id'],'to':out[1]['episode_id'],
                        'relation':labels['relation'], 'speaker_projection':attribution,
                        'status':'REPORTED','source_root':source_root},
                'trace':{'boundary_index':boundary,'learned_connector':marker,
                         'n_training_pairs':len(self.examples),
                         'independent_world_roots_used_as_language_demos':len(self.roots)}}

    def retract_teacher(self, teacher_source: str):
        doomed = [e for e in self.examples if e['teacher_source']==teacher_source]
        if not doomed: return 0
        self.examples = [e for e in self.examples if e['teacher_source']!=teacher_source]
        for e in doomed:self.roots.difference_update([e['root']]+e['node_roots'])
        self.atomic.retract_teacher(teacher_source)
        self.fit()
        return len(doomed)

    def to_dict(self):
        return {'version':self.VERSION,'examples':self.examples,'roots':sorted(self.roots),
                'atomic':self.atomic.to_dict(),'trained':self.trained}

    @classmethod
    def from_dict(cls,d):
        if d['version']!=cls.VERSION:raise ValueError('unknown discourse model state')
        a=cls();a.examples=d['examples'];a.roots=set(d['roots'])
        a.atomic=GroundedFrameInducer.from_dict(d['atomic'])
        if d['trained']:a.fit()
        return a

    def digest(self):return _hash(self.to_dict())


def _raise_duplicate():
    raise PermissionError('reused event root under another teaching linkage')
