"""Typed API request and response models."""

from pydantic import BaseModel


class MeasurementSummary(BaseModel):
    """Metadata for one field sweep."""

    measurement_id: str
    filename: str
    frequency_ghz: float


class ResonancePoint(BaseModel):
    """Resonance field and linewidth extracted from one sweep."""

    measurement_id: str
    filename: str
    frequency_ghz: float
    resonance_field_oe: float
    linewidth_pp_oe: float
    resonance_r_squared: float


class CurvePoint(BaseModel):
    """Coordinate pair for a server-generated fit curve."""

    field_oe: float | None = None
    frequency_ghz: float
    linewidth_pp_oe: float | None = None


class KittelFitResult(BaseModel):
    """Fitted in-plane Kittel parameters and model curve."""

    g_factor: float
    effective_perpendicular_field_t: float
    fourfold_field_t: float
    r_squared: float
    equation: str
    curve: list[CurvePoint]


class LinewidthFitResult(BaseModel):
    """Fitted linewidth slope, damping and model curve."""

    slope_oe_per_ghz: float
    intercept_oe: float
    damping: float
    r_squared: float
    equation: str
    curve: list[CurvePoint]


class AnalysisResponse(BaseModel):
    """Full extracted FMR dataset and fit results."""

    measurements: list[ResonancePoint]
    kittel_fit: KittelFitResult
    linewidth_fit: LinewidthFitResult


class TraceResponse(BaseModel):
    """Measured lock-in trace and its fitted derivative-Lorentzian curve."""

    measurement_id: str
    filename: str
    frequency_ghz: float
    resonance_field_oe: float
    linewidth_pp_oe: float
    r_squared: float
    field_oe: list[float]
    signal: list[float]
    fit_signal: list[float]


class DatasetUploadResponse(BaseModel):
    """Result of accepting a replacement dataset."""

    measurement_count: int
