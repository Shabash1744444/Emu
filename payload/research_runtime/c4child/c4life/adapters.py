"""REG adapters (design §6.4): the old special organs re-implemented on the general mechanism of candidate S.

RuleInductionOrganS — the PROTOCOL of the old RuleInductionOrgan (examples with splits and source classes, studies and
their next needs, validation gates, independent-source and non-model-anchor requirements, counterexample suspension,
support retraction, read-only inference, persistence) is kept as a contract — it is what the old tests test.  What is
replaced is the special part: the antecedent search.  The old organ intersected the features of the positives and
enumerated conjunctions with a hand-made score.  Here the candidates come from the structural learner S: a static
target over the boolean feature universe of the examples, trained prequentially on the TRAIN split only; its
hypotheses (typed programs with description-length priors and Bayesian credit) are ranked by posterior, and those that
read as rules (a conjunction of present features of order <= max_order) are offered to the unchanged validation gates.
Validation rows are never shown to the learner: they are fresh tests (the same role the certificate plays in S).

ExperimentSelectorS — the old selector's expected-information-gain computation is the mutual information between
hypothesis identity and outcome, i.e. exactly the BALD value S's DRIVE uses for its experiments; the adapter computes
it with the S formula (entropy of the mixture predictive minus the expected entropy of the members)."""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from .operators import OperatorSpace
from .smodel import TargetModel

_SPACE = OperatorSpace()                  # the adapters' own operator space (library version 0, no lessons)
STATS = {'s_searches': 0, 's_hypotheses': 0, 'mi_calls': 0}


def mutual_information_bits(weights: List[float], dists: List[Dict[str, float]]) -> float:
    """BALD / mutual information I(H; O) in bits for a mixture with member predictive distributions."""
    s = sum(max(0.0, w) for w in weights)
    if s <= 0:
        return 0.0
    w = [max(0.0, x) / s for x in weights]
    outs = sorted({o for d in dists for o in d})
    mix = {o: sum(wi * max(0.0, float(d.get(o, 0.0))) for wi, d in zip(w, dists)) for o in outs}

    def H(p):
        return -sum(v * math.log2(v) for v in p if v > 0)
    return max(0.0, H(mix.values()) - sum(wi * H([max(0.0, float(v)) for v in d.values()]) for wi, d in zip(w, dists)))


def make_rule_organ(base_module):
    """Build the S-backed organ as a subclass of the ORIGINAL class from the (research copy of the) runtime."""
    Base = base_module.RuleInductionOrgan

    class RuleInductionOrganS(Base):
        ADAPTER = 'S'

        def _s_candidates(self, g, rows, *, target_relation, target_object_kind, target_object_value, principal, viewer):
            pos = [x for x in rows if x.split == 'train' and x.expected]
            neg = [x for x in rows if x.split == 'train' and not x.expected]
            if len(pos) < self.min_train_pos:
                return [], {}
            excl = (str(target_relation).upper(), target_object_kind, str(target_object_value))
            fmap = {x.entity: self._features(g, x.entity, principal=principal, viewer=viewer, exclude_target=excl)
                    for x in rows}
            # the variables: every feature of a TRAIN example (validation rows are never shown to the learner)
            universe = sorted(set().union(*[fmap[x.entity] for x in pos + neg]))
            if not universe:
                return [], fmap
            n = len(universe)
            col = {f: i for i, f in enumerate(universe)}
            k = min(self.max_order, n)
            tm = TargetModel('rule', [2] * n, None, 2, _SPACE, 0, init_k=k, init_size=3)
            STATS['s_searches'] += 1
            STATS['s_hypotheses'] += tm.n_hypotheses()
            for x in sorted(pos + neg, key=lambda r: r.order):
                v = [0] * n
                for f in fmap[x.entity]:
                    if f in col:
                        v[col[f]] = 1
                tm.update(v, int(bool(x.expected)))
            # rules = hypotheses whose function is a conjunction of present features (k parents, AND of all)
            cands = []
            for fam in tm.families:
                if not fam.parents or len(fam.parents) > self.max_order or fam.private is not None:
                    continue
                sig = _SPACE.sigs[fam.sig_key]
                kk = len(fam.parents)
                conj = np.array([int(all(c)) for c in np.ndindex(*([2] * kk))], dtype=np.int8)
                for j, op in enumerate(fam.ops):
                    if not np.array_equal(sig.op_tables[int(op)], conj):
                        continue
                    ant = [tuple(universe[i]) for i in fam.parents]
                    lw = float(tm.logw[fam.start + j])
                    cands.append((lw, ant))
            # posterior order (description length and credit); deterministic tie-break
            cands.sort(key=lambda z: (-round(z[0], 9), len(z[1]), tuple(z[1])))
            return cands, fmap

        def _candidate_pool(self, g, rows, *, target_relation, target_object_kind, target_object_value, principal, viewer):
            cands, fmap = self._s_candidates(g, rows, target_relation=target_relation, target_object_kind=target_object_kind,
                                             target_object_value=target_object_value, principal=principal, viewer=viewer)
            pos = [x for x in rows if x.split == 'train' and x.expected]
            neg = [x for x in rows if x.split == 'train' and not x.expected]
            out = []
            for lw, ant in cands:
                # a rule must explain every train positive and reject every train negative (the organ's contract)
                if all(self._matches(fmap[x.entity], ant) for x in pos) and \
                        all(not self._matches(fmap[x.entity], ant) for x in neg):
                    out.append((ant, fmap))
            return out

        def reassess(self, g, relation, object_value, *, object_kind='literal', polarity='POS', principal='USER', viewer='USER'):
            """The old protocol, with candidates from S taken in POSTERIOR order (the first one that passes the
            unchanged validation and source gates is admitted)."""
            key = self.target_key(relation, object_kind, str(object_value), polarity)
            self._refresh_example_activity(g, key)
            rows = [x for x in self.examples.get(key, []) if x.active]
            for r in self.rules.values():
                if self.target_key(r.target_relation, r.target_object_kind, r.target_object_value, r.target_polarity) != key or r.status != 'ADMITTED':
                    continue
                for ex in rows:
                    if ex.expected:
                        continue
                    fs = self._features(g, ex.entity, principal=principal, viewer=viewer,
                                        exclude_target=(str(relation).upper(), object_kind, str(object_value)))
                    if self._matches(fs, r.antecedent):
                        r.status = 'SUSPENDED'
                        r.failure_reason = 'COUNTEREXAMPLE'
                        break
            cands = self._candidate_pool(g, rows, target_relation=relation, target_object_kind=object_kind,
                                         target_object_value=object_value, principal=principal, viewer=viewer)
            val_pos = [x for x in rows if x.split == 'validation' and x.expected]
            val_neg = [x for x in rows if x.split == 'validation' and not x.expected]
            if len(val_pos) < self.min_validation_pos or len(val_neg) < self.min_validation_neg:
                return None
            NM = base_module.RULE_NONMODEL_CLASSES
            nm_train_pos = [x for x in rows if x.split == 'train' and x.expected and x.source_class in NM]
            nm_val_pos = [x for x in val_pos if x.source_class in NM]
            nm_val_neg = [x for x in val_neg if x.source_class in NM]
            if not nm_train_pos or not nm_val_pos or (self.min_validation_neg > 0 and not nm_val_neg):
                return None
            best = None
            for ant, fmap in cands:                       # already in posterior order
                if not all(self._matches(fmap.get(x.entity) or self._features(g, x.entity, principal=principal, viewer=viewer,
                           exclude_target=(str(relation).upper(), object_kind, str(object_value))), ant) for x in val_pos):
                    continue
                vfm = {x.entity: (fmap.get(x.entity) or self._features(g, x.entity, principal=principal, viewer=viewer,
                                  exclude_target=(str(relation).upper(), object_kind, str(object_value)))) for x in rows}
                if not all(not self._matches(vfm[x.entity], ant) for x in val_neg):
                    continue
                matching = [x for x in rows if x.expected and self._matches(vfm[x.entity], ant)]
                srcs = {x.source_group for x in matching if x.source_class in NM}
                if len(srcs) < self.min_independent_sources:
                    continue
                best = (ant, srcs)
                break
            if best is None:
                return None
            ant, srcs = best
            train_support = sum(1 for x in rows if x.split == 'train' and x.expected)
            rid = base_module._fid([key, repr(ant)])
            existing = self.rules.get(rid)
            if existing is not None:
                existing.status = 'ADMITTED'
                existing.failure_reason = None
                existing.train_support = train_support
                existing.validation_support = len(val_pos)
                existing.validation_negatives = len(val_neg)
                existing.independent_sources = len(srcs)
                return existing
            supersedes = None
            for r in sorted(self.rules.values(), key=lambda z: z.created_order, reverse=True):
                if self.target_key(r.target_relation, r.target_object_kind, r.target_object_value, r.target_polarity) == key and r.status == 'SUSPENDED':
                    supersedes = r.rule_id
                    break
            self.order += 1
            r = base_module.LearnedRule(rid, str(relation).upper(), object_kind, str(object_value), str(polarity).upper(),
                                        list(ant), 'ADMITTED', train_support, len(val_pos), len(val_neg), len(srcs),
                                        self.order, supersedes, None)
            self.rules[rid] = r
            return r

    RuleInductionOrganS.__name__ = 'RuleInductionOrgan'
    RuleInductionOrganS.__qualname__ = 'RuleInductionOrgan'
    return RuleInductionOrganS


def make_experiment_selector(base_module):
    Base = base_module.ExperimentSelector
    Proposal = base_module.ExperimentProposal

    class ExperimentSelectorS(Base):
        ADAPTER = 'S'

        def choose(self, hypotheses, allowed_actions: Optional[List[str]] = None):
            if len(hypotheses) < 2:
                return None
            priors = [max(0.0, h.prior) for h in hypotheses]
            actions = set()
            for h in hypotheses:
                actions.update(h.predictions)
            if allowed_actions is not None:
                actions.intersection_update(allowed_actions)
            best = None
            for action in sorted(actions):
                outcomes = set()
                for h in hypotheses:
                    outcomes.update(h.predictions.get(action, {}))
                if not outcomes:
                    continue
                ig = mutual_information_bits(priors, [h.predictions.get(action, {}) for h in hypotheses])
                STATS['mi_calls'] += 1
                prop = Proposal(action, ig, tuple(sorted(outcomes)), tuple(h.hypothesis_id for h in hypotheses))
                if best is None or prop.expected_information_gain_bits > best.expected_information_gain_bits + 1e-12:
                    best = prop
            if best is None or best.expected_information_gain_bits <= 1e-12:
                return None
            return best

    ExperimentSelectorS.__name__ = 'ExperimentSelector'
    ExperimentSelectorS.__qualname__ = 'ExperimentSelector'
    return ExperimentSelectorS
