# data/wind_loader.py

from __future__ import annotations

import math
import time

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    timezone,
)
from enum import Enum
from typing import Protocol
from urllib.parse import urlunparse

import requests

from data.cache import JsonResourceCache

from core.models import (
    Location,
)

from core.resources import (
    ResourceMetadata,
    WindResourcePoint,
    WindResourceSeries,
)


# ============================================================
# WIND DATA MODE
# ============================================================

class WindDataMode(str, Enum):
    """
    Type of wind-resource data requested.

    HISTORICAL:
        Long-term reanalysis data used for
        techno-economic assessment.

    FORECAST:
        Current/future weather-model data.
    """

    HISTORICAL = "historical"
    FORECAST = "forecast"


# ============================================================
# WIND DATA REQUEST
# ============================================================

@dataclass(frozen=True)
class WindDataRequest:
    """
    Provider-independent request for wind-resource data.

    location:
        Exact proposed project coordinate.

    start_date / end_date:
        Requested weather period.

    measurement_height_m:
        Height of the requested wind-speed data.

        Historical Open-Meteo data currently support
        10 m and 100 m directly. We use 100 m for
        utility-scale wind assessment.
    """

    location: Location

    start_date: date
    end_date: date

    measurement_height_m: float = 100.0

    mode: WindDataMode = (
        WindDataMode.HISTORICAL
    )

    def __post_init__(self):

        if self.start_date > self.end_date:
            raise ValueError(
                "start_date cannot be after end_date."
            )

        if self.measurement_height_m <= 0:
            raise ValueError(
                "Measurement height must be "
                "greater than zero."
            )


# ============================================================
# PROVIDER INTERFACE
# ============================================================

class WindResourceProvider(Protocol):
    """
    Common interface for wind-resource providers.

    Future examples could include:

        OpenMeteoWindProvider
        GlobalWindAtlasProvider
        ERA5DirectProvider
    """

    def fetch(
        self,
        request: WindDataRequest,
    ) -> WindResourceSeries:
        ...


# ============================================================
# PROVIDER ERROR
# ============================================================

class WindDataProviderError(RuntimeError):
    """
    Raised when an external wind-data provider fails.
    """

    pass


# ============================================================
# OPEN-METEO PROVIDER
# ============================================================

class OpenMeteoWindProvider:
    """
    Coordinate-based Open-Meteo wind-resource provider.

    Historical assessment uses 100 m wind data
    from a consistent reanalysis model.

    Returned observations are converted into
    WindResourceSeries.
    """

    HISTORICAL_MEASUREMENT_HEIGHT_M = 100.0

    HOURLY_VARIABLES_100M = (
        "wind_speed_100m",
        "wind_direction_100m",
        "temperature_2m",
        "surface_pressure",
    )

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        historical_model: str = "era5",
        session: requests.Session | None = None,
        cache: JsonResourceCache | None = None,
        cache_enabled: bool = True,
    ):

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater "
                "than zero."
            )

        if max_retries < 1:
            raise ValueError(
                "max_retries must be at least 1."
            )

        if not historical_model.strip():
            raise ValueError(
                "historical_model cannot be empty."
            )

        self.timeout_seconds = (
            timeout_seconds
        )

        self.max_retries = (
            max_retries
        )

        self.historical_model = (
            historical_model
        )

        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        self.cache = (
            cache
            if cache is not None
            else JsonResourceCache()
        )

        self.cache_enabled = bool(cache_enabled)


    # ========================================================
    # PUBLIC ENTRY POINT
    # ========================================================

    def fetch(
        self,
        request: WindDataRequest,
    ) -> WindResourceSeries:
        """
        Fetch wind-resource data for an arbitrary
        latitude and longitude.
        """

        self._validate_request_for_provider(
            request
        )

        endpoint = self._build_endpoint(
            request.mode
        )

        params = self._build_parameters(
            request
        )

        cache_material = {
            "endpoint": endpoint,
            "params": params,
        }
        cached = None
        if self.cache_enabled:
            cached = self.cache.get(
                "open-meteo-wind",
                cache_material,
                max_age_seconds=(
                    30 * 24 * 60 * 60
                    if request.mode is WindDataMode.HISTORICAL
                    else 60 * 60
                ),
            )

        if cached is not None:
            payload = cached.payload
        else:
            payload = self._request_json(
                endpoint=endpoint,
                params=params,
            )
            if self.cache_enabled:
                self.cache.put(
                    "open-meteo-wind",
                    cache_material,
                    payload,
                )

        return self._parse_response(
            request=request,
            payload=payload,
        )


    # ========================================================
    # PROVIDER-SPECIFIC VALIDATION
    # ========================================================

    def _validate_request_for_provider(
        self,
        request: WindDataRequest,
    ) -> None:
        """
        Validate whether this provider can directly
        satisfy the requested measurement height.

        For historical assessment we deliberately
        request 100 m data and let physics/wind.py
        extrapolate to the actual turbine hub height.
        """

        if (
            request.mode
            is WindDataMode.HISTORICAL
        ):

            if not math.isclose(
                request.measurement_height_m,
                self.HISTORICAL_MEASUREMENT_HEIGHT_M,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):

                raise ValueError(
                    "Historical Open-Meteo wind loading "
                    "currently uses 100 m wind data. "
                    "Request measurement_height_m=100. "
                    "Hub-height adjustment belongs in "
                    "physics/wind.py."
                )


    # ========================================================
    # ENDPOINT
    # ========================================================

    @staticmethod
    def _build_endpoint(
        mode: WindDataMode,
    ) -> str:

        if mode is WindDataMode.HISTORICAL:

            return urlunparse(
                (
                    "https",
                    "archive-api.open-meteo.com",
                    "/v1/archive",
                    "",
                    "",
                    "",
                )
            )

        if mode is WindDataMode.FORECAST:

            return urlunparse(
                (
                    "https",
                    "api.open-meteo.com",
                    "/v1/forecast",
                    "",
                    "",
                    "",
                )
            )

        raise ValueError(
            f"Unsupported wind-data mode: {mode}"
        )


    # ========================================================
    # REQUEST PARAMETERS
    # ========================================================

    def _build_parameters(
        self,
        request: WindDataRequest,
    ) -> dict[str, object]:
        """
        Convert our provider-independent request
        into Open-Meteo parameters.
        """

        params: dict[str, object] = {

            "latitude": (
                request.location.latitude
            ),

            "longitude": (
                request.location.longitude
            ),

            "start_date": (
                request.start_date.isoformat()
            ),

            "end_date": (
                request.end_date.isoformat()
            ),

            "hourly": ",".join(
                self.HOURLY_VARIABLES_100M
            ),

            # Internal resource timestamps remain UTC.
            "timezone": "GMT",

            # wind.py expects m/s.
            "wind_speed_unit": "ms",

            "temperature_unit": "celsius",
        }

        if (
            request.mode
            is WindDataMode.HISTORICAL
        ):

            params["models"] = (
                self.historical_model
            )

        return params


    # ========================================================
    # HTTP REQUEST
    # ========================================================

    def _request_json(
        self,
        endpoint: str,
        params: dict[str, object],
    ) -> dict:
        """
        Request provider JSON with retry handling.
        """

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.max_retries + 1,
        ):

            try:

                response = self.session.get(
                    endpoint,
                    params=params,
                    timeout=self.timeout_seconds,
                )

                # --------------------------------------------
                # Permanent client-side request problem
                # --------------------------------------------

                if (
                    400
                    <= response.status_code
                    < 500
                ):

                    try:
                        details = response.json()

                    except ValueError:
                        details = response.text

                    raise WindDataProviderError(
                        "Wind-data provider rejected "
                        f"the request: {details}"
                    )

                # --------------------------------------------
                # Server/network response
                # --------------------------------------------

                response.raise_for_status()

                try:
                    payload = response.json()

                except ValueError as exc:

                    raise WindDataProviderError(
                        "Wind-data provider returned "
                        "invalid JSON."
                    ) from exc

                if payload.get("error"):

                    raise WindDataProviderError(
                        "Wind-data provider returned "
                        f"an error: "
                        f"{payload.get('reason')}"
                    )

                return payload


            except WindDataProviderError:
                raise


            except requests.RequestException as exc:

                last_error = exc

                if attempt == self.max_retries:
                    break

                delay_seconds = (
                    2 ** (attempt - 1)
                )

                time.sleep(
                    delay_seconds
                )


        raise WindDataProviderError(
            "Unable to retrieve wind-resource "
            "data after repeated attempts."
        ) from last_error


    # ========================================================
    # RESPONSE PARSING
    # ========================================================

    def _parse_response(
        self,
        request: WindDataRequest,
        payload: dict,
    ) -> WindResourceSeries:
        """
        Convert Open-Meteo response into our
        internal WindResourceSeries.
        """

        hourly = payload.get(
            "hourly"
        )

        if not isinstance(
            hourly,
            dict,
        ):

            raise WindDataProviderError(
                "Provider response does not contain "
                "hourly wind-resource data."
            )

        # ----------------------------------------------------
        # Retrieve arrays
        # ----------------------------------------------------

        timestamps = self._require_list(
            hourly,
            "time",
        )

        wind_speed_values = (
            self._require_list(
                hourly,
                "wind_speed_100m",
            )
        )

        wind_direction_values = (
            self._require_list(
                hourly,
                "wind_direction_100m",
            )
        )

        temperature_values = (
            self._require_list(
                hourly,
                "temperature_2m",
            )
        )

        pressure_values = (
            self._require_list(
                hourly,
                "surface_pressure",
            )
        )

        expected_length = len(
            timestamps
        )

        data_arrays = {
            "wind speed": (
                wind_speed_values
            ),
            "wind direction": (
                wind_direction_values
            ),
            "temperature": (
                temperature_values
            ),
            "surface pressure": (
                pressure_values
            ),
        }

        for name, values in (
            data_arrays.items()
        ):

            if len(values) != expected_length:

                raise WindDataProviderError(
                    f"{name} data length does "
                    "not match timestamp length."
                )

        if expected_length < 2:

            raise WindDataProviderError(
                "At least two wind-resource "
                "observations are required."
            )

        # ----------------------------------------------------
        # Build standardized observations
        # ----------------------------------------------------

        points: list[
            WindResourcePoint
        ] = []

        for index in range(
            expected_length
        ):

            timestamp = (
                self._parse_utc_timestamp(
                    timestamps[index]
                )
            )

            wind_speed = (
                self._required_number(
                    wind_speed_values[index],
                    "Wind speed",
                    index,
                )
            )

            wind_direction = (
                self._optional_number(
                    wind_direction_values[index],
                    "Wind direction",
                    index,
                )
            )

            # Open-Meteo may encode North as 360 degrees.
            # The simulator's frozen internal convention is
            # the equivalent half-open interval [0, 360).
            if wind_direction is not None:
                wind_direction %= 360.0

            temperature = (
                self._optional_number(
                    temperature_values[index],
                    "Temperature",
                    index,
                )
            )

            surface_pressure = (
                self._optional_number(
                    pressure_values[index],
                    "Surface pressure",
                    index,
                )
            )

            points.append(
                WindResourcePoint(
                    timestamp=timestamp,

                    wind_speed_ms=(
                        wind_speed
                    ),

                    wind_direction_deg=(
                        wind_direction
                    ),

                    temperature_c=(
                        temperature
                    ),

                    surface_pressure_hpa=(
                        surface_pressure
                    ),

                    # Do not manufacture a hub-height
                    # air-density value from surface
                    # observations at this stage.
                    air_density_kg_m3=None,
                )
            )

        # ----------------------------------------------------
        # Provider-grid metadata
        # ----------------------------------------------------

        resolved_latitude = (
            self._optional_payload_number(
                payload.get("latitude")
            )
        )

        resolved_longitude = (
            self._optional_payload_number(
                payload.get("longitude")
            )
        )

        elevation_m = (
            self._optional_payload_number(
                payload.get("elevation")
            )
        )

        if (
            request.mode
            is WindDataMode.HISTORICAL
        ):

            dataset_name = (
                "Open-Meteo "
                f"{self.historical_model.upper()} "
                "Historical Wind Reanalysis"
            )

        else:

            dataset_name = (
                "Open-Meteo Wind Forecast"
            )

        metadata = ResourceMetadata(

            source_name="Open-Meteo",

            dataset_name=dataset_name,

            retrieved_at=datetime.now(
                timezone.utc
            ),

            source_reference=(
                f"open-meteo:"
                f"{request.mode.value}:wind"
            ),

            resolved_latitude=(
                resolved_latitude
            ),

            resolved_longitude=(
                resolved_longitude
            ),

            elevation_m=(
                elevation_m
            ),

            provider_timezone=(
                payload.get("timezone")
            ),
        )

        # ----------------------------------------------------
        # The ResourceSeries location remains the exact
        # project coordinate requested by the user.
        #
        # The actual weather grid coordinate remains
        # in metadata.
        # ----------------------------------------------------

        return WindResourceSeries(

            location=request.location,

            metadata=metadata,

            measurement_height_m=(
                request.measurement_height_m
            ),

            points=tuple(
                points
            ),
        )


    # ========================================================
    # PARSING HELPERS
    # ========================================================

    @staticmethod
    def _require_list(
        container: dict,
        key: str,
    ) -> list:

        value = container.get(
            key
        )

        if not isinstance(
            value,
            list,
        ):

            raise WindDataProviderError(
                f"Provider response is missing "
                f"required array: {key}"
            )

        return value


    @staticmethod
    def _parse_utc_timestamp(
        value: object,
    ) -> datetime:

        if not isinstance(
            value,
            str,
        ):

            raise WindDataProviderError(
                "Wind-resource timestamp "
                "is invalid."
            )

        try:

            timestamp = (
                datetime.fromisoformat(
                    value
                )
            )

        except ValueError as exc:

            raise WindDataProviderError(
                f"Invalid timestamp: {value}"
            ) from exc

        if timestamp.tzinfo is None:

            timestamp = (
                timestamp.replace(
                    tzinfo=timezone.utc
                )
            )

        else:

            timestamp = (
                timestamp.astimezone(
                    timezone.utc
                )
            )

        return timestamp


    @staticmethod
    def _required_number(
        value: object,
        name: str,
        index: int,
    ) -> float:

        if value is None:

            raise WindDataProviderError(
                f"{name} is missing at "
                f"observation {index}."
            )

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise WindDataProviderError(
                f"{name} is invalid at "
                f"observation {index}."
            ) from exc

        if not math.isfinite(
            number
        ):

            raise WindDataProviderError(
                f"{name} is not finite at "
                f"observation {index}."
            )

        return number


    @staticmethod
    def _optional_number(
        value: object,
        name: str,
        index: int,
    ) -> float | None:

        if value is None:
            return None

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise WindDataProviderError(
                f"{name} is invalid at "
                f"observation {index}."
            ) from exc

        if not math.isfinite(
            number
        ):

            raise WindDataProviderError(
                f"{name} is not finite at "
                f"observation {index}."
            )

        return number


    @staticmethod
    def _optional_payload_number(
        value: object,
    ) -> float | None:

        if value is None:
            return None

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        if not math.isfinite(
            number
        ):
            return None

        return number


# ============================================================
# PROVIDER-INDEPENDENT ENTRY POINT
# ============================================================

def load_wind_resource(
    request: WindDataRequest,
    provider: WindResourceProvider | None = None,
) -> WindResourceSeries:
    """
    Main wind-resource loading function.

    Default:
        Open-Meteo historical/forecast data.

    Later another provider can be substituted without
    changing wind.py or the rest of the simulator.
    """

    if provider is None:

        provider = (
            OpenMeteoWindProvider()
        )

    return provider.fetch(
        request
    )
