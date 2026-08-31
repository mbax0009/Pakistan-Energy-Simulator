from __future__ import annotations

from datetime import date

from core.models import Location, SolarConfig
from data.cache import JsonResourceCache
from data.solar_loader import (
    OpenMeteoSolarProvider,
    SolarDataRequest,
)
from data.wind_loader import (
    OpenMeteoWindProvider,
    WindDataRequest,
)
from data.wave_loader import (
    OpenMeteoMarineWaveProvider,
    WaveDataRequest,
)


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, payload: dict):
        self.payload = payload
        self.call_count = 0

    def get(self, *args, **kwargs) -> _FakeResponse:
        self.call_count += 1
        return _FakeResponse(self.payload)


def _payload() -> dict:
    hourly = {
        "time": ["2020-01-01T00:00", "2020-01-01T01:00"],
        "shortwave_radiation": [0.0, 10.0],
        "direct_normal_irradiance": [0.0, 5.0],
        "diffuse_radiation": [0.0, 5.0],
        "global_tilted_irradiance": [0.0, 12.0],
        "temperature_2m": [18.0, 18.0],
        "wind_speed_10m": [2.0, 2.0],
    }
    return {
        "latitude": 25.0,
        "longitude": 68.0,
        "elevation": 43.0,
        "timezone": "GMT",
        "hourly": hourly,
    }


def test_json_resource_cache_round_trip_and_clear(tmp_path):
    cache = JsonResourceCache(tmp_path / "resources")
    material = {"provider": "test", "coordinates": [25.0, 68.0]}
    payload = {"values": [1, 2, 3]}

    stored = cache.put("unit-test", material, payload)
    loaded = cache.get("unit-test", material)

    assert stored.path.is_file()
    assert loaded is not None
    assert loaded.payload == payload
    assert cache.entry_count() == 1
    assert cache.clear("unit-test") == 1
    assert cache.entry_count() == 0


def test_open_meteo_solar_provider_reuses_identical_cached_request(tmp_path):
    session = _FakeSession(_payload())
    provider = OpenMeteoSolarProvider(
        session=session,
        max_retries=1,
        cache=JsonResourceCache(tmp_path / "resources"),
    )
    request = SolarDataRequest(
        location=Location("Jhimpir", 25.025, 67.95),
        solar_config=SolarConfig(tilt_deg=25.0, azimuth_deg=180.0),
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 1),
    )

    first = provider.fetch(request)
    second = provider.fetch(request)

    assert first.points == second.points
    assert session.call_count == 1


def test_open_meteo_wind_provider_normalizes_360_degree_north(tmp_path):
    session = _FakeSession(
        {
            "latitude": 25.0,
            "longitude": 68.0,
            "elevation": 43.0,
            "timezone": "GMT",
            "hourly": {
                "time": ["2020-01-01T00:00", "2020-01-01T01:00"],
                "wind_speed_100m": [7.0, 8.0],
                "wind_direction_100m": [360.0, 180.0],
                "temperature_2m": [18.0, 18.0],
                "surface_pressure": [1005.0, 1005.0],
            },
        }
    )
    provider = OpenMeteoWindProvider(
        session=session,
        max_retries=1,
        cache=JsonResourceCache(tmp_path / "resources"),
    )
    resource = provider.fetch(
        WindDataRequest(
            location=Location("Jhimpir", 25.025, 67.95),
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 1),
        )
    )

    assert resource.points[0].wind_direction_deg == 0.0
    assert resource.points[1].wind_direction_deg == 180.0


def test_open_meteo_marine_provider_parses_and_caches_wave_data(tmp_path):
    session = _FakeSession(
        {
            "latitude": 24.5,
            "longitude": 66.5,
            "timezone": "GMT",
            "hourly": {
                "time": ["2020-01-01T00:00", "2020-01-01T01:00"],
                "wave_height": [1.5, 1.6],
                "wave_period": [6.0, 6.2],
                "wave_direction": [360.0, 225.0],
            },
        }
    )
    provider = OpenMeteoMarineWaveProvider(
        session=session,
        max_retries=1,
        cache=JsonResourceCache(tmp_path / "resources"),
    )
    request = WaveDataRequest(
        location=Location("Arabian Sea", 24.5, 66.5),
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 1),
    )

    first = provider.fetch(request)
    second = provider.fetch(request)

    assert first.points == second.points
    assert first.points[0].wave_direction_deg == 0.0
    assert first.water_depth_m is None
    assert session.call_count == 1
