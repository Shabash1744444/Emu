"""World-level knowledge for the structural learner S: one TargetModel per observable non-switch variable.

What the learner is told about a world (by the host through MEDIATE, the 'body schema'): variable names, domains and
which variables it may try to set (switches).  Nothing about mechanisms, hidden variables or which variables are
noise.  Transitions x(t) -> x(t+1) are INTERVENTIONAL when some input value at t was set by the agent's own verified
action (the receipt says so), otherwise observational."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .operators import OperatorSpace
from .smodel import TargetModel, _lse

EXT_ORDER = (('ARITY', 3), ('SIZE', 7), ('LAG', None), ('ARITY', 4), ('SIZE', 8))   # the fixed meta-grammar


class WorldModelS:
    kind = 'S'

    def __init__(self, world_id: str, names: List[str], domains: List[int], switches: List[str],
                 space: OperatorSpace, lib_version: int, static: bool = False, targets: Optional[List[str]] = None):
        self.world_id, self.names, self.domains = world_id, list(names), list(domains)
        self.switches, self.space, self.lib_version, self.static = list(switches), space, lib_version, static
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.targets: Dict[str, TargetModel] = {}
        tset = set(targets) if targets is not None else None
        for n in self.names:
            if n in self.switches or (tset is not None and n not in tset):
                continue
            i = self.idx[n]
            if static:
                ctx = [d for j, d in enumerate(self.domains) if j != i]
                self.targets[n] = TargetModel(n, ctx, None, self.domains[i], space, lib_version)
            else:
                self.targets[n] = TargetModel(n, self.domains, i, self.domains[i], space, lib_version)
        self.prev: Optional[List[int]] = None
        self.prev2: Optional[List[int]] = None
        self.last_t: Optional[int] = None
        self.ext_done: Dict[str, int] = {n: 0 for n in self.targets}
        self.n_transitions = 0
        self.n_interventional = 0
        self.int_counts: Dict[str, int] = {}      # variable -> transitions whose input had it set by our action

    # ------------------------------------------------------------------ observation (credit changes only here)
    def vec(self, percept: Dict[str, int]) -> List[int]:
        return [int(percept[n]) for n in self.names]

    def observe(self, t: int, percept: Dict[str, int], intervened_prev: bool, int_vars=(), seq=None) -> Dict[str, dict]:
        """int_vars: names of variables whose value at t-1 was set by our own verified action."""
        x = self.vec(percept)
        out = {}
        iv = {self.idx[v] for v in int_vars if v in self.idx}
        if self.prev is not None and self.last_t == t - 1:
            for n, tm in sorted(self.targets.items()):
                out[n] = tm.update(self.prev, x[self.idx[n]], xp=self.prev2, interventional=intervened_prev,
                                   int_vars=iv, seq=seq)
            self.n_transitions += 1
            self.n_interventional += int(intervened_prev)
            for v in int_vars:
                self.int_counts[v] = self.int_counts.get(v, 0) + 1
        self.prev2 = self.prev if (self.last_t == t - 1) else None
        self.prev, self.last_t = x, t
        return out

    def observe_static(self, row: Dict[str, int], seq=None) -> Dict[str, dict]:
        out = {}
        for n, tm in sorted(self.targets.items()):
            if n in row:
                x = [int(row[m]) for m in self.names if m != n]
                out[n] = tm.update(x, int(row[n]), seq=seq)
        return out

    # ------------------------------------------------------------------ answers
    def assert_static(self, target: str, features: Dict[str, int]):
        x = [int(features[m]) for m in self.names if m != target]
        return self.targets[target].assertable(x)

    def assert_next(self, target: str, x: List[Optional[int]], xp=None):
        tm = self.targets[target]
        if tm.lag_enabled and xp is None:
            xp = [None] * len(x)
        if any(v is None for v in x) or (xp is not None and tm.lag_enabled and any(v is None for v in xp)):
            return tm.assertable_partial(x, xp if tm.lag_enabled else None)
        return tm.assertable(x, xp if tm.lag_enabled else None)

    def simulate(self, state: Dict[str, int], k: int, do: Optional[Dict[str, int]] = None) -> Tuple[List[Dict[str, Optional[int]]], List[str]]:
        """Predicted states for steps 1..k with switches held (or set by `do` from step 1).  Unknown -> None.
        Returns (trajectory, bases).  This is SIMULATION: never evidence."""
        x = self.vec(state)
        xp = list(self.prev2) if (self.prev2 is not None and self.prev is not None and self.vec(state) == self.prev) else None
        traj, bases = [], []
        held = {s: x[self.idx[s]] for s in self.switches}
        if do:
            held.update({s: int(v) for s, v in do.items()})
        for step in range(k):
            nx: List[Optional[int]] = [None] * len(self.names)
            for s in self.switches:
                nx[self.idx[s]] = held[s]
            for n in sorted(self.targets):
                v, basis, _ = self.assert_next(n, x, xp)
                nx[self.idx[n]] = v
                bases.append(f'{n}@{step + 1}:{basis}')
            traj.append({m: nx[self.idx[m]] for m in self.names})
            xp, x = x, nx
        return traj, bases

    def causal(self, cause: str, effect: str, k: int, state: Dict[str, int]) -> Tuple[Optional[str], dict]:
        """Does setting `cause` change `effect` within k steps?  Answers only from certified models, and only with
        interventional evidence about the cause (association is not causation):
          YES  the simulated trajectories differ AND some certified direct child of the cause on a path to the
               effect has >= 2 fresh confident-correct predictions on transitions where WE had set the cause;
          NO   both trajectories fully certified and equal AND the cause has been set by us on >= 2 transitions."""
        t0, _ = self.simulate(state, k, {cause: 0})
        t1, _ = self.simulate(state, k, {cause: 1})
        vals0 = [s[effect] for s in t0]
        vals1 = [s[effect] for s in t1]
        ci = self.idx[cause]
        graph = {}
        for n, tm in self.targets.items():
            m = tm.map_hypothesis() if tm.certified() else None
            if m is None:
                continue
            fam, o, e = m
            dep = tm.fam_depends(fam, o)
            nn = len(tm.ctx_domains)
            graph[n] = {self.names[i % nn] for j, i in enumerate(fam.parents) if dep[j]}
        children = [n for n, ps in graph.items() if cause in ps]
        validated = [n for n in children if self.targets[n].int_by_var.get(ci, 0) >= 2]

        def reach(src):
            seen, todo = {src}, [src]
            while todo:
                u = todo.pop()
                if u == effect:
                    return True
                for n, ps in graph.items():
                    if u in ps and n not in seen:
                        seen.add(n)
                        todo.append(n)
            return False
        path_ok = any(reach(c) for c in validated)
        info = {'do0': vals0, 'do1': vals1, 'certified_children_of_cause': sorted(children),
                'interventionally_validated_children': sorted(validated),
                'times_cause_set_by_us': self.int_counts.get(cause, 0)}
        if any(a is not None and b is not None and a != b for a, b in zip(vals0, vals1)):
            return ('YES' if path_ok else None), info
        if all(a is not None and b is not None for a, b in zip(vals0, vals1)) and self.int_counts.get(cause, 0) >= 2:
            return 'NO', info
        return None, info

    # ------------------------------------------------------------------ action values
    def eig_actions(self, state: Dict[str, int], permitted: List[str], bonus_targets=()) -> List[Tuple[float, dict]]:
        x = self.vec(state)
        cands = [{}] + [{s: v} for s in sorted(permitted) for v in range(self.domains[self.idx[s]])
                        if v != x[self.idx[s]]]
        out = []
        base = list(x)
        for n in sorted(self.targets):                     # MAP-expected next device values (approximation)
            p, _ = self.targets[n].predictive(x, self.prev2)
            base[self.idx[n]] = int(np.argmax(p))
        for act in cands:
            nx = list(base)
            for s, v in act.items():
                nx[self.idx[s]] = v
            val = 0.0
            for n, tm in sorted(self.targets.items()):
                e = tm.eig(nx, x if tm.lag_enabled else None) / math.log(2)
                p, _ = tm.predictive(nx, x if tm.lag_enabled else None)
                if not tm.certified():
                    full = tuple(nx) + (tuple(x) if tm.lag_enabled else ())
                    if p.max() >= tm.tau and full not in tm.memory:
                        e += 0.3                                # a validation step towards a certificate
                if tm.rival(nx, x if tm.lag_enabled else None, int(np.argmax(p))):
                    e += 0.3                                    # CL-R5 G0.3: curiosity about a plausible rival
                if n in bonus_targets:
                    e *= 2.0
                val += e
            out.append((val, act))
        out.sort(key=lambda z: (-z[0], sorted(z[1].items())))
        return out

    def extension_candidates(self) -> List[Tuple[float, str, str]]:
        out = []
        for n, tm in sorted(self.targets.items()):
            if tm.n_obs < 12:
                continue
            i = self.ext_done[n]
            if i >= len(EXT_ORDER):
                continue
            u = tm.inadequacy()
            if u < 0.05:
                continue
            kind, lim = EXT_ORDER[i]
            out.append((u * 0.5 ** i, n, kind))
        out.sort(key=lambda z: (-z[0], z[1]))
        return out

    def extend(self, target: str, kind: str) -> dict:
        tm = self.targets[target]
        i = self.ext_done[target]
        res = tm.extend(kind)
        self.ext_done[target] = i + 1
        return res

    def rebuild_target(self, n: str, events: List[tuple], lesson_fn=None) -> TargetModel:
        """Exact revision of ONE target: a fresh model replays the target's own admitted rows, with the internal
        extensions (and admitted lessons) re-applied at the very observation counts at which they happened.
        events: (n_obs, 'EXTEND', kind) | (n_obs, 'LESSON', payload) in journal order."""
        old = self.targets[n]
        tm = TargetModel(n, old.ctx_domains, old.self_idx, old.out_domain, self.space, self.lib_version)
        evs = sorted(events, key=lambda e: e[0])
        k = 0

        def apply_until(pos):
            nonlocal k
            while k < len(evs) and evs[k][0] <= pos:
                pos_, kind, pay = evs[k]
                if kind == 'EXTEND':
                    tm.extend(pay)
                elif kind == 'LESSON' and lesson_fn is not None:
                    lesson_fn(tm, pay)
                k += 1
        for i, (x, xp, y, interv) in enumerate(old.rows):
            apply_until(i)
            tm.update(x, y, xp=xp, interventional=interv, int_vars=set(old.int_rows[i]) if i < len(old.int_rows) else (),
                      seq=old.row_seqs[i] if i < len(old.row_seqs) else None)
        apply_until(len(old.rows))
        self.targets[n] = tm
        return tm

    def describe(self) -> Dict[str, dict]:
        return {n: tm.map_description(self.names) for n, tm in sorted(self.targets.items())}

    # ------------------------------------------------------------------ serialization
    def to_dict(self):
        return {'kind': 'S', 'world_id': self.world_id, 'names': self.names, 'domains': self.domains,
                'switches': self.switches, 'lib_version': self.lib_version, 'static': self.static,
                'targets': {n: tm.to_dict() for n, tm in self.targets.items()}, 'prev': self.prev,
                'prev2': self.prev2, 'last_t': self.last_t, 'ext_done': self.ext_done,
                'n_transitions': self.n_transitions, 'n_interventional': self.n_interventional,
                'int_counts': self.int_counts}

    @classmethod
    def from_dict(cls, d, space):
        self = cls.__new__(cls)
        self.world_id, self.names, self.domains = d['world_id'], d['names'], d['domains']
        self.switches, self.space, self.lib_version, self.static = d['switches'], space, d['lib_version'], d['static']
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.targets = {n: TargetModel.from_dict(t, space) for n, t in d['targets'].items()}
        self.prev, self.prev2, self.last_t = d['prev'], d['prev2'], d['last_t']
        self.ext_done, self.n_transitions, self.n_interventional = d['ext_done'], d['n_transitions'], d['n_interventional']
        self.int_counts = dict(d.get('int_counts', {}))
        return self
