"""FastAPI routes and static app hosting."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from app.dataset_store import DatasetStore
from app.models import (
    AnalysisResponse,
    DatasetUploadResponse,
    Geometry,
    MeasurementSummary,
    TraceResponse,
)
from app.pipeline import (
    MeasurementNotFoundError,
    analyze_dataset,
    analyze_trace,
    list_measurement_files,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = Path(os.environ.get("FMR_DATA_DIR", PROJECT_ROOT / "broadband_100"))
WEB_DIRECTORY = Path(__file__).resolve().parents[1] / "web"
DATASET_STORE = DatasetStore(DATA_DIRECTORY)

app = FastAPI(
    title="FMR Measurement Visualizer",
    description="Analyze field-swept lock-in ferromagnetic resonance measurements.",
    version="0.1.0",
)


@app.get("/api/measurements", response_model=list[MeasurementSummary])
def get_measurements() -> list[MeasurementSummary]:
    """List available frequency sweeps."""
    with DATASET_STORE.active_directory() as directory:
        try:
            files = list_measurement_files(directory)
        except ValueError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return [
        MeasurementSummary(
            measurement_id=filename,
            filename=filename,
            frequency_ghz=frequency_ghz,
        )
        for filename, frequency_ghz in files
    ]


@app.post("/api/datasets", response_model=DatasetUploadResponse)
def upload_dataset(
    files: Annotated[list[UploadFile], File()],
    geometry: Geometry = "in_plane",
    initial_perpendicular_field_t: float | None = Query(
        default=None, ge=-2, le=2, allow_inf_nan=False
    ),
    initial_linewidth_pp_oe: float | None = Query(
        default=None, gt=0, le=10000, allow_inf_nan=False
    ),
) -> DatasetUploadResponse:
    """Validate and activate uploaded CSV measurements."""
    try:
        uploads = [(upload.filename or "", upload.file) for upload in files]
        measurement_count = DATASET_STORE.replace_from_upload(
            uploads,
            geometry=geometry,
            initial_perpendicular_field_t=initial_perpendicular_field_t,
            initial_linewidth_pp_oe=initial_linewidth_pp_oe,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        for upload in files:
            upload.file.close()
    return DatasetUploadResponse(measurement_count=measurement_count, geometry=geometry)


@app.get("/api/measurements/{measurement_id}", response_model=TraceResponse)
def get_measurement_trace(
    measurement_id: str,
    initial_linewidth_pp_oe: float | None = Query(
        default=None, gt=0, le=10000, allow_inf_nan=False
    ),
) -> TraceResponse:
    """Return one raw trace and the backend-fitted resonance line."""
    with DATASET_STORE.active_analysis() as (directory, geometry, _, stored_linewidth):
        try:
            linewidth = (
                initial_linewidth_pp_oe if initial_linewidth_pp_oe is not None else stored_linewidth
            )
            if linewidth is None and geometry == "out_of_plane":
                linewidth = 10.0
            result = analyze_trace(directory, measurement_id, linewidth)
        except MeasurementNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    return TraceResponse.model_validate(result)


@app.get("/api/analysis", response_model=AnalysisResponse)
def get_analysis(
    geometry: Geometry | None = None,
    excluded_measurement_ids: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=255)]] | None,
        Query(max_length=1000),
    ] = None,
    initial_perpendicular_field_t: float | None = Query(
        default=None, ge=-2, le=2, allow_inf_nan=False
    ),
    initial_linewidth_pp_oe: float | None = Query(
        default=None, gt=0, le=10000, allow_inf_nan=False
    ),
) -> AnalysisResponse:
    """Extract all sweeps and fit both models using the same included measurements."""
    with DATASET_STORE.active_analysis() as (
        directory,
        stored_geometry,
        stored_field,
        stored_linewidth,
    ):
        try:
            selected_geometry = geometry or stored_geometry
            field = initial_perpendicular_field_t
            linewidth = initial_linewidth_pp_oe
            if selected_geometry == stored_geometry:
                field = stored_field if field is None else field
                linewidth = stored_linewidth if linewidth is None else linewidth
            result = analyze_dataset(
                directory,
                field,
                geometry=selected_geometry,
                initial_linewidth_pp_oe=linewidth,
                excluded_measurement_ids=excluded_measurement_ids,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    return AnalysisResponse.model_validate(result)


app.mount("/vendor", StaticFiles(directory="/vendor"), name="vendor")
app.mount("/", StaticFiles(directory=WEB_DIRECTORY, html=True), name="web")
