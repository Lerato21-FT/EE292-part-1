"""Scientific processing pipelines for field-swept FMR measurements."""

from __future__ import annotations

import csv
import logging
import math
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

from app.models import Geometry

LOGGER = logging.getLogger(__name__)

# CODATA 2018: μB/h = e/(4π mₑ) = 1.39962449361e10 Hz/T.
BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T = 13.9962449361
OE_TO_TESLA = 1e-4
FREQUENCY_PATTERN = re.compile(r"-(\d+(?:\.\d+)?)MHz", re.IGNORECASE)
MODULATION_PATTERN = re.compile(r"(\d+(?:\.\d+)?)OeRMS", re.IGNORECASE)

DEFAULT_IN_PLANE_FIELD_T = 0.9
DEFAULT_OUT_OF_PLANE_FIELD_T = -0.4
DEFAULT_OUT_OF_PLANE_LINEWIDTH_PP_OE = 10.0
# Resonance fits explaining less than 98 % of the signal variance are flagged for inspection.
# The threshold and its reasoning are recorded in PROMPT.md.
RESONANCE_R_SQUARED_THRESHOLD = 0.98
# Peak-to-peak modulation above ΔHpp/3 measurably broadens and distorts the derivative line.
MODULATION_LINEWIDTH_RATIO = 1.0 / 3.0
# Fraction of a parameter's allowed range within which a fit is reported as "at a bound".
BOUND_TOLERANCE = 1e-4
# Damping is reported as not established when the linewidth line explains less than half
# of the linewidth variance, or when ΔH0 is negative by more than two standard errors
# (a physical inhomogeneous linewidth cannot be negative). Reasoning in PROMPT.md.
LINEWIDTH_R_SQUARED_THRESHOLD = 0.5


@dataclass(frozen=True, slots=True)
class ResonanceFit:
    """Result of fitting one field-modulated derivative resonance line."""

    center_oe: float
    linewidth_pp_oe: float
    signal_fit: list[float]
    r_squared: float


@dataclass(frozen=True, slots=True)
class KittelFit:
    """Kittel fit parameters with 1σ standard errors and goodness of fit."""

    g_factor: float
    effective_perpendicular_field_t: float
    fourfold_field_t: float | None
    r_squared: float
    g_factor_sigma: float | None = None
    effective_perpendicular_field_sigma_t: float | None = None
    fourfold_field_sigma_t: float | None = None
    at_bound: list[str] = dataclass_field(default_factory=list)
    mirror_effective_perpendicular_field_t: float | None = None
    mirror_fourfold_field_t: float | None = None


@dataclass(frozen=True, slots=True)
class LinewidthFit:
    """Linear linewidth fit, derived Gilbert damping, and their 1σ standard errors."""

    slope_oe_per_ghz: float
    intercept_oe: float
    damping: float
    r_squared: float
    slope_sigma_oe_per_ghz: float = 0.0
    intercept_sigma_oe: float = 0.0
    damping_sigma: float = 0.0
    damping_resolved: bool = True
    damping_concerns: list[str] = dataclass_field(default_factory=list)

    @property
    def damping_established(self) -> bool:
        """True when no concern undermines the damping value."""
        return not self.damping_concerns


@dataclass(frozen=True, slots=True)
class Measurement:
    """One loaded lock-in field sweep."""

    measurement_id: str
    filename: str
    frequency_ghz: float
    field_oe: list[float]
    signal: list[float]
    modulation_rms_oe: float | None = None


class MeasurementNotFoundError(ValueError):
    """Raised when a requested measurement ID is not present in the dataset."""


def _coefficient_of_determination(observed: np.ndarray, predicted: np.ndarray) -> float:
    """Return R-squared, including a defined result for constant observations."""
    residual_sum = float(np.sum((observed - predicted) ** 2))
    total_sum = float(np.sum((observed - np.mean(observed)) ** 2))
    if total_sum == 0:
        return 1.0 if residual_sum == 0 else 0.0
    return 1.0 - residual_sum / total_sum


def _standard_errors(covariance: np.ndarray) -> list[float | None]:
    """Return 1σ errors from a covariance matrix, or None where it is undetermined."""
    errors: list[float | None] = []
    for variance in np.diag(covariance):
        value = float(variance)
        errors.append(math.sqrt(value) if math.isfinite(value) and value >= 0 else None)
    return errors


def _parameters_at_bounds(
    names: list[str], parameters: np.ndarray, lower: list[float], upper: list[float]
) -> list[str]:
    """Name the parameters that ended within BOUND_TOLERANCE of their allowed range."""
    pinned = []
    for name, value, low, high in zip(names, parameters, lower, upper, strict=True):
        tolerance = BOUND_TOLERANCE * (high - low)
        if value - low <= tolerance or high - value <= tolerance:
            pinned.append(name)
    return pinned


def _derivative_lorentzian(
    field_oe: np.ndarray,
    amplitude: float,
    center_oe: float,
    half_width_oe: float,
    offset: float,
    slope: float,
) -> np.ndarray:
    """Model the lock-in derivative of a Lorentzian absorption line plus baseline."""
    displacement = field_oe - center_oe
    denominator = displacement**2 + half_width_oe**2
    return (
        offset
        + slope * displacement
        + amplitude * 2.0 * half_width_oe**2 * displacement / denominator**2
    )


def fit_derivative_signal(
    field_oe: list[float], signal: list[float], initial_linewidth_pp_oe: float | None = None
) -> ResonanceFit:
    """Fit a derivative-Lorentzian resonance and return its peak-to-peak linewidth."""
    field = np.asarray(field_oe, dtype=float)
    values = np.asarray(signal, dtype=float)
    if field.ndim != 1 or values.ndim != 1 or field.size != values.size:
        raise ValueError("Field and signal must be one-dimensional arrays of equal length.")
    if field.size < 8 or not np.all(np.isfinite(field)) or not np.all(np.isfinite(values)):
        raise ValueError("A resonance trace needs at least eight finite field and signal samples.")

    order = np.argsort(field)
    field = field[order]
    values = values[order]
    unique_field, inverse, counts = np.unique(field, return_inverse=True, return_counts=True)
    if unique_field.size < 8:
        raise ValueError("A resonance trace needs at least eight distinct field samples.")
    unique_signal = np.bincount(inverse, weights=values) / counts
    steps = np.diff(unique_field)

    span = float(unique_field[-1] - unique_field[0])
    if span <= 0:
        raise ValueError("Field sweep must cover a non-zero range.")
    gradient = np.gradient(unique_signal, unique_field)
    initial_center = float(unique_field[int(np.argmax(np.abs(gradient)))])
    step_size = float(np.median(steps))
    initial_width = min(max(span * 0.02, step_size), span * 0.25)
    if initial_linewidth_pp_oe is not None:
        if not math.isfinite(initial_linewidth_pp_oe) or initial_linewidth_pp_oe <= 0:
            raise ValueError("Initial peak-to-peak linewidth must be finite and positive.")
        initial_width = min(
            max(initial_linewidth_pp_oe * math.sqrt(3.0) / 2.0, step_size), span * 0.25
        )
    signal_scale = float(np.max(np.abs(values - np.median(values))))
    initial_amplitude = max(signal_scale * initial_width * 2.0, np.finfo(float).tiny)

    try:
        parameters, _ = curve_fit(
            _derivative_lorentzian,
            field,
            values,
            p0=[
                initial_amplitude,
                initial_center,
                initial_width,
                float(np.median(values)),
                0.0,
            ],
            bounds=(
                [-np.inf, unique_field[0], step_size * 0.1, -np.inf, -np.inf],
                [np.inf, unique_field[-1], span, np.inf, np.inf],
            ),
            maxfev=50_000,
        )
    except RuntimeError as error:
        raise ValueError("Could not fit the derivative-Lorentzian resonance line.") from error
    fitted_values = _derivative_lorentzian(field, *parameters)
    fitted_center = float(parameters[1])
    half_width = float(parameters[2])
    return ResonanceFit(
        center_oe=fitted_center,
        linewidth_pp_oe=2.0 * half_width / math.sqrt(3.0),
        signal_fit=_derivative_lorentzian(np.asarray(field_oe, dtype=float), *parameters).tolist(),
        r_squared=_coefficient_of_determination(values, fitted_values),
    )


def _kittel_frequency(
    field_t: np.ndarray,
    g_factor: float,
    effective_perpendicular_field_t: float,
    fourfold_field_t: float,
) -> np.ndarray:
    """Evaluate the aligned-axis in-plane Kittel model in GHz."""
    longitudinal_field = field_t + fourfold_field_t
    transverse_field = longitudinal_field + effective_perpendicular_field_t
    return (
        BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T
        * g_factor
        * np.sqrt(longitudinal_field * transverse_field)
    )


def fit_kittel(
    field_oe: list[float],
    frequency_ghz: list[float],
    initial_perpendicular_field_t: float = DEFAULT_IN_PLANE_FIELD_T,
) -> KittelFit:
    """Fit g, effective perpendicular field, and aligned-axis fourfold field.

    The effective perpendicular field is bounded to 1e-5–2 T: this in-plane model cannot
    represent a film whose perpendicular anisotropy exceeds its demagnetizing field.
    Parameters that end at a bound are named in `at_bound`.

    The model has an exact mirror solution: (Beff,⊥, B4) and (−Beff,⊥, B4 + Beff,⊥) give
    the same curve, because the two field factors under the square root swap. The bound
    Beff,⊥ > 0 always picks the first. When the mirror's B4 also lies inside the B4 fit
    range, the data alone cannot tell the two apart, and the mirror is returned in the
    `mirror_*` fields.
    """
    field = np.asarray(field_oe, dtype=float) * OE_TO_TESLA
    frequency = np.asarray(frequency_ghz, dtype=float)
    if field.ndim != 1 or frequency.ndim != 1 or field.size != frequency.size:
        raise ValueError("Resonance field and frequency arrays must have equal length.")
    if field.size < 4 or not np.all(np.isfinite(field)) or not np.all(np.isfinite(frequency)):
        raise ValueError("Kittel fitting needs at least four finite resonance points.")
    if not 0.0 <= initial_perpendicular_field_t <= 2.0:
        raise ValueError("Initial perpendicular field must be between 0 and 2 T.")
    if np.any(frequency <= 0):
        raise ValueError("Resonance frequencies must be positive.")
    if np.any(field <= 0):
        raise ValueError("The in-plane Kittel model requires positive resonance fields.")

    minimum_fourfold_field = max(-0.5, -float(np.min(field)) + 1e-7)
    if minimum_fourfold_field >= 0.5:
        raise ValueError("Measured resonance fields do not support the fourfold fit range.")
    lower = [1.0, 1e-5, minimum_fourfold_field]
    upper = [4.0, 2.0, 0.5]
    initial_fourfold = min(max(0.0, minimum_fourfold_field + 1e-6), 0.499)
    try:
        parameters, covariance = curve_fit(
            _kittel_frequency,
            field,
            frequency,
            p0=[2.0, min(max(initial_perpendicular_field_t, 1e-4), 1.999), initial_fourfold],
            bounds=(lower, upper),
            maxfev=50_000,
        )
    except RuntimeError as error:
        raise ValueError("Could not fit the aligned-axis Kittel model.") from error
    predicted = _kittel_frequency(field, *parameters)
    errors = _standard_errors(covariance)
    mirror_fourfold = float(parameters[2] + parameters[1])
    mirror_is_allowed = lower[2] <= mirror_fourfold <= upper[2]
    return KittelFit(
        g_factor=float(parameters[0]),
        effective_perpendicular_field_t=float(parameters[1]),
        fourfold_field_t=float(parameters[2]),
        r_squared=_coefficient_of_determination(frequency, predicted),
        g_factor_sigma=errors[0],
        effective_perpendicular_field_sigma_t=errors[1],
        fourfold_field_sigma_t=errors[2],
        at_bound=_parameters_at_bounds(
            ["g_factor", "effective_perpendicular_field_t", "fourfold_field_t"],
            parameters,
            lower,
            upper,
        ),
        mirror_effective_perpendicular_field_t=-float(parameters[1]) if mirror_is_allowed else None,
        mirror_fourfold_field_t=mirror_fourfold if mirror_is_allowed else None,
    )


def _out_of_plane_frequency(
    field_t: np.ndarray, g_factor: float, effective_perpendicular_field_t: float
) -> np.ndarray:
    """Evaluate the saturated perpendicular model using Beff = μ0 Ms − μ0 H2⊥."""
    return (
        BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T * g_factor * (field_t - effective_perpendicular_field_t)
    )


def fit_out_of_plane_kittel(
    field_oe: list[float],
    frequency_ghz: list[float],
    initial_perpendicular_field_t: float = DEFAULT_OUT_OF_PLANE_FIELD_T,
) -> KittelFit:
    """Fit g and signed effective field for a saturated perpendicular field sweep."""
    field = np.asarray(field_oe, dtype=float) * OE_TO_TESLA
    frequency = np.asarray(frequency_ghz, dtype=float)
    if (
        field.ndim != 1
        or frequency.ndim != 1
        or field.size != frequency.size
        or field.size < 4
        or not np.all(np.isfinite(field))
        or not np.all(np.isfinite(frequency))
    ):
        raise ValueError("Out-of-plane Kittel fitting needs at least four finite resonance points.")
    if np.any(field < 0) or np.any(frequency <= 0):
        raise ValueError("Use nonnegative resonance fields and positive frequencies.")
    if np.unique(field).size < 2:
        raise ValueError("Out-of-plane fitting needs distinct resonance fields.")
    if (
        not math.isfinite(initial_perpendicular_field_t)
        or not -2 <= initial_perpendicular_field_t <= 2
    ):
        raise ValueError("Initial effective perpendicular field must be between −2 and 2 T.")
    upper_field = min(2.0, float(np.min(field)) - 1e-8)
    initial_field = min(initial_perpendicular_field_t, upper_field - 1e-8)
    initial_field = max(-2 + 1e-8, initial_field)
    lower = [1.0, -2.0]
    upper = [4.0, upper_field]
    try:
        parameters, covariance = curve_fit(
            _out_of_plane_frequency,
            field,
            frequency,
            p0=[2.0, initial_field],
            bounds=(lower, upper),
            maxfev=50_000,
        )
    except RuntimeError as error:
        raise ValueError("Could not fit the saturated out-of-plane Kittel model.") from error
    errors = _standard_errors(covariance)
    return KittelFit(
        g_factor=float(parameters[0]),
        effective_perpendicular_field_t=float(parameters[1]),
        fourfold_field_t=None,
        r_squared=_coefficient_of_determination(
            frequency, _out_of_plane_frequency(field, *parameters)
        ),
        g_factor_sigma=errors[0],
        effective_perpendicular_field_sigma_t=errors[1],
        at_bound=_parameters_at_bounds(
            ["g_factor", "effective_perpendicular_field_t"], parameters, lower, upper
        ),
    )


def fit_linewidth(
    frequency_ghz: list[float],
    linewidth_pp_oe: list[float],
    g_factor: float,
    g_factor_sigma: float | None = None,
) -> LinewidthFit:
    """Fit peak-to-peak linewidth versus frequency and derive Gilbert damping.

    The slope and intercept come from ordinary least squares, with standard errors
    from the residual variance s² = SSR/(n − 2). The damping error combines the slope
    and g-factor errors in quadrature, treating them as independent. Damping is marked
    unresolved when the slope is within two standard errors of zero.

    `damping_concerns` lists every reason the damping value is not established: an
    unresolved slope, a linewidth R² below LINEWIDTH_R_SQUARED_THRESHOLD, or an
    intercept ΔH0 that is negative by more than two standard errors.
    """
    frequency = np.asarray(frequency_ghz, dtype=float)
    linewidth = np.asarray(linewidth_pp_oe, dtype=float)
    if frequency.ndim != 1 or linewidth.ndim != 1 or frequency.size != linewidth.size:
        raise ValueError("Frequency and linewidth arrays must have equal length.")
    if (
        frequency.size < 3
        or not np.all(np.isfinite(frequency))
        or not np.all(np.isfinite(linewidth))
    ):
        raise ValueError("Linewidth fitting needs at least three finite measurements.")
    if g_factor <= 0 or not math.isfinite(g_factor):
        raise ValueError("The Landé g factor must be finite and positive.")
    if g_factor_sigma is not None and (not math.isfinite(g_factor_sigma) or g_factor_sigma < 0):
        raise ValueError("The g-factor uncertainty must be finite and nonnegative.")

    count = frequency.size
    mean_frequency = float(np.mean(frequency))
    centered = frequency - mean_frequency
    sum_squares = float(np.sum(centered**2))
    if sum_squares == 0:
        raise ValueError("Linewidth fitting needs at least two distinct frequencies.")
    slope = float(np.sum(centered * (linewidth - np.mean(linewidth))) / sum_squares)
    intercept = float(np.mean(linewidth)) - slope * mean_frequency
    predicted = slope * frequency + intercept
    residual_variance = float(np.sum((linewidth - predicted) ** 2)) / (count - 2)
    slope_sigma = math.sqrt(residual_variance / sum_squares)
    intercept_sigma = math.sqrt(residual_variance * (1 / count + mean_frequency**2 / sum_squares))
    if slope < 0:
        raise ValueError(
            f"Fitted linewidth decreases with frequency ({slope:.3g} ± {slope_sigma:.2g} Oe/GHz); "
            "damping is not resolved by these sweeps."
        )

    # α = (√3/2) · slope · γ/2π, with the slope converted from Oe/GHz to T/Hz.
    damping_per_slope_and_g = (
        math.sqrt(3.0) / 2.0 * OE_TO_TESLA / 1e9 * BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T * 1e9
    )
    damping = damping_per_slope_and_g * slope * g_factor
    damping_sigma = damping_per_slope_and_g * math.hypot(
        g_factor * slope_sigma, slope * (g_factor_sigma or 0.0)
    )
    r_squared = _coefficient_of_determination(linewidth, predicted)
    damping_resolved = slope > 2 * slope_sigma
    concerns = []
    if not damping_resolved:
        concerns.append("the linewidth slope is within two standard errors of zero")
    if r_squared < LINEWIDTH_R_SQUARED_THRESHOLD:
        concerns.append(
            f"the linewidth fit has R² = {r_squared:.3f}, below {LINEWIDTH_R_SQUARED_THRESHOLD}"
        )
    if intercept + 2 * intercept_sigma < 0:
        concerns.append(
            f"ΔH0 = {intercept:.3g} ± {intercept_sigma:.2g} Oe is negative by more than 2σ"
        )
    return LinewidthFit(
        slope_oe_per_ghz=slope,
        intercept_oe=intercept,
        damping=damping,
        r_squared=r_squared,
        slope_sigma_oe_per_ghz=slope_sigma,
        intercept_sigma_oe=intercept_sigma,
        damping_sigma=damping_sigma,
        damping_resolved=damping_resolved,
        damping_concerns=concerns,
    )


def _frequency_from_filename(filename: str) -> float:
    """Read the sweep frequency in GHz from a `...-NNNNNMHz-...csv` filename."""
    match = FREQUENCY_PATTERN.search(filename)
    if match is None:
        raise ValueError(f"Cannot find a frequency in measurement filename {filename!r}.")
    frequency = float(match.group(1)) / 1000.0
    if not math.isfinite(frequency) or frequency <= 0:
        raise ValueError(f"Measurement frequency must be finite and positive: {filename}.")
    return frequency


def _modulation_from_filename(filename: str) -> float | None:
    """Read an optional `...N.NOeRMS...` field-modulation amplitude from a filename."""
    match = MODULATION_PATTERN.search(filename)
    return float(match.group(1)) if match else None


def list_measurement_files(directory: Path) -> list[tuple[str, float]]:
    """List CSV sweeps with their parsed GHz frequencies in ascending order."""
    if not directory.is_dir():
        LOGGER.error("Measurement directory does not exist: %s", directory)
        raise ValueError("The measurement directory is not available.")
    files = sorted(directory.glob("*.csv"))
    if not files:
        LOGGER.error("No CSV measurements found in %s", directory)
        raise ValueError("No CSV measurements were found in the active dataset.")
    measurements = [(path.name, _frequency_from_filename(path.name)) for path in files]
    return sorted(measurements, key=lambda item: (item[1], item[0]))


def load_measurement(directory: Path, filename: str) -> Measurement:
    """Load field and lock-in columns from one measurement CSV listed in `directory`."""
    available_files = {name for name, _ in list_measurement_files(directory)}
    if filename not in available_files:
        raise MeasurementNotFoundError("Unknown measurement file.")
    return _read_measurement(directory, filename)


def _read_measurement(directory: Path, filename: str) -> Measurement:
    """Parse one CSV whose name has already been checked against the directory listing."""
    field: list[float] = []
    signal: list[float] = []
    path = directory / filename
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ValueError(f"Could not read measurement file {filename}: {error.strerror}") from error
    for line_number, row in enumerate(csv.reader(content.splitlines()), start=1):
        if not row or all(not value.strip() for value in row):
            continue
        if len(row) < 2:
            raise ValueError(f"{filename}:{line_number} has fewer than two columns.")
        try:
            field_value, signal_value = float(row[0]), float(row[1])
        except ValueError as error:
            raise ValueError(f"{filename}:{line_number} has non-numeric data.") from error
        if not math.isfinite(field_value) or not math.isfinite(signal_value):
            raise ValueError(f"{filename}:{line_number} contains a non-finite value.")
        field.append(field_value)
        signal.append(signal_value)

    if len(field) < 8:
        raise ValueError(f"{filename} contains fewer than eight valid data rows.")
    frequency_ghz = _frequency_from_filename(filename)
    return Measurement(
        filename, filename, frequency_ghz, field, signal, _modulation_from_filename(filename)
    )


def resolve_analysis_settings(
    geometry: Geometry,
    initial_perpendicular_field_t: float | None,
    initial_linewidth_pp_oe: float | None,
) -> tuple[float, float | None]:
    """Apply geometry defaults and validate settings, independently of fit success."""
    if geometry not in {"in_plane", "out_of_plane"}:
        raise ValueError("Geometry must be in_plane or out_of_plane.")
    if initial_perpendicular_field_t is None:
        initial_perpendicular_field_t = (
            DEFAULT_OUT_OF_PLANE_FIELD_T if geometry == "out_of_plane" else DEFAULT_IN_PLANE_FIELD_T
        )
    minimum = -2 if geometry == "out_of_plane" else 0
    if (
        not math.isfinite(initial_perpendicular_field_t)
        or not minimum <= initial_perpendicular_field_t <= 2
    ):
        raise ValueError(
            f"Initial effective perpendicular field must be between {minimum} and 2 T."
        )
    if initial_linewidth_pp_oe is None and geometry == "out_of_plane":
        initial_linewidth_pp_oe = DEFAULT_OUT_OF_PLANE_LINEWIDTH_PP_OE
    if initial_linewidth_pp_oe is not None and (
        not math.isfinite(initial_linewidth_pp_oe) or not 0 < initial_linewidth_pp_oe <= 10000
    ):
        raise ValueError(
            "Initial peak-to-peak linewidth must be finite and between 0 and 10000 Oe."
        )
    return initial_perpendicular_field_t, initial_linewidth_pp_oe


def validate_dataset(
    directory: Path,
    initial_perpendicular_field_t: float | None = None,
    *,
    geometry: Geometry = "in_plane",
    initial_linewidth_pp_oe: float | None = None,
) -> None:
    """Validate settings and every CSV without requiring a successful scientific fit."""
    resolve_analysis_settings(geometry, initial_perpendicular_field_t, initial_linewidth_pp_oe)
    for filename, _ in list_measurement_files(directory):
        _read_measurement(directory, filename)


def _extract_resonance(
    measurement: Measurement, initial_linewidth_pp_oe: float | None
) -> tuple[ResonanceFit | None, str | None]:
    """Preserve a failed extraction as an explicit error alongside the raw measurement."""
    try:
        return (
            fit_derivative_signal(
                measurement.field_oe, measurement.signal, initial_linewidth_pp_oe
            ),
            None,
        )
    except ValueError as error:
        return None, str(error)


def _is_low_quality(fit: ResonanceFit | None) -> bool:
    """A resonance fit below the R² threshold needs a human look before it is trusted."""
    return fit is not None and fit.r_squared < RESONANCE_R_SQUARED_THRESHOLD


def _modulation_pp_oe(measurement: Measurement) -> float | None:
    """Peak-to-peak amplitude of sinusoidal field modulation: 2√2 times its RMS value."""
    if measurement.modulation_rms_oe is None:
        return None
    return 2.0 * math.sqrt(2.0) * measurement.modulation_rms_oe


def _modulation_broadens(measurement: Measurement, fit: ResonanceFit | None) -> bool:
    """True when peak-to-peak modulation exceeds MODULATION_LINEWIDTH_RATIO · ΔHpp."""
    modulation = _modulation_pp_oe(measurement)
    if modulation is None or fit is None:
        return False
    return modulation > MODULATION_LINEWIDTH_RATIO * fit.linewidth_pp_oe


def analyze_trace(
    directory: Path, measurement_id: str, initial_linewidth_pp_oe: float | None = None
) -> dict[str, object]:
    """Return raw samples even when a derivative resonance cannot be fitted."""
    measurement = load_measurement(directory, measurement_id)
    fit, error = _extract_resonance(measurement, initial_linewidth_pp_oe)
    return {
        "measurement_id": measurement.measurement_id,
        "filename": measurement.filename,
        "frequency_ghz": measurement.frequency_ghz,
        "resonance_field_oe": fit.center_oe if fit else None,
        "linewidth_pp_oe": fit.linewidth_pp_oe if fit else None,
        "r_squared": fit.r_squared if fit else None,
        "low_quality": _is_low_quality(fit),
        "extraction_error": error,
        "field_oe": measurement.field_oe,
        "signal": measurement.signal,
        "fit_signal": fit.signal_fit if fit else [],
    }


def _summarize_names(names: list[str]) -> str:
    """List up to three names, then a count of the rest."""
    shown = ", ".join(names[:3])
    return shown if len(names) <= 3 else f"{shown} and {len(names) - 3} more"


def analyze_dataset(
    directory: Path,
    initial_perpendicular_field_t: float | None = None,
    *,
    geometry: Geometry = "in_plane",
    initial_linewidth_pp_oe: float | None = None,
    excluded_measurement_ids: list[str] | None = None,
) -> dict[str, object]:
    """Return inspectable sweeps, property fits or explicit fit errors, and warnings."""
    initial_perpendicular_field_t, initial_linewidth_pp_oe = resolve_analysis_settings(
        geometry, initial_perpendicular_field_t, initial_linewidth_pp_oe
    )
    files = list_measurement_files(directory)
    excluded = set(excluded_measurement_ids or [])
    if len(excluded) != len(excluded_measurement_ids or []):
        raise ValueError("Duplicate excluded measurement IDs are not allowed.")
    if excluded - {filename for filename, _ in files}:
        raise ValueError("Unknown excluded measurement ID; select a dataset from the active plots.")
    measurements = [_read_measurement(directory, filename) for filename, _ in files]
    resonance_fits = [
        (measurement, *_extract_resonance(measurement, initial_linewidth_pp_oe))
        for measurement in measurements
    ]
    included_fits = [
        (measurement, fit, error)
        for measurement, fit, error in resonance_fits
        if measurement.measurement_id not in excluded
    ]
    warnings = _sweep_warnings(included_fits)
    result: dict[str, object] = {
        "geometry": geometry,
        "initial_perpendicular_field_t": initial_perpendicular_field_t,
        "initial_linewidth_pp_oe": initial_linewidth_pp_oe,
        "included_measurement_count": len(included_fits),
        "measurements": [
            {
                "measurement_id": measurement.measurement_id,
                "filename": measurement.filename,
                "frequency_ghz": measurement.frequency_ghz,
                "resonance_field_oe": fit.center_oe if fit else None,
                "linewidth_pp_oe": fit.linewidth_pp_oe if fit else None,
                "resonance_r_squared": fit.r_squared if fit else None,
                "low_quality": _is_low_quality(fit),
                "modulation_rms_oe": measurement.modulation_rms_oe,
                "modulation_pp_oe": _modulation_pp_oe(measurement),
                "modulation_warning": _modulation_broadens(measurement, fit),
                "extraction_error": error,
                "excluded": measurement.measurement_id in excluded,
            }
            for measurement, fit, error in resonance_fits
        ],
        "kittel_fit": None,
        "linewidth_fit": None,
        "fit_error": None,
        "linewidth_fit_error": None,
        "warnings": warnings,
    }
    try:
        failed = [measurement.filename for measurement, fit, _ in included_fits if fit is None]
        if failed:
            raise ValueError(
                f"Resonance fitting failed for {failed[0]}"
                f" ({len(failed)} included sweep(s)). Inspect raw traces and exclude these "
                "datasets before fitting magnetic properties."
            )
        if len(included_fits) < 4:
            raise ValueError(
                "Both magnetic-property fits need at least four included measurements. "
                "Restore datasets or exclude fewer points."
            )
        result.update(
            _fit_magnetic_properties(
                [(measurement, fit) for measurement, fit, _ in included_fits if fit is not None],
                initial_perpendicular_field_t,
                geometry,
                warnings,
            )
        )
    except ValueError as error:
        result["fit_error"] = str(error)
    result["summary"] = summarize_analysis(result)
    return result


def _with_sigma(value: float, sigma: float | None, digits: int) -> str:
    """Format a value with its 1σ error, or the value alone when the error is undetermined."""
    text = f"{value:.{digits}f}"
    return text if sigma is None else f"{text} ± {sigma:.2g}"


def summarize_analysis(result: dict[str, object]) -> list[str]:
    """State the analysis outcome in two or three plain sentences for the page's first screen.

    Every judgement here (a failed fit, damping not established, warnings raised) comes
    from the fields already computed in `result`; nothing is re-derived.
    """
    count = result["included_measurement_count"]
    geometry = "in-plane" if result["geometry"] == "in_plane" else "out-of-plane"
    kittel = result["kittel_fit"]
    linewidth = result["linewidth_fit"]
    warnings = result["warnings"]
    if kittel is None:
        return [
            f"No magnetic properties are reported yet for these {count} included sweeps.",
            str(result["fit_error"]),
        ]
    g_text = _with_sigma(kittel["g_factor"], kittel["g_factor_sigma"], 4)
    field_text = _with_sigma(
        kittel["effective_perpendicular_field_t"],
        kittel["effective_perpendicular_field_sigma_t"],
        4,
    )
    fourfold = ""
    if kittel["fourfold_field_t"] is not None:
        fourfold_text = _with_sigma(kittel["fourfold_field_t"], kittel["fourfold_field_sigma_t"], 4)
        fourfold = f" and B4 = {fourfold_text} T"
    sentences = [
        f"From {count} included sweeps, the {geometry} Kittel fit gives g = {g_text}, "
        f"Beff,⊥ = {field_text} T{fourfold} (R² = {kittel['r_squared']:.3f})."
    ]
    if linewidth is None:
        sentences.append(f"Damping is unavailable: {result['linewidth_fit_error']}")
    else:
        damping = f"α = {linewidth['damping']:.3g} ± {linewidth['damping_sigma']:.2g}"
        if linewidth["damping_established"]:
            sentences.append(
                f"The Gilbert damping is {damping} (linewidth R² = {linewidth['r_squared']:.3f})."
            )
        else:
            sentences.append(
                f"The Gilbert damping {damping} is not established: "
                f"{'; '.join(linewidth['damping_concerns'])}."
            )
    sentences.append(
        f"Read the {len(warnings)} warning(s) below before relying on these values."
        if warnings
        else "No quality warnings were raised for the included sweeps."
    )
    return sentences


def _sweep_warnings(
    included_fits: list[tuple[Measurement, ResonanceFit | None, str | None]],
) -> list[str]:
    """Explain per-sweep quality concerns among the measurements used by the fits."""
    warnings = []
    low_quality = [m.filename for m, fit, _ in included_fits if _is_low_quality(fit)]
    if low_quality:
        warnings.append(
            f"{len(low_quality)} included sweep(s) have resonance R² below "
            f"{RESONANCE_R_SQUARED_THRESHOLD}: {_summarize_names(low_quality)}. Inspect their "
            "raw traces and exclude them if the line shape is not a single resonance."
        )
    broadened = [m.filename for m, fit, _ in included_fits if _modulation_broadens(m, fit)]
    if broadened:
        warnings.append(
            f"{len(broadened)} included sweep(s) have peak-to-peak field modulation above "
            f"ΔHpp/3: {_summarize_names(broadened)}. Modulation broadening may bias their "
            "linewidths, ΔH0 and damping."
        )
    return warnings


def _fit_magnetic_properties(
    included_fits: list[tuple[Measurement, ResonanceFit]],
    initial_perpendicular_field_t: float,
    geometry: Geometry,
    warnings: list[str],
) -> dict[str, object]:
    """Fit the Kittel model, then the linewidth model, against the same included resonances.

    A failed linewidth fit is reported in `linewidth_fit_error` and does not discard a
    successful Kittel fit. New warnings are appended to `warnings`.
    """
    frequencies = [measurement.frequency_ghz for measurement, _ in included_fits]
    fields = [fit.center_oe for _, fit in included_fits]
    linewidths = [fit.linewidth_pp_oe for _, fit in included_fits]
    if geometry == "out_of_plane":
        negative = [
            f"{measurement.filename} ({fit.center_oe:.2f} Oe)"
            for measurement, fit in included_fits
            if fit.center_oe < 0
        ]
        if negative:
            raise ValueError(
                "The current perpendicular model requires nonnegative resonance fields. "
                f"Negative fitted resonances ({len(negative)}): {', '.join(negative[:3])}. "
                "Inspect these raw sweeps and exclude the affected datasets to fit the "
                "remaining positive-branch points. Signed fields are preserved."
            )
        kittel = fit_out_of_plane_kittel(fields, frequencies, initial_perpendicular_field_t)
        equation = "f = (g μB/h) (Bres − Beff,⊥)"
    else:
        nonpositive = [
            f"{measurement.filename} ({fit.center_oe:.2f} Oe)"
            for measurement, fit in included_fits
            if fit.center_oe <= 0
        ]
        if nonpositive:
            raise ValueError(
                "The in-plane Kittel model requires positive resonance fields. "
                f"Zero or negative fitted resonances ({len(nonpositive)}): "
                f"{', '.join(nonpositive[:3])}. Inspect these raw sweeps and exclude the "
                "affected datasets to fit the remaining points. Signed fields are preserved."
            )
        kittel = fit_kittel(fields, frequencies, initial_perpendicular_field_t)
        equation = "f = (g μB/h) √[(Bres + B4)(Bres + B4 + Beff,⊥)]"
    if kittel.at_bound:
        warnings.append(
            f"Kittel parameter(s) at a fit bound: {', '.join(kittel.at_bound)}. A value at a "
            "bound is a limit of the model, not a measurement; check the geometry and seed."
        )
    if kittel.mirror_effective_perpendicular_field_t is not None:
        warnings.append(
            "The in-plane Kittel model has a mirror solution that fits these points equally "
            f"well: Beff,⊥ = {kittel.mirror_effective_perpendicular_field_t:.4g} T with "
            f"B4 = {kittel.mirror_fourfold_field_t:.4g} T. The fit bounds picked "
            f"Beff,⊥ = {kittel.effective_perpendicular_field_t:.4g} T > 0 by assumption, not "
            "from the data; an independent measurement (out-of-plane sweeps or Ms) is "
            "needed to choose between them."
        )

    field_min, field_max = min(fields), max(fields)
    field_curve = np.linspace(field_min, field_max, 300)
    if geometry == "out_of_plane":
        frequency_curve = _out_of_plane_frequency(
            field_curve * OE_TO_TESLA, kittel.g_factor, kittel.effective_perpendicular_field_t
        )
    else:
        frequency_curve = _kittel_frequency(
            field_curve * OE_TO_TESLA,
            kittel.g_factor,
            kittel.effective_perpendicular_field_t,
            kittel.fourfold_field_t,
        )
    result: dict[str, object] = {
        "kittel_fit": {
            "g_factor": kittel.g_factor,
            "g_factor_sigma": kittel.g_factor_sigma,
            "effective_perpendicular_field_t": kittel.effective_perpendicular_field_t,
            "effective_perpendicular_field_sigma_t": kittel.effective_perpendicular_field_sigma_t,
            "fourfold_field_t": kittel.fourfold_field_t,
            "fourfold_field_sigma_t": kittel.fourfold_field_sigma_t,
            "r_squared": kittel.r_squared,
            "at_bound": kittel.at_bound,
            "mirror_effective_perpendicular_field_t": (
                kittel.mirror_effective_perpendicular_field_t
            ),
            "mirror_fourfold_field_t": kittel.mirror_fourfold_field_t,
            "equation": equation,
            "curve": [
                {"field_oe": float(field), "frequency_ghz": float(frequency)}
                for field, frequency in zip(field_curve, frequency_curve, strict=True)
            ],
        },
        "linewidth_fit": None,
        "linewidth_fit_error": None,
    }

    try:
        linewidth_fit = fit_linewidth(
            frequencies, linewidths, kittel.g_factor, kittel.g_factor_sigma
        )
    except ValueError as error:
        result["linewidth_fit_error"] = str(error)
        return result
    if not linewidth_fit.damping_resolved:
        warnings.append(
            "The linewidth slope is within two standard errors of zero; the damping value "
            "is consistent with zero and is not resolved by these sweeps."
        )
    if not linewidth_fit.damping_established:
        warnings.append(
            "Damping is not established: "
            + "; ".join(linewidth_fit.damping_concerns)
            + ". Inspect the linewidth plot and exclude outlying sweeps before relying on α."
        )
    frequency_min, frequency_max = min(frequencies), max(frequencies)
    linewidth_curve_frequency = np.linspace(frequency_min, frequency_max, 200)
    linewidth_curve = (
        linewidth_fit.slope_oe_per_ghz * linewidth_curve_frequency + linewidth_fit.intercept_oe
    )
    result["linewidth_fit"] = {
        "slope_oe_per_ghz": linewidth_fit.slope_oe_per_ghz,
        "slope_sigma_oe_per_ghz": linewidth_fit.slope_sigma_oe_per_ghz,
        "intercept_oe": linewidth_fit.intercept_oe,
        "intercept_sigma_oe": linewidth_fit.intercept_sigma_oe,
        "damping": linewidth_fit.damping,
        "damping_sigma": linewidth_fit.damping_sigma,
        "damping_resolved": linewidth_fit.damping_resolved,
        "damping_established": linewidth_fit.damping_established,
        "damping_concerns": linewidth_fit.damping_concerns,
        "r_squared": linewidth_fit.r_squared,
        "equation": "ΔHpp = ΔH0 + (4πα/√3γ)·f",
        "curve": [
            {"frequency_ghz": float(frequency), "linewidth_pp_oe": float(linewidth)}
            for frequency, linewidth in zip(linewidth_curve_frequency, linewidth_curve, strict=True)
        ],
    }
    return result
