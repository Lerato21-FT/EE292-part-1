"""Typed API request and response models."""

from typing import Literal

from pydantic import BaseModel, Field

Geometry = Literal["in_plane", "out_of_plane"]


class MeasurementSummary(BaseModel):
    """Metadata for one field sweep."""

    measurement_id: str
    filename: str
    frequency_ghz: float


class ResonancePoint(BaseModel):
    """Resonance field and linewidth extracted from one sweep, with quality flags."""

    measurement_id: str
    filename: str
    frequency_ghz: float
    resonance_field_oe: float | None
    linewidth_pp_oe: float | None
    resonance_r_squared: float | None
    low_quality: bool = Field(description="Resonance R² is below the 0.98 inspection threshold.")
    modulation_rms_oe: float | None = Field(description="RMS modulation read from the filename.")
    modulation_pp_oe: float | None = Field(description="Peak-to-peak modulation, 2√2 × RMS.")
    modulation_warning: bool = Field(description="Peak-to-peak modulation exceeds ΔHpp/3.")
    extraction_error: str | None
    excluded: bool


class CurvePoint(BaseModel):
    """Coordinate pair for a server-generated fit curve."""

    field_oe: float | None = None
    frequency_ghz: float
    linewidth_pp_oe: float | None = None


class KittelFitResult(BaseModel):
    """Geometry-specific Kittel parameters, 1σ standard errors and model curve."""

    g_factor: float
    g_factor_sigma: float | None
    effective_perpendicular_field_t: float
    effective_perpendicular_field_sigma_t: float | None
    fourfold_field_t: float | None
    fourfold_field_sigma_t: float | None
    r_squared: float
    at_bound: list[str] = Field(description="Parameters that ended at a fit bound.")
    equation: str
    curve: list[CurvePoint]


class LinewidthFitResult(BaseModel):
    """Fitted linewidth slope, damping, 1σ standard errors and model curve."""

    slope_oe_per_ghz: float
    slope_sigma_oe_per_ghz: float
    intercept_oe: float
    intercept_sigma_oe: float
    damping: float
    damping_sigma: float
    damping_resolved: bool = Field(description="Slope exceeds two standard errors.")
    r_squared: float
    equation: str
    curve: list[CurvePoint]


class AnalysisResponse(BaseModel):
    """Full extracted FMR dataset, fit results, and quality warnings."""

    geometry: Geometry
    initial_perpendicular_field_t: float
    initial_linewidth_pp_oe: float | None
    measurements: list[ResonancePoint]
    included_measurement_count: int
    kittel_fit: KittelFitResult | None
    linewidth_fit: LinewidthFitResult | None
    fit_error: str | None = Field(description="Why no magnetic-property fit is available.")
    linewidth_fit_error: str | None = Field(
        description="Why the linewidth fit alone is unavailable while the Kittel fit succeeded."
    )
    warnings: list[str]


class TraceResponse(BaseModel):
    """Measured lock-in trace and its fitted derivative-Lorentzian curve."""

    measurement_id: str
    filename: str
    frequency_ghz: float
    resonance_field_oe: float | None
    linewidth_pp_oe: float | None
    r_squared: float | None
    low_quality: bool
    extraction_error: str | None
    field_oe: list[float]
    signal: list[float]
    fit_signal: list[float]


class DatasetUploadResponse(BaseModel):
    """Result of accepting a replacement dataset."""

    measurement_count: int
    geometry: Geometry
