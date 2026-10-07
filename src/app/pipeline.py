"""Scientific processing pipelines for field-swept FMR measurements."""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T = 13.99624555
OE_TO_TESLA = 1e-4
FREQUENCY_PATTERN = re.compile(r"-(\d+(?:\.\d+)?)MHz", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ResonanceFit:
    """Result of fitting one field-modulated derivative resonance line."""

    center_oe: float
    linewidth_pp_oe: float
    signal_fit: list[float]
    r_squared: float


@dataclass(frozen=True, slots=True)
class KittelFit:
    """Aligned-axis Kittel fit parameters and goodness of fit."""

    g_factor: float
    effective_perpendicular_field_t: float
    fourfold_field_t: float
    r_squared: float


@dataclass(frozen=True, slots=True)
class LinewidthFit:
    """Linear linewidth fit and derived Gilbert damping parameter."""

    slope_oe_per_ghz: float
    intercept_oe: float
    damping: float
    r_squared: float


@dataclass(frozen=True, slots=True)
class Measurement:
    """One loaded lock-in field sweep."""

    measurement_id: str
    filename: str
    frequency_ghz: float
    field_oe: list[float]
    signal: list[float]


class MeasurementNotFoundError(ValueError):
    """Raised when a requested measurement ID is not present in the dataset."""


def _coefficient_of_determination(observed: np.ndarray, predicted: np.ndarray) -> float:
    """Return R-squared, including a defined result for constant observations."""
    residual_sum = float(np.sum((observed - predicted) ** 2))
    total_sum = float(np.sum((observed - np.mean(observed)) ** 2))
    if total_sum == 0:
        return 1.0 if residual_sum == 0 else 0.0
    return 1.0 - residual_sum / total_sum


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


def fit_derivative_signal(field_oe: list[float], signal: list[float]) -> ResonanceFit:
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
    initial_perpendicular_field_t: float = 0.9,
) -> KittelFit:
    """Fit g, effective perpendicular field, and aligned-axis fourfold field."""
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

    minimum_fourfold_field = max(-0.5, -float(np.min(field)) + 1e-7)
    if minimum_fourfold_field >= 0.5:
        raise ValueError("Measured resonance fields do not support the fourfold fit range.")
    try:
        parameters, _ = curve_fit(
            _kittel_frequency,
            field,
            frequency,
            p0=[2.0, min(max(initial_perpendicular_field_t, 1e-4), 1.999), 0.0],
            bounds=([1.0, 1e-5, minimum_fourfold_field], [4.0, 2.0, 0.5]),
            maxfev=50_000,
        )
    except RuntimeError as error:
        raise ValueError("Could not fit the aligned-axis Kittel model.") from error
    predicted = _kittel_frequency(field, *parameters)
    return KittelFit(
        g_factor=float(parameters[0]),
        effective_perpendicular_field_t=float(parameters[1]),
        fourfold_field_t=float(parameters[2]),
        r_squared=_coefficient_of_determination(frequency, predicted),
    )


def fit_linewidth(
    frequency_ghz: list[float],
    linewidth_pp_oe: list[float],
    g_factor: float,
) -> LinewidthFit:
    """Fit peak-to-peak linewidth versus frequency and derive Gilbert damping."""
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

    slope, intercept = np.polyfit(frequency, linewidth, 1)
    predicted = slope * frequency + intercept
    if slope < 0:
        raise ValueError("Fitted linewidth decreases with frequency; damping is not physical.")

    slope_tesla_per_hz = float(slope) * OE_TO_TESLA / 1e9
    gamma_over_2pi_hz_per_t = g_factor * BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T * 1e9
    damping = slope_tesla_per_hz * math.sqrt(3.0) * gamma_over_2pi_hz_per_t / 2.0
    return LinewidthFit(
        slope_oe_per_ghz=float(slope),
        intercept_oe=float(intercept),
        damping=damping,
        r_squared=_coefficient_of_determination(linewidth, predicted),
    )


def _frequency_from_filename(filename: str) -> float:
    """Read the sweep frequency in GHz from a `...-NNNNNMHz-...csv` filename."""
    match = FREQUENCY_PATTERN.search(filename)
    if match is None:
        raise ValueError(f"Cannot find a frequency in measurement filename {filename!r}.")
    return float(match.group(1)) / 1000.0


def list_measurement_files(directory: Path) -> list[tuple[str, float]]:
    """List CSV sweeps with their parsed GHz frequencies in ascending order."""
    if not directory.is_dir():
        raise ValueError(f"Measurement directory does not exist: {directory}")
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise ValueError(f"No CSV measurements found in {directory}.")
    measurements = [(path.name, _frequency_from_filename(path.name)) for path in files]
    return sorted(measurements, key=lambda item: (item[1], item[0]))


def load_measurement(directory: Path, filename: str) -> Measurement:
    """Load field and lock-in columns from one measurement CSV."""
    available_files = {name for name, _ in list_measurement_files(directory)}
    if filename not in available_files:
        raise MeasurementNotFoundError("Unknown measurement file.")

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
    return Measurement(filename, filename, frequency_ghz, field, signal)


def analyze_dataset(
    directory: Path, initial_perpendicular_field_t: float = 0.9
) -> dict[str, object]:
    """Extract resonances, fit the Kittel model and calculate linewidth damping."""
    measurements = [
        load_measurement(directory, filename) for filename, _ in list_measurement_files(directory)
    ]
    resonance_fits = [
        (measurement, fit_derivative_signal(measurement.field_oe, measurement.signal))
        for measurement in measurements
    ]
    frequencies = [measurement.frequency_ghz for measurement, _ in resonance_fits]
    fields = [fit.center_oe for _, fit in resonance_fits]
    linewidths = [fit.linewidth_pp_oe for _, fit in resonance_fits]
    kittel = fit_kittel(fields, frequencies, initial_perpendicular_field_t)
    linewidth_fit = fit_linewidth(frequencies, linewidths, kittel.g_factor)

    field_min, field_max = min(fields), max(fields)
    field_curve = np.linspace(field_min, field_max, 300)
    frequency_curve = _kittel_frequency(
        field_curve * OE_TO_TESLA,
        kittel.g_factor,
        kittel.effective_perpendicular_field_t,
        kittel.fourfold_field_t,
    )
    frequency_min, frequency_max = min(frequencies), max(frequencies)
    linewidth_curve_frequency = np.linspace(frequency_min, frequency_max, 200)
    linewidth_curve = (
        linewidth_fit.slope_oe_per_ghz * linewidth_curve_frequency + linewidth_fit.intercept_oe
    )
    return {
        "measurements": [
            {
                "measurement_id": measurement.measurement_id,
                "filename": measurement.filename,
                "frequency_ghz": measurement.frequency_ghz,
                "resonance_field_oe": fit.center_oe,
                "linewidth_pp_oe": fit.linewidth_pp_oe,
                "resonance_r_squared": fit.r_squared,
            }
            for measurement, fit in resonance_fits
        ],
        "kittel_fit": {
            "g_factor": kittel.g_factor,
            "effective_perpendicular_field_t": kittel.effective_perpendicular_field_t,
            "fourfold_field_t": kittel.fourfold_field_t,
            "r_squared": kittel.r_squared,
            "equation": "f = (g μB/h) √[(Bres + B4)(Bres + B4 + Beff,⊥)]",
            "curve": [
                {"field_oe": float(field), "frequency_ghz": float(frequency)}
                for field, frequency in zip(field_curve, frequency_curve, strict=True)
            ],
        },
        "linewidth_fit": {
            "slope_oe_per_ghz": linewidth_fit.slope_oe_per_ghz,
            "intercept_oe": linewidth_fit.intercept_oe,
            "damping": linewidth_fit.damping,
            "r_squared": linewidth_fit.r_squared,
            "equation": "ΔHpp = ΔH0 + (4πα/√3γ)·f",
            "curve": [
                {"frequency_ghz": float(frequency), "linewidth_pp_oe": float(linewidth)}
                for frequency, linewidth in zip(
                    linewidth_curve_frequency, linewidth_curve, strict=True
                )
            ],
        },
    }
