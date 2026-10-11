"""C4 G1.3 scope-indexed *reported* temporal constraint graph.

This is universal event-order arithmetic, NOT a parser of 'раньше/после'.
A prior language organ learns which surface cues denote typed BEFORE/AFTER.
Temporal transitivity must NEVER promote narrated relationships into external
observations and must NEVER combine quotations, worlds or independent stories
without an explicit declared common scope.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json


class ScopedTimeline:
    VERSION=1

    def __init__(self):
        self.edges: dict[str,list[dict]] = defaultdict(list)
        self.conflicts: list[dict] = []

    @staticmethod
    def _scope(scope):
        if not isinstance(scope,(list,tuple)) or not scope or any(not isinstance(v,str) or not v for v in scope):
            raise ValueError('scope must be explicit nonempty immutable-name sequence')
        return json.dumps(list(scope),ensure_ascii=False,separators=(',',':'))

    @staticmethod
    def _path(edges, start, dest):
        adjacency=defaultdict(set)
        for item in edges:
            adjacency[item['from']].add(item['to'])
        visited={start};frontier=[start]
        while frontier:
            n=frontier.pop(0)
            for nxt in sorted(adjacency.get(n,())):
                if nxt==dest:return True
                if nxt not in visited:visited.add(nxt);frontier.append(nxt)
        return False

    def add_reported(self, *, scope:tuple[str,...], source_root:str, before:str, after:str,
                     provenance_status:str='REPORTED'):
        """Accepts a claim ONLY as a reported relation, not a physical observation.

        Contradictory claims are preserved as counterexamples but not added to
        the consistent graph. Replaying a source root cannot duplicate support.
        """
        key=self._scope(scope)
        if provenance_status!='REPORTED':
            raise PermissionError('this reported-timeline store cannot claim verified observations')
        if not source_root or not before or not after:raise ValueError('missing relation provenance')
        item={'from':before,'to':after,'source_root':source_root,'status':'REPORTED'}
        all_items=self.edges[key]
        for e in all_items:
            if e['source_root']==source_root:
                return 'REPLAY' if e==item else 'ROOT_CONFLICT'
        if before==after or self._path(all_items,after,before):
            self.conflicts.append({'scope':list(scope),**item,'reason':'TEMPORAL_CYCLE'})
            return 'CONTRADICTION_REPORTED'
        all_items.append(item)
        return 'ACCEPTED_REPORTED'

    def infer(self, scope:tuple[str,...], a:str, b:str):
        key=self._scope(scope)
        if not a or not b or a==b:return {'status':'UNKNOWN','reason':'NO_ORDER'}
        edges=self.edges.get(key,[])
        before=self._path(edges,a,b)
        after=self._path(edges,b,a)
        if before and not after:
            return {'status':'DERIVED_REPORTED','relation':'BEFORE',
                    'note':'narrative entailment, not world observation'}
        if after and not before:
            return {'status':'DERIVED_REPORTED','relation':'AFTER',
                    'note':'narrative entailment, not world observation'}
        return {'status':'UNKNOWN','reason':'UNSUPPORTED_OR_CONTRADICTORY'}

    def to_dict(self):
        return {'version':self.VERSION,'edges':dict(sorted(self.edges.items())),
                'conflicts':self.conflicts}

    @classmethod
    def from_dict(cls,d):
        if d['version']!=cls.VERSION:raise ValueError('unknown timeline schema')
        a=cls();a.edges=defaultdict(list,{k:deepcopy(v) for k,v in d['edges'].items()})
        a.conflicts=deepcopy(d['conflicts']);return a
