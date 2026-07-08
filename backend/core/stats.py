"""Statistical engine: Wilson confidence intervals, Fisher's exact test, and flakiness scoring.

Implemented from scratch in pure Python (no scipy/numpy) since agenttest treats
LLM reliability as a statistics problem rather than a pass/fail problem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Z_SCORE_95 = 1.96


@dataclass
class PassRateResult:
    """Summary statistics for a single test's pass/fail outcomes across N runs."""

    passes: int
    total: int
    pass_rate: float
    ci_lower: float
    ci_upper: float
    meets_threshold: bool
    threshold: float
    verdict: str


@dataclass
class RegressionResult:
    """Outcome of comparing a baseline pass rate to a candidate pass rate."""

    baseline_pass_rate: float
    candidate_pass_rate: float
    delta: float
    p_value: float
    is_regression: bool
    verdict: str


SIGNIFICANCE_THRESHOLD = 0.05


def wilson_score_interval(passes: int, total: int, z: float = Z_SCORE_95) -> tuple[float, float]:
    """Compute the Wilson score confidence interval for a binomial proportion.

    Preferred over the naive normal-approximation interval because it stays
    bounded within [0, 1] and behaves well for small sample sizes and
    proportions near 0 or 1 — both common with small N test runs.
    """
    if total <= 0:
        return (0.0, 0.0)

    p_hat = passes / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p_hat + z2 / (2 * total)) / denominator
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / total + z2 / (4 * total * total))) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (lower, upper)


def compute_pass_rate(passes: int, total: int, threshold: float) -> PassRateResult:
    """Compute the full pass-rate summary (rate, CI, threshold verdict) for one test."""
    if total <= 0:
        raise ValueError("total must be greater than 0")

    pass_rate = passes / total
    ci_lower, ci_upper = wilson_score_interval(passes, total)
    meets_threshold = pass_rate >= threshold

    verdict_word = "PASS" if meets_threshold else "FAIL"
    verdict = (
        f"{verdict_word} — {pass_rate * 100:.1f}% "
        f"(CI: {ci_lower * 100:.0f}–{ci_upper * 100:.0f}%) vs threshold {threshold * 100:.0f}%"
    )

    return PassRateResult(
        passes=passes,
        total=total,
        pass_rate=pass_rate,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        meets_threshold=meets_threshold,
        threshold=threshold,
        verdict=verdict,
    )


def _log_factorial(n: int) -> float:
    """log(n!) via lgamma — numerically stable for the factorials used in hypergeometric math."""
    return math.lgamma(n + 1)


def _log_hypergeom_pmf(k: int, big_n: int, big_k: int, n: int) -> float:
    """Log-probability of the hypergeometric PMF: P(X = k) for the 2x2 table's margins."""
    return (
        _log_factorial(big_k)
        - _log_factorial(k)
        - _log_factorial(big_k - k)
        + _log_factorial(big_n - big_k)
        - _log_factorial(n - k)
        - _log_factorial(big_n - big_k - n + k)
        - _log_factorial(big_n)
        + _log_factorial(n)
        + _log_factorial(big_n - n)
    )


def fisher_exact_test(
    baseline_passes: int, baseline_total: int, candidate_passes: int, candidate_total: int
) -> float:
    """Two-sided Fisher's exact test p-value for a 2x2 contingency table.

    Table layout:
                  passed   failed
        baseline    a        b
        candidate   c        d

    Sums the probability of every table with the same margins that is as
    extreme or more extreme (by probability) than the observed table.
    """
    a = baseline_passes
    b = baseline_total - baseline_passes
    c = candidate_passes
    d = candidate_total - candidate_passes

    row1 = a + b
    row2 = c + d
    col1 = a + c
    big_n = row1 + row2

    if big_n == 0 or col1 == 0 or col1 == big_n or row1 == 0 or row2 == 0:
        return 1.0

    k_min = max(0, col1 - row2)
    k_max = min(row1, col1)

    observed_log_p = _log_hypergeom_pmf(a, big_n, col1, row1)

    total_p = 0.0
    epsilon = 1e-9
    for k in range(k_min, k_max + 1):
        log_p = _log_hypergeom_pmf(k, big_n, col1, row1)
        if log_p <= observed_log_p + epsilon:
            total_p += math.exp(log_p)

    return min(1.0, total_p)


def detect_regression(
    baseline_passes: int, baseline_total: int, candidate_passes: int, candidate_total: int
) -> RegressionResult:
    """Compare a baseline pass rate to a candidate pass rate and flag statistically significant drops."""
    baseline_rate = baseline_passes / baseline_total if baseline_total else 0.0
    candidate_rate = candidate_passes / candidate_total if candidate_total else 0.0
    delta = candidate_rate - baseline_rate

    p_value = fisher_exact_test(baseline_passes, baseline_total, candidate_passes, candidate_total)
    is_regression = p_value < SIGNIFICANCE_THRESHOLD and delta < 0

    if is_regression:
        verdict = (
            f"REGRESSION — pass rate dropped {abs(delta) * 100:.1f}pp "
            f"(p={p_value:.3f}, statistically significant)"
        )
    elif delta < 0:
        verdict = f"No significant change — dropped {abs(delta) * 100:.1f}pp but p={p_value:.3f} (likely noise)"
    else:
        verdict = f"No regression — pass rate changed {delta * 100:+.1f}pp (p={p_value:.3f})"

    return RegressionResult(
        baseline_pass_rate=baseline_rate,
        candidate_pass_rate=candidate_rate,
        delta=delta,
        p_value=p_value,
        is_regression=is_regression,
        verdict=verdict,
    )


def flakiness_score(pass_rates: list[float]) -> float:
    """Score 0.0 (rock solid) to 1.0 (completely unreliable) from historical pass-rate variance.

    Uses the standard deviation of pass rates across run batches, normalized
    by the maximum possible standard deviation for values in [0, 1] (0.5),
    so a set of rates alternating between 0.0 and 1.0 scores 1.0.
    """
    if len(pass_rates) < 2:
        return 0.0

    mean = sum(pass_rates) / len(pass_rates)
    variance = sum((r - mean) ** 2 for r in pass_rates) / len(pass_rates)
    std_dev = math.sqrt(variance)

    max_std_dev = 0.5
    return min(1.0, std_dev / max_std_dev)
