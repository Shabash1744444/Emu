"""Structural learner S, one target: a Bayesian mixture over mechanism hypotheses with prequential credit.

Hypothesis h = (parent tuple P, operator table g, noise eta):  y(t+1) = g(x_P(t), y(t)) (dynamic) or y = g(x_P).
FAMILIES are blocks of hypotheses sharing P and a signature.  Two kinds of families:
  * innate   — present at the world's birth, data-independent: full Bayesian credit on every observation;
  * extended — created LATER by an internal iteration that looked at the data (more parents, larger programs, lag
    inputs).  Because their creation depended on the data, they are SPECIALISTS (Freund et al. 1997): they get
    credit only for observations that arrive AFTER their birth.  Past data may be used to decide WHICH tables to
    instantiate (they must be consistent with it), never to give them weight.  This is the formal content of
    REPLAY != NEW EVIDENCE for the learner: thinking can propose, only the world can confirm.
Credit changes only in `update`, i.e. only on an admitted, verified observation.
Answers (`assertable`) are UNKNOWN unless backed by (i) memory of the very same full situation since the last
change point, or (ii) a certificate: posterior >= tau AND >= n_cert consecutive confident predictions that came true
on situations never seen before, since the MAP last changed or failed.

Implementation: weights of all hypotheses live in flat arrays (N, n_eta); predictions for a context are gathered
per signature group with one fancy-index per group (no per-hypothesis Python)."""
from __future__ import annotations

import base64
import itertools
import math
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import numpy as np

from .operators import OperatorSpace, configs, prog_str, strides


def _lse(a: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    if a.size == 0:
        return -math.inf
    m = float(np.max(a))
    if not np.isfinite(m):
        return m
    return m + math.log(float(np.sum(np.exp(a - m))))


def _enc(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=np.float64).tobytes()).decode('ascii')


def _dec(s: str, cols: int) -> np.ndarray:
    a = np.frombuffer(base64.b64decode(s.encode('ascii')), dtype=np.float64).copy()
    return a.reshape(-1, cols)


def _sha(a: np.ndarray) -> str:
    import hashlib
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def table_depends(in_domains, T: np.ndarray) -> np.ndarray:
    """Which inputs each table row depends on; T shape (n, n_conf) -> bool (n, n_inputs)."""
    T = np.atleast_2d(np.asarray(T))
    conf = configs(tuple(in_domains))
    st = strides(tuple(in_domains))
    out = np.zeros((len(T), len(in_domains)), dtype=bool)
    for i, d in enumerate(in_domains):
        for v in range(1, d):
            alt = conf.copy()
            alt[:, i] = (alt[:, i] + v) % d
            idx = (alt.astype(np.int64) * st).sum(1)
            out[:, i] |= (T != T[:, idx]).any(1)
    return out


class Family:
    __slots__ = ('fid', 'parents', 'sig_key', 'ops', 'born_obs', 'specialist', 'lag', 'origin', 'private', 'start',
                 'end', 'bonus', 'private_size')

    def __init__(self, fid, parents, sig_key, ops, born_obs, specialist, lag, origin, private=None, start=0, end=0,
                 bonus=0.0, private_size=8):
        self.fid, self.parents, self.sig_key = fid, tuple(parents), tuple(sig_key)
        self.ops = np.asarray(ops, dtype=np.int64)
        self.born_obs, self.specialist, self.lag, self.origin = born_obs, specialist, lag, origin
        self.private = None if private is None else np.asarray(private, dtype=np.int8)   # tables taught by a lesson
        self.start, self.end = start, end
        self.bonus, self.private_size = bonus, private_size

    def to_dict(self):
        return {'fid': self.fid, 'parents': list(self.parents), 'sig_key': [list(self.sig_key[0]), self.sig_key[1],
                                                                            self.sig_key[2]],
                'ops': base64.b64encode(self.ops.astype(np.int32).tobytes()).decode('ascii'),
                'born_obs': self.born_obs, 'specialist': self.specialist, 'lag': self.lag,
                'origin': self.origin, 'private': None if self.private is None else self.private.tolist(),
                'start': self.start, 'end': self.end, 'bonus': self.bonus, 'private_size': self.private_size}


class TargetModel:
    # Noise of a hypothesis is LEARNED: each hypothesis carries counts of its own hits and misses since its birth and
    # predicts its value with probability (hits + A) / (hits + misses + A + B)  (Beta(A, B) prior integrated out).
    A_PRIOR = 1.0
    B_PRIOR = 0.25
    FORGET = 1.0                  # hit/miss counts discount factor (1.0 = none; 0.98 was tried on dev seed 1 and added wrong assertions)
    MEMORY_QUIET = 100            # memory of exact situations is trusted only this long after its last contradiction
    SWITCH_MIN = 3                # an entry whose outcomes switched cleanly (v..v v'..v', >= 3 v') is in a new regime
    PCACHE = 96
    # CL-R5 G0.3: a hypothesis whose posterior weight is within LAMBDA_BITS of the best hypothesis predicting v is a
    # PLAUSIBLE rival; where a plausible rival predicts another value, the model is not confident.
    # Cycle 1 chose 8 bits by the rule of CL-R5_G0_DESIGN.md §G0.3 and was RED (G3: early confidence on new seeds).
    # Cycle 3 (CL-R5_G0R3_ADDENDUM.md §4, rule R2.2 of CL-R5_G0R2_ADDENDUM.md): the smallest grid value with 0 wrong OP
    # assertions in all roles but NOISE, A3 = 0 % and LIFE passed on dev seeds 1-3 — results/calibration_r3/
    # CALIBRATION_G0R3.json.  The calibration hook is removed (DEVIATIONS_G0R3.md §2).
    LAMBDA_BITS = 20.0

    def __init__(self, name: str, ctx_domains: List[int], self_idx: Optional[int], out_domain: int,
                 space: OperatorSpace, lib_version: int, *, init_k: int = 2, init_size: int = 6,
                 log_pi_u: float = -8 * math.log(2), alpha: float = 0.002, tau: float = 0.9, n_cert: int = 6):
        self.name, self.ctx_domains, self.self_idx, self.out_domain = name, list(ctx_domains), self_idx, out_domain
        self.space, self.lib_version = space, lib_version
        self.alpha, self.tau, self.n_cert = alpha, tau, n_cert
        self.families: List[Family] = []
        self.logw = np.zeros(0)
        self.logprior = np.zeros(0)
        self.hits = np.zeros(0)
        self.miss = np.zeros(0)
        self.last_mem_contra: Optional[int] = None
        self.mem_confirmations = 0                # repeats of a remembered situation with the same outcome (window)
        self.logw_u = log_pi_u
        self.logprior_u = log_pi_u
        self.n_obs = 0
        self.rows: List[Tuple[Tuple[int, ...], Optional[Tuple[int, ...]], int, bool]] = []   # (x_t, x_prev, y, interv.)
        self.int_rows: List[List[int]] = []       # per row: context indices set by the agent's own action
        self.size_max: Dict[int, int] = {}
        self.lag_enabled = False
        # certification / memory
        self.streak = 0                           # consecutive confident-correct predictions on fresh situations
        self.int_streak = 0                       # ... of which on interventional transitions (any variable set by us)
        self.int_by_var: Dict[int, int] = {}      # ... of which with THIS context variable set by us and a MAP parent
        self.memory: Dict[Tuple[int, ...], set] = {}
        self.row_seqs: List[Optional[int]] = []   # CL-R5 G0.1: journal seq of each admitted observation (row)
        self.witness: List[int] = []              # ... of the observations on which the current streak grew
        self.change_points: List[int] = []
        self.table_windows: List[int] = []        # CL-R5 G0-R3: observations at which a certificate failed
        self.failures = 0
        self.history: List[dict] = []             # MAP changes with reasons (observation index)
        self._fid = 0
        self._reset_caches()
        # the learned library is part of the vocabulary of worlds born after it: an a-ary library operator makes
        # a-parent mechanisms part of the innate grammar (with the library symbol's short code)
        lib_ar = [len(l.in_domains) for l in space.library if l.version <= lib_version]
        k0 = max([init_k] + lib_ar)
        self.k_max = k0
        self.innate(k0, init_size)

    # ------------------------------------------------------------------ caches
    def _reset_caches(self):
        self._sver = 0           # structure version (families)
        self._wver = 0           # weight version
        self._pcache: 'OrderedDict' = OrderedDict()
        self._cache: Dict = {}
        self._groups_cache = None
        self._lP = None

    def _struct_changed(self):
        self._sver += 1
        self._wver += 1
        self._pcache.clear()
        self._cache = {}
        self._groups_cache = None
        self._lP = None

    def _weights_changed(self):
        self._wver += 1
        self._cache = {k: v for k, v in self._cache.items() if k[0] == 'st'}

    # ------------------------------------------------------------------ structure
    def _cand_parents(self, k: int, lag: bool = False):
        idx = [i for i in range(len(self.ctx_domains)) if i != self.self_idx]
        if lag:
            n = len(self.ctx_domains)
            idx = idx + [n + i for i in range(n)]            # lagged copies x(t-1) of every context variable
        return [c for c in itertools.combinations(idx, k)]

    def _dom(self, i):
        n = len(self.ctx_domains)
        return self.ctx_domains[i % n]

    def _sig(self, parents):
        ins = [self._dom(i) for i in parents]
        if self.self_idx is not None:
            ins = ins + [self.out_domain]
        return (tuple(ins), self.out_domain, self.lib_version)

    def _op_logprior(self, sig_key, ops: np.ndarray) -> np.ndarray:
        s = self.space.sigs[sig_key]
        bps = self.space.bits_per_symbol(self.lib_version)
        sizes = s.sizes()[ops].astype(np.float64)
        return -sizes * bps * math.log(2)

    def _k_logprior(self, k: int, n_cands: int) -> float:
        return -(k + 1) * math.log(2) - math.log(max(1, n_cands))

    def _fam_logprior(self, fam: 'Family') -> np.ndarray:
        """Prior of a family's hypotheses: description length of the program (or of the taught program), the
        parent-set prior, the noise-level prior, plus a lesson's bonus.  A pure function of the family."""
        if fam.private is not None:
            lp_op = np.full(len(fam.private), -fam.private_size * self.space.bits_per_symbol(self.lib_version) * math.log(2))
        else:
            lp_op = self._op_logprior(fam.sig_key, fam.ops)
        k = len(fam.parents)
        lp_k = self._k_logprior(k, len(self._cand_parents(k, fam.lag)))
        return lp_op + lp_k + fam.bonus

    def _add_family(self, parents, ops: np.ndarray, *, specialist: bool, lag: bool, origin: str, private=None,
                    private_size: int = 8):
        if len(ops) == 0 and private is None:
            return None
        sig_key = self._sig(parents)
        if private is not None:
            private = np.asarray(private, dtype=np.int8)
            ops = np.arange(len(private))
        else:
            ops = np.asarray(ops, dtype=np.int64)
        start = self.logw.shape[0]
        fam = Family(self._fid, parents, sig_key, ops, self.n_obs, specialist, lag, origin, private=private,
                     start=start, end=start + len(ops), private_size=private_size)
        lp = self._fam_logprior(fam)
        self._fid += 1
        self.families.append(fam)
        self.logw = np.concatenate([self.logw, lp])
        self.logprior = np.concatenate([self.logprior, lp])
        self.hits = np.concatenate([self.hits, np.zeros(len(lp))])
        self.miss = np.concatenate([self.miss, np.zeros(len(lp))])
        self._struct_changed()
        return fam

    def add_bonus(self, fam: Family, nats: float):
        """A lesson's hypothesis gets a prior bonus (a proposal from a lawful teacher, never a certificate)."""
        fam.bonus += nats
        self.logw[fam.start:fam.end] += nats
        self.logprior[fam.start:fam.end] += nats
        self._lP = None
        self._weights_changed()

    def _essential_ops(self, sig_key, size: int, n_parents: int) -> np.ndarray:
        s = self.space.ensure(sig_key[0], sig_key[1], size, sig_key[2])
        sizes = s.sizes()
        ok = sizes <= size
        if n_parents:
            ok &= s.op_depends[:, :n_parents].all(1)        # depends on every parent (self may be inessential)
        else:
            ok &= ~s.op_depends.any(1) if self.self_idx is None else np.ones(len(sizes), dtype=bool)
        return np.nonzero(ok)[0]

    def innate(self, k_max: int, size: int):
        for k in range(0, k_max + 1):
            for P in self._cand_parents(k):
                sig_key = self._sig(P)
                ops = self._essential_ops(sig_key, size, k)
                self._add_family(P, ops, specialist=False, lag=False, origin=f'innate k={k} size<={size}')
            self.size_max[k] = size

    # ------------------------------------------------------------------ prediction
    def _tab(self, fam: Family, c: int) -> np.ndarray:
        if fam.private is not None:
            return fam.private[:, c]
        return self.space.sigs[fam.sig_key].op_tables[fam.ops, c]

    def _strides(self, ins):
        key = ('st', ins)
        r = self._cache.get(key)
        if r is None:
            r = [int(v) for v in strides(ins)]
            self._cache[key] = r
        return r

    def _cfg(self, fam: Family, x, xp) -> int:
        n = len(self.ctx_domains)
        st = self._strides(fam.sig_key[0])
        c = 0
        for j, i in enumerate(fam.parents):
            if i < n:
                v = x[i]
            else:
                if xp is None:
                    return -1
                v = xp[i - n]
            if v is None:
                return -1
            c += int(v) * st[j]
        if self.self_idx is not None:
            v = x[self.self_idx]
            if v is None:
                return -1
            c += int(v) * st[-1]
        return c

    def _groups(self):
        if self._groups_cache is None:
            g: Dict[tuple, dict] = {}
            priv = []
            for fi, fam in enumerate(self.families):
                if fam.private is not None:
                    priv.append(fi)
                    continue
                d = g.setdefault(fam.sig_key, {'fis': [], 'ops': [], 'pos': [], 'lens': []})
                d['fis'].append(fi)
                d['ops'].append(fam.ops)
                d['pos'].append(np.arange(fam.start, fam.end))
                d['lens'].append(fam.end - fam.start)
            out = []
            for sk, d in g.items():
                out.append((sk, d['fis'], np.concatenate(d['ops']), np.concatenate(d['pos']), np.array(d['lens'])))
            self._groups_cache = (out, priv)
        return self._groups_cache

    def _pred(self, x, xp) -> np.ndarray:
        """Each hypothesis' predicted output at context (x, xp); -1 where it reads an unknown input."""
        key = (self._sver, tuple(x), None if xp is None else tuple(xp))
        hit = self._pcache.get(key)
        if hit is not None:
            self._pcache.move_to_end(key)
            return hit
        pred = np.full(self.logw.shape[0], -1, dtype=np.int16)
        groups, priv = self._groups()
        for sk, fis, ops_cat, pos_cat, lens in groups:
            cs = np.array([self._cfg(self.families[fi], x, xp) for fi in fis], dtype=np.int64)
            T = self.space.sigs[sk].op_tables
            if (cs >= 0).all():
                pred[pos_cat] = T[ops_cat, np.repeat(cs, lens)]
            else:
                cc = np.repeat(cs, lens)
                ok = cc >= 0
                if ok.any():
                    pred[pos_cat[ok]] = T[ops_cat[ok], cc[ok]]
        for fi in priv:
            fam = self.families[fi]
            c = self._cfg(fam, x, xp)
            if c >= 0:
                pred[fam.start:fam.end] = fam.private[:, c]
        self._pcache[key] = pred
        if len(self._pcache) > self.PCACHE:
            self._pcache.popitem(last=False)
        return pred

    def _weights(self):
        """(gmax, W = exp(logw - gmax), wu, q) cached until the next change of credit or structure; q = each
        hypothesis' current probability that its own predicted value occurs."""
        key = ('w', self._wver)
        r = self._cache.get(key)
        if r is None:
            gmax = max(float(np.max(self.logw)) if self.logw.size else -math.inf, self.logw_u)
            q = (self.hits + self.A_PRIOR) / (self.hits + self.miss + self.A_PRIOR + self.B_PRIOR)
            r = (gmax, np.exp(self.logw - gmax), math.exp(self.logw_u - gmax), q)
            self._cache = {k: v for k, v in self._cache.items() if k[0] == 'st'}
            self._cache[key] = r
        return r

    def _mix(self, pred: np.ndarray, known_only_denominator: bool = True):
        """Mixture over hypotheses that can see the context (pred >= 0).  Returns (p, Z, stats)."""
        D = self.out_domain
        gmax, W, wu, q = self._weights()
        if pred.size and pred.min() >= 0:
            pk, Wk, qk = pred, W, q
        else:
            ok = pred >= 0
            pk, Wk, qk = pred[ok], W[ok], q[ok]
        hit = np.bincount(pk, weights=Wk * qk, minlength=D)[:D]
        other = Wk * (1 - qk) / (D - 1)
        miss_by = np.bincount(pk, weights=other, minlength=D)[:D]
        mass = hit + (other.sum() - miss_by)
        Zk = float(Wk.sum())
        return mass, Zk, wu, Wk, qk

    def predictive(self, x, xp=None) -> Tuple[np.ndarray, list]:
        """Mixture predictive distribution over the output domain at context x (and lagged xp)."""
        ck = ('p', self._wver, tuple(x), tuple(xp) if xp is not None else None)
        hit = self._cache.get(ck)
        if hit is not None:
            return hit
        D = self.out_domain
        mass, Zk, wu, Wk, qk = self._mix(self._pred(x, xp))
        p = (mass + wu / D) / (Zk + wu)
        # expected entropy of the members (for the information value)
        with np.errstate(divide='ignore', invalid='ignore'):
            hq = -(qk * np.log(qk) + (1 - qk) * np.log(np.where(qk < 1, (1 - qk) / (D - 1), 1.0)))
        exp_h = (float((Wk * hq).sum()) + wu * math.log(D)) / (Zk + wu)
        res = (p, [exp_h, wu / (Zk + wu)])
        self._cache[ck] = res
        return res

    def eig(self, x, xp=None) -> float:
        """Expected information gain (nats) about the hypothesis identity from observing y at context x (BALD).
        Zero for pure noise: if every credible hypothesis predicts a flat distribution there is nothing to learn."""
        p, (exp_h, wu) = self.predictive(x, xp)
        h_mix = -float(np.sum(p * np.log(np.clip(p, 1e-300, 1))))
        return max(0.0, h_mix - exp_h)

    def _fam_of(self, i: int) -> int:
        key = ('starts', self._sver)
        st = self._cache.get(key)
        if st is None:
            st = np.array([f.start for f in self.families], dtype=np.int64)
            self._cache[key] = st
        return int(np.searchsorted(st, i, side='right') - 1)

    def map_hypothesis(self):
        key = ('map', self._wver)
        if key in self._cache:
            return self._cache[key]
        best = None
        if self.logw.size:
            i = int(np.argmax(self.logw))
            if float(self.logw[i]) > self.logw_u:
                fam = self.families[self._fam_of(i)]
                best = (fam, i - fam.start, 0)
        self._cache[key] = best
        return best

    def map_key(self):
        m = self.map_hypothesis()
        if m is None:
            return ('UNIFORM',)
        fam, o, e = m
        if fam.private is not None:
            return (fam.parents, fam.sig_key[0], 'private', fam.private[o].tobytes().hex())
        return (fam.parents, fam.sig_key[0], int(fam.ops[o]))

    # ------------------------------------------------------------------ update (the ONLY place credit changes)
    def update(self, x, y: int, xp=None, interventional: bool = False, int_vars=(), seq: Optional[int] = None) -> dict:
        """int_vars: context indices whose values in x were SET by the agent's own verified action (receipt).
        seq: journal seq of the admitted observation (the evidence root of anything this update contributes to)."""
        D = self.out_domain
        p, _ = self.predictive(x, xp)
        map_before = self.map_hypothesis()
        pred = int(np.argmax(p))
        conf = float(p[pred]) >= self.tau and not self.rival(x, xp, pred)
        mkey_before = self.map_key()
        full = tuple(x) + (tuple(xp) if (self.lag_enabled and xp is not None) else ())
        mem_before = self.memory.get(full)
        fresh = mem_before is None             # a situation never seen since the last change point: a real test
        # --- Bayesian / specialist credit ---
        logpmix = math.log(max(float(p[y]), 1e-300))
        hp = self._pred(x, xp)
        gmax, W, wu, q = self._weights()
        hitm = hp == y
        delta = np.where(hitm, np.log(q), np.log((1 - q) / (D - 1))) - logpmix
        asleep = hp < 0                        # hypotheses that cannot see this context are asleep
        if asleep.any():
            delta[asleep] = 0.0
        self.logw = self.logw + delta
        awake = ~asleep
        lam = np.where(awake, self.FORGET, 1.0)
        self.hits = self.hits * lam + (hitm & awake)
        self.miss = self.miss * lam + ((~hitm) & awake)
        self.logw_u = self.logw_u + math.log(1.0 / D) - logpmix
        self._fixed_share()
        self._weights_changed()
        self.n_obs += 1
        self.rows.append((tuple(x), tuple(xp) if xp is not None else None, int(y), bool(interventional)))
        self.int_rows.append(sorted(int(i) for i in int_vars))
        self.row_seqs.append(None if seq is None else int(seq))
        # --- certification bookkeeping ---
        correct = pred == y
        out = {'p_true': float(p[y]), 'pred': pred, 'confident': conf, 'correct': correct, 'fresh': fresh,
               'map_before': str(mkey_before)}
        if mem_before is not None and y not in mem_before:           # the very same situation now gives another outcome
            self.change_points.append(self.n_obs)
            self.memory = {}
            self.last_mem_contra = self.n_obs
            self.mem_confirmations = 0
            out['change_point'] = 'MEMORY_CONTRADICTED'
        elif mem_before is not None:
            self.mem_confirmations += 1                              # determinism positively evidenced once more
        streak0 = self.streak
        if conf and not correct:
            self.failures += 1
            if self.certified():
                # a failed certified prediction: either the world changed or the certificate was wrong.  Memory is
                # suspended (not erased).  CL-R5 G0-R3 (R3.1): it also opens a new evidence window for the ASSERTED
                # TABLE of the mechanism (mechanism()); local contradictions keep their window (they only forbid):
                # a sign of change may make the model forget what it may claim, never what it saw contradicted.
                self.last_mem_contra = self.n_obs
                self.table_windows.append(self.n_obs)
                out['certificate_failed'] = True
            self.streak = 0
            self.int_streak = 0
            self.int_by_var = {}
            self.witness = []
        elif conf and correct and fresh:
            self.streak += 1
            if seq is not None:
                self.witness.append(int(seq))
            if interventional:
                self.int_streak += 1
            if int_vars and map_before is not None:
                fam, o, e = map_before
                dep = self.fam_depends(fam, o)
                for j, i in enumerate(fam.parents):
                    if i in int_vars and dep[j]:
                        self.int_by_var[i] = self.int_by_var.get(i, 0) + 1
        self.memory.setdefault(full, set()).add(int(y))
        mkey_after = self.map_key()
        if mkey_after != mkey_before:
            self.history.append({'obs': self.n_obs, 'from': str(mkey_before), 'to': str(mkey_after),
                                 'reason': 'FAILED_PREDICTION' if (conf and not correct) else 'CREDIT_SHIFT'})
            self.streak = 0
            self.int_streak = 0
            self.int_by_var = {}
            self.witness = []
        out['map_after'] = str(mkey_after)
        out['map_changed'] = mkey_after != mkey_before
        out['certified'] = self.certified()
        out['streak'] = self.streak
        out['streak_up'] = self.streak > streak0
        return out

    def _fixed_share(self):
        if self.alpha <= 0 or not self.logw.size:
            return
        if self._lP is None:
            self._lP = _lse(np.concatenate([self.logprior, [self.logprior_u]]))
        lM = _lse(np.concatenate([self.logw, [self.logw_u]]))
        a = self.alpha
        base = math.log(a) + lM - self._lP
        self.logw = np.logaddexp(self.logw + math.log(1 - a), base + self.logprior)
        self.logw_u = float(np.logaddexp(self.logw_u + math.log(1 - a), base + self.logprior_u))

    # ------------------------------------------------------------------ knowledge state
    def certified(self) -> bool:
        return self.streak >= self.n_cert and self.map_hypothesis() is not None

    def _total(self) -> float:
        return _lse(np.concatenate([self.logw, [self.logw_u]]))

    def unexplained(self) -> float:
        return float(math.exp(self.logw_u - self._total()))

    def inadequacy(self) -> float:
        """Posterior expected error rate: how much the current representation fails to explain deterministically
        (the uniform component counts as chance).  Pure noise and a missing input look alike here; the finite
        meta-grammar bounds the effort spent on finding out which one it is."""
        gmax, W, wu, q = self._weights()
        D = self.out_domain
        Z = float(W.sum()) + wu
        return float((float((W * (1 - q)).sum()) + wu * (1 - 1 / D)) / Z) if Z > 0 else 1.0

    def fam_table(self, fam: Family, o: int) -> np.ndarray:
        if fam.private is not None:
            return fam.private[o]
        return self.space.sigs[fam.sig_key].op_tables[int(fam.ops[o])]

    def fam_depends(self, fam: Family, o: int) -> np.ndarray:
        if fam.private is not None:
            return table_depends(fam.sig_key[0], fam.private[o][None, :])[0]
        return self.space.sigs[fam.sig_key].op_depends[int(fam.ops[o])]

    def function_mass(self) -> float:
        """Posterior mass of the MAP's function (both noise levels; identical tables in other families of the
        same parents counted too)."""
        m = self.map_hypothesis()
        if m is None:
            return 0.0
        fam, o, e = m
        tab = self.fam_table(fam, o)
        acc = []
        for f in self.families:
            if f.parents != fam.parents or f.sig_key[:2] != fam.sig_key[:2]:
                continue
            T = f.private if f.private is not None else self.space.sigs[f.sig_key].op_tables[f.ops]
            same = np.nonzero((T == tab[None, :]).all(1))[0]
            if len(same):
                acc.append(self.logw[f.start + same])
        return float(math.exp(_lse(np.concatenate(acc)) - self._total())) if acc else 0.0

    def since_change_rows(self):
        start = max(0, self.change_points[-1] - 1) if self.change_points else 0
        return start, self.rows[start:]

    def since_sign_rows(self):
        """CL-R5 G0-R3: rows since the last SIGN of change (memory contradiction or failed certificate) — the evidence
        window of the asserted mechanism table."""
        marks = ([self.change_points[-1]] if self.change_points else []) + \
            ([self.table_windows[-1]] if self.table_windows else [])
        start = max(0, max(marks) - 1) if marks else 0
        return start, self.rows[start:]

    def mechanism(self, names: List[str]) -> dict:
        """The MAP mechanism as a table over its ESSENTIAL inputs.  An entry is asserted only if that input
        configuration was actually observed since the last sign of change (memory contradiction or, CL-R5 G0-R3,
        failed certificate) and every such observation agreed with the table; never-visited configurations stay
        UNKNOWN (no extrapolation into unvisited regions of the mechanism's own input space: the identifiability
        limit)."""
        m = self.map_hypothesis()
        if m is None:
            return {'program': None, 'inputs': [], 'domains': [], 'table': [], 'support': [], 'complete': False,
                    'function_mass': 0.0, 'family_origin': None}
        fam, o, e = m
        n = len(self.ctx_domains)
        sig_in = fam.sig_key[0]
        sig_names = [(names[i] if i < n else names[i - n] + '(t-1)') for i in fam.parents]
        src: list = list(fam.parents)
        if self.self_idx is not None:
            sig_names.append('__SELF__')
            src.append(('SELF',))
        tab = self.fam_table(fam, o)
        dep = self.fam_depends(fam, o)
        ess = [j for j in range(len(sig_in)) if dep[j]]
        st = strides(tuple(sig_in))
        red_doms = tuple(sig_in[j] for j in ess)
        red_conf = configs(red_doms)
        red_tab, idx_of = [], {}
        for r, c in enumerate(red_conf):
            full = np.zeros(len(sig_in), dtype=np.int64)
            for jj, j in enumerate(ess):
                full[j] = c[jj]
            red_tab.append(int(tab[int((full * st).sum())]))
            idx_of[tuple(int(v) for v in c)] = r
        seen: Dict[int, list] = {}
        cnt: Dict[int, int] = {}
        start, rows = self.since_sign_rows()
        for x, xp, y, _ in rows:
            vals = []
            ok = True
            for j in ess:
                s_ = src[j]
                if s_ == ('SELF',):
                    v = x[self.self_idx]
                elif s_ < n:
                    v = x[s_]
                else:
                    v = xp[s_ - n] if xp is not None else None
                if v is None:
                    ok = False
                    break
                vals.append(int(v))
            if ok:
                k_ = idx_of[tuple(vals)]
                seen.setdefault(k_, []).append(int(y))
                cnt[k_] = cnt.get(k_, 0) + 1
        table = []
        for r in range(len(red_conf)):
            outs = self.effective_outcomes(seen[r]) if r in seen else None
            table.append(red_tab[r] if (outs is not None and outs == {red_tab[r]}) else None)
        support = [cnt.get(r, 0) for r in range(len(red_conf))]
        s = self.space.sigs.get(fam.sig_key)
        prog = s.op_progs[int(fam.ops[o])] if fam.private is None else None
        return {'program': prog_str(prog, sig_names) if prog is not None else f'taught({fam.origin})',
                'inputs': [sig_names[j] for j in ess], 'domains': list(red_doms), 'table': table, 'map_table': red_tab,
                'support': support, 'complete': all(v is not None for v in table) and len(table) > 0,
                'function_mass': self.function_mass(), 'since_obs': start, 'family_origin': fam.origin}

    # ------------------------------------------------------------------ assertions with unknown inputs
    def predictive_lb(self, x, xp=None) -> np.ndarray:
        """Lower bound of the predictive distribution when some inputs are unknown (None): hypotheses that read
        an unknown input support no value (their mass only enlarges the denominator)."""
        D = self.out_domain
        mass, Zk, wu, Wk, qk = self._mix(self._pred(x, xp))
        gmax, W, wu_, q = self._weights()
        return (mass + wu / D) / (float(W.sum()) + wu)

    def heavy_inputs(self, frac: float = 1e-3) -> set:
        """Context indices (lagged: n+i) read by families holding at least `frac` of the posterior mass."""
        key = ('heavy', self._wver, frac)
        r = self._cache.get(key)
        if r is not None:
            return r
        gmax, W, wu, q = self._weights()
        tot = float(W.sum()) + wu
        out = set()
        for fam in self.families:
            if float(W[fam.start:fam.end].sum()) >= frac * tot:
                out.update(fam.parents)
        self._cache[key] = out
        return out

    def assertable_partial(self, x, xp=None, max_combos: int = 512) -> Tuple[Optional[int], str, float]:
        """Assert y only if EVERY completion of the unknown inputs that matter yields the same confident,
        certified (or remembered) value."""
        n = len(self.ctx_domains)
        x = list(x)
        xp = list(xp) if xp is not None else None
        heavy = self.heavy_inputs()
        unk = []
        for i in sorted(heavy):
            if i < n and x[i] is None:
                unk.append(i)
            elif i >= n and xp is not None and xp[i - n] is None:
                unk.append(i)
        if self.self_idx is not None and x[self.self_idx] is None and self.self_idx not in unk:
            unk.append(self.self_idx)
        doms = [self._dom(i) for i in unk]
        if doms and int(np.prod(doms)) > max_combos:
            return None, 'UNKNOWN', 0.0
        vals, pmin, bases = set(), 1.0, set()
        for combo in (itertools.product(*[range(d) for d in doms]) if doms else [()]):
            xx, xxp = list(x), (list(xp) if xp is not None else None)
            for i, v in zip(unk, combo):
                if i < n:
                    xx[i] = v
                else:
                    xxp[i - n] = v
            complete = all(v is not None for v in xx) and (xxp is None or all(v is not None for v in xxp))
            if complete:
                v, basis, p = self.assertable(xx, xxp)
                if v is None:
                    return None, 'UNKNOWN', p
            else:
                if not self.certified():
                    return None, 'UNKNOWN', 0.0
                p_ = self.predictive_lb(xx, xxp)
                v = int(np.argmax(p_))
                p = float(p_[v])
                if p < self.tau or self.local_contradiction(xx, xxp, v) or self.rival(xx, xxp, v):
                    return None, 'UNKNOWN', p
                basis = 'CERTIFIED'
            vals.add(v)
            bases.add(basis)
            pmin = min(pmin, p)
            if len(vals) > 1:
                return None, 'UNKNOWN', 0.0
        return vals.pop(), ('CERTIFIED' if 'CERTIFIED' in bases else 'MEMORY'), pmin

    @property
    def memory_confirm(self) -> int:
        """CL-R5 G0.2: repeats that must agree before exact-situation memory is trusted, DERIVED from tau: against a
        noise alternative whose agreement rate is unknown (r ~ U(0,1)), a agreeing repeats and no disagreement give
        P(deterministic) = (a+1)/(a+2) >= tau  <=>  a >= (2 tau - 1)/(1 - tau)  (= 8 for tau = 0.9)."""
        return max(1, math.ceil((2 * self.tau - 1) / (1 - self.tau) - 1e-9))

    def memory_trusted(self) -> bool:
        """Exact-situation memory presumes the target is a function of what is observed.  Trusted only with
        positive evidence of that (>= memory_confirm repeats that agreed) and without a recent sign of world change or
        hidden causes (a contradiction of memory, or a failed certificate, within MEMORY_QUIET observations)."""
        quiet = self.last_mem_contra is None or self.n_obs - self.last_mem_contra >= self.MEMORY_QUIET
        return quiet and self.mem_confirmations >= self.memory_confirm

    def rival(self, x, xp, v) -> bool:
        """CL-R5 G0.3: does a PLAUSIBLE rival predict a value other than v at (x, xp)?  Plausible = not refuted more
        than the best hypothesis predicting v (no more misses) and posterior weight within LAMBDA_BITS of it.
        Plausibility is relative: a rival with tiny mass that the data have not refuted still makes the model unsure
        exactly where it disagrees.  Hypotheses that cannot see the context (an unknown input) do not count here."""
        if not self.logw.size:
            return False
        key = ('rv', self._wver, tuple(x), None if xp is None else tuple(xp), int(v))
        r = self._cache.get(key)
        if r is not None:
            return r
        hp = self._pred(x, xp)
        agree = hp == v
        dis = (hp >= 0) & ~agree
        if not dis.any():
            r = False
        elif not agree.any():
            r = True                                   # nothing that can see this context predicts v
        else:
            ia = np.flatnonzero(agree)
            iref = int(ia[np.argmax(self.logw[ia])])
            # a rival is plausible only if the data have not refuted it more than the reference (DEVIATIONS_G0 §1):
            # a hypothesis that already erred where the reference did not is a worse explanation, not a live rival
            cand = dis & (self.miss <= self.miss[iref] + 1e-9)
            r = bool(cand.any() and float(np.max(self.logw[cand])) >= float(self.logw[iref]) - self.LAMBDA_BITS * math.log(2))
        self._cache[key] = r
        return r

    def _entry_outcomes(self):
        """For the current MAP: outcomes observed since the last change point per configuration of its essential
        inputs (cached until the MAP or the data change)."""
        key = ('entries', self._wver)
        r = self._cache.get(key)
        if r is not None:
            return r
        m = self.map_hypothesis()
        if m is None:
            self._cache[key] = (None, None, {})
            return self._cache[key]
        fam, o, e = m
        dep = self.fam_depends(fam, o)
        n = len(self.ctx_domains)
        src = list(fam.parents) + ([('SELF',)] if self.self_idx is not None else [])
        ess = [src[j] for j in range(len(src)) if dep[j]]
        start, rows = self.since_change_rows()
        seqs: Dict[tuple, list] = {}
        for x, xp, y, _ in rows:
            k = self._entry_key(ess, x, xp)
            if k is not None:
                seqs.setdefault(k, []).append(int(y))
        outs = {k: self.effective_outcomes(v) for k, v in seqs.items()}
        r = (m, ess, outs)
        self._cache[key] = r
        return r

    @classmethod
    def effective_outcomes(cls, seq: List[int]) -> set:
        """Outcomes of one input configuration that count NOW: all of them, unless they switched cleanly from one
        constant value to another (>= SWITCH_MIN times the new value at the end) — a regime change of this case;
        interleaved outcomes stay contradictory."""
        if not seq:
            return set()
        last = seq[-1]
        j = len(seq)
        while j > 0 and seq[j - 1] == last:
            j -= 1
        suffix, prefix = len(seq) - j, seq[:j]
        if prefix and suffix >= cls.SWITCH_MIN and len(set(prefix)) == 1:
            return {last}
        return set(seq)

    def _entry_key(self, ess, x, xp):
        n = len(self.ctx_domains)
        k = []
        for s_ in ess:
            if s_ == ('SELF',):
                v = x[self.self_idx]
            elif s_ < n:
                v = x[s_]
            else:
                v = xp[s_ - n] if xp is not None else None
            if v is None:
                return None
            k.append(int(v))
        return tuple(k)

    def local_contradiction(self, x, xp, v) -> bool:
        """Has the MAP's own input configuration for this query been observed since the last change point with an
        outcome other than v?  Then the certificate does not cover this case."""
        m, ess, outs = self._entry_outcomes()
        if m is None:
            return False
        k = self._entry_key(ess, x, xp)
        if k is None:
            return False
        o = outs.get(k)
        return o is not None and o != {int(v)}

    def assertable(self, x, xp=None) -> Tuple[Optional[int], str, float]:
        """(value or None, basis, probability).  basis: MEMORY | CERTIFIED | UNKNOWN."""
        full = tuple(x) + (tuple(xp) if (self.lag_enabled and xp is not None) else ())
        seen = self.memory.get(full)
        if seen is not None and len(seen) == 1 and self.memory_trusted():
            return next(iter(seen)), 'MEMORY', 1.0
        p, _ = self.predictive(x, xp)
        v = int(np.argmax(p))
        if p[v] >= self.tau and self.certified() and not self.local_contradiction(x, xp, v) \
                and not self.rival(x, xp, v):
            return v, 'CERTIFIED', float(p[v])
        return None, 'UNKNOWN', float(p[v])

    def map_description(self, names: List[str]) -> dict:
        m = self.map_hypothesis()
        if m is None:
            return {'map': 'UNEXPLAINED', 'unexplained': self.unexplained()}
        fam, o, e = m
        s = self.space.sigs.get(fam.sig_key)
        n = len(self.ctx_domains)
        in_names = [(names[i] if i < n else names[i - n] + '(t-1)') for i in fam.parents]
        if self.self_idx is not None:
            in_names.append(names[self.self_idx] + '(t)')
        if fam.private is not None:
            mp = f'taught({fam.origin})({", ".join(in_names)})'
        else:
            mp = prog_str(s.op_progs[int(fam.ops[o])], in_names)
        i = fam.start + o
        err = float((self.miss[i] + self.B_PRIOR) / (self.hits[i] + self.miss[i] + self.A_PRIOR + self.B_PRIOR))
        return {'map': mp, 'parents': [names[i_ % n] for i_ in fam.parents],
                'lag': any(i_ >= n for i_ in fam.parents), 'eta': round(err, 5),
                'posterior': float(math.exp(float(self.logw[i]) - self._total())),
                'unexplained': self.unexplained(), 'certified': self.certified(), 'streak': self.streak,
                'specialist': fam.specialist, 'family_origin': fam.origin}

    def n_hypotheses(self) -> int:
        return int(self.logw.shape[0])

    # ------------------------------------------------------------------ internal iterations (proposals)
    def extend(self, kind: str) -> dict:
        """Data-triggered representation extension.  New hypotheses are SPECIALISTS: born now, weight = prior, credit
        only from future observations; the past data only selects which tables are worth instantiating."""
        before = self.logw.shape[0]
        if kind == 'ARITY':
            k = self.k_max + 1
            self.k_max = k
            size = max(self.size_max.values()) if self.size_max else 6
            self._extend_parents(k, size, lag=False, origin=f'extension ARITY k={k}')
            self.size_max[k] = size
        elif kind == 'SIZE':
            for k in range(0, self.k_max + 1):
                size = self.size_max.get(k, 6) + 1
                self._extend_parents(k, size, lag=False, origin=f'extension SIZE k={k} size={size}')
                self.size_max[k] = size
        elif kind == 'LAG':
            self.lag_enabled = True
            self._extend_parents(1, max(self.size_max.values()), lag=True, origin='extension LAG k=1')
            self._extend_parents(2, max(self.size_max.values()), lag=True, origin='extension LAG k=2')
        after = self.logw.shape[0]
        return {'kind': kind, 'new_hypotheses': int(after - before), 'k_max': self.k_max,
                'size_max': {str(k): v for k, v in sorted(self.size_max.items())}, 'lag': self.lag_enabled}

    def _consistent(self, sig_key, parents, ops: np.ndarray, max_err_frac: float = 0.3) -> np.ndarray:
        if not self.rows or len(ops) == 0:
            return ops
        tabs = self.space.sigs[sig_key].op_tables[ops]
        n = len(self.ctx_domains)
        st = strides(sig_key[0])
        cfgs, ys = [], []
        for x, xp, y, _ in self.rows:
            vals = [(x[i] if i < n else (xp[i - n] if xp is not None else None)) for i in parents]
            if any(v is None for v in vals):
                continue
            if self.self_idx is not None:
                vals.append(x[self.self_idx])
            cfgs.append(int(sum(int(v) * int(s) for v, s in zip(vals, st))))
            ys.append(y)
        if not cfgs:
            return ops
        pred = tabs[:, np.array(cfgs)]
        err = (pred != np.array(ys)[None, :]).mean(1)
        return ops[err <= max_err_frac]

    def _extend_parents(self, k, size, *, lag, origin):
        for P in self._cand_parents(k, lag):
            if lag and not any(i >= len(self.ctx_domains) for i in P):
                continue                                  # lag families must use at least one lagged input
            sig_key = self._sig(P)
            ops = self._essential_ops(sig_key, size, k)
            have = set()
            for f in self.families:
                if f.parents == tuple(P) and f.sig_key == sig_key and f.private is None:
                    have.update(int(o) for o in f.ops)
            ops = np.array([o for o in ops if int(o) not in have], dtype=np.int64)
            ops = self._consistent(sig_key, P, ops)
            self._add_family(P, ops, specialist=True, lag=lag, origin=origin)

    # ------------------------------------------------------------------ serialization
    def to_dict(self):
        return {'name': self.name, 'ctx_domains': self.ctx_domains, 'self_idx': self.self_idx,
                'out_domain': self.out_domain, 'lib_version': self.lib_version, 'alpha': self.alpha, 'tau': self.tau,
                'n_cert': self.n_cert, 'families': [f.to_dict() for f in self.families],
                'logw': _enc(self.logw), 'logprior_sha': _sha(self.logprior), 'logw_u': self.logw_u,
                'hits': _enc(self.hits), 'miss': _enc(self.miss), 'last_mem_contra': self.last_mem_contra,
                'mem_confirmations': self.mem_confirmations,
                'logprior_u': self.logprior_u, 'n_obs': self.n_obs,
                'rows': [[list(x), (list(xp) if xp is not None else None), y, i] for x, xp, y, i in self.rows],
                'int_rows': self.int_rows, 'k_max': self.k_max,
                'size_max': {str(k): v for k, v in self.size_max.items()},
                'lag_enabled': self.lag_enabled, 'streak': self.streak, 'int_streak': self.int_streak,
                'int_by_var': [[int(k), int(v)] for k, v in sorted(self.int_by_var.items())],
                'memory': [[list(k), sorted(v)] for k, v in self.memory.items()],
                'change_points': self.change_points, 'table_windows': self.table_windows,
                'failures': self.failures, 'history': self.history,
                '_fid': self._fid, 'row_seqs': self.row_seqs, 'witness': self.witness}

    @classmethod
    def from_dict(cls, d, space):
        self = cls.__new__(cls)
        self.name, self.ctx_domains, self.self_idx = d['name'], d['ctx_domains'], d['self_idx']
        self.out_domain, self.space, self.lib_version = d['out_domain'], space, d['lib_version']
        self.alpha, self.tau, self.n_cert = d['alpha'], d['tau'], d['n_cert']
        self._reset_caches()
        self.families = []
        for f in d['families']:
            sk = (tuple(f['sig_key'][0]), f['sig_key'][1], f['sig_key'][2])
            ops = (np.asarray(f['ops'], dtype=np.int64) if isinstance(f['ops'], list) else
                   np.frombuffer(base64.b64decode(f['ops'].encode('ascii')), dtype=np.int32).astype(np.int64))
            self.families.append(Family(f['fid'], f['parents'], sk, ops, f['born_obs'], f['specialist'],
                                        f['lag'], f['origin'], private=f.get('private'), start=f['start'],
                                        end=f['end'], bonus=f.get('bonus', 0.0), private_size=f.get('private_size', 8)))
        self.logw = _dec(d['logw'], 1).ravel()
        self.hits, self.miss = _dec(d['hits'], 1).ravel(), _dec(d['miss'], 1).ravel()
        self.last_mem_contra = d.get('last_mem_contra')
        self.mem_confirmations = d.get('mem_confirmations', 0)
        self.logprior = np.concatenate([self._fam_logprior(f) for f in self.families]) if self.families else np.zeros(0)
        if _sha(self.logprior) != d['logprior_sha']:
            raise ValueError(f'prior of target {self.name} not reproducible on load')
        self.logw_u, self.logprior_u, self.n_obs = d['logw_u'], d['logprior_u'], d['n_obs']
        self.rows = [(tuple(x), tuple(xp) if xp is not None else None, y, i) for x, xp, y, i in d['rows']]
        self.int_rows = [list(r) for r in d['int_rows']]
        self.k_max = d['k_max']
        self.size_max = {int(k): v for k, v in d['size_max'].items()}
        self.lag_enabled, self.streak, self.int_streak = d['lag_enabled'], d['streak'], d['int_streak']
        self.int_by_var = {int(k): int(v) for k, v in d['int_by_var']}
        self.memory = {tuple(k): set(v) for k, v in d['memory']}
        self.change_points, self.failures, self.history = d['change_points'], d['failures'], d['history']
        self.table_windows = list(d.get('table_windows', []))
        self._fid = d['_fid']
        self.row_seqs = list(d.get('row_seqs', [None] * len(self.rows)))
        self.witness = list(d.get('witness', []))
        return self
