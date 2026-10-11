"""Candidate W — the integrated WEIGHTED learner (design §3.2): neural mechanism modules with routing and three
timescales of plasticity, a bootstrap ensemble for uncertainty, and replay ('sleep') for consolidation.

Per target (FAST weights, this world only):  routing logits A (slots x inputs) — which inputs each of S slots reads
(soft attention over x(t) and x(t-1)) — and module-choice logits B over K modules.
Shared SLOW weights (all worlds): K small MLP modules z=[slot values, own value] -> logits.  Slow weights change ONLY
in sleep (replay quanta chosen by DRIVE); fast weights change online on every admitted observation (prequential:
predict first, then a gradient step) and in sleep.
EPISODIC memory: the admitted transitions (with the journal seq of their percept = lineage), plus lesson samples
(with the lesson's seq).  Ensemble: E independent copies (different initialisations, Poisson(1) bootstrap weights per
sample); the predictive distribution is the ensemble mean and its disagreement is the information value (BALD).
Certification of assertions is the SAME rule as for S (tau, n_cert fresh confident-correct predictions, memory of the
exact situation, change points), so the two candidates are compared under one assertion policy.
Determinism: every random draw comes from generators whose state is part of the snapshot."""
from __future__ import annotations

import base64
import hashlib
import itertools
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

E_MEMBERS = 4
K_MODULES = 6
SLOTS = 4
HIDDEN = 16
DMAX = 4
Z = SLOTS + 1
LR_FAST = 0.05
LR_SLOW = 0.05
B1, B2, EPS = 0.9, 0.999, 1e-8


def _enc(a: np.ndarray) -> list:
    a = np.ascontiguousarray(a, dtype=np.float64)
    return [list(a.shape), base64.b64encode(a.tobytes()).decode('ascii')]


def _dec(x) -> np.ndarray:
    shape, b = x
    return np.frombuffer(base64.b64decode(b.encode('ascii')), dtype=np.float64).copy().reshape(shape)


def _softmax(a, axis=-1):
    m = np.max(a, axis=axis, keepdims=True)
    e = np.exp(a - m)
    return e / e.sum(axis=axis, keepdims=True)


def _seed(*parts) -> int:
    return int(hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()[:16], 16)


class Adam:
    def __init__(self, shapes: Dict[str, tuple]):
        self.m = {k: np.zeros(s) for k, s in shapes.items()}
        self.v = {k: np.zeros(s) for k, s in shapes.items()}
        self.t = 0

    def step(self, params: Dict[str, np.ndarray], grads: Dict[str, np.ndarray], lr: float):
        self.t += 1
        for k, g in grads.items():
            self.m[k] = B1 * self.m[k] + (1 - B1) * g
            self.v[k] = B2 * self.v[k] + (1 - B2) * g * g
            mh = self.m[k] / (1 - B1 ** self.t)
            vh = self.v[k] / (1 - B2 ** self.t)
            params[k] -= lr * mh / (np.sqrt(vh) + EPS)

    def to_dict(self):
        return {'t': self.t, 'm': {k: _enc(v) for k, v in self.m.items()}, 'v': {k: _enc(v) for k, v in self.v.items()}}

    @classmethod
    def from_dict(cls, d):
        a = cls.__new__(cls)
        a.t = d['t']
        a.m = {k: _dec(v) for k, v in d['m'].items()}
        a.v = {k: _dec(v) for k, v in d['v'].items()}
        return a


class SlowModules:
    """Shared mechanism modules (one set per ensemble member).  Changed only in sleep."""

    def __init__(self, seed: int = 0):
        rng = np.random.default_rng(_seed('slow', seed))
        self.p = {'W1': rng.normal(0, 1 / math.sqrt(Z), (E_MEMBERS, K_MODULES, HIDDEN, Z)) * 1.5,
                  'b1': rng.normal(0, 0.5, (E_MEMBERS, K_MODULES, HIDDEN)),
                  'W2': rng.normal(0, 1 / math.sqrt(HIDDEN), (E_MEMBERS, K_MODULES, DMAX, HIDDEN)),
                  'b2': np.zeros((E_MEMBERS, K_MODULES, DMAX))}
        self.opt = Adam({k: v.shape for k, v in self.p.items()})
        self.updates = 0
        self.seed = seed

    def to_dict(self):
        return {'p': {k: _enc(v) for k, v in self.p.items()}, 'opt': self.opt.to_dict(), 'updates': self.updates,
                'seed': self.seed}

    @classmethod
    def from_dict(cls, d):
        s = cls.__new__(cls)
        s.p = {k: _dec(v) for k, v in d['p'].items()}
        s.opt = Adam.from_dict(d['opt'])
        s.updates, s.seed = d['updates'], d['seed']
        return s


def forward(slow: Dict[str, np.ndarray], A: np.ndarray, Bm: np.ndarray, X: np.ndarray, S: np.ndarray, D: int):
    """Batched forward for one target.  A (E,SL,m), Bm (E,K), X (b,m) scaled inputs, S (b,) own value scaled.
    Returns p (E,b,D) and a cache for backward."""
    alpha = _softmax(A, -1)                                   # (E,SL,m)
    u = np.einsum('esm,bm->ebs', alpha, X)                    # (E,b,SL)
    z = np.concatenate([u, np.broadcast_to(S[None, :, None], (A.shape[0], len(S), 1))], -1)   # (E,b,Z)
    pre = np.einsum('ekhz,ebz->ebkh', slow['W1'], z) + slow['b1'][:, None]                    # (E,b,K,H)
    h = np.tanh(pre)
    o = np.einsum('ekdh,ebkh->ebkd', slow['W2'][:, :, :D], h) + slow['b2'][:, None, :, :D]    # (E,b,K,D)
    beta = _softmax(Bm, -1)                                   # (E,K)
    logits = np.einsum('ek,ebkd->ebd', beta, o)
    p = _softmax(logits, -1)
    return p, (alpha, u, z, h, o, beta, X)


def backward(slow, A, Bm, cache, p, y: np.ndarray, w: np.ndarray, D: int, need_slow: bool):
    """Gradients of sum_e sum_b w[e,b] * (-log p[e,b,y_b]).  y (b,), w (E,b)."""
    alpha, u, z, h, o, beta, X = cache
    E, b = w.shape
    oh = np.zeros((b, D))
    oh[np.arange(b), y] = 1.0
    dlog = w[:, :, None] * (p - oh[None])                     # (E,b,D)
    dbeta = np.einsum('ebd,ebkd->ek', dlog, o)
    dB = beta * (dbeta - (beta * dbeta).sum(-1, keepdims=True))
    do = beta[:, None, :, None] * dlog[:, :, None, :]         # (E,b,K,D)
    W2 = slow['W2'][:, :, :D]
    dh = np.einsum('ekdh,ebkd->ebkh', W2, do)
    dpre = dh * (1 - h * h)
    dz = np.einsum('ekhz,ebkh->ebz', slow['W1'], dpre)
    du = dz[:, :, :SLOTS]
    dalpha = np.einsum('ebs,bm->esm', du, X)
    dA = alpha * (dalpha - (alpha * dalpha).sum(-1, keepdims=True))
    g = {'A': dA, 'B': dB}
    if need_slow:
        dW2 = np.zeros_like(slow['W2'])
        dW2[:, :, :D] = np.einsum('ebkd,ebkh->ekdh', do, h)
        db2 = np.zeros_like(slow['b2'])
        db2[:, :, :D] = do.sum(1)
        g['W1'] = np.einsum('ebkh,ebz->ekhz', dpre, z)
        g['b1'] = dpre.sum(1)
        g['W2'] = dW2
        g['b2'] = db2
    return g


class WTarget:
    """One target of the weighted learner, with the SAME certification bookkeeping as the structural learner."""
    ETAS = (0.0,)

    def __init__(self, name, ctx_domains, self_idx, out_domain, slow: SlowModules, seed: int, *, tau=0.9, n_cert=6,
                 lagged=True):
        self.name, self.ctx_domains, self.self_idx, self.out_domain = name, list(ctx_domains), self_idx, out_domain
        self.slow, self.tau, self.n_cert = slow, tau, n_cert
        self.lagged = lagged and self_idx is not None
        n = len(self.ctx_domains)
        self.m = 2 * n if self.lagged else n
        rng = np.random.default_rng(_seed('fast', name, seed))
        self.A = rng.normal(0, 0.1, (E_MEMBERS, SLOTS, self.m))
        self.Bm = np.zeros((E_MEMBERS, K_MODULES))
        self.opt = Adam({'A': self.A.shape, 'B': self.Bm.shape})
        self.boot_state = np.random.default_rng(_seed('boot', name, seed)).bit_generator.state
        self.n_obs = 0
        self.rows: List[tuple] = []          # (x, xp, y, interventional, percept_seq)
        self.int_rows: List[List[int]] = []
        self.lesson_rows: List[tuple] = []   # (x, xp, y, lesson_seq)
        self.streak = 0
        self.int_streak = 0
        self.int_by_var: Dict[int, int] = {}
        self.memory: Dict[tuple, set] = {}
        self.change_points: List[int] = []
        self.table_windows: List[int] = []        # CL-R5 G0-R3: observations at which a certificate failed
        self.failures = 0
        self.history: List[dict] = []
        self.lag_enabled = self.lagged
        self.recent_loss: List[float] = []
        self.last_mem_contra = None
        self.mem_confirmations = 0
        self.probe: List[tuple] = []          # recent distinct situations: their decisions define 'the hypothesis'
        self.witness: List[int] = []          # CL-R5 G0.1: observation seqs on which the current streak grew
        self._ver = 0
        self._cache: Dict = {}

    # ------------------------------------------------------------------ encoding
    def _scale(self, i, v):
        d = self.ctx_domains[i % len(self.ctx_domains)]
        return float(v) / (d - 1) if d > 1 else 0.0

    def encode(self, x, xp) -> Tuple[np.ndarray, float]:
        n = len(self.ctx_domains)
        vec = [self._scale(i, x[i]) if (i != self.self_idx) else 0.0 for i in range(n)]
        if self.lagged:
            vec += [self._scale(i, xp[i]) if xp is not None else 0.0 for i in range(n)]
        s = self._scale(self.self_idx, x[self.self_idx]) if self.self_idx is not None else 0.0
        return np.array(vec), s

    # ------------------------------------------------------------------ prediction
    def member_probs(self, x, xp=None) -> np.ndarray:
        key = ('pm', self._ver, self.slow.updates, tuple(x), None if xp is None else tuple(xp))
        r = self._cache.get(key)
        if r is None:
            X, s = self.encode(x, xp)
            p, _ = forward(self.slow.p, self.A, self.Bm, X[None], np.array([s]), self.out_domain)
            r = p[:, 0, :]
            if len(self._cache) > 512:
                self._cache = {}
            self._cache[key] = r
        return r

    def predictive(self, x, xp=None):
        pm = self.member_probs(x, xp)
        return pm.mean(0), [np.array([1.0]), 0.0]

    def eig(self, x, xp=None) -> float:
        pm = np.clip(self.member_probs(x, xp), 1e-12, 1)
        pbar = pm.mean(0)
        return max(0.0, float(-(pbar * np.log(pbar)).sum() + (pm * np.log(pm)).sum(1).mean()))

    # ------------------------------------------------------------------ online update (fast weights only)
    def _boot(self, k: int) -> np.ndarray:
        g = np.random.default_rng()
        g.bit_generator.state = self.boot_state
        w = g.poisson(1.0, size=(E_MEMBERS, k)).astype(np.float64)
        self.boot_state = g.bit_generator.state
        return w

    def probs_batch(self, ctxs) -> np.ndarray:
        """Ensemble-member probabilities for many contexts at once: (E, b, D)."""
        enc = [self.encode(x, xp) for x, xp in ctxs]
        X = np.array([e[0] for e in enc])
        S = np.array([e[1] for e in enc])
        p, _ = forward(self.slow.p, self.A, self.Bm, X, S, self.out_domain)
        return p

    def _decisions(self, ctxs) -> List[int]:
        if not ctxs:
            return []
        return [int(v) for v in np.argmax(self.probs_batch(ctxs).mean(0), -1)]

    def rival(self, x, xp, v) -> bool:
        """CL-R5 G0.3 for W: the ensemble members are the rivals; any member whose decision differs from v makes
        the model unsure here (no parameter)."""
        return bool((np.argmax(self.member_probs(x, xp), -1) != int(v)).any())

    def update(self, x, y: int, xp=None, interventional=False, int_vars=(), seq=None) -> dict:
        p, _ = self.predictive(x, xp)
        pred = int(np.argmax(p))
        conf = float(p[pred]) >= self.tau and not self.rival(x, xp, pred)
        full = tuple(x) + (tuple(xp) if (self.lagged and xp is not None) else ())
        mem_before = self.memory.get(full)
        fresh = mem_before is None
        correct = pred == y
        ess_before = self.essential() if (conf and correct and fresh and int_vars) else set()
        self.recent_loss = (self.recent_loss + [-math.log2(max(float(p[y]), 1e-12))])[-50:]
        dec_before = self._decisions(self.probe)
        # prequential gradient step on the fast weights
        X, s = self.encode(x, xp)
        w = self._boot(1)
        pr, cache = forward(self.slow.p, self.A, self.Bm, X[None], np.array([s]), self.out_domain)
        g = backward(self.slow.p, self.A, self.Bm, cache, pr, np.array([int(y)]), w, self.out_domain, False)
        params = {'A': self.A, 'B': self.Bm}
        self.opt.step(params, g, LR_FAST)
        self.A, self.Bm = params['A'], params['B']
        self._ver += 1
        self.n_obs += 1
        self.rows.append((tuple(x), tuple(xp) if xp is not None else None, int(y), bool(interventional), seq))
        self.int_rows.append(sorted(int(i) for i in int_vars))
        out = {'p_true': float(p[y]), 'pred': pred, 'confident': conf, 'correct': correct, 'fresh': fresh}
        if mem_before is not None and y not in mem_before:
            self.change_points.append(self.n_obs)
            self.memory = {}
            self.last_mem_contra = self.n_obs
            self.mem_confirmations = 0
            out['change_point'] = 'MEMORY_CONTRADICTED'
        elif mem_before is not None:
            self.mem_confirmations += 1
        streak0 = self.streak
        if conf and not correct:
            self.failures += 1
            if self.certified():
                # a failed certified prediction: either the world changed or the certificate was wrong.  Memory is
                # suspended (not erased).  CL-R5 G0-R3 (R3.1): it also opens a new evidence window for the asserted
                # mechanism table only (same rule as S); local contradictions keep their window.
                self.last_mem_contra = self.n_obs
                self.table_windows.append(self.n_obs)
                out['certificate_failed'] = True
            self.streak, self.int_streak, self.int_by_var = 0, 0, {}
            self.witness = []
        elif conf and correct and fresh:
            self.streak += 1
            if seq is not None:
                self.witness.append(int(seq))
            if interventional:
                self.int_streak += 1
            for i in int_vars:
                if i in ess_before:
                    self.int_by_var[i] = self.int_by_var.get(i, 0) + 1
        self.memory.setdefault(full, set()).add(int(y))
        # analogue of 'the MAP changed': the decision function moved on recently seen situations
        changed = bool(dec_before) and self._decisions(self.probe) != dec_before
        if changed:
            self.streak, self.int_streak, self.int_by_var = 0, 0, {}
            self.witness = []
            self.history.append({'obs': self.n_obs, 'reason': 'DECISION_FUNCTION_CHANGED'})
        ctx = (tuple(x), tuple(xp) if xp is not None else None)
        if ctx not in self.probe:
            self.probe = (self.probe + [ctx])[-32:]
        out['map_changed'] = changed
        out['certified'] = self.certified()
        out['streak'] = self.streak
        out['streak_up'] = self.streak > streak0
        return out

    def certified(self) -> bool:
        return self.streak >= self.n_cert

    def unexplained(self) -> float:
        return 0.0

    def inadequacy(self) -> float:
        return 0.0

    def mean_recent_loss(self) -> float:
        return float(np.mean(self.recent_loss)) if self.recent_loss else 1.0

    # ------------------------------------------------------------------ what the net depends on
    def essential(self, max_rows: int = 32) -> set:
        """Context inputs whose change alters the ensemble's decision on recently observed situations
        (sensitivity analysis: a weighted model has no symbolic parents).  One batched forward."""
        key = ('ess', self._ver, self.slow.updates)
        r = self._cache.get(key)
        if r is not None:
            return r
        n = len(self.ctx_domains)
        rows = self.rows[-max_rows:]
        ctxs, tags = [], []
        for ri, (x, xp, y, _, _) in enumerate(rows):
            ctxs.append((x, xp))
            tags.append((ri, None))
            for i in range(n):
                if i == self.self_idx and False:
                    continue
                d = self.ctx_domains[i]
                for dv in range(1, d):
                    xx = list(x)
                    xx[i] = (xx[i] + dv) % d
                    ctxs.append((tuple(xx), xp))
                    tags.append((ri, i))
            if self.lagged and xp is not None:
                for i in range(n):
                    d = self.ctx_domains[i]
                    xxp = list(xp)
                    xxp[i] = (xxp[i] + 1) % d
                    ctxs.append((x, tuple(xxp)))
                    tags.append((ri, n + i))
        out = set()
        if ctxs:
            dec = self._decisions(ctxs)
            base = {}
            for (ri, i), d_ in zip(tags, dec):
                if i is None:
                    base[ri] = d_
            for (ri, i), d_ in zip(tags, dec):
                if i is not None and d_ != base[ri]:
                    out.add(i)
        self._cache[key] = out
        return out

    # ------------------------------------------------------------------ assertions
    MEMORY_QUIET = 100

    @property
    def memory_confirm(self) -> int:
        """CL-R5 G0.2: the same derivation as for S: (a+1)/(a+2) >= tau."""
        return max(1, math.ceil((2 * self.tau - 1) / (1 - self.tau) - 1e-9))

    def memory_trusted(self) -> bool:
        quiet = self.last_mem_contra is None or self.n_obs - self.last_mem_contra >= self.MEMORY_QUIET
        return quiet and self.mem_confirmations >= self.memory_confirm

    def local_contradiction(self, x, xp, v) -> bool:
        """Same guard as for S: the query's configuration of the inputs the net depends on was observed since the
        last change point with another outcome."""
        key = ('loc', self._ver, self.slow.updates)
        r = self._cache.get(key)
        n = len(self.ctx_domains)
        if r is None:
            from .smodel import TargetModel as _TM
            ess = sorted(self.essential())
            seqs: Dict[tuple, list] = {}
            start, rows = self.since_change_rows()
            for x_, xp_, y_, _, _ in rows:
                k = tuple((x_[i] if i < n else (xp_[i - n] if xp_ is not None else None)) for i in ess)
                if None not in k:
                    seqs.setdefault(k, []).append(int(y_))
            outs = {k: _TM.effective_outcomes(v) for k, v in seqs.items()}
            r = (ess, outs)
            self._cache[key] = r
        ess, outs = r
        k = tuple((x[i] if i < n else (xp[i - n] if xp is not None else None)) for i in ess)
        if None in k:
            return False
        o = outs.get(k)
        return o is not None and o != {int(v)}

    def assertable(self, x, xp=None):
        full = tuple(x) + (tuple(xp) if (self.lagged and xp is not None) else ())
        seen = self.memory.get(full)
        if seen is not None and len(seen) == 1 and self.memory_trusted():
            return next(iter(seen)), 'MEMORY', 1.0
        p, _ = self.predictive(x, xp)
        v = int(np.argmax(p))
        if p[v] >= self.tau and self.certified() and not self.local_contradiction(x, xp, v) \
                and not self.rival(x, xp, v):
            return v, 'CERTIFIED', float(p[v])
        return None, 'UNKNOWN', float(p[v])

    def assertable_partial(self, x, xp=None, max_combos: int = 512):
        n = len(self.ctx_domains)
        ess = self.essential()
        unk = [i for i in sorted(ess) if (i < n and x[i] is None) or (i >= n and (xp is None or xp[i - n] is None))]
        if self.self_idx is not None and x[self.self_idx] is None and self.self_idx not in unk:
            unk.append(self.self_idx)
        doms = [self.ctx_domains[i % n] for i in unk]
        if doms and int(np.prod(doms)) > max_combos:
            return None, 'UNKNOWN', 0.0
        vals, pmin = set(), 1.0
        for combo in (itertools.product(*[range(d) for d in doms]) if doms else [()]):
            xx = [0 if v is None else v for v in x]
            xxp = [0 if v is None else v for v in xp] if xp is not None else None
            for i, v in zip(unk, combo):
                if i < n:
                    xx[i] = v
                else:
                    if xxp is None:
                        xxp = [0] * n
                    xxp[i - n] = v
            v, basis, p = self.assertable(xx, xxp)
            if v is None:
                return None, 'UNKNOWN', p
            vals.add(v)
            pmin = min(pmin, p)
            if len(vals) > 1:
                return None, 'UNKNOWN', 0.0
        return vals.pop(), 'CERTIFIED', pmin

    def since_change_rows(self):
        start = max(0, self.change_points[-1] - 1) if self.change_points else 0
        return start, self.rows[start:]

    def since_sign_rows(self):
        """CL-R5 G0-R3: rows since the last sign of change (memory contradiction or failed certificate)."""
        marks = ([self.change_points[-1]] if self.change_points else []) + \
            ([self.table_windows[-1]] if self.table_windows else [])
        start = max(0, max(marks) - 1) if marks else 0
        return start, self.rows[start:]

    def mechanism(self, names: List[str]) -> dict:
        n = len(self.ctx_domains)
        ess = sorted(self.essential())
        if len(ess) > 6:
            return {'program': None, 'inputs': [], 'domains': [], 'table': [], 'support': [], 'complete': False,
                    'function_mass': 0.0, 'family_origin': 'W'}
        inputs = [(names[i] if i < n else names[i - n] + '(t-1)') for i in ess]
        doms = [self.ctx_domains[i % n] for i in ess]
        start, rows = self.since_sign_rows()
        from .smodel import TargetModel as _TM
        seen: Dict[tuple, list] = {}
        predicted: Dict[tuple, set] = {}
        cnt: Dict[tuple, int] = {}
        for x, xp, y, _, _ in rows:
            key = tuple((x[i] if i < n else (xp[i - n] if xp is not None else None)) for i in ess)
            if any(v is None for v in key):
                continue
            seen.setdefault(key, []).append(int(y))
            predicted.setdefault(key, set()).add(int(np.argmax(self.predictive(x, xp)[0])))
            cnt[key] = cnt.get(key, 0) + 1
        table, support = [], []
        for c in itertools.product(*[range(d) for d in doms]):
            outs = _TM.effective_outcomes(seen[c]) if c in seen else None
            preds = predicted.get(c)
            ok = outs is not None and len(outs) == 1 and preds == outs
            table.append(next(iter(outs)) if ok else None)
            support.append(cnt.get(c, 0))
        return {'program': 'W-net(' + ', '.join(inputs) + ')', 'inputs': inputs, 'domains': doms, 'table': table,
                'map_table': table, 'support': support, 'complete': bool(table) and all(v is not None for v in table),
                'function_mass': None, 'since_obs': start, 'family_origin': 'W'}

    def map_description(self, names):
        n = len(self.ctx_domains)
        ess = sorted(self.essential())
        return {'map': 'W-net(' + ', '.join((names[i] if i < n else names[i - n] + '(t-1)') for i in ess) + ')',
                'parents': [names[i % n] for i in ess], 'certified': self.certified(), 'streak': self.streak,
                'recent_loss_bits': round(self.mean_recent_loss(), 4), 'family_origin': 'W'}

    def map_hypothesis(self):
        return ('W', sorted(self.essential())) if self.rows else None

    def n_hypotheses(self) -> int:
        return int(self.A.size + self.Bm.size)

    # ------------------------------------------------------------------ serialization
    def to_dict(self):
        return {'name': self.name, 'ctx_domains': self.ctx_domains, 'self_idx': self.self_idx,
                'out_domain': self.out_domain, 'tau': self.tau, 'n_cert': self.n_cert, 'lagged': self.lagged,
                'A': _enc(self.A), 'B': _enc(self.Bm), 'opt': self.opt.to_dict(), 'boot_state': self.boot_state,
                'n_obs': self.n_obs, 'rows': [[list(x), (list(xp) if xp is not None else None), y, i, s]
                                              for x, xp, y, i, s in self.rows],
                'int_rows': self.int_rows, 'lesson_rows': [[list(x), (list(xp) if xp is not None else None), y, s]
                                                           for x, xp, y, s in self.lesson_rows],
                'streak': self.streak, 'int_streak': self.int_streak,
                'int_by_var': [[int(k), int(v)] for k, v in sorted(self.int_by_var.items())],
                'memory': [[list(k), sorted(v)] for k, v in self.memory.items()], 'change_points': self.change_points,
                'table_windows': self.table_windows,
                'failures': self.failures, 'history': self.history, 'recent_loss': self.recent_loss, '_ver': self._ver,
                'last_mem_contra': self.last_mem_contra, 'mem_confirmations': self.mem_confirmations,
                'probe': [[list(a), (list(b) if b is not None else None)] for a, b in self.probe],
                'witness': self.witness}

    @classmethod
    def from_dict(cls, d, slow):
        t = cls.__new__(cls)
        t.name, t.ctx_domains, t.self_idx, t.out_domain = d['name'], d['ctx_domains'], d['self_idx'], d['out_domain']
        t.slow, t.tau, t.n_cert, t.lagged = slow, d['tau'], d['n_cert'], d['lagged']
        n = len(t.ctx_domains)
        t.m = 2 * n if t.lagged else n
        t.A, t.Bm = _dec(d['A']), _dec(d['B'])
        t.opt = Adam.from_dict(d['opt'])
        t.boot_state = d['boot_state']
        t.n_obs = d['n_obs']
        t.rows = [(tuple(x), tuple(xp) if xp is not None else None, y, i, s) for x, xp, y, i, s in d['rows']]
        t.int_rows = [list(r) for r in d['int_rows']]
        t.lesson_rows = [(tuple(x), tuple(xp) if xp is not None else None, y, s) for x, xp, y, s in d['lesson_rows']]
        t.streak, t.int_streak = d['streak'], d['int_streak']
        t.int_by_var = {int(k): int(v) for k, v in d['int_by_var']}
        t.memory = {tuple(k): set(v) for k, v in d['memory']}
        t.change_points, t.failures, t.history = d['change_points'], d['failures'], d['history']
        t.table_windows = list(d.get('table_windows', []))
        t.recent_loss, t._ver = d['recent_loss'], d['_ver']
        t.last_mem_contra = d.get('last_mem_contra')
        t.mem_confirmations = d.get('mem_confirmations', 0)
        t.probe = [(tuple(a), tuple(b) if b is not None else None) for a, b in d['probe']]
        t.witness = list(d.get('witness', []))
        t.lag_enabled = t.lagged
        t._cache = {}
        return t


class WorldModelW:
    """World-level wrapper with the same interface the kernel uses for WorldModelS."""
    kind = 'W'

    def __init__(self, world_id, names, domains, switches, *, slow: SlowModules, seed: int = 0, static=False,
                 targets=None):
        self.world_id, self.names, self.domains = world_id, list(names), list(domains)
        self.switches, self.static, self.slow, self.seed = list(switches), static, slow, seed
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.targets: Dict[str, WTarget] = {}
        tset = set(targets) if targets is not None else None
        for n in self.names:
            if n in self.switches or (tset is not None and n not in tset):
                continue
            i = self.idx[n]
            if static:
                ctx = [d for j, d in enumerate(self.domains) if j != i]
                self.targets[n] = WTarget(f'{world_id}/{n}', ctx, None, self.domains[i], slow, seed)
            else:
                self.targets[n] = WTarget(f'{world_id}/{n}', self.domains, i, self.domains[i], slow, seed)
        self.prev, self.prev2, self.last_t = None, None, None
        self.ext_done = {n: 0 for n in self.targets}
        self.n_transitions = 0
        self.n_interventional = 0
        self.int_counts: Dict[str, int] = {}

    def vec(self, percept):
        return [int(percept[n]) for n in self.names]

    def observe(self, t, percept, intervened_prev, int_vars=(), seq=None):
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

    def observe_static(self, row, seq=None):
        out = {}
        for n, tm in sorted(self.targets.items()):
            if n in row:
                x = [int(row[m]) for m in self.names if m != n]
                out[n] = tm.update(x, int(row[n]), seq=seq)
        return out

    def assert_static(self, target, features):
        x = [int(features[m]) for m in self.names if m != target]
        return self.targets[target].assertable(x)

    def assert_next(self, target, x, xp=None):
        tm = self.targets[target]
        if any(v is None for v in x) or (xp is not None and any(v is None for v in xp)) or (tm.lagged and xp is None):
            return tm.assertable_partial(x, xp)
        return tm.assertable(x, xp)

    def simulate(self, state, k, do=None):
        x = self.vec(state)
        xp = list(self.prev2) if (self.prev2 is not None and self.prev is not None and x == self.prev) else None
        traj, bases = [], []
        held = {s: x[self.idx[s]] for s in self.switches}
        if do:
            held.update({s: int(v) for s, v in do.items()})
        for step in range(k):
            nx = [None] * len(self.names)
            for s in self.switches:
                nx[self.idx[s]] = held[s]
            for n in sorted(self.targets):
                v, basis, _ = self.assert_next(n, x, xp)
                nx[self.idx[n]] = v
                bases.append(f'{n}@{step + 1}:{basis}')
            traj.append({m: nx[self.idx[m]] for m in self.names})
            xp, x = x, nx
        return traj, bases

    def causal(self, cause, effect, k, state):
        t0, _ = self.simulate(state, k, {cause: 0})
        t1, _ = self.simulate(state, k, {cause: 1})
        vals0 = [s[effect] for s in t0]
        vals1 = [s[effect] for s in t1]
        ci = self.idx[cause]
        graph = {}
        for n, tm in self.targets.items():
            if tm.certified():
                nn = len(tm.ctx_domains)
                graph[n] = {self.names[i % nn] for i in tm.essential()}
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

    def eig_actions(self, state, permitted, bonus_targets=()):
        x = self.vec(state)
        cands = [{}] + [{s: v} for s in sorted(permitted) for v in range(self.domains[self.idx[s]]) if v != x[self.idx[s]]]
        base = list(x)
        for n in sorted(self.targets):
            p, _ = self.targets[n].predictive(x, self.prev2)
            base[self.idx[n]] = int(np.argmax(p))
        out = []
        for act in cands:
            nx = list(base)
            for s, v in act.items():
                nx[self.idx[s]] = v
            val = 0.0
            for n, tm in sorted(self.targets.items()):
                e = tm.eig(nx, x if tm.lagged else None) / math.log(2)
                if n in bonus_targets:
                    e *= 2.0
                val += e
            out.append((val, act))
        out.sort(key=lambda z: (-z[0], sorted(z[1].items())))
        return out

    def extension_candidates(self):
        return []

    def extend(self, target, kind):
        return {'kind': kind, 'new_hypotheses': 0}

    def describe(self):
        return {n: tm.map_description(self.names if not self.static else [m for m in self.names if m != n])
                for n, tm in sorted(self.targets.items())}

    def to_dict(self):
        return {'kind': 'W', 'world_id': self.world_id, 'names': self.names, 'domains': self.domains,
                'switches': self.switches, 'static': self.static, 'seed': self.seed,
                'targets': {n: tm.to_dict() for n, tm in self.targets.items()}, 'prev': self.prev, 'prev2': self.prev2,
                'last_t': self.last_t, 'n_transitions': self.n_transitions, 'n_interventional': self.n_interventional,
                'int_counts': self.int_counts}

    @classmethod
    def from_dict(cls, d, slow):
        w = cls.__new__(cls)
        w.world_id, w.names, w.domains = d['world_id'], d['names'], d['domains']
        w.switches, w.static, w.slow, w.seed = d['switches'], d['static'], slow, d['seed']
        w.idx = {n: i for i, n in enumerate(w.names)}
        w.targets = {n: WTarget.from_dict(t, slow) for n, t in d['targets'].items()}
        w.prev, w.prev2, w.last_t = d['prev'], d['prev2'], d['last_t']
        w.ext_done = {n: 0 for n in w.targets}
        w.n_transitions, w.n_interventional = d['n_transitions'], d['n_interventional']
        w.int_counts = dict(d['int_counts'])
        return w


def _eval_loss(slow, targets, items) -> float:
    """Mean ensemble log-loss (nats) of a fixed evaluation sample of replay items."""
    by_t: Dict[int, list] = {}
    for ti, kind, ri in items:
        by_t.setdefault(ti, []).append((kind, ri))
    tot, n = 0.0, 0
    for ti, its in sorted(by_t.items()):
        t = targets[ti]
        ctx, ys = [], []
        for kind, ri in its:
            row = t.rows[ri] if kind == 'obs' else t.lesson_rows[ri]
            ctx.append((row[0], row[1]))
            ys.append(int(row[2]))
        p = t.probs_batch(ctx).mean(0)
        tot += float(-np.log(np.clip(p[np.arange(len(ys)), np.array(ys)], 1e-12, 1)).sum())
        n += len(ys)
    return tot / max(1, n)


def sleep(slow: SlowModules, targets: List[WTarget], seed: int, *, steps: int = 16, batch: int = 64) -> dict:
    """Replay consolidation: minibatches drawn from the episodic memories (and lesson samples) of the given targets;
    slow AND fast weights are updated.  Returns the lineage (journal seqs of the rows used) and the loss change on
    a fixed evaluation sample drawn before training."""
    rng = np.random.default_rng(_seed('sleep', seed))
    pool = []
    for ti, t in enumerate(targets):
        for ri in range(len(t.rows)):
            pool.append((ti, 'obs', ri))
        for ri in range(len(t.lesson_rows)):
            pool.append((ti, 'lesson', ri))
    if not pool:
        return {'used_percepts': [], 'used_lessons': [], 'loss_before': None, 'loss_after': None, 'steps': 0}
    evs = [pool[int(k)] for k in rng.integers(0, len(pool), size=min(256, len(pool)))]
    loss_before = _eval_loss(slow, targets, evs)
    used_p, used_l = set(), set()
    for st in range(steps):
        pick = rng.integers(0, len(pool), size=min(batch, len(pool)))
        by_t: Dict[int, list] = {}
        for k in pick:
            ti, kind, ri = pool[int(k)]
            by_t.setdefault(ti, []).append((kind, ri))
        grads_slow = {k: np.zeros_like(v) for k, v in slow.p.items()}
        for ti, items in sorted(by_t.items()):
            t = targets[ti]
            Xs, Ss, ys = [], [], []
            for kind, ri in items:
                if kind == 'obs':
                    x, xp, y, _, s = t.rows[ri]
                    if s is not None:
                        used_p.add(int(s))
                else:
                    x, xp, y, s = t.lesson_rows[ri]
                    used_l.add(int(s))
                X, sv = t.encode(x, xp)
                Xs.append(X)
                Ss.append(sv)
                ys.append(int(y))
            X, S, y = np.array(Xs), np.array(Ss), np.array(ys)
            w = rng.poisson(1.0, size=(E_MEMBERS, len(y))).astype(np.float64) / len(pick)
            p, cache = forward(slow.p, t.A, t.Bm, X, S, t.out_domain)
            g = backward(slow.p, t.A, t.Bm, cache, p, y, w, t.out_domain, True)
            for k in grads_slow:
                grads_slow[k] += g[k]
            params = {'A': t.A, 'B': t.Bm}
            t.opt.step(params, {'A': g['A'], 'B': g['B']}, LR_FAST)
            t.A, t.Bm = params['A'], params['B']
            t._ver += 1
        slow.opt.step(slow.p, grads_slow, LR_SLOW)
        slow.updates += 1
    loss_after = _eval_loss(slow, targets, evs)
    return {'used_percepts': sorted(used_p), 'used_lessons': sorted(used_l),
            'loss_before': round(loss_before, 6), 'loss_after': round(loss_after, 6), 'steps': steps}
