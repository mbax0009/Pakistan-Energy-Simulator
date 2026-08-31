# analysis/risk_analysis.py

from __future__ import annotations

import math
import statistics

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from analysis.uncertainty import (
    MonteCarloAnalysis,
)


# ============================================================
# RISK RANKING METRICS
# ============================================================

class RiskMetric(str, Enum):
    """
    Metrics used to compare probabilistic project risk.
    """

    PROBABILITY_NPV_POSITIVE = (
        "probability_npv_positive"
    )

    PROBABILITY_OF_LOSS = (
        "probability_of_loss"
    )

    MEDIAN_NPV = (
        "median_npv"
    )

    NPV_DOWNSIDE_PERCENTILE = (
        "npv_downside_percentile"
    )

    NPV_EXPECTED_SHORTFALL = (
        "npv_expected_shortfall"
    )

    EXPECTED_LOSS_GIVEN_LOSS = (
        "expected_loss_given_loss"
    )

    PROBABILITY_IRR_ABOVE_HURDLE = (
        "probability_irr_above_hurdle"
    )

    MEDIAN_LCOE = (
        "median_lcoe"
    )

    LCOE_UPSIDE_RISK_PERCENTILE = (
        "lcoe_upside_risk_percentile"
    )

    PROBABILITY_LCOE_BELOW_BENCHMARK = (
        "probability_lcoe_below_benchmark"
    )


# ============================================================
# RANKING DIRECTION
# ============================================================

class RiskRankingDirection(str, Enum):
    """
    Defines whether higher or lower is preferable.
    """

    HIGHER_IS_BETTER = (
        "higher_is_better"
    )

    LOWER_IS_BETTER = (
        "lower_is_better"
    )


# ============================================================
# PROJECT RISK PROFILE
# ============================================================

@dataclass(frozen=True)
class ProjectRiskProfile:
    """
    Decision-oriented summary of one project's
    Monte Carlo results.

    npv_downside_probability:
        Statistical percentile used for downside
        analysis.

        Example:
            0.05 = 5th percentile.

    npv_downside_percentile_usd:
        NPV threshold at that percentile.

    npv_expected_shortfall_usd:
        Mean NPV among outcomes at or below the
        downside-percentile threshold.

        This describes the average result in the
        severe downside tail.

    expected_loss_given_loss_usd:
        Average monetary loss conditional on NPV < 0.
        Stored as a positive loss amount.
    """

    scenario_id: str

    sample_count: int

    # --------------------------------------------------------
    # NPV
    # --------------------------------------------------------

    mean_npv_usd: float

    median_npv_usd: float

    probability_npv_positive: float

    probability_of_loss: float

    npv_downside_probability: float

    npv_downside_percentile_usd: float

    npv_expected_shortfall_usd: float

    expected_loss_given_loss_usd: float | None

    # --------------------------------------------------------
    # IRR
    # --------------------------------------------------------

    irr_hurdle_rate: float | None

    probability_irr_above_hurdle: float | None

    # --------------------------------------------------------
    # LCOE
    # --------------------------------------------------------

    median_lcoe_usd_per_mwh: float | None

    lcoe_risk_percentile_probability: float

    lcoe_risk_percentile_usd_per_mwh: (
        float | None
    )

    lcoe_benchmark_usd_per_mwh: (
        float | None
    )

    probability_lcoe_below_benchmark: (
        float | None
    )

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if not self.scenario_id.strip():

            raise ValueError(
                "Scenario ID cannot be empty."
            )

        if self.sample_count < 1:

            raise ValueError(
                "Sample count must be positive."
            )

        probabilities = (
            self.probability_npv_positive,
            self.probability_of_loss,
            self.npv_downside_probability,
            self.lcoe_risk_percentile_probability,
        )

        for probability in probabilities:

            if not (
                0
                <= probability
                <= 1
            ):

                raise ValueError(
                    "Probabilities must lie "
                    "between 0 and 1."
                )


# ============================================================
# RISK RANKING
# ============================================================

@dataclass(frozen=True)
class RiskRanking:
    """
    Ranking of projects according to one
    probabilistic risk metric.
    """

    metric: RiskMetric

    direction: RiskRankingDirection

    ordered_scenario_ids: tuple[
        str,
        ...
    ]

    @property
    def best_scenario_id(
        self,
    ) -> str | None:

        if not self.ordered_scenario_ids:
            return None

        return (
            self.ordered_scenario_ids[0]
        )


# ============================================================
# CROSS-PROJECT RISK COMPARISON
# ============================================================

@dataclass(frozen=True)
class RiskComparison:
    """
    Comparison of probabilistic risk profiles.

    No universal weighted winner is created.
    """

    profiles: tuple[
        ProjectRiskProfile,
        ...
    ]

    rankings: tuple[
        RiskRanking,
        ...
    ]

    warnings: tuple[str, ...] = ()

    def __post_init__(self):

        if len(self.profiles) < 2:

            raise ValueError(
                "Risk comparison requires at "
                "least two projects."
            )

    def ranking_for(
        self,
        metric: RiskMetric,
    ) -> RiskRanking:

        for ranking in self.rankings:

            if ranking.metric is metric:
                return ranking

        raise KeyError(
            f"No ranking exists for "
            f"{metric.value}."
        )


# ============================================================
# EMPIRICAL PERCENTILE
# ============================================================

def _percentile(
    values: Sequence[float],
    probability: float,
) -> float:
    """
    Empirical percentile using linear interpolation.
    """

    if not values:

        raise ValueError(
            "Cannot calculate percentile "
            "from empty values."
        )

    if not (
        0
        <= probability
        <= 1
    ):

        raise ValueError(
            "Probability must be between 0 and 1."
        )

    ordered = sorted(
        float(value)
        for value in values
    )

    if len(ordered) == 1:
        return ordered[0]

    position = (
        probability
        * (len(ordered) - 1)
    )

    lower_index = math.floor(
        position
    )

    upper_index = math.ceil(
        position
    )

    if lower_index == upper_index:

        return ordered[
            lower_index
        ]

    fraction = (
        position
        - lower_index
    )

    return (
        ordered[lower_index]
        + fraction
        * (
            ordered[upper_index]
            - ordered[lower_index]
        )
    )


# ============================================================
# VALID NPV VALUES
# ============================================================

def _npv_values(
    analysis: MonteCarloAnalysis,
) -> tuple[float, ...]:

    values = tuple(
        float(sample.npv_usd)
        for sample in analysis.samples
        if math.isfinite(
            sample.npv_usd
        )
    )

    if not values:

        raise ValueError(
            "Monte Carlo analysis contains "
            "no valid NPV results."
        )

    return values


# ============================================================
# VALID IRR VALUES
# ============================================================

def _irr_values(
    analysis: MonteCarloAnalysis,
) -> tuple[float, ...]:

    return tuple(
        float(sample.irr)

        for sample in analysis.samples

        if (
            sample.irr is not None
            and math.isfinite(
                sample.irr
            )
        )
    )


# ============================================================
# VALID LCOE VALUES
# ============================================================

def _lcoe_values(
    analysis: MonteCarloAnalysis,
) -> tuple[float, ...]:

    return tuple(
        float(
            sample.lcoe_usd_per_mwh
        )

        for sample
        in analysis.samples

        if (
            sample.lcoe_usd_per_mwh
            is not None
            and math.isfinite(
                sample.lcoe_usd_per_mwh
            )
        )
    )


# ============================================================
# PROBABILITY OF LOSS
# ============================================================

def calculate_probability_of_loss(
    npv_values: Sequence[float],
) -> float:
    """
    Calculate:

        P(NPV < 0)
    """

    if not npv_values:

        raise ValueError(
            "NPV values cannot be empty."
        )

    loss_count = sum(
        npv < 0
        for npv in npv_values
    )

    return (
        loss_count
        / len(npv_values)
    )


# ============================================================
# EXPECTED LOSS GIVEN LOSS
# ============================================================

def calculate_expected_loss_given_loss_usd(
    npv_values: Sequence[float],
) -> float | None:
    """
    Average monetary loss conditional on:

        NPV < 0

    Returned as a positive amount.

    Example:

        negative NPVs:
            -$10m
            -$20m
            -$30m

        expected loss given loss:
            $20m
    """

    losses = tuple(
        -npv
        for npv in npv_values
        if npv < 0
    )

    if not losses:
        return None

    return statistics.fmean(
        losses
    )


# ============================================================
# DOWNSIDE NPV PERCENTILE
# ============================================================

def calculate_npv_downside_percentile_usd(
    npv_values: Sequence[float],
    downside_probability: float = 0.05,
) -> float:
    """
    Calculate a low-tail NPV percentile.

    Example:

        downside_probability = 0.05

    gives the 5th-percentile NPV.

    Only approximately 5% of simulated outcomes
    are below this threshold.
    """

    return _percentile(
        values=npv_values,
        probability=downside_probability,
    )


# ============================================================
# EXPECTED SHORTFALL
# ============================================================

def calculate_npv_expected_shortfall_usd(
    npv_values: Sequence[float],
    downside_probability: float = 0.05,
) -> float:
    """
    Calculate expected NPV in the severe downside tail.

    First determine the downside percentile q:

        q = percentile_alpha(NPV)

    Then calculate:

        ES =
            mean(
                NPV values <= q
            )

    For alpha = 5%, this is approximately the
    average NPV among the worst 5% of outcomes.

    Unlike the loss amount, this remains expressed
    directly as NPV and may therefore be negative.
    """

    threshold = (
        calculate_npv_downside_percentile_usd(

            npv_values=npv_values,

            downside_probability=(
                downside_probability
            ),
        )
    )

    tail_values = tuple(
        npv
        for npv in npv_values
        if npv <= threshold
    )

    if not tail_values:

        raise ValueError(
            "Unable to construct NPV "
            "downside tail."
        )

    return statistics.fmean(
        tail_values
    )


# ============================================================
# PROBABILITY IRR BEATS HURDLE
# ============================================================

def calculate_probability_irr_above_hurdle(
    irr_values: Sequence[float],
    hurdle_rate: float,
) -> float | None:
    """
    Calculate:

        P(IRR > hurdle rate)

    using only simulations in which IRR exists.
    """

    hurdle_rate = float(
        hurdle_rate
    )

    if not math.isfinite(
        hurdle_rate
    ):

        raise ValueError(
            "Hurdle rate must be finite."
        )

    if not irr_values:
        return None

    count = sum(
        irr > hurdle_rate
        for irr in irr_values
    )

    return (
        count
        / len(irr_values)
    )


# ============================================================
# PROBABILITY LCOE BEATS FIXED BENCHMARK
# ============================================================

def calculate_probability_lcoe_below_benchmark(
    lcoe_values: Sequence[float],
    benchmark_usd_per_mwh: float,
) -> float | None:
    """
    Calculate:

        P(
            project LCOE
            <=
            fixed benchmark LCOE
        )

    Example:

        benchmark = deterministic solar P50 LCOE

    Important:
        This compares a stochastic project against a
        fixed benchmark.

        It is NOT yet the same as comparing two
        jointly uncertain technologies.
    """

    benchmark_usd_per_mwh = float(
        benchmark_usd_per_mwh
    )

    if not math.isfinite(
        benchmark_usd_per_mwh
    ):

        raise ValueError(
            "LCOE benchmark must be finite."
        )

    if not lcoe_values:
        return None

    count = sum(
        lcoe
        <= benchmark_usd_per_mwh

        for lcoe
        in lcoe_values
    )

    return (
        count
        / len(lcoe_values)
    )


# ============================================================
# BUILD PROJECT RISK PROFILE
# ============================================================

def build_project_risk_profile(
    analysis: MonteCarloAnalysis,

    npv_downside_probability: float = 0.05,

    lcoe_risk_percentile_probability: float = 0.95,

    irr_hurdle_rate: float | None = None,

    lcoe_benchmark_usd_per_mwh: (
        float | None
    ) = None,
) -> ProjectRiskProfile:
    """
    Convert raw Monte Carlo outputs into a
    decision-oriented project risk profile.
    """

    if not (
        0
        < npv_downside_probability
        < 0.5
    ):

        raise ValueError(
            "NPV downside probability should "
            "be between 0 and 0.5."
        )

    if not (
        0.5
        < lcoe_risk_percentile_probability
        < 1
    ):

        raise ValueError(
            "LCOE risk percentile should "
            "be between 0.5 and 1."
        )

    npvs = (
        _npv_values(
            analysis
        )
    )

    irrs = (
        _irr_values(
            analysis
        )
    )

    lcoes = (
        _lcoe_values(
            analysis
        )
    )

    warnings: list[str] = []

    # --------------------------------------------------------
    # NPV statistics
    # --------------------------------------------------------

    mean_npv = (
        statistics.fmean(
            npvs
        )
    )

    median_npv = (
        statistics.median(
            npvs
        )
    )

    probability_loss = (
        calculate_probability_of_loss(
            npvs
        )
    )

    probability_positive = (
        sum(
            npv > 0
            for npv in npvs
        )
        / len(npvs)
    )

    npv_downside = (
        calculate_npv_downside_percentile_usd(

            npv_values=npvs,

            downside_probability=(
                npv_downside_probability
            ),
        )
    )

    expected_shortfall = (
        calculate_npv_expected_shortfall_usd(

            npv_values=npvs,

            downside_probability=(
                npv_downside_probability
            ),
        )
    )

    expected_loss_given_loss = (
        calculate_expected_loss_given_loss_usd(
            npvs
        )
    )

    # --------------------------------------------------------
    # IRR
    # --------------------------------------------------------

    resolved_hurdle_rate = (
        irr_hurdle_rate
    )

    if resolved_hurdle_rate is None:

        resolved_hurdle_rate = (
            analysis.irr_hurdle_rate
        )

    probability_irr_above: (
        float | None
    ) = None

    if resolved_hurdle_rate is not None:

        probability_irr_above = (
            calculate_probability_irr_above_hurdle(

                irr_values=irrs,

                hurdle_rate=(
                    resolved_hurdle_rate
                ),
            )
        )

        if probability_irr_above is None:

            warnings.append(
                "IRR was undefined in every "
                "simulation, so hurdle-rate risk "
                "could not be calculated."
            )

    # --------------------------------------------------------
    # LCOE
    # --------------------------------------------------------

    median_lcoe: float | None = None

    lcoe_risk_percentile: (
        float | None
    ) = None

    probability_lcoe_below: (
        float | None
    ) = None

    if lcoes:

        median_lcoe = (
            statistics.median(
                lcoes
            )
        )

        # High LCOE is economically adverse,
        # so use an upper-tail percentile.
        lcoe_risk_percentile = (
            _percentile(

                values=lcoes,

                probability=(
                    lcoe_risk_percentile_probability
                ),
            )
        )

        if (
            lcoe_benchmark_usd_per_mwh
            is not None
        ):

            probability_lcoe_below = (
                calculate_probability_lcoe_below_benchmark(

                    lcoe_values=lcoes,

                    benchmark_usd_per_mwh=(
                        lcoe_benchmark_usd_per_mwh
                    ),
                )
            )

    else:

        warnings.append(
            "LCOE was undefined in every "
            "Monte Carlo simulation."
        )

    # --------------------------------------------------------
    # Final profile
    # --------------------------------------------------------

    return ProjectRiskProfile(

        scenario_id=(
            analysis.scenario_id
        ),

        sample_count=(
            analysis.sample_count
        ),

        mean_npv_usd=(
            mean_npv
        ),

        median_npv_usd=(
            median_npv
        ),

        probability_npv_positive=(
            probability_positive
        ),

        probability_of_loss=(
            probability_loss
        ),

        npv_downside_probability=(
            npv_downside_probability
        ),

        npv_downside_percentile_usd=(
            npv_downside
        ),

        npv_expected_shortfall_usd=(
            expected_shortfall
        ),

        expected_loss_given_loss_usd=(
            expected_loss_given_loss
        ),

        irr_hurdle_rate=(
            resolved_hurdle_rate
        ),

        probability_irr_above_hurdle=(
            probability_irr_above
        ),

        median_lcoe_usd_per_mwh=(
            median_lcoe
        ),

        lcoe_risk_percentile_probability=(
            lcoe_risk_percentile_probability
        ),

        lcoe_risk_percentile_usd_per_mwh=(
            lcoe_risk_percentile
        ),

        lcoe_benchmark_usd_per_mwh=(
            lcoe_benchmark_usd_per_mwh
        ),

        probability_lcoe_below_benchmark=(
            probability_lcoe_below
        ),

        warnings=tuple(
            warnings
        ),
    )


# ============================================================
# EXTRACT RISK METRIC
# ============================================================

def _risk_metric_value(
    profile: ProjectRiskProfile,
    metric: RiskMetric,
) -> float | None:

    if (
        metric
        is RiskMetric.PROBABILITY_NPV_POSITIVE
    ):

        return (
            profile.probability_npv_positive
        )

    if (
        metric
        is RiskMetric.PROBABILITY_OF_LOSS
    ):

        return (
            profile.probability_of_loss
        )

    if (
        metric
        is RiskMetric.MEDIAN_NPV
    ):

        return (
            profile.median_npv_usd
        )

    if (
        metric
        is RiskMetric.NPV_DOWNSIDE_PERCENTILE
    ):

        return (
            profile
            .npv_downside_percentile_usd
        )

    if (
        metric
        is RiskMetric.NPV_EXPECTED_SHORTFALL
    ):

        return (
            profile
            .npv_expected_shortfall_usd
        )

    if (
        metric
        is RiskMetric.EXPECTED_LOSS_GIVEN_LOSS
    ):

        return (
            profile
            .expected_loss_given_loss_usd
        )

    if (
        metric
        is RiskMetric
        .PROBABILITY_IRR_ABOVE_HURDLE
    ):

        return (
            profile
            .probability_irr_above_hurdle
        )

    if (
        metric
        is RiskMetric.MEDIAN_LCOE
    ):

        return (
            profile
            .median_lcoe_usd_per_mwh
        )

    if (
        metric
        is RiskMetric
        .LCOE_UPSIDE_RISK_PERCENTILE
    ):

        return (
            profile
            .lcoe_risk_percentile_usd_per_mwh
        )

    if (
        metric
        is RiskMetric
        .PROBABILITY_LCOE_BELOW_BENCHMARK
    ):

        return (
            profile
            .probability_lcoe_below_benchmark
        )

    raise ValueError(
        f"Unsupported risk metric: {metric}"
    )


# ============================================================
# RISK RANKING DIRECTION
# ============================================================

def _risk_ranking_direction(
    metric: RiskMetric,
) -> RiskRankingDirection:
    """
    Define what better means for risk metrics.
    """

    higher_is_better = {

        RiskMetric
        .PROBABILITY_NPV_POSITIVE,

        RiskMetric.MEDIAN_NPV,

        RiskMetric
        .NPV_DOWNSIDE_PERCENTILE,

        RiskMetric
        .NPV_EXPECTED_SHORTFALL,

        RiskMetric
        .PROBABILITY_IRR_ABOVE_HURDLE,

        RiskMetric
        .PROBABILITY_LCOE_BELOW_BENCHMARK,
    }

    lower_is_better = {

        RiskMetric
        .PROBABILITY_OF_LOSS,

        RiskMetric
        .EXPECTED_LOSS_GIVEN_LOSS,

        RiskMetric.MEDIAN_LCOE,

        RiskMetric
        .LCOE_UPSIDE_RISK_PERCENTILE,
    }

    if metric in higher_is_better:

        return (
            RiskRankingDirection
            .HIGHER_IS_BETTER
        )

    if metric in lower_is_better:

        return (
            RiskRankingDirection
            .LOWER_IS_BETTER
        )

    raise ValueError(
        f"No ranking direction defined "
        f"for {metric.value}."
    )


# ============================================================
# RANK RISK PROFILES
# ============================================================

def rank_risk_profiles(
    profiles: Sequence[
        ProjectRiskProfile
    ],
    metric: RiskMetric,
) -> RiskRanking:
    """
    Rank projects under one probabilistic
    risk measure.
    """

    direction = (
        _risk_ranking_direction(
            metric
        )
    )

    valid = []
    missing = []

    for profile in profiles:

        value = (
            _risk_metric_value(
                profile,
                metric,
            )
        )

        if (
            value is None
            or not math.isfinite(
                value
            )
        ):

            missing.append(
                profile
            )

        else:

            valid.append(
                profile
            )

    reverse = (
        direction
        is RiskRankingDirection
        .HIGHER_IS_BETTER
    )

    valid.sort(
        key=lambda profile: (
            _risk_metric_value(
                profile,
                metric,
            )
        ),
        reverse=reverse,
    )

    ordered = (
        valid
        + missing
    )

    return RiskRanking(

        metric=metric,

        direction=direction,

        ordered_scenario_ids=tuple(
            profile.scenario_id
            for profile in ordered
        ),
    )


# ============================================================
# COMPARE PROJECT RISK
# ============================================================

def compare_project_risk(
    profiles: Sequence[
        ProjectRiskProfile
    ],
) -> RiskComparison:
    """
    Compare two or more renewable projects using
    probabilistic risk measures.

    No composite weighted risk score is created.
    """

    profiles = tuple(
        profiles
    )

    if len(profiles) < 2:

        raise ValueError(
            "At least two risk profiles "
            "are required."
        )

    scenario_ids = tuple(
        profile.scenario_id
        for profile in profiles
    )

    if (
        len(set(scenario_ids))
        != len(scenario_ids)
    ):

        raise ValueError(
            "Each project risk profile must "
            "have a unique scenario ID."
        )

    metrics = [

        RiskMetric
        .PROBABILITY_NPV_POSITIVE,

        RiskMetric
        .PROBABILITY_OF_LOSS,

        RiskMetric.MEDIAN_NPV,

        RiskMetric
        .NPV_DOWNSIDE_PERCENTILE,

        RiskMetric
        .NPV_EXPECTED_SHORTFALL,

        RiskMetric
        .EXPECTED_LOSS_GIVEN_LOSS,

        RiskMetric.MEDIAN_LCOE,

        RiskMetric
        .LCOE_UPSIDE_RISK_PERCENTILE,
    ]

    # --------------------------------------------------------
    # Include hurdle-rate ranking only when every project
    # has a comparable probability.
    # --------------------------------------------------------

    if all(
        profile
        .probability_irr_above_hurdle
        is not None

        for profile in profiles
    ):

        metrics.append(
            RiskMetric
            .PROBABILITY_IRR_ABOVE_HURDLE
        )

    # --------------------------------------------------------
    # Fixed-LCOE benchmark comparison
    # --------------------------------------------------------

    if all(
        profile
        .probability_lcoe_below_benchmark
        is not None

        for profile in profiles
    ):

        metrics.append(
            RiskMetric
            .PROBABILITY_LCOE_BELOW_BENCHMARK
        )

    rankings = tuple(

        rank_risk_profiles(
            profiles=profiles,
            metric=metric,
        )

        for metric in metrics
    )

    warnings: list[str] = []

    # --------------------------------------------------------
    # Different hurdle rates make IRR probabilities
    # incomparable.
    # --------------------------------------------------------

    hurdle_rates = {
        profile.irr_hurdle_rate
        for profile in profiles
        if profile.irr_hurdle_rate
        is not None
    }

    if len(hurdle_rates) > 1:

        warnings.append(
            "Projects use different IRR hurdle rates. "
            "Their hurdle probabilities should not "
            "be interpreted as like-for-like."
        )

    benchmarks = {
        profile.lcoe_benchmark_usd_per_mwh
        for profile in profiles
        if profile.lcoe_benchmark_usd_per_mwh
        is not None
    }

    if len(benchmarks) > 1:

        warnings.append(
            "Projects use different fixed LCOE "
            "benchmarks, so benchmark probabilities "
            "are not directly comparable."
        )

    warnings.append(
        "Separate Monte Carlo distributions should "
        "not automatically be interpreted as a "
        "paired probability that one technology "
        "outperforms another. Joint comparison "
        "requires compatible shared uncertainty "
        "assumptions."
    )

    return RiskComparison(

        profiles=profiles,

        rankings=rankings,

        warnings=tuple(
            warnings
        ),
    )