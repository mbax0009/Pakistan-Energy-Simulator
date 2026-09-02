from __future__ import annotations

import os
import sys

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from data.assumptions.assumptions import REFERENCE_CASES
from data.market_context import build_market_context
from simulator_api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    BreakEvenRequest,
    BreakEvenResponse,
    CacheClearResponse,
    ComparisonRequest,
    ComparisonResponse,
    HealthResponse,
    JointUncertaintyRequest,
    JointUncertaintyResponse,
    MarketContextResponse,
    OneWaySensitivityRequest,
    OneWaySensitivityResponse,
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    TwoWaySensitivityRequest,
    TwoWaySensitivityResponse,
)
from simulator_api.service import (
    build_cache,
    run_analysis,
    run_break_even_analysis,
    run_comparison,
    run_joint_risk_analysis,
    run_one_way_analysis,
    run_risk_analysis,
    run_two_way_analysis,
)
from simulator_api.version import METHODOLOGY_VERSION, VERSION


def _jsonable(value: Any):
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


app = FastAPI(
    title="Pakistan Renewable Energy Simulator API",
    version=VERSION,
    description=(
        "Authoritative local API for solar, wind, and wave techno-economic analysis."
    ),
)

origins = [
    value.strip()
    for value in os.getenv(
        "PAK_ENERGY_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        software_version=VERSION,
        methodology_version=METHODOLOGY_VERSION,
    )


@app.get("/api/v1/assumptions")
def assumptions():
    return {
        technology.value: _jsonable(reference)
        for technology, reference in REFERENCE_CASES.items()
    }


@app.get("/api/v1/market-context", response_model=MarketContextResponse)
def market_context() -> MarketContextResponse:
    return MarketContextResponse.model_validate(build_market_context())


@app.post("/api/v1/analyses", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    try:
        return run_analysis(request)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "The external resource provider or analysis engine could not "
                f"complete the request: {exc}"
            ),
        ) from exc


def _analysis_error(exc: Exception) -> HTTPException:
    status_code = 400 if isinstance(exc, (ValueError, TypeError)) else 502
    return HTTPException(status_code=status_code, detail=str(exc))


@app.post(
    "/api/v1/sensitivity/one-way",
    response_model=OneWaySensitivityResponse,
)
def one_way_sensitivity(request: OneWaySensitivityRequest):
    try:
        return run_one_way_analysis(request)
    except Exception as exc:
        raise _analysis_error(exc) from exc


@app.post(
    "/api/v1/sensitivity/break-even",
    response_model=BreakEvenResponse,
)
def break_even(request: BreakEvenRequest):
    try:
        return run_break_even_analysis(request)
    except Exception as exc:
        raise _analysis_error(exc) from exc


@app.post(
    "/api/v1/sensitivity/two-way",
    response_model=TwoWaySensitivityResponse,
)
def two_way_sensitivity(request: TwoWaySensitivityRequest):
    try:
        return run_two_way_analysis(request)
    except Exception as exc:
        raise _analysis_error(exc) from exc


@app.post("/api/v1/risk", response_model=RiskAnalysisResponse)
def risk(request: RiskAnalysisRequest):
    try:
        return run_risk_analysis(request)
    except Exception as exc:
        raise _analysis_error(exc) from exc


@app.post("/api/v1/risk/joint", response_model=JointUncertaintyResponse)
def joint_risk(request: JointUncertaintyRequest):
    try:
        return run_joint_risk_analysis(request)
    except Exception as exc:
        raise _analysis_error(exc) from exc


@app.post("/api/v1/comparisons", response_model=ComparisonResponse)
def comparisons(request: ComparisonRequest):
    try:
        return run_comparison(request)
    except Exception as exc:
        raise _analysis_error(exc) from exc


@app.delete("/api/v1/cache", response_model=CacheClearResponse)
def clear_cache(
    namespace: str | None = Query(default=None, min_length=1, max_length=80),
) -> CacheClearResponse:
    deleted = build_cache().clear(namespace)
    return CacheClearResponse(deleted_entries=deleted, namespace=namespace)


if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
    BUNDLE_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_DIST = BUNDLE_ROOT / "frontend" / "dist" / "client"
if FRONTEND_DIST.is_dir():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
