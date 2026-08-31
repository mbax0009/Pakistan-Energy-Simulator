from __future__ import annotations

import math

from dataclasses import dataclass
from datetime import datetime

from core.models import Location


# ============================================================
# VALIDATION
# ============================================================

def _validate_timestamp(
    timestamp: datetime,
) -> datetime:

    if not isinstance(timestamp, datetime):
        raise TypeError(
            "Timestamp must be a datetime object."
        )

    if timestamp.tzinfo is None:
        raise ValueError(
            "Timestamp must be timezone-aware."
        )

    return timestamp


def _validate_chronological_order(
    timestamps: tuple[datetime, ...],
) -> None:

    for previous, current in zip(
        timestamps,
        timestamps[1:],
    ):

        if current <= previous:
            raise ValueError(
                "Resource timestamps must be "
                "strictly increasing."
            )


def infer_time_step_hours(
    timestamps: tuple[datetime, ...],
) -> float | None:

    if len(timestamps) < 2:
        return None

    intervals = []

    for previous, current in zip(
        timestamps,
        timestamps[1:],
    ):

        difference = current - previous

        hours = (
            difference.total_seconds()
            / 3600
        )

        intervals.append(hours)


    first_interval = intervals[0]


    for interval in intervals[1:]:

        if not math.isclose(
            interval,
            first_interval,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "Resource series contains "
                "irregular time intervals."
            )


    return first_interval


# ============================================================
# METADATA
# ============================================================

@dataclass(frozen=True)
class ResourceMetadata:
    """
    Traceability information describing the origin
    of a resource dataset.

    The requested project location is stored separately
    in the ResourceSeries.

    resolved_latitude / resolved_longitude describe the
    actual provider grid-cell used, when available.
    """

    source_name: str
    dataset_name: str

    retrieved_at: datetime

    source_reference: str | None = None

    resolved_latitude: float | None = None
    resolved_longitude: float | None = None

    elevation_m: float | None = None

    provider_timezone: str | None = None

    def __post_init__(self):

        if not self.source_name.strip():
            raise ValueError(
                "Resource source name cannot be empty."
            )

        if not self.dataset_name.strip():
            raise ValueError(
                "Dataset name cannot be empty."
            )

        _validate_timestamp(
            self.retrieved_at
        )

        # Either both resolved coordinates exist,
        # or neither exists.
        if (
            self.resolved_latitude is None
        ) != (
            self.resolved_longitude is None
        ):
            raise ValueError(
                "Resolved latitude and longitude "
                "must either both be provided or "
                "both be omitted."
            )

        if self.resolved_latitude is not None:

            if not (
                -90
                <= self.resolved_latitude
                <= 90
            ):
                raise ValueError(
                    "Resolved latitude must be "
                    "between -90 and 90."
                )

        if self.resolved_longitude is not None:

            if not (
                -180
                <= self.resolved_longitude
                <= 180
            ):
                raise ValueError(
                    "Resolved longitude must be "
                    "between -180 and 180."
                )

        if self.elevation_m is not None:

            if not math.isfinite(
                self.elevation_m
            ):
                raise ValueError(
                    "Elevation must be finite."
                )


# ============================================================
# SOLAR
# ============================================================

@dataclass(frozen=True)
class SolarResourcePoint:
    """
    Solar-resource conditions at one point in time.

    Units:
    - GHI: W/m²
    - DNI: W/m²
    - DHI: W/m²
    - POA irradiance: W/m²
    - temperatures: °C
    - wind speed: m/s
    """

    timestamp: datetime

    ghi_wm2: float

    dni_wm2: float | None = None
    dhi_wm2: float | None = None

    poa_irradiance_wm2: float | None = None

    ambient_temperature_c: float | None = None
    cell_temperature_c: float | None = None

    wind_speed_ms: float | None = None

    def __post_init__(self):

        _validate_timestamp(self.timestamp)

        irradiance_values = (
            ("GHI", self.ghi_wm2),
            ("DNI", self.dni_wm2),
            ("DHI", self.dhi_wm2),
            ("POA irradiance", self.poa_irradiance_wm2),
        )

        for name, value in irradiance_values:

            if value is None:
                continue

            if not math.isfinite(value):
                raise ValueError(
                    f"{name} must be finite."
                )

            if value < 0:
                raise ValueError(
                    f"{name} cannot be negative."
                )

        temperature_values = (
            (
                "Ambient temperature",
                self.ambient_temperature_c,
            ),
            (
                "Cell temperature",
                self.cell_temperature_c,
            ),
        )

        for name, value in temperature_values:

            if value is not None:

                if not math.isfinite(value):
                    raise ValueError(
                        f"{name} must be finite."
                    )

        if self.wind_speed_ms is not None:

            if not math.isfinite(
                self.wind_speed_ms
            ):
                raise ValueError(
                    "Wind speed must be finite."
                )

            if self.wind_speed_ms < 0:
                raise ValueError(
                    "Wind speed cannot be negative."
                )

@dataclass(frozen=True)
class SolarResourceSeries:

    location: Location

    metadata: ResourceMetadata

    points: tuple[
        SolarResourcePoint,
        ...
    ]

    def __post_init__(self):

        if not self.points:
            raise ValueError(
                "Solar resource series cannot be empty."
            )

        _validate_chronological_order(
            tuple(
                point.timestamp
                for point in self.points
            )
        )

    @property
    def start_time(self) -> datetime:
        return self.points[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.points[-1].timestamp

    @property
    def sample_count(self) -> int:
        return len(self.points)

    @property
    def time_step_hours(self) -> float | None:

        return infer_time_step_hours(
            tuple(
                point.timestamp
                for point in self.points
            )
        )


# ============================================================
# WIND
# ============================================================

@dataclass(frozen=True)
class WindResourcePoint:
    """
    Wind-resource conditions at one point in time.

    Units:
    - wind speed: m/s
    - wind direction: degrees clockwise from North
    - temperature: °C
    - surface pressure: hPa
    - air density: kg/m³
    """

    timestamp: datetime

    wind_speed_ms: float

    wind_direction_deg: float | None = None

    temperature_c: float | None = None

    surface_pressure_hpa: float | None = None

    air_density_kg_m3: float | None = None

    def __post_init__(self):

        _validate_timestamp(
            self.timestamp
        )

        # ----------------------------------------------------
        # Wind speed
        # ----------------------------------------------------

        if not math.isfinite(
            self.wind_speed_ms
        ):
            raise ValueError(
                "Wind speed must be finite."
            )

        if self.wind_speed_ms < 0:
            raise ValueError(
                "Wind speed cannot be negative."
            )

        # ----------------------------------------------------
        # Wind direction
        # ----------------------------------------------------

        if self.wind_direction_deg is not None:

            if not math.isfinite(
                self.wind_direction_deg
            ):
                raise ValueError(
                    "Wind direction must be finite."
                )

            if not (
                0
                <= self.wind_direction_deg
                < 360
            ):
                raise ValueError(
                    "Wind direction must be between "
                    "0 and 360 degrees."
                )

        # ----------------------------------------------------
        # Temperature
        # ----------------------------------------------------

        if self.temperature_c is not None:

            if not math.isfinite(
                self.temperature_c
            ):
                raise ValueError(
                    "Temperature must be finite."
                )

        # ----------------------------------------------------
        # Surface pressure
        # ----------------------------------------------------

        if self.surface_pressure_hpa is not None:

            if (
                not math.isfinite(
                    self.surface_pressure_hpa
                )
                or self.surface_pressure_hpa <= 0
            ):
                raise ValueError(
                    "Surface pressure must be finite "
                    "and greater than zero."
                )

        # ----------------------------------------------------
        # Air density
        # ----------------------------------------------------

        if self.air_density_kg_m3 is not None:

            if (
                not math.isfinite(
                    self.air_density_kg_m3
                )
                or self.air_density_kg_m3 <= 0
            ):
                raise ValueError(
                    "Air density must be finite "
                    "and greater than zero."
                )


@dataclass(frozen=True)
class WindResourceSeries:

    location: Location

    metadata: ResourceMetadata

    measurement_height_m: float

    points: tuple[
        WindResourcePoint,
        ...
    ]

    def __post_init__(self):

        if self.measurement_height_m <= 0:
            raise ValueError(
                "Wind measurement height must "
                "be greater than zero."
            )

        if not self.points:
            raise ValueError(
                "Wind resource series cannot be empty."
            )

        _validate_chronological_order(
            tuple(
                point.timestamp
                for point in self.points
            )
        )

    @property
    def start_time(self) -> datetime:
        return self.points[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.points[-1].timestamp

    @property
    def sample_count(self) -> int:
        return len(self.points)

    @property
    def time_step_hours(self) -> float | None:

        return infer_time_step_hours(
            tuple(
                point.timestamp
                for point in self.points
            )
        )


# ============================================================
# WAVE
# ============================================================

@dataclass(frozen=True)
class WaveResourcePoint:

    timestamp: datetime

    significant_wave_height_m: float
    energy_period_s: float

    wave_direction_deg: float | None = None

    def __post_init__(self):

        _validate_timestamp(
            self.timestamp
        )

        if (
            not math.isfinite(
                self.significant_wave_height_m
            )
            or self.significant_wave_height_m < 0
        ):
            raise ValueError(
                "Wave height must be finite "
                "and non-negative."
            )

        if (
            not math.isfinite(
                self.energy_period_s
            )
            or self.energy_period_s <= 0
        ):
            raise ValueError(
                "Wave period must be finite "
                "and greater than zero."
            )

        if self.wave_direction_deg is not None:

            if (
                not math.isfinite(
                    self.wave_direction_deg
                )
                or not (
                    0
                    <= self.wave_direction_deg
                    < 360
                )
            ):
                raise ValueError(
                    "Wave direction must be between "
                    "0 and 360 degrees."
                )


@dataclass(frozen=True)
class WaveResourceSeries:
    """
    Complete time series of wave-resource observations.

    water_depth_m:
        Sea-floor depth at the selected marine grid cell,
        when available.

        This will later allow wave.py to test whether the
        deep-water approximation is physically appropriate.
    """

    location: Location

    metadata: ResourceMetadata

    points: tuple[
        WaveResourcePoint,
        ...
    ]

    water_depth_m: float | None = None

    def __post_init__(self):

        if not self.points:
            raise ValueError(
                "Wave resource series cannot be empty."
            )

        if self.water_depth_m is not None:

            if (
                not math.isfinite(
                    self.water_depth_m
                )
                or self.water_depth_m <= 0
            ):
                raise ValueError(
                    "Water depth must be finite "
                    "and greater than zero."
                )

        timestamps = tuple(
            point.timestamp
            for point in self.points
        )

        _validate_chronological_order(
            timestamps
        )

    @property
    def start_time(self) -> datetime:
        return self.points[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.points[-1].timestamp

    @property
    def sample_count(self) -> int:
        return len(self.points)

    @property
    def time_step_hours(self) -> float | None:

        return infer_time_step_hours(
            tuple(
                point.timestamp
                for point in self.points
            )
        )
