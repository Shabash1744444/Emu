"""Simulated environments for CL-R4 (the EVALUATOR side: the learner never reads anything here except what MEDIATE
delivers through percepts and receipts).

MechWorld — a dynamic structural causal model ('room with devices'):
  switch   exogenous; flips spontaneously with probability flip_p (passive variation) or copies a hidden driver
           (confounding); the agent may set it (an intervention) if permitted
  device   endogenous: device(t+1) = program(state(t)), programs in the same small DSL the learner uses
  hidden   unobserved driver (confounder), flips with probability flip_p
  hidden_device  unobserved, computed like a device (e.g. a delay line: the observable sees x(t-1) effects)
  noise    observed, unlearnable: a fresh coin every tick ('noisy TV')
Interventions take effect at t+1 (do(v := c) sets v(t+1) = c); their effect on children appears at t+2.
Mechanism changes are scheduled (non-stationarity).
EntityWorld — another class of task (static classification of renamed entities by hidden rules over features)."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SYL_C = 'бвгдзклмнпрстфхцш'
SYL_V = 'аеиоуыэюя'


def pseudo_name(rng: random.Random, used: set) -> str:
    while True:
        n = ''.join(rng.choice(SYL_C) + rng.choice(SYL_V) for _ in range(2)) + rng.choice(SYL_C)
        n = n.capitalize()
        if n not in used:
            used.add(n)
            return n


def ev(prog, state: Dict[str, int], self_val: Optional[int] = None) -> int:
    op = prog[0]
    if op == 'V':
        return int(state[prog[1]])
    if op == 'SELF':
        return int(self_val)
    if op == 'C':
        return int(prog[1])
    a = [ev(x, state, self_val) for x in prog[1:]]
    if op == 'NOT':
        return 1 - a[0]
    if op == 'AND':
        return a[0] & a[1]
    if op == 'OR':
        return a[0] | a[1]
    if op == 'XOR':
        return a[0] ^ a[1]
    if op == 'IF':
        return a[1] if a[0] else a[2]
    if op == 'EQ':
        return int(a[0] == a[1])
    if op == 'GE':
        return int(a[0] >= a[1])
    if op == 'ADD':
        return (a[0] + a[1]) % 4
    if op == 'MAJ':                      # used only by world generators; equals IF(XOR(a,b), c, a)
        return int(a[0] + a[1] + a[2] >= 2)
    if op == 'ATLEAST':                  # hidden aggregation: at least k of the listed inputs
        return int(sum(a[1:]) >= a[0])
    raise ValueError(op)


def prog_vars(prog) -> List[str]:
    if prog[0] == 'V':
        return [prog[1]]
    if prog[0] in ('SELF', 'C'):
        return []
    out = []
    for x in prog[1:]:
        for v in prog_vars(x):
            if v not in out:
                out.append(v)
    return out


@dataclass
class VarSpec:
    name: str
    role: str                      # switch | device | hidden | noise
    domain: int = 2
    flip_p: float = 0.1
    driver: Optional[str] = None   # switch copying a hidden variable (confounding)
    program: Optional[tuple] = None


@dataclass
class MechWorld:
    world_id: str
    vars: List[VarSpec]
    seed: int
    changes: List[Tuple[int, str, tuple]] = field(default_factory=list)   # (t, device, new program)
    t: int = 0
    state: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        if not self.state:
            for v in self.vars:
                self.state[v.name] = 0
        self.spec = {v.name: v for v in self.vars}

    @property
    def observable(self) -> List[str]:
        return [v.name for v in self.vars if v.role not in ('hidden', 'hidden_device')]

    @property
    def switches(self) -> List[str]:
        return [v.name for v in self.vars if v.role == 'switch']

    def percept(self) -> Dict[str, int]:
        return {n: self.state[n] for n in self.observable}

    def step(self, interventions: Optional[Dict[str, int]] = None) -> Dict[str, int]:
        interventions = interventions or {}
        for (tc, dev, prog) in self.changes:
            if tc == self.t:
                self.spec[dev].program = prog
        old = dict(self.state)
        new = {}
        for v in self.vars:
            if v.role == 'hidden':
                new[v.name] = 1 - old[v.name] if self.rng.random() < v.flip_p else old[v.name]
            elif v.role == 'noise':
                new[v.name] = self.rng.randrange(v.domain)
            elif v.role == 'switch':
                r = self.rng.random()                        # always consumed: same RNG path with/without action
                if v.name in interventions:
                    new[v.name] = int(interventions[v.name])
                elif v.driver:
                    new[v.name] = old[v.driver]
                else:
                    new[v.name] = 1 - old[v.name] if r < v.flip_p else old[v.name]
            else:
                new[v.name] = ev(v.program, old, old[v.name])
        self.state = new
        self.t += 1
        return self.percept()

    def true_parents(self, device: str) -> List[str]:
        return prog_vars(self.spec[device].program)

    def snapshot(self) -> dict:
        return {'world_id': self.world_id, 't': self.t, 'state': dict(self.state), 'rng': repr(self.rng.getstate()),
                'programs': {v.name: v.program for v in self.vars if v.program is not None}}

    def simulate(self, k: int, interventions_now: Optional[Dict[str, int]] = None, hold: bool = True) -> Dict[str, int]:
        """Evaluator-side ground truth for 'what will happen': a COPY of the world, k steps, switches held at their
        (intervened) values when hold=True (the question says 'nobody touches anything else')."""
        import copy
        w = copy.deepcopy(self)
        held = dict(w.percept())
        if interventions_now:
            held.update(interventions_now)
        for i in range(k):
            iv = {s: held[s] for s in w.switches} if hold else (interventions_now if i == 0 else {})
            w.step(iv)
        return w.state

    def digest(self) -> str:
        return hashlib.sha256(json.dumps({'id': self.world_id, 'vars': [(v.name, v.role, v.domain, v.flip_p, v.driver,
                                         v.program) for v in self.vars], 'changes': self.changes, 'seed': self.seed},
                                         ensure_ascii=False, sort_keys=True).encode()).hexdigest()


MECH_FAMILY = {                      # name: (arity, program builder over input programs a, b, c, d)
    'COPY': (1, lambda a: a),
    'NOT': (1, lambda a: ('NOT', a)),
    'AND': (2, lambda a, b: ('AND', a, b)),
    'OR': (2, lambda a, b: ('OR', a, b)),
    'XOR': (2, lambda a, b: ('XOR', a, b)),
    'ANDNOT': (2, lambda a, b: ('AND', a, ('NOT', b))),
    'TOGGLE': (1, lambda a: ('XOR', ('SELF',), a)),                  # flips when a is on
    'LATCH': (1, lambda a: ('OR', ('SELF',), a)),                    # turns on and stays on
    'MAJ': (3, lambda a, b, c: ('IF', ('XOR', a, b), c, a)),
    'ATLEAST3OF4': (4, lambda a, b, c, d: ('ATLEAST', ('C', 3), a, b, c, d)),
    'XOR3': (3, lambda a, b, c: ('XOR', ('XOR', a, b), c)),
    'ANDOR': (3, lambda a, b, c: ('AND', a, ('OR', b, c))),
    'XORAND': (3, lambda a, b, c: ('XOR', a, ('AND', b, c))),
}


def gen_mechworld(seed: int, *, n_switch: int = 3, devices: List[Tuple[str, List[str]]] = (), noise: int = 0,
                  confounded: bool = False, flip_p: float = 0.15, world_id: Optional[str] = None,
                  changes: List[Tuple[int, int, str, List[str]]] = (), names: Optional[List[str]] = None) -> MechWorld:
    """devices: list of (family, input refs) where refs are 'S0'..'S2' (switches), 'D0'.. (earlier devices).
    changes: (t, device index, new family, new refs).  All symbols renamed with pseudo-words from `seed`."""
    rng = random.Random(seed)
    used: set = set()
    nm = names or []
    k = 0

    def nxt():
        nonlocal k
        if k < len(nm):
            k += 1
            return nm[k - 1]
        return pseudo_name(rng, used)
    vs: List[VarSpec] = []
    sw = [nxt() for _ in range(n_switch)]
    hid = None
    if confounded:
        hid = 'скрытый'
        vs.append(VarSpec(hid, 'hidden', flip_p=0.08))
    for i, s in enumerate(sw):
        vs.append(VarSpec(s, 'switch', flip_p=flip_p, driver=(hid if (confounded and i == 0) else None)))
    dev_names = []
    ref = {f'S{i}': ('V', s) for i, s in enumerate(sw)}
    if hid:
        ref['H'] = ('V', hid)
    for j, (fam, refs) in enumerate(devices):
        d = nxt()
        dev_names.append(d)
        ar, build = MECH_FAMILY[fam]
        vs.append(VarSpec(d, 'device', program=build(*[ref[r] for r in refs])))
        ref[f'D{j}'] = ('V', d)
    for _ in range(noise):
        vs.append(VarSpec(nxt(), 'noise'))
    ch = []
    for (t, di, fam, refs) in changes:
        ar, build = MECH_FAMILY[fam]
        ch.append((t, dev_names[di], build(*[ref[r] for r in refs])))
    return MechWorld(world_id or f'mech{seed}', vs, seed, ch)


@dataclass
class EntityWorld:
    """Static classification: entities with boolean features; target relation = hidden rule over <= 4 features."""
    world_id: str
    features: List[str]
    rule: tuple                        # program over ('V', feature)
    entities: Dict[str, Dict[str, int]]
    relation: str

    def label(self, entity: str) -> int:
        return ev(self.rule, self.entities[entity])

    def digest(self) -> str:
        return hashlib.sha256(json.dumps({'id': self.world_id, 'f': self.features, 'rule': self.rule,
                                          'e': self.entities}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def gen_entityworld(seed: int, family: str, n_features: int = 5, n_entities: int = 32,
                    world_id: Optional[str] = None) -> EntityWorld:
    rng = random.Random(seed)
    used: set = set()
    feats = [pseudo_name(rng, used).lower() for _ in range(n_features)]
    ar, build = MECH_FAMILY[family]
    chosen = rng.sample(feats, ar)
    rule = build(*[('V', f) for f in chosen])
    ents = {}
    for _ in range(n_entities):
        e = pseudo_name(rng, used)
        ents[e] = {f: rng.randrange(2) for f in feats}
    return EntityWorld(world_id or f'ent{seed}', feats, rule, ents, pseudo_name(rng, used).lower())
