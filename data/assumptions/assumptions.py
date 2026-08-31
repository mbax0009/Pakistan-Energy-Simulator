# data/assumptions.py

from __future__ import annotations

import math

from dataclasses import dataclass
from enum import Enum

from core.models import (
    FinancialInputs,
    Technology,
)


# ============================================================
# EVIDENCE CLASSIFICATION
# ============================================================

class EvidenceLevel(str, Enum):
    """
    Describes how an assumption should be interpreted.

    GLOBAL_BENCHMARK
        Strong published international benchmark.

    TECHNICAL_REFERENCE
        Engineering/reference-technology assumption.

    PAKISTAN_EVIDENCE
        Derived from an authoritative Pakistan source.

    SCENARIO_ASSUMPTION
        Plausible research scenario, but not a measured
        universal value.

    USER_REQUIRED
        Must be supplied for the actual project/site.

    VALIDATION_ONLY
        Used to check whether model outputs are plausible,
        not fed directly into the simulation.
    """

    GLOBAL_BENCHMARK = "global_benchmark"

    TECHNICAL_REFERENCE = (
        "technical_reference"
    )

    PAKISTAN_EVIDENCE = (
        "pakistan_evidence"
    )

    SCENARIO_ASSUMPTION = (
        "scenario_assumption"
    )

    USER_REQUIRED = "user_required"

    VALIDATION_ONLY = "validation_only"


# ============================================================
# SOURCE
# ============================================================

@dataclass(frozen=True)
class AssumptionSource:
    """
    Bibliographic provenance for model assumptions.

    source_id:
        Short stable identifier used elsewhere
        in the code.

    geography:
        Important because US/global assumptions should
        not be silently labelled as Pakistan data.
    """

    source_id: str

    organization: str

    title: str

    publication_year: int

    geography: str

    source_url: str | None = None

    notes: str = ""

    def __post_init__(self):

        if not self.source_id.strip():
            raise ValueError(
                "Source ID cannot be empty."
            )

        if not self.organization.strip():
            raise ValueError(
                "Source organization cannot be empty."
            )

        if not self.title.strip():
            raise ValueError(
                "Source title cannot be empty."
            )

        if self.publication_year < 1900:
            raise ValueError(
                "Publication year appears invalid."
            )


# ============================================================
# NUMERIC ASSUMPTION
# ============================================================

@dataclass(frozen=True)
class NumericAssumption:
    """
    One quantitative model assumption with provenance.

    Example:

        key:
            "solar_capex_per_kw"

        value:
            691

        unit:
            "USD/kW"

        evidence_level:
            GLOBAL_BENCHMARK
    """

    key: str

    value: float

    unit: str

    source_id: str

    evidence_level: EvidenceLevel

    notes: str = ""

    def __post_init__(self):

        if not self.key.strip():
            raise ValueError(
                "Assumption key cannot be empty."
            )

        if not math.isfinite(
            self.value
        ):
            raise ValueError(
                "Assumption value must be finite."
            )

        if not self.unit.strip():
            raise ValueError(
                "Assumption unit cannot be empty."
            )

        if not self.source_id.strip():
            raise ValueError(
                "Assumption source ID cannot be empty."
            )


# ============================================================
# TECHNOLOGY REFERENCE CASE
# ============================================================

@dataclass(frozen=True)
class TechnologyReferenceCase:
    """
    Published reference assumptions for one technology.

    A None value is intentional.

    It means:
        we do not currently have a sufficiently defensible
        generic assumption and should NOT invent one.
    """

    technology: Technology

    capex_per_kw: NumericAssumption | None

    fixed_opex_per_kw_year: (
        NumericAssumption | None
    )

    lifetime_years: (
        NumericAssumption | None
    )

    annual_degradation_rate: (
        NumericAssumption | None
    )

    validation_capacity_factor: (
        NumericAssumption | None
    )

    technical_assumptions: tuple[
        NumericAssumption,
        ...
    ] = ()

    unresolved_inputs: tuple[
        str,
        ...
    ] = ()

    notes: tuple[str, ...] = ()

    def assumption(
        self,
        key: str,
    ) -> NumericAssumption:
        """
        Find one assumption by its key.
        """

        candidates = (

            self.capex_per_kw,

            self.fixed_opex_per_kw_year,

            self.lifetime_years,

            self.annual_degradation_rate,

            self.validation_capacity_factor,

            *self.technical_assumptions,
        )

        for assumption in candidates:

            if (
                assumption is not None
                and assumption.key == key
            ):

                return assumption

        raise KeyError(
            f"No assumption named {key!r} "
            f"exists for {self.technology.value}."
        )


# ============================================================
# SOURCES
# ============================================================

SOURCES: dict[
    str,
    AssumptionSource,
] = {

    # --------------------------------------------------------
    # IRENA
    # --------------------------------------------------------

    "IRENA_RPGC_2024": AssumptionSource(

        source_id="IRENA_RPGC_2024",

        organization=(
            "International Renewable Energy Agency"
        ),

        title=(
            "Renewable Power Generation "
            "Costs in 2024"
        ),

        publication_year=2025,

        geography="Global",

        source_url=(
            "https://www.irena.org/Publications/2025/Jun/"
            "Renewable-Power-Generation-Costs-in-2024"
        ),

        notes=(
            "Used primarily for global 2024 "
            "utility-scale renewable cost and "
            "performance benchmarking."
        ),
    ),

    "IRENA_RPGC_2025": AssumptionSource(

        source_id="IRENA_RPGC_2025",

        organization=(
            "International Renewable Energy Agency"
        ),

        title=(
            "Renewable Power Generation "
            "Costs in 2025"
        ),

        publication_year=2026,

        geography="Global",

        source_url=(
            "https://www.irena.org/Publications/2026/Jul/"
            "Renewable-Power-Generation-Costs-in-2025"
        ),

        notes=(
            "Latest published global utility-scale "
            "renewable cost benchmark available as of "
            "30 August 2026. Cost observations are for "
            "projects commissioned in 2025."
        ),
    ),

    # --------------------------------------------------------
    # NREL 2024 ATB - utility PV
    # --------------------------------------------------------

    "NREL_ATB_2024_PV": AssumptionSource(

        source_id="NREL_ATB_2024_PV",

        organization=(
            "National Renewable Energy Laboratory"
        ),

        title=(
            "2024 Annual Technology Baseline: "
            "Utility-Scale PV"
        ),

        publication_year=2024,

        geography="United States",

        notes=(
            "Used for technical reference assumptions. "
            "US-specific values must not be presented "
            "as Pakistan observations."
        ),
    ),

    # --------------------------------------------------------
    # NREL ATB technical lifetimes
    # --------------------------------------------------------

    "NREL_ATB_2024_LIFE": AssumptionSource(

        source_id="NREL_ATB_2024_LIFE",

        organization=(
            "National Renewable Energy Laboratory"
        ),

        title=(
            "2024 Annual Technology Baseline: "
            "Definitions and Technical Lifetimes"
        ),

        publication_year=2024,

        geography="United States",

        notes=(
            "Provides 30-year technical-life "
            "assumptions for utility PV and "
            "land-based wind."
        ),
    ),

    # --------------------------------------------------------
    # NREL land-based wind
    # --------------------------------------------------------

    "NREL_ATB_2024_WIND": AssumptionSource(

        source_id="NREL_ATB_2024_WIND",

        organization=(
            "National Renewable Energy Laboratory"
        ),

        title=(
            "2024 Annual Technology Baseline: "
            "Land-Based Wind"
        ),

        publication_year=2024,

        geography="United States",

        notes=(
            "Used for representative turbine and "
            "O&M benchmarking."
        ),
    ),

    # --------------------------------------------------------
    # DOE wave-energy status
    # --------------------------------------------------------

    "DOE_WAVE_2024": AssumptionSource(

        source_id="DOE_WAVE_2024",

        organization=(
            "U.S. Department of Energy"
        ),

        title=(
            "Oceans of Opportunity: "
            "U.S. Wave Energy Open Water Testing"
        ),

        publication_year=2024,

        geography="United States",

        notes=(
            "Used to document wave energy's current "
            "commercial-readiness uncertainty rather "
            "than to impose a single mature-market "
            "cost assumption."
        ),
    ),

    # --------------------------------------------------------
    # Historical WEC reference model
    # --------------------------------------------------------

    "NREL_RM5": AssumptionSource(

        source_id="NREL_RM5",

        organization=(
            "U.S. Department of Energy "
            "National Laboratories"
        ),

        title=(
            "Reference Model 5: "
            "Oscillating Surge Wave Energy Converter"
        ),

        publication_year=2015,

        geography="Reference-model study",

        notes=(
            "Historical reference technology only. "
            "Should not be treated as a current "
            "Pakistan wave-cost benchmark."
        ),
    ),

    # --------------------------------------------------------
    # Pakistan tariff evidence
    # --------------------------------------------------------

    "NEPRA_RE_TARIFF_2025": AssumptionSource(

        source_id="NEPRA_RE_TARIFF_2025",

        organization=(
            "National Electric Power "
            "Regulatory Authority"
        ),

        title=(
            "Tariff for Renewable Power Plants "
            "as at 30 June 2025"
        ),

        publication_year=2025,

        geography="Pakistan",

        notes=(
            "Contains plant-specific indexed tariffs. "
            "These should not be interpreted as one "
            "universal electricity sale price for a "
            "new project."
        ),
    ),
}


# ============================================================
# SOLAR REFERENCE CASE
# ============================================================

SOLAR_REFERENCE = TechnologyReferenceCase(

    technology=Technology.SOLAR,

    # --------------------------------------------------------
    # 2025 global installed cost
    # --------------------------------------------------------

    capex_per_kw=NumericAssumption(

        key="solar_capex_per_kw",

        value=667.0,

        unit="2025 USD/kW",

        source_id="IRENA_RPGC_2025",

        evidence_level=(
            EvidenceLevel.GLOBAL_BENCHMARK
        ),

        notes=(
            "Global weighted-average total installed "
            "cost for utility-scale PV projects "
            "commissioned in 2025."
        ),
    ),

    # --------------------------------------------------------
    # Do not hide uncertainty in O&M.
    #
    # We use the NREL reference value only as an
    # engineering benchmark.
    # --------------------------------------------------------

    fixed_opex_per_kw_year=(
        NumericAssumption(

            key=(
                "solar_fixed_opex_per_kw_year"
            ),

            value=22.0,

            unit="USD/kW_AC/year",

            source_id="NREL_ATB_2024_PV",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),

            notes=(
                "NREL reference O&M magnitude. "
                "Use as a range/check rather than "
                "claiming this is a measured "
                "Pakistan O&M cost."
            ),
        )
    ),

    lifetime_years=(
        NumericAssumption(

            key="solar_lifetime_years",

            value=30.0,

            unit="years",

            source_id="NREL_ATB_2024_LIFE",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),
        )
    ),

    annual_degradation_rate=(
        NumericAssumption(

            key=(
                "solar_annual_degradation_rate"
            ),

            value=0.007,

            unit="fraction/year",

            source_id="NREL_ATB_2024_PV",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),

            notes=(
                "0.7%/year baseline PV "
                "degradation assumption."
            ),
        )
    ),

    validation_capacity_factor=(
        NumericAssumption(

            key=(
                "solar_global_capacity_factor_2024"
            ),

            value=0.174,

            unit="fraction",

            source_id="IRENA_RPGC_2024",

            evidence_level=(
                EvidenceLevel.VALIDATION_ONLY
            ),

            notes=(
                "Global weighted-average capacity "
                "factor for newly commissioned "
                "utility-scale PV. Do not force the "
                "Pakistan physics model to equal it."
            ),
        )
    ),

    technical_assumptions=(

        NumericAssumption(

            key="solar_system_losses",

            value=0.141,

            unit="fraction",

            source_id="NREL_ATB_2024_PV",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),

            notes=(
                "NREL baseline DC-loss assumption."
            ),
        ),

    ),

    unresolved_inputs=(

        "site-specific tilt",

        "site-specific azimuth",

        "Pakistan/site-specific O&M evidence",

        "project electricity sale price",

        "project discount rate",

    ),

    notes=(

        "CAPEX benchmark is global, not "
        "Pakistan-specific.",

        "Capacity factor must come from the "
        "Pakistan solar resource simulation.",
    ),
)


# ============================================================
# WIND REFERENCE CASE
# ============================================================

WIND_REFERENCE = TechnologyReferenceCase(

    technology=Technology.WIND,

    capex_per_kw=NumericAssumption(

        key="wind_capex_per_kw",

        value=976.0,

        unit="2025 USD/kW",

        source_id="IRENA_RPGC_2025",

        evidence_level=(
            EvidenceLevel.GLOBAL_BENCHMARK
        ),

        notes=(
            "Global weighted-average total installed "
            "cost for onshore wind commissioned "
            "in 2025."
        ),
    ),

    fixed_opex_per_kw_year=(
        NumericAssumption(

            key=(
                "wind_fixed_opex_per_kw_year"
            ),

            value=44.0,

            unit="USD/kW/year",

            source_id="NREL_ATB_2024_WIND",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),

            notes=(
                "2022 US market-average wind "
                "OPEX reference reported by ATB."
            ),
        )
    ),

    lifetime_years=(
        NumericAssumption(

            key="wind_lifetime_years",

            value=30.0,

            unit="years",

            source_id="NREL_ATB_2024_LIFE",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),
        )
    ),

    # We deliberately do not invent a generic
    # wind degradation rate.
    annual_degradation_rate=None,

    validation_capacity_factor=(
        NumericAssumption(

            key=(
                "wind_global_capacity_factor_2024"
            ),

            value=0.34,

            unit="fraction",

            source_id="IRENA_RPGC_2024",

            evidence_level=(
                EvidenceLevel.VALIDATION_ONLY
            ),

            notes=(
                "Global 2024 weighted-average "
                "capacity factor for newly "
                "commissioned onshore wind."
            ),
        )
    ),

    technical_assumptions=(

        NumericAssumption(

            key=(
                "wind_reference_turbine_power_mw"
            ),

            value=3.2,

            unit="MW",

            source_id="NREL_ATB_2024_WIND",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),

            notes=(
                "2022 market-average reference "
                "turbine rating."
            ),
        ),

        NumericAssumption(

            key=(
                "wind_reference_hub_height_m"
            ),

            value=98.0,

            unit="m",

            source_id="NREL_ATB_2024_WIND",

            evidence_level=(
                EvidenceLevel
                .TECHNICAL_REFERENCE
            ),

            notes=(
                "2022 market-average reference "
                "hub height."
            ),
        ),
    ),

    unresolved_inputs=(

        "specific turbine model",

        "cut-in wind speed",

        "rated wind speed",

        "cut-out wind speed",

        "site-specific availability",

        "Pakistan/site-specific O&M evidence",

        "annual performance degradation assumption",

        "project electricity sale price",

        "project discount rate",
    ),

    notes=(

        "Do not use global capacity factor as "
        "the Pakistan wind project's CF.",

        "Power-curve parameters should preferably "
        "come from the selected turbine model.",
    ),
)


# ============================================================
# WAVE REFERENCE CASE
# ============================================================

WAVE_REFERENCE = TechnologyReferenceCase(

    technology=Technology.WAVE,

    # --------------------------------------------------------
    # Deliberately unresolved.
    #
    # Wave technology is not mature enough for us to
    # pretend that one global CAPEX value represents
    # commercial utility-scale WEC projects.
    # --------------------------------------------------------

    capex_per_kw=None,

    fixed_opex_per_kw_year=None,

    lifetime_years=None,

    annual_degradation_rate=None,

    validation_capacity_factor=None,

    technical_assumptions=(),

    unresolved_inputs=(

        "wave device architecture",

        "device rated power",

        "capture width or device power matrix",

        "conversion efficiency",

        "availability",

        "CAPEX",

        "OPEX",

        "design lifetime",

        "performance degradation",

        "electricity sale price",

        "discount rate",
    ),

    notes=(

        "Wave energy remains pre-commercial or "
        "early-commercial across many applications.",

        "Cost and performance should be modelled "
        "as explicit research scenarios rather "
        "than presented as a mature-market fact.",

        "Historical DOE/NREL reference models may "
        "be used for comparison, not as unquestioned "
        "2026 Pakistan baselines.",
    ),
)


# ============================================================
# TECHNOLOGY CATALOG
# ============================================================

REFERENCE_CASES: dict[
    Technology,
    TechnologyReferenceCase,
] = {

    Technology.SOLAR:
        SOLAR_REFERENCE,

    Technology.WIND:
        WIND_REFERENCE,

    Technology.WAVE:
        WAVE_REFERENCE,
}


# ============================================================
# RETRIEVE REFERENCE CASE
# ============================================================

def get_reference_case(
    technology: Technology,
) -> TechnologyReferenceCase:
    """
    Retrieve published assumptions for one technology.
    """

    try:

        return REFERENCE_CASES[
            technology
        ]

    except KeyError as exc:

        raise ValueError(
            f"No reference assumptions exist for "
            f"{technology.value}."
        ) from exc


# ============================================================
# SOURCE LOOKUP
# ============================================================

def get_source(
    source_id: str,
) -> AssumptionSource:
    """
    Retrieve bibliographic information for one
    assumption source.
    """

    try:

        return SOURCES[
            source_id
        ]

    except KeyError as exc:

        raise KeyError(
            f"Unknown assumption source "
            f"{source_id!r}."
        ) from exc


# ============================================================
# VALIDATE CATALOG
# ============================================================

def validate_assumption_catalog() -> None:
    """
    Verify that every numeric assumption points to
    a real registered source.

    Run this in development/tests or application startup.
    """

    for case in (
        REFERENCE_CASES.values()
    ):

        assumptions = (

            case.capex_per_kw,

            case.fixed_opex_per_kw_year,

            case.lifetime_years,

            case.annual_degradation_rate,

            case.validation_capacity_factor,

            *case.technical_assumptions,
        )

        for assumption in assumptions:

            if assumption is None:
                continue

            if (
                assumption.source_id
                not in SOURCES
            ):

                raise ValueError(
                    f"Assumption "
                    f"{assumption.key!r} "
                    "references unknown source "
                    f"{assumption.source_id!r}."
                )


# ============================================================
# GLOBAL-BENCHMARK FINANCE BUILDER
# ============================================================

def build_global_benchmark_finance(
    technology: Technology,

    electricity_price_per_mwh: float,

    discount_rate: float,

    variable_opex_per_mwh: float = 0.0,

    electricity_price_growth_rate: (
        float
    ) = 0.0,

    opex_growth_rate: float = 0.0,
) -> FinancialInputs:
    """
    Build FinancialInputs using published global/reference
    CAPEX and FOM values.

    IMPORTANT
    ---------
    This is a GLOBAL BENCHMARK case.

    It must not be labelled:

        "Pakistan project cost"

    unless Pakistan-specific evidence later replaces
    these assumptions.

    Wave intentionally cannot use this helper because
    we have not defined a mature generic wave-cost
    benchmark.
    """

    reference = (
        get_reference_case(
            technology
        )
    )

    if reference.capex_per_kw is None:

        raise ValueError(
            f"{technology.value} has no defensible "
            "generic CAPEX benchmark. Supply an "
            "explicit scenario assumption instead."
        )

    if (
        reference.fixed_opex_per_kw_year
        is None
    ):

        raise ValueError(
            f"{technology.value} has no defensible "
            "generic fixed-OPEX benchmark."
        )

    return FinancialInputs(

        capex_per_kw=(
            reference
            .capex_per_kw
            .value
        ),

        fixed_opex_per_kw_year=(
            reference
            .fixed_opex_per_kw_year
            .value
        ),

        variable_opex_per_mwh=(
            variable_opex_per_mwh
        ),

        electricity_price_per_mwh=(
            electricity_price_per_mwh
        ),

        discount_rate=(
            discount_rate
        ),

        electricity_price_growth_rate=(
            electricity_price_growth_rate
        ),

        opex_growth_rate=(
            opex_growth_rate
        ),
    )
