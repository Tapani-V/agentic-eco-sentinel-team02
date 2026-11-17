"""
Calibrated deferral gate via split conformal prediction.

The weak point of any "let's wait until Friday" recommendation is that the risk
of waiting is a point estimate with no coverage guarantee. A reliability
engineer is personally accountable if the pump dies on Thursday, so "78%
probability of failure" is not a number they can act on.

This module replaces it with a distribution-free lower bound on remaining
useful life:

    P( true_TTF >= TTF_lower_bound ) >= 1 - alpha

which holds in finite samples under exchangeability, for ANY underlying
predictor -- no distributional assumptions, no model retraining. Deferral to
day D is permitted only if D < TTF_lower_bound minus a safety margin.

Two properties matter for the demo:

1. It can REFUSE. If the calibration set is too small to support the requested
   confidence level, no finite bound exists and the gate blocks deferral rather
   than inventing a number. An agent that knows when it cannot answer is worth
   more than one that always answers.

2. It is Mondrian (group-conditional) by equipment type, so a bound for pumps
   is calibrated on pump residuals. Marginal coverage can hide systematic
   under-coverage on a minority asset class -- exactly the class most likely to
   be the one that fails.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class CalibrationRecord:
    """One historical episode: what we predicted vs. what actually happened."""

    equipment_type: str
    predicted_ttf_days: float
    actual_ttf_days: float

    @property
    def nonconformity(self) -> float:
        """Over-prediction error. Positive = we were optimistic = dangerous."""
        return self.predicted_ttf_days - self.actual_ttf_days


@dataclass
class DeferralVerdict:
    permitted: bool
    requested_defer_days: float
    ttf_point_estimate_days: float
    ttf_lower_bound_days: Optional[float]
    alpha: float
    coverage: float
    calibration_n: int
    group: str
    safety_margin_days: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "deferral_permitted": self.permitted,
            "requested_defer_days": round(self.requested_defer_days, 2),
            "ttf_point_estimate_days": round(self.ttf_point_estimate_days, 2),
            "ttf_lower_bound_days": (
                round(self.ttf_lower_bound_days, 2)
                if self.ttf_lower_bound_days is not None
                else None
            ),
            "coverage_level": self.coverage,
            "calibration_set_size": self.calibration_n,
            "calibration_group": self.group,
            "safety_margin_days": self.safety_margin_days,
            "reason": self.reason,
        }


class ConformalDeferralGate:
    """Split-conformal lower bound on remaining useful life.

    Usage:
        gate = ConformalDeferralGate(alpha=0.10, safety_margin_days=1.0)
        gate.fit(calibration_records)
        verdict = gate.evaluate("PUMP", predicted_ttf_days=21.0, defer_days=5.0)
    """

    def __init__(
        self,
        alpha: float = 0.10,
        safety_margin_days: float = 1.0,
        min_group_size: int = 20,
        mondrian: bool = True,
    ):
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = alpha
        self.safety_margin_days = safety_margin_days
        self.min_group_size = min_group_size
        self.mondrian = mondrian
        self._scores_by_group: Dict[str, List[float]] = defaultdict(list)
        self._scores_pooled: List[float] = []
        self._fitted = False

    # -- calibration ------------------------------------------------------
    def fit(self, records: Sequence[CalibrationRecord]) -> "ConformalDeferralGate":
        self._scores_by_group.clear()
        self._scores_pooled.clear()
        for rec in records:
            score = rec.nonconformity
            self._scores_by_group[rec.equipment_type].append(score)
            self._scores_pooled.append(score)
        for group in self._scores_by_group:
            self._scores_by_group[group].sort()
        self._scores_pooled.sort()
        self._fitted = True
        return self

    def _select_scores(self, equipment_type: str) -> Tuple[List[float], str]:
        """Group-conditional scores when the group is big enough, else pooled."""
        if self.mondrian:
            group_scores = self._scores_by_group.get(equipment_type, [])
            if len(group_scores) >= self.min_group_size:
                return group_scores, equipment_type
        return self._scores_pooled, "pooled"

    # -- the conformal quantile ------------------------------------------
    @staticmethod
    def _conformal_quantile(sorted_scores: List[float], alpha: float) -> Optional[float]:
        """The finite-sample-valid (1-alpha) quantile of the calibration scores.

        Rank is ceil((n+1)(1-alpha)). If that exceeds n, the calibration set is
        too small to certify this confidence level and we return None rather
        than silently degrading to the sample maximum.
        """
        n = len(sorted_scores)
        if n == 0:
            return None
        rank = math.ceil((n + 1) * (1.0 - alpha))
        if rank > n:
            return None
        return sorted_scores[rank - 1]

    def ttf_lower_bound(
        self, equipment_type: str, predicted_ttf_days: float
    ) -> Tuple[Optional[float], int, str]:
        """Lower bound on true remaining useful life at level 1 - alpha."""
        if not self._fitted:
            raise RuntimeError("Gate is not calibrated. Call fit() first.")
        scores, group = self._select_scores(equipment_type)
        q = self._conformal_quantile(scores, self.alpha)
        if q is None:
            return None, len(scores), group
        return predicted_ttf_days - q, len(scores), group

    # -- the decision -----------------------------------------------------
    def evaluate(
        self,
        equipment_type: str,
        predicted_ttf_days: float,
        defer_days: float,
    ) -> DeferralVerdict:
        lower_bound, n, group = self.ttf_lower_bound(equipment_type, predicted_ttf_days)
        coverage = 1.0 - self.alpha

        if lower_bound is None:
            return DeferralVerdict(
                permitted=False,
                requested_defer_days=defer_days,
                ttf_point_estimate_days=predicted_ttf_days,
                ttf_lower_bound_days=None,
                alpha=self.alpha,
                coverage=coverage,
                calibration_n=n,
                group=group,
                safety_margin_days=self.safety_margin_days,
                reason=(
                    f"Calibration set of {n} episodes cannot certify "
                    f"{coverage:.0%} coverage (needs at least "
                    f"{math.ceil(1.0 / self.alpha) - 1}). Deferral blocked: the "
                    f"risk of waiting is not quantifiable, not merely unknown."
                ),
            )

        required = defer_days + self.safety_margin_days
        permitted = required <= lower_bound

        if permitted:
            reason = (
                f"At {coverage:.0%} coverage, remaining life is at least "
                f"{lower_bound:.1f} days (calibrated on {n} {group} episodes). "
                f"Deferring {defer_days:.1f} days plus a {self.safety_margin_days:.1f}-day "
                f"margin stays inside that bound."
            )
        else:
            reason = (
                f"At {coverage:.0%} coverage, remaining life may be as low as "
                f"{lower_bound:.1f} days. Deferring {defer_days:.1f} days plus a "
                f"{self.safety_margin_days:.1f}-day margin needs {required:.1f} days "
                f"of certified life. Deferral blocked."
            )

        return DeferralVerdict(
            permitted=permitted,
            requested_defer_days=defer_days,
            ttf_point_estimate_days=predicted_ttf_days,
            ttf_lower_bound_days=lower_bound,
            alpha=self.alpha,
            coverage=coverage,
            calibration_n=n,
            group=group,
            safety_margin_days=self.safety_margin_days,
            reason=reason,
        )

    def max_safe_deferral_days(self, equipment_type: str, predicted_ttf_days: float) -> float:
        """Longest deferral the calibration supports. 0.0 means repair now."""
        lower_bound, _, _ = self.ttf_lower_bound(equipment_type, predicted_ttf_days)
        if lower_bound is None:
            return 0.0
        return max(0.0, lower_bound - self.safety_margin_days)


def empirical_coverage(
    gate: ConformalDeferralGate, test_records: Sequence[CalibrationRecord]
) -> dict:
    """Validate the bound on held-out data. Put this number on a slide.

    If empirical coverage lands near the nominal level, the guarantee is not
    just theoretical -- it held on this fleet's data.
    """
    covered = 0
    evaluated = 0
    for rec in test_records:
        lb, _, _ = gate.ttf_lower_bound(rec.equipment_type, rec.predicted_ttf_days)
        if lb is None:
            continue
        evaluated += 1
        if rec.actual_ttf_days >= lb:
            covered += 1
    return {
        "nominal_coverage": 1.0 - gate.alpha,
        "empirical_coverage": round(covered / evaluated, 4) if evaluated else None,
        "n_evaluated": evaluated,
    }
