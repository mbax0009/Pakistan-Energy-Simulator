# data/solar_loader.py

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
    SolarConfig,
)

from core.resources import (
    ResourceMetadata,
    SolarResourcePoint,
    SolarResourceSeries,
)


# ============================================================
# DATA MODE
# ============================================================

class SolarDataMode(str, Enum):
    """
    Type of solar-resource data requested.

    HISTORICAL:
        Reanalysis data for past dates.
        Intended for techno-economic modelling.

    FORECAST:
        Current / future weather-model data.
        Intended for current-condition or operational views.
    """

    HISTORICAL = "historical"
    FORECAST = "forecast"


# ============================================================
# REQUEST MODEL
# ============================================================

@dataclass(frozen=True)
class SolarDataRequest:
    """
    Complete request for coordinate-based solar-resource data.

    The request is independent of any specific API provider.
    """

    location: Location

    solar_config: SolarConfig

    start_date: date
    end_date: date

    mode: SolarDataMode = (
        SolarDataMode.HISTORICAL
    )

    def __post_init__(self):

        if self.start_date > self.end_date:
            raise ValueError(
                "start_date cannot be after end_date."
            )


# ============================================================
# PROVIDER INTERFACE
# ============================================================

class SolarResourceProvider(Protocol):
    """
    Interface that every solar-data provider should follow.

    Future examples:

        OpenMeteoSolarProvider
        PVGISSolarProvider
        GlobalSolarAtlasRasterProvider
    """

    def fetch(
        self,
        request: SolarDataRequest,
    ) -> SolarResourceSeries:
        ...


# ============================================================
# PROVIDER ERROR
# ============================================================

class SolarDataProviderError(RuntimeError):
    """
    Raised when an external solar-data provider fails.
    """

    pass


# ============================================================
# OPEN-METEO PROVIDER
# ============================================================

class OpenMeteoSolarProvider:
    """
    Coordinate-based Open-Meteo solar-resource provider.

    Historical mode:
        Uses a consistent reanalysis dataset.

    Forecast mode:
        Uses the forecast service.

    Returned data are converted into our internal
    SolarResourceSeries format.
    """

    HOURLY_VARIABLES = (
        "shortwave_radiation",
        "direct_normal_irradiance",
        "diffuse_radiation",
        "global_tilted_irradiance",
        "temperature_2m",
        "wind_speed_10m",
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
    # PUBLIC METHOD
    # ========================================================

    def fetch(
        self,
        request: SolarDataRequest,
    ) -> SolarResourceSeries:
        """
        Download solar-resource data for arbitrary
        geographic coordinates.
        """

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
                "open-meteo-solar",
                cache_material,
                max_age_seconds=(
                    30 * 24 * 60 * 60
                    if request.mode is SolarDataMode.HISTORICAL
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
                    "open-meteo-solar",
                    cache_material,
                    payload,
                )

        return self._parse_response(
            request=request,
            payload=payload,
        )


    # ========================================================
    # API ENDPOINT
    # ========================================================

    @staticmethod
    def _build_endpoint(
        mode: SolarDataMode,
    ) -> str:
        """
        Construct provider endpoint.

        URL components are deliberately assembled rather
        than spread throughout the program.
        """

        if mode is SolarDataMode.HISTORICAL:

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

        if mode is SolarDataMode.FORECAST:

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
            f"Unsupported solar-data mode: {mode}"
        )


    # ========================================================
    # AZIMUTH CONVERSION
    # ========================================================

    @staticmethod
    def _convert_azimuth_to_provider(
        compass_azimuth_deg: float,
    ) -> float:
        """
        Convert our internal compass convention:

            North =   0°
            East  =  90°
            South = 180°
            West  = 270°

        into the provider convention:

            South =   0°
            East  = -90°
            West  = +90°
            North = ±180°
        """

        if not (
            0
            <= compass_azimuth_deg
            < 360
        ):
            raise ValueError(
                "Compass azimuth must be between "
                "0 and 360 degrees."
            )

        return (
            compass_azimuth_deg
            - 180.0
        )


    # ========================================================
    # REQUEST PARAMETERS
    # ========================================================

    def _build_parameters(
        self,
        request: SolarDataRequest,
    ) -> dict[str, object]:
        """
        Translate our provider-independent request into
        Open-Meteo parameters.
        """

        config = request.solar_config

        provider_azimuth = (
            self._convert_azimuth_to_provider(
                config.azimuth_deg
            )
        )

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
                self.HOURLY_VARIABLES
            ),

            # Keep all internal timestamps in UTC.
            "timezone": "GMT",

            "temperature_unit": "celsius",

            "wind_speed_unit": "ms",

            # Required for tilted-plane irradiance.
            "tilt": config.tilt_deg,

            "azimuth": provider_azimuth,
        }

        # A fixed reanalysis model gives better
        # comparability across long historical periods.
        if (
            request.mode
            is SolarDataMode.HISTORICAL
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
        Perform an API request with basic retry handling.

        Temporary network/server failures are retried.

        Permanent client errors are reported immediately.
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
                # Client-side error: do not retry blindly
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

                    raise SolarDataProviderError(
                        "Solar-data provider rejected "
                        f"the request: {details}"
                    )

                # --------------------------------------------
                # Server error
                # --------------------------------------------

                response.raise_for_status()

                try:
                    payload = response.json()

                except ValueError as exc:
                    raise SolarDataProviderError(
                        "Solar-data provider returned "
                        "invalid JSON."
                    ) from exc


                if payload.get("error"):

                    raise SolarDataProviderError(
                        "Solar-data provider returned "
                        f"an error: "
                        f"{payload.get('reason')}"
                    )


                return payload


            except SolarDataProviderError:
                raise


            except requests.RequestException as exc:

                last_error = exc

                if attempt == self.max_retries:
                    break

                # Exponential backoff:
                #
                # attempt 1 → 1 second
                # attempt 2 → 2 seconds
                # attempt 3 → 4 seconds
                #
                delay_seconds = (
                    2 ** (attempt - 1)
                )

                time.sleep(
                    delay_seconds
                )


        raise SolarDataProviderError(
            "Unable to retrieve solar-resource "
            "data after repeated attempts."
        ) from last_error


    # ========================================================
    # RESPONSE PARSING
    # ========================================================

    def _parse_response(
        self,
        request: SolarDataRequest,
        payload: dict,
    ) -> SolarResourceSeries:
        """
        Convert provider JSON into our internal
        SolarResourceSeries format.
        """

        hourly = payload.get(
            "hourly"
        )

        if not isinstance(
            hourly,
            dict,
        ):
            raise SolarDataProviderError(
                "Provider response does not contain "
                "hourly resource data."
            )


        timestamps = self._require_list(
            hourly,
            "time",
        )

        ghi_values = self._require_list(
            hourly,
            "shortwave_radiation",
        )

        dni_values = self._require_list(
            hourly,
            "direct_normal_irradiance",
        )

        dhi_values = self._require_list(
            hourly,
            "diffuse_radiation",
        )

        poa_values = self._require_list(
            hourly,
            "global_tilted_irradiance",
        )

        temperature_values = self._require_list(
            hourly,
            "temperature_2m",
        )

        wind_values = self._require_list(
            hourly,
            "wind_speed_10m",
        )


        expected_length = len(
            timestamps
        )

        data_arrays = {
            "GHI": ghi_values,
            "DNI": dni_values,
            "DHI": dhi_values,
            "POA": poa_values,
            "temperature": temperature_values,
            "wind speed": wind_values,
        }


        for name, values in (
            data_arrays.items()
        ):

            if len(values) != expected_length:

                raise SolarDataProviderError(
                    f"{name} data length does not "
                    "match timestamp length."
                )


        if expected_length < 2:

            raise SolarDataProviderError(
                "At least two resource observations "
                "are required."
            )


        # ----------------------------------------------------
        # Convert each provider observation into
        # SolarResourcePoint
        # ----------------------------------------------------

        points: list[
            SolarResourcePoint
        ] = []


        for index in range(
            expected_length
        ):

            timestamp = (
                self._parse_utc_timestamp(
                    timestamps[index]
                )
            )


            ghi = self._required_number(
                ghi_values[index],
                "GHI",
                index,
            )


            dni = self._optional_number(
                dni_values[index],
                "DNI",
                index,
            )


            dhi = self._optional_number(
                dhi_values[index],
                "DHI",
                index,
            )


            poa = self._optional_number(
                poa_values[index],
                "POA irradiance",
                index,
            )


            ambient_temperature = (
                self._optional_number(
                    temperature_values[index],
                    "Ambient temperature",
                    index,
                )
            )


            wind_speed = (
                self._optional_number(
                    wind_values[index],
                    "Wind speed",
                    index,
                )
            )


            points.append(
                SolarResourcePoint(
                    timestamp=timestamp,

                    ghi_wm2=ghi,

                    dni_wm2=dni,

                    dhi_wm2=dhi,

                    poa_irradiance_wm2=poa,

                    ambient_temperature_c=(
                        ambient_temperature
                    ),

                    # Open-Meteo gives ambient air
                    # temperature, NOT PV cell temperature.
                    cell_temperature_c=None,

                    wind_speed_ms=wind_speed,
                )
            )


        # ----------------------------------------------------
        # Record provider grid information
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
            is SolarDataMode.HISTORICAL
        ):

            dataset_name = (
                "Open-Meteo "
                f"{self.historical_model.upper()} "
                "Historical Reanalysis"
            )

        else:

            dataset_name = (
                "Open-Meteo Forecast"
            )


        metadata = ResourceMetadata(
            source_name="Open-Meteo",

            dataset_name=dataset_name,

            retrieved_at=datetime.now(
                timezone.utc
            ),

            source_reference=(
                f"open-meteo:"
                f"{request.mode.value}"
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


        # IMPORTANT:
        #
        # resource.location remains the REQUESTED
        # project location.
        #
        # The provider's actual grid location is stored
        # separately in ResourceMetadata.
        #
        # This preserves both:
        #
        #   user/site coordinate
        #
        # and
        #
        #   model grid coordinate

        return SolarResourceSeries(
            location=request.location,

            metadata=metadata,

            points=tuple(points),
        )


    # ========================================================
    # PARSING HELPERS
    # ========================================================

    @staticmethod
    def _require_list(
        container: dict,
        key: str,
    ) -> list:
        """
        Retrieve a required provider array.
        """

        value = container.get(
            key
        )

        if not isinstance(
            value,
            list,
        ):
            raise SolarDataProviderError(
                f"Provider response is missing "
                f"required array: {key}"
            )

        return value


    @staticmethod
    def _parse_utc_timestamp(
        value: object,
    ) -> datetime:
        """
        Parse an ISO timestamp returned in GMT/UTC.
        """

        if not isinstance(
            value,
            str,
        ):
            raise SolarDataProviderError(
                "Resource timestamp is invalid."
            )

        try:
            timestamp = (
                datetime.fromisoformat(
                    value
                )
            )

        except ValueError as exc:
            raise SolarDataProviderError(
                f"Invalid timestamp: {value}"
            ) from exc


        if timestamp.tzinfo is None:

            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        else:

            timestamp = timestamp.astimezone(
                timezone.utc
            )


        return timestamp


    @staticmethod
    def _required_number(
        value: object,
        name: str,
        index: int,
    ) -> float:
        """
        Parse a required numeric observation.
        """

        if value is None:
            raise SolarDataProviderError(
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
            raise SolarDataProviderError(
                f"{name} is invalid at "
                f"observation {index}."
            ) from exc


        if not math.isfinite(
            number
        ):
            raise SolarDataProviderError(
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
        """
        Parse an optional numeric observation.

        Missing optional values become None.
        """

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
            raise SolarDataProviderError(
                f"{name} is invalid at "
                f"observation {index}."
            ) from exc


        if not math.isfinite(
            number
        ):
            raise SolarDataProviderError(
                f"{name} is not finite at "
                f"observation {index}."
            )


        return number


    @staticmethod
    def _optional_payload_number(
        value: object,
    ) -> float | None:
        """
        Parse optional numerical API metadata.
        """

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
# CONVENIENCE FUNCTION
# ============================================================

def load_solar_resource(
    request: SolarDataRequest,
    provider: SolarResourceProvider | None = None,
) -> SolarResourceSeries:
    """
    Main provider-independent entry point.

    If no provider is supplied, Open-Meteo is used.

    Later:

        load_solar_resource(
            request,
            provider=PVGISSolarProvider(),
        )

    can use exactly the same application code.
    """

    if provider is None:

        provider = (
            OpenMeteoSolarProvider()
        )


    return provider.fetch(
        request
    )
