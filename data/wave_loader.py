# data/wave_loader.py

from __future__ import annotations

import math
import time as time_module

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time,
    timezone,
)
from typing import Protocol

import numpy as np
import pandas as pd
import requests

from data.cache import JsonResourceCache

from core.models import (
    Location,
)

from core.resources import (
    ResourceMetadata,
    WaveResourcePoint,
    WaveResourceSeries,
)


# ============================================================
# COPERNICUS DATASET IDENTIFIERS
# ============================================================

COPERNICUS_WAVE_DATASET_ID = (
    "cmems_mod_glo_wav_my_0.2deg_PT3H-i"
)

COPERNICUS_WAVE_STATIC_DATASET_ID = (
    "cmems_mod_glo_wav_my_0.2deg_static"
)


# ============================================================
# VARIABLES
# ============================================================

SIGNIFICANT_WAVE_HEIGHT_VARIABLE = "VHM0"

ENERGY_PERIOD_VARIABLE = "VTM10"

WAVE_DIRECTION_VARIABLE = "VMDR"

BATHYMETRY_VARIABLE = "deptho"


# ============================================================
# REQUEST MODEL
# ============================================================

@dataclass(frozen=True)
class WaveDataRequest:
    """
    Coordinate-based historical wave-resource request.

    location:
        Proposed offshore project coordinate.

    start_date / end_date:
        Historical period requested.

    include_bathymetry:
        When True, also retrieve sea-floor depth
        for the selected marine grid cell.
    """

    location: Location

    start_date: date
    end_date: date

    include_bathymetry: bool = True

    def __post_init__(self):

        if self.start_date > self.end_date:

            raise ValueError(
                "start_date cannot be after end_date."
            )


# ============================================================
# PROVIDER INTERFACE
# ============================================================

class WaveResourceProvider(Protocol):
    """
    Interface followed by every historical
    wave-resource provider.
    """

    def fetch(
        self,
        request: WaveDataRequest,
    ) -> WaveResourceSeries:
        ...


# ============================================================
# PROVIDER ERROR
# ============================================================

class WaveDataProviderError(RuntimeError):
    """
    Raised when marine-resource retrieval or parsing fails.
    """

    pass


# ============================================================
# OPEN-METEO ERA5-OCEAN FALLBACK PROVIDER
# ============================================================

class OpenMeteoMarineWaveProvider:
    """
    Credential-free historical wave fallback based on
    Open-Meteo's ERA5-Ocean marine endpoint.

    The returned ``wave_period`` is a mean wave period, not
    Copernicus VTM10. It is preserved in the common
    ``energy_period_s`` field as an explicit approximation;
    downstream reports must surface that limitation.
    """

    ENDPOINT = "https://marine-api.open-meteo.com/v1/marine"

    def __init__(
        self,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        session: requests.Session | None = None,
        cache: JsonResourceCache | None = None,
        cache_enabled: bool = True,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1.")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = session if session is not None else requests.Session()
        self.cache = cache if cache is not None else JsonResourceCache()
        self.cache_enabled = bool(cache_enabled)

    def fetch(self, request: WaveDataRequest) -> WaveResourceSeries:
        params = {
            "latitude": request.location.latitude,
            "longitude": request.location.longitude,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "hourly": "wave_height,wave_period,wave_direction",
            "models": "era5_ocean",
            "timezone": "GMT",
            "cell_selection": "sea",
        }
        material = {"endpoint": self.ENDPOINT, "params": params}
        cached = None
        if self.cache_enabled:
            cached = self.cache.get(
                "open-meteo-marine-wave",
                material,
                max_age_seconds=30 * 24 * 60 * 60,
            )

        if cached is not None:
            payload = cached.payload
        else:
            payload = self._request_json(params)
            if self.cache_enabled:
                self.cache.put("open-meteo-marine-wave", material, payload)

        return self._parse_response(request, payload)

    def _request_json(self, params: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    self.ENDPOINT,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise WaveDataProviderError(
                        "Open-Meteo Marine returned a non-object response."
                    )
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time_module.sleep(0.5 * attempt)
        raise WaveDataProviderError(
            "Open-Meteo Marine request failed after retries."
        ) from last_error

    @staticmethod
    def _parse_response(
        request: WaveDataRequest,
        payload: dict,
    ) -> WaveResourceSeries:
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            raise WaveDataProviderError(
                "Open-Meteo Marine response is missing hourly data."
            )

        arrays = {
            name: hourly.get(name)
            for name in ("time", "wave_height", "wave_period", "wave_direction")
        }
        if not all(isinstance(value, list) for value in arrays.values()):
            raise WaveDataProviderError(
                "Open-Meteo Marine response is missing required arrays."
            )
        expected_length = len(arrays["time"])
        if expected_length < 2 or any(
            len(values) != expected_length for values in arrays.values()
        ):
            raise WaveDataProviderError(
                "Open-Meteo Marine arrays are empty or have inconsistent lengths."
            )

        points: list[WaveResourcePoint] = []
        for index in range(expected_length):
            try:
                timestamp = datetime.fromisoformat(arrays["time"][index]).replace(
                    tzinfo=timezone.utc
                )
                wave_height = float(arrays["wave_height"][index])
                wave_period = float(arrays["wave_period"][index])
                direction_value = arrays["wave_direction"][index]
                wave_direction = (
                    None
                    if direction_value is None
                    else float(direction_value) % 360.0
                )
            except (TypeError, ValueError) as exc:
                raise WaveDataProviderError(
                    f"Invalid Open-Meteo Marine value at index {index}."
                ) from exc
            points.append(
                WaveResourcePoint(
                    timestamp=timestamp,
                    significant_wave_height_m=wave_height,
                    energy_period_s=wave_period,
                    wave_direction_deg=wave_direction,
                )
            )

        resolved_latitude = payload.get("latitude")
        resolved_longitude = payload.get("longitude")
        metadata = ResourceMetadata(
            source_name="Open-Meteo",
            dataset_name="Open-Meteo ERA5-Ocean Historical Marine Reanalysis",
            retrieved_at=datetime.now(timezone.utc),
            source_reference="open-meteo:era5-ocean:marine",
            resolved_latitude=(
                None if resolved_latitude is None else float(resolved_latitude)
            ),
            resolved_longitude=(
                None if resolved_longitude is None else float(resolved_longitude)
            ),
            provider_timezone=str(payload.get("timezone", "GMT")),
        )
        return WaveResourceSeries(
            location=request.location,
            metadata=metadata,
            points=tuple(points),
            water_depth_m=None,
        )


# ============================================================
# COPERNICUS MARINE PROVIDER
# ============================================================

class CopernicusMarineWaveProvider:
    """
    Historical wave-resource provider based on
    Copernicus Marine WAVERYS.

    Main variables:

        VHM0
            Significant wave height, metres.

        VTM10
            Spectral Tm-10 period, seconds.

            This is used as the wave-energy period
            in our deep-water wave-power equation.

        VMDR
            Mean direction waves are coming from.

    The provider returns the nearest available marine
    model grid cell to the requested coordinates.
    """

    def __init__(
        self,
        dataset_id: str = (
            COPERNICUS_WAVE_DATASET_ID
        ),
        static_dataset_id: str = (
            COPERNICUS_WAVE_STATIC_DATASET_ID
        ),
        credentials_file: str | None = None,
    ):

        if not dataset_id.strip():

            raise ValueError(
                "Wave dataset ID cannot be empty."
            )

        if not static_dataset_id.strip():

            raise ValueError(
                "Static wave dataset ID cannot be empty."
            )

        self.dataset_id = (
            dataset_id
        )

        self.static_dataset_id = (
            static_dataset_id
        )

        self.credentials_file = (
            credentials_file
        )


    # ========================================================
    # PUBLIC ENTRY POINT
    # ========================================================

    def fetch(
        self,
        request: WaveDataRequest,
    ) -> WaveResourceSeries:
        """
        Load historical wave conditions for the
        requested offshore coordinate.
        """

        copernicusmarine = (
            self._import_copernicusmarine()
        )

        dataset = (
            self._open_wave_dataset(
                copernicusmarine=(
                    copernicusmarine
                ),
                request=request,
            )
        )

        try:

            resource = (
                self._parse_wave_dataset(
                    request=request,
                    dataset=dataset,
                    copernicusmarine=(
                        copernicusmarine
                    ),
                )
            )

        finally:

            close_method = getattr(
                dataset,
                "close",
                None,
            )

            if callable(close_method):
                close_method()

        return resource


    # ========================================================
    # PACKAGE IMPORT
    # ========================================================

    @staticmethod
    def _import_copernicusmarine():

        try:

            import copernicusmarine

        except ImportError as exc:

            raise WaveDataProviderError(
                "The 'copernicusmarine' package is "
                "required for historical wave data. "
                "Install it with: "
                "pip install copernicusmarine"
            ) from exc

        return copernicusmarine


    # ========================================================
    # DATE/TIME LIMITS
    # ========================================================

    @staticmethod
    def _start_datetime(
        request: WaveDataRequest,
    ) -> datetime:

        return datetime.combine(
            request.start_date,
            time.min,
            tzinfo=timezone.utc,
        )


    @staticmethod
    def _end_datetime(
        request: WaveDataRequest,
    ) -> datetime:

        return datetime.combine(
            request.end_date,
            time.max,
            tzinfo=timezone.utc,
        )


    # ========================================================
    # OPEN REMOTE WAVE DATASET
    # ========================================================

    def _open_wave_dataset(
        self,
        copernicusmarine,
        request: WaveDataRequest,
    ):
        """
        Open only the requested point, period and variables.

        No full global dataset is downloaded.
        """

        longitude = (
            request.location.longitude
        )

        latitude = (
            request.location.latitude
        )

        parameters = {

            "dataset_id": (
                self.dataset_id
            ),

            "variables": [
                SIGNIFICANT_WAVE_HEIGHT_VARIABLE,
                ENERGY_PERIOD_VARIABLE,
                WAVE_DIRECTION_VARIABLE,
            ],

            "minimum_longitude": longitude,
            "maximum_longitude": longitude,

            "minimum_latitude": latitude,
            "maximum_latitude": latitude,

            "start_datetime": (
                self._start_datetime(
                    request
                )
            ),

            "end_datetime": (
                self._end_datetime(
                    request
                )
            ),

            # Select the model grid location
            # nearest the requested coordinate.
            "coordinates_selection_method": (
                "nearest"
            ),

            "disable_progress_bar": True,
        }

        if self.credentials_file is not None:

            parameters[
                "credentials_file"
            ] = self.credentials_file

        try:

            return (
                copernicusmarine.open_dataset(
                    **parameters
                )
            )

        except Exception as exc:

            raise WaveDataProviderError(
                "Unable to open the Copernicus "
                "historical wave dataset."
            ) from exc


    # ========================================================
    # PARSE COMPLETE DATASET
    # ========================================================

    def _parse_wave_dataset(
        self,
        request: WaveDataRequest,
        dataset,
        copernicusmarine,
    ) -> WaveResourceSeries:
        """
        Convert Copernicus/xarray data into our
        technology-independent resource structures.
        """

        self._validate_required_variables(
            dataset
        )

        resolved_latitude = (
            self._extract_coordinate(
                dataset,
                "latitude",
            )
        )

        resolved_longitude = (
            self._extract_coordinate(
                dataset,
                "longitude",
            )
        )

        timestamps = (
            self._extract_timestamps(
                dataset
            )
        )

        wave_heights = (
            self._extract_variable(
                dataset,
                SIGNIFICANT_WAVE_HEIGHT_VARIABLE,
            )
        )

        energy_periods = (
            self._extract_variable(
                dataset,
                ENERGY_PERIOD_VARIABLE,
            )
        )

        wave_directions = (
            self._extract_variable(
                dataset,
                WAVE_DIRECTION_VARIABLE,
            )
        )

        expected_length = len(
            timestamps
        )

        for name, values in (
            (
                "significant wave height",
                wave_heights,
            ),
            (
                "energy period",
                energy_periods,
            ),
            (
                "wave direction",
                wave_directions,
            ),
        ):

            if len(values) != expected_length:

                raise WaveDataProviderError(
                    f"{name} array length does "
                    "not match the timestamp array."
                )

        if expected_length < 2:

            raise WaveDataProviderError(
                "At least two marine observations "
                "are required."
            )

        # ----------------------------------------------------
        # Construct resource points
        # ----------------------------------------------------

        points: list[
            WaveResourcePoint
        ] = []

        for index in range(
            expected_length
        ):

            wave_height = (
                self._required_number(
                    wave_heights[index],
                    name="Significant wave height",
                    index=index,
                )
            )

            energy_period = (
                self._required_number(
                    energy_periods[index],
                    name="Wave energy period",
                    index=index,
                )
            )

            wave_direction = (
                self._optional_number(
                    wave_directions[index],
                    name="Wave direction",
                    index=index,
                )
            )

            points.append(
                WaveResourcePoint(

                    timestamp=(
                        timestamps[index]
                    ),

                    significant_wave_height_m=(
                        wave_height
                    ),

                    energy_period_s=(
                        energy_period
                    ),

                    wave_direction_deg=(
                        wave_direction
                    ),
                )
            )

        # ----------------------------------------------------
        # Optional bathymetry
        # ----------------------------------------------------

        water_depth_m: float | None = None

        if request.include_bathymetry:

            water_depth_m = (
                self._load_bathymetry(
                    copernicusmarine=(
                        copernicusmarine
                    ),

                    longitude=(
                        resolved_longitude
                    ),

                    latitude=(
                        resolved_latitude
                    ),
                )
            )

        # ----------------------------------------------------
        # Traceability
        # ----------------------------------------------------

        metadata = ResourceMetadata(

            source_name=(
                "Copernicus Marine Service"
            ),

            dataset_name=(
                "Global Ocean Waves Reanalysis "
                "(WAVERYS)"
            ),

            retrieved_at=datetime.now(
                timezone.utc
            ),

            source_reference=(
                self.dataset_id
            ),

            resolved_latitude=(
                resolved_latitude
            ),

            resolved_longitude=(
                resolved_longitude
            ),

            provider_timezone="UTC",
        )

        # ----------------------------------------------------
        # Preserve requested location separately.
        #
        # project location:
        #     what the user requested
        #
        # resolved coordinates:
        #     actual marine grid cell
        # ----------------------------------------------------

        return WaveResourceSeries(

            location=request.location,

            metadata=metadata,

            points=tuple(
                points
            ),

            water_depth_m=(
                water_depth_m
            ),
        )


    # ========================================================
    # REQUIRED VARIABLES
    # ========================================================

    @staticmethod
    def _validate_required_variables(
        dataset,
    ) -> None:

        required = (
            SIGNIFICANT_WAVE_HEIGHT_VARIABLE,
            ENERGY_PERIOD_VARIABLE,
            WAVE_DIRECTION_VARIABLE,
        )

        missing = tuple(
            variable
            for variable in required
            if variable not in dataset
        )

        if missing:

            raise WaveDataProviderError(
                "Copernicus wave dataset is "
                "missing required variables: "
                + ", ".join(missing)
            )


    # ========================================================
    # COORDINATE EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_coordinate(
        dataset,
        name: str,
    ) -> float:
        """
        Extract the selected model-grid coordinate.
        """

        if name not in dataset.coords:

            raise WaveDataProviderError(
                f"Dataset is missing coordinate: {name}"
            )

        values = np.asarray(
            dataset.coords[
                name
            ].values
        ).reshape(-1)

        if values.size == 0:

            raise WaveDataProviderError(
                f"No {name} coordinate was returned."
            )

        value = float(
            values[0]
        )

        if not math.isfinite(
            value
        ):

            raise WaveDataProviderError(
                f"Resolved {name} is not finite."
            )

        return value


    # ========================================================
    # TIMESTAMP EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_timestamps(
        dataset,
    ) -> tuple[datetime, ...]:
        """
        Convert provider timestamps into timezone-aware UTC
        Python datetime values.
        """

        if "time" not in dataset.coords:

            raise WaveDataProviderError(
                "Wave dataset does not contain "
                "a time coordinate."
            )

        values = np.asarray(
            dataset.coords[
                "time"
            ].values
        ).reshape(-1)

        if values.size == 0:

            raise WaveDataProviderError(
                "Wave dataset returned no timestamps."
            )

        timestamps = tuple(
            pd.Timestamp(value)
            .tz_localize("UTC")
            .to_pydatetime()

            for value in values
        )

        return timestamps


    # ========================================================
    # VARIABLE EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_variable(
        dataset,
        variable_name: str,
    ) -> np.ndarray:
        """
        Extract one variable as a one-dimensional
        time-series array.
        """

        if variable_name not in dataset:

            raise WaveDataProviderError(
                f"Dataset does not contain "
                f"{variable_name}."
            )

        values = np.asarray(
            dataset[
                variable_name
            ].values
        ).squeeze()

        # After selecting one geographic cell,
        # the only remaining meaningful dimension
        # should be time.

        values = np.asarray(
            values
        ).reshape(-1)

        return values


    # ========================================================
    # REQUIRED NUMBER
    # ========================================================

    @staticmethod
    def _required_number(
        value: object,
        name: str,
        index: int,
    ) -> float:

        try:

            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise WaveDataProviderError(
                f"{name} is invalid at "
                f"observation {index}."
            ) from exc

        if not math.isfinite(
            number
        ):

            raise WaveDataProviderError(
                f"{name} is missing or invalid at "
                f"observation {index}. "
                "The requested coordinate may not "
                "correspond to a valid ocean grid cell."
            )

        return number


    # ========================================================
    # OPTIONAL NUMBER
    # ========================================================

    @staticmethod
    def _optional_number(
        value: object,
        name: str,
        index: int,
    ) -> float | None:

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


    # ========================================================
    # BATHYMETRY
    # ========================================================

    def _load_bathymetry(
        self,
        copernicusmarine,
        longitude: float,
        latitude: float,
    ) -> float | None:
        """
        Retrieve sea-floor depth from the static
        WAVERYS bathymetry dataset.

        Failure to retrieve bathymetry does not destroy
        otherwise valid wave-resource data.
        """

        parameters = {

            "dataset_id": (
                self.static_dataset_id
            ),

            "variables": [
                BATHYMETRY_VARIABLE
            ],

            "minimum_longitude": longitude,
            "maximum_longitude": longitude,

            "minimum_latitude": latitude,
            "maximum_latitude": latitude,

            "coordinates_selection_method": (
                "nearest"
            ),

            "disable_progress_bar": True,
        }

        if self.credentials_file is not None:

            parameters[
                "credentials_file"
            ] = self.credentials_file

        dataset = None

        try:

            dataset = (
                copernicusmarine.open_dataset(
                    **parameters
                )
            )

            if (
                BATHYMETRY_VARIABLE
                not in dataset
            ):

                return None

            values = np.asarray(
                dataset[
                    BATHYMETRY_VARIABLE
                ].values
            ).reshape(-1)

            if values.size == 0:

                return None

            depth = float(
                values[0]
            )

            if (
                not math.isfinite(depth)
                or depth <= 0
            ):

                return None

            return depth

        except Exception:

            return None

        finally:

            if dataset is not None:

                close_method = getattr(
                    dataset,
                    "close",
                    None,
                )

                if callable(close_method):
                    close_method()


# ============================================================
# PROVIDER-INDEPENDENT ENTRY POINT
# ============================================================

def load_wave_resource(
    request: WaveDataRequest,
    provider: WaveResourceProvider | None = None,
) -> WaveResourceSeries:
    """
    Main wave-resource loading function.

    Default historical source:
        Copernicus Marine WAVERYS.

    The rest of the simulator does not depend directly
    on Copernicus. Another provider can later implement
    WaveResourceProvider.
    """

    if provider is None:

        provider = (
            CopernicusMarineWaveProvider()
        )

    return provider.fetch(
        request
    )
