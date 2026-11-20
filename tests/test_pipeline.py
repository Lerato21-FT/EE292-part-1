import math
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from codata import BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T, OE_TO_TESLA
from test_out_of_plane import write_perpendicular_dataset

from app import pipeline
from app.pipeline import (
    _coefficient_of_determination,
    _kittel_frequency,
    _out_of_plane_frequency,
    analyze_dataset,
    fit_derivative_signal,
    fit_kittel,
    fit_linewidth,
    load_measurement,
)


def test_constant_series_has_defined_r_squared():
    assert _coefficient_of_determination(np.array([1.0, 1.0]), np.array([2.0, 2.0])) == 0.0


def test_extracts_peak_to_peak_width_from_derivative_lorentzian():
    center_oe = 875.0
    half_width_oe = 18.0
    field_oe = [700.0 + index * 0.5 for index in range(701)]
    signal = [
        2.5e-7
        + 1.2e-6
        * (
            2.0
            * half_width_oe**2
            * (field - center_oe)
            / ((field - center_oe) ** 2 + half_width_oe**2) ** 2
        )
        for field in field_oe
    ]
    field_oe.insert(200, field_oe[199])
    signal.insert(200, signal[199])

    fit = fit_derivative_signal(field_oe, signal)

    assert fit.center_oe == pytest.approx(center_oe, abs=0.1)
    assert fit.linewidth_pp_oe == pytest.approx(2.0 * half_width_oe / 3**0.5, abs=0.2)


def test_kittel_fit_recovers_g_factor_and_anisotropy_fields():
    expected_g = 2.13
    expected_perpendicular_t = 0.82
    expected_fourfold_t = 0.035
    field_t = [0.12 + index * 0.035 for index in range(22)]
    frequency_ghz = [
        BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T
        * expected_g
        * math.sqrt(
            (field + expected_fourfold_t) * (field + expected_fourfold_t + expected_perpendicular_t)
        )
        for field in field_t
    ]

    fit = fit_kittel([field / OE_TO_TESLA for field in field_t], frequency_ghz)

    assert fit.g_factor == pytest.approx(expected_g, rel=1e-5)
    assert fit.effective_perpendicular_field_t == pytest.approx(expected_perpendicular_t, rel=1e-5)
    assert fit.fourfold_field_t == pytest.approx(expected_fourfold_t, abs=1e-6)
    assert fit.r_squared == pytest.approx(1.0)


def test_linewidth_fit_converts_peak_to_peak_slope_to_damping():
    expected_g = 2.1
    expected_damping = 0.006
    gamma_over_2pi = expected_g * BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T * 1e9
    slope_oe_per_ghz = expected_damping * 2.0 / math.sqrt(3.0) / gamma_over_2pi * 1e13
    frequency_ghz = [5.0 + index for index in range(9)]
    linewidth_oe = [13.0 + slope_oe_per_ghz * frequency for frequency in frequency_ghz]

    fit = fit_linewidth(frequency_ghz, linewidth_oe, expected_g)

    # μB/h itself is only known to about 3e-10 (CODATA 2018 electron mass), so asking the
    # damping for 1e-10 tests rounding, not physics. The constant has its own test below.
    assert fit.damping == pytest.approx(expected_damping, rel=1e-9)
    assert fit.slope_oe_per_ghz == pytest.approx(slope_oe_per_ghz, rel=1e-9)
    assert fit.r_squared == pytest.approx(1.0)


def test_gyromagnetic_constant_matches_codata():
    """μB/h must equal e/(4π mₑ); this catches the classic 28 GHz/T (γ/2π) mix-up."""
    # Both sides come from the same CODATA 2018 inputs, so they agree to rounding
    # (~1e-12). 2e-11 still catches a single wrong digit, such as 13.99624493361.
    assert pipeline.BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T == pytest.approx(
        BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T, rel=2e-11
    )
    assert BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T == pytest.approx(13.99624494, rel=1e-9)


def test_dispersion_models_match_hand_calculated_values():
    """Hand-evaluated anchors: g = 2, μB/h = 13.99624494 GHz/T, numbers written out in full."""
    # Out-of-plane: f = 2 · 13.99624494 · (1.0 − 0) = 27.99248988 GHz.
    assert _out_of_plane_frequency(np.array([1.0]), 2.0, 0.0)[0] == pytest.approx(
        27.99248988, rel=1e-7
    )
    # In-plane: f = 27.99248988 · √(0.1 · 1.0) = 27.99248988 · 0.31622777 = 8.85200254 GHz.
    assert _kittel_frequency(np.array([0.1]), 2.0, 0.9, 0.0)[0] == pytest.approx(
        8.85200254, rel=1e-7
    )


def test_damping_matches_hand_calculated_value():
    """1 Oe/GHz at g = 2: α = (√3/2) · 1e-4 T/GHz · 27.99248988 GHz/T = 0.0024242207."""
    frequency_ghz = [5.0, 10.0, 15.0, 20.0]
    fit = fit_linewidth(frequency_ghz, [12.0 + f for f in frequency_ghz], 2.0)

    assert fit.damping == pytest.approx(0.0024242207, rel=1e-7)


def test_linewidth_fit_reports_hand_calculated_standard_errors():
    """Ordinary least squares on x = 1..4, y = 0, 1, 1, 3, worked by hand.

    x̄ = 2.5, ȳ = 1.25, Sxx = 5, Sxy = 4.5, so slope = 0.9 and intercept = −1.0.
    Residuals 0.1, 0.2, −0.7, 0.4 give SSR = 0.70 and s² = SSR / (n − 2) = 0.35.
    σ_slope = √(s²/Sxx) = √0.07; σ_intercept = √(s² (1/n + x̄²/Sxx)) = √0.525.
    With an exact g = 2, σ_α = σ_slope · 0.0024242207 per (Oe/GHz).
    """
    fit = fit_linewidth([1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 1.0, 3.0], 2.0)

    assert fit.slope_oe_per_ghz == pytest.approx(0.9)
    assert fit.intercept_oe == pytest.approx(-1.0)
    assert fit.slope_sigma_oe_per_ghz == pytest.approx(math.sqrt(0.07), rel=1e-9)
    assert fit.intercept_sigma_oe == pytest.approx(math.sqrt(0.525), rel=1e-9)
    assert fit.damping_sigma == pytest.approx(math.sqrt(0.07) * 0.0024242207, rel=1e-7)
    assert fit.damping_resolved is True


def test_damping_uncertainty_includes_g_factor_uncertainty():
    """Independent relative errors add in quadrature: σ_α/α = √((σ_s/s)² + (σ_g/g)²)."""
    fit = fit_linewidth([1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 1.0, 3.0], 2.0, g_factor_sigma=0.02)

    relative = math.hypot(math.sqrt(0.07) / 0.9, 0.02 / 2.0)
    assert fit.damping_sigma == pytest.approx(fit.damping * relative, rel=1e-9)


def test_small_positive_slope_is_flagged_as_unresolved_damping():
    """A slope within two standard errors of zero is reported but not claimed as resolved."""
    # By hand: slope = Sxy/Sxx = 0.45/5 = 0.09 Oe/GHz, σ_slope = √(0.4635/5) ≈ 0.30.
    fit = fit_linewidth([1.0, 2.0, 3.0, 4.0], [0.3, 1.2, 0.0, 1.0], 2.0)

    assert fit.slope_oe_per_ghz > 0
    assert fit.slope_oe_per_ghz < 2 * fit.slope_sigma_oe_per_ghz
    assert fit.damping_resolved is False


def test_kittel_fit_reports_uncertainties_that_cover_the_truth():
    """Noisy synthetic dispersion: 1σ errors are finite, positive and cover the true values."""
    rng = np.random.default_rng(7)
    field_t = np.linspace(0.05, 0.85, 25)
    frequency_ghz = _known_in_plane_frequency(field_t, 2.05, 0.9, -0.02)
    noisy = frequency_ghz + rng.normal(0.0, 0.02, field_t.size)

    fit = fit_kittel(list(field_t / OE_TO_TESLA), list(noisy))

    for value, sigma, truth in (
        (fit.g_factor, fit.g_factor_sigma, 2.05),
        (fit.effective_perpendicular_field_t, fit.effective_perpendicular_field_sigma_t, 0.9),
        (fit.fourfold_field_t, fit.fourfold_field_sigma_t, -0.02),
    ):
        assert sigma is not None and 0 < sigma < 0.05
        assert abs(value - truth) < 5 * sigma


def _known_in_plane_frequency(
    field_t: np.ndarray, g_factor: float, effective_field_t: float, fourfold_field_t: float
) -> np.ndarray:
    """Independent in-plane Kittel evaluation using the CODATA constant from `codata`."""
    longitudinal = field_t + fourfold_field_t
    return (
        BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T
        * g_factor
        * np.sqrt(longitudinal * (longitudinal + effective_field_t))
    )


def test_measurement_loader_reads_first_two_columns(tmp_path: Path):
    filename = "sample-IP-05000MHz-sweep.csv"
    (tmp_path / filename).write_text(
        "\n".join(f"{900 + index},{index * 0.25},999" for index in range(10)),
        encoding="utf-8",
    )

    measurement = load_measurement(tmp_path, filename)

    assert measurement.frequency_ghz == 5.0
    assert measurement.field_oe == [float(900 + index) for index in range(10)]
    assert measurement.signal == [index * 0.25 for index in range(10)]


def test_broadband_dataset_analysis_returns_all_sweeps():
    data_directory = Path(os.environ["FMR_DATA_DIR"])

    result = analyze_dataset(data_directory)

    assert len(result["measurements"]) == 49
    assert result["measurements"][0]["frequency_ghz"] == 5.0
    assert result["measurements"][-1]["frequency_ghz"] == 29.0
    assert result["kittel_fit"]["g_factor"] == pytest.approx(1.9957, abs=0.02)
    assert result["kittel_fit"]["effective_perpendicular_field_t"] == pytest.approx(
        0.9487, abs=0.04
    )
    assert result["kittel_fit"]["fourfold_field_t"] == pytest.approx(-0.02006, abs=0.01)
    assert result["kittel_fit"]["r_squared"] > 0.99
    assert result["linewidth_fit"]["damping"] == pytest.approx(0.00492, abs=0.001)
    assert len(result["kittel_fit"]["curve"]) == 300


@pytest.mark.parametrize("geometry", ["in_plane", "out_of_plane"])
def test_linked_exclusions_refit_both_models_and_restore_raw_data(tmp_path: Path, geometry: str):
    directory = (
        Path(os.environ["FMR_DATA_DIR"])
        if geometry == "in_plane"
        else write_perpendicular_dataset(tmp_path)
    )
    original = analyze_dataset(directory, geometry=geometry)
    excluded_ids = [point["measurement_id"] for point in original["measurements"][:2]]
    raw_before = {path.name: path.read_bytes() for path in directory.glob("*.csv")}
    reduced = tmp_path / "reduced"
    reduced.mkdir()
    for filename in raw_before:
        if filename not in excluded_ids:
            shutil.copyfile(directory / filename, reduced / filename)
    expected = analyze_dataset(reduced, geometry=geometry)

    result = analyze_dataset(directory, geometry=geometry, excluded_measurement_ids=excluded_ids)

    assert result["included_measurement_count"] == len(original["measurements"]) - 2
    assert len(result["measurements"]) == len(original["measurements"])
    assert [p["measurement_id"] for p in result["measurements"] if p["excluded"]] == excluded_ids
    assert result["kittel_fit"] == expected["kittel_fit"]
    assert result["linewidth_fit"] == expected["linewidth_fit"]
    assert analyze_dataset(directory, geometry=geometry, excluded_measurement_ids=[]) == original
    assert {path.name: path.read_bytes() for path in directory.glob("*.csv")} == raw_before


def test_exclusions_reject_unknown_and_duplicate_selections():
    directory = Path(os.environ["FMR_DATA_DIR"])
    ids = [path.name for path in sorted(directory.glob("*.csv"))]
    for selection, message in [
        (["unknown.csv"], "Unknown"),
        ([ids[0], ids[0]], "Duplicate"),
    ]:
        with pytest.raises(ValueError, match=message):
            analyze_dataset(directory, excluded_measurement_ids=selection)


def test_insufficient_included_points_remain_inspectable() -> None:
    """Applying valid exclusions clears unavailable fits while retaining every measurement."""
    directory = Path(os.environ["FMR_DATA_DIR"])
    ids = [path.name for path in sorted(directory.glob("*.csv"))]
    for selection in (ids[:-3], ids):
        result = analyze_dataset(directory, excluded_measurement_ids=selection)
        assert result["kittel_fit"] is None
        assert result["linewidth_fit"] is None
        assert "at least four" in result["fit_error"]
        assert len(result["measurements"]) == 49
        assert result["included_measurement_count"] == 49 - len(selection)


@pytest.mark.parametrize("create", [False, True])
def test_dataset_errors_do_not_reveal_server_paths(tmp_path: Path, create: bool) -> None:
    """Missing or empty measurement directories are reported without their filesystem path."""
    directory = tmp_path / "secret-location"
    if create:
        directory.mkdir()
    with pytest.raises(ValueError) as error:
        analyze_dataset(directory)
    assert "secret-location" not in str(error.value)
    assert str(tmp_path) not in str(error.value)


def test_bundled_sweeps_report_their_modulation_amplitude():
    """Demo filenames record 2.0 Oe RMS modulation: 2√2 · 2.0 ≈ 5.66 Oe peak-to-peak."""
    result = analyze_dataset(Path(os.environ["FMR_DATA_DIR"]))

    for point in result["measurements"]:
        assert point["modulation_rms_oe"] == 2.0
        assert point["modulation_pp_oe"] == pytest.approx(5.656854, rel=1e-6)


def test_clean_linewidth_line_establishes_damping():
    """A straight line with a positive ΔH0 raises no damping concern."""
    fit = fit_linewidth([5.0, 10.0, 15.0, 20.0], [12.0 + f for f in [5.0, 10.0, 15.0, 20.0]], 2.0)

    assert fit.damping_established is True
    assert fit.damping_concerns == []


def test_low_linewidth_r_squared_means_damping_is_not_established():
    """Scatter that the line barely explains (R² < 0.5) must not be presented as α."""
    frequency_ghz = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    fit = fit_linewidth(frequency_ghz, [20.0, 30.0, 18.0, 31.0, 21.0, 32.0], 2.0)

    assert fit.r_squared < 0.5
    assert fit.damping_established is False
    assert any("R²" in concern for concern in fit.damping_concerns)


def test_intercept_negative_beyond_two_sigma_means_damping_is_not_established():
    """ΔH0 cannot be negative; −10 Oe with a tiny error flags α, but R² is fine."""
    frequency_ghz = [5.0, 10.0, 15.0, 20.0, 25.0]
    noise_oe = [0.1, -0.1, 0.0, 0.1, -0.1]
    linewidth_oe = [-10.0 + 2.0 * f + n for f, n in zip(frequency_ghz, noise_oe, strict=True)]
    fit = fit_linewidth(frequency_ghz, linewidth_oe, 2.0)

    assert fit.r_squared > 0.99
    assert fit.intercept_oe + 2 * fit.intercept_sigma_oe < 0
    assert fit.damping_established is False
    assert any("ΔH0" in concern for concern in fit.damping_concerns)


def test_intercept_negative_within_two_sigma_still_establishes_damping():
    """Like the review's −14.5 ± 17 Oe: negative, but consistent with zero, so no flag.

    The hand-worked x = 1..4, y = 0, 1, 1, 3 line has ΔH0 = −1.0 ± √0.525 = −1.0 ± 0.72 Oe
    and R² = 1 − 0.70/4.75 = 0.853.
    """
    fit = fit_linewidth([1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 1.0, 3.0], 2.0)

    assert fit.intercept_oe < 0
    assert fit.intercept_oe + 2 * fit.intercept_sigma_oe >= 0
    assert fit.r_squared == pytest.approx(1 - 0.70 / 4.75)
    assert fit.damping_established is True
