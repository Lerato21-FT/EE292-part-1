"""Known-answer checks for the in-plane pipeline, built from independently stated physics."""

import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from codata import BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T, OE_TO_TESLA

from app.pipeline import analyze_dataset

FREQUENCIES_GHZ = range(5, 30, 2)


def damping_slope_oe_per_ghz(damping: float, g_factor: float) -> float:
    """ΔHpp slope from ΔHpp = ΔH0 + 4πα f/(√3 γ), with γ/2π = g μB/h."""
    gamma_over_2pi_ghz_per_t = g_factor * BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T
    return 2 * damping / (math.sqrt(3) * gamma_over_2pi_ghz_per_t) / OE_TO_TESLA


def in_plane_resonance_oe(
    frequency_ghz: float, g_factor: float, effective_field_t: float, fourfold_field_t: float
) -> float:
    """Invert f = (g μB/h) √[(B + B4)(B + B4 + Beff)] for B, taking the positive root."""
    k = frequency_ghz / (g_factor * BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T)
    longitudinal = (-effective_field_t + math.sqrt(effective_field_t**2 + 4 * k**2)) / 2
    return (longitudinal - fourfold_field_t) / OE_TO_TESLA


def write_sweep(
    path: Path,
    center_oe: float,
    linewidth_pp_oe: float,
    noise: float = 0.0,
    seed: int = 0,
) -> None:
    """Write one derivative-Lorentzian lock-in sweep spanning ±6 half-widths."""
    half_width = linewidth_pp_oe * math.sqrt(3) / 2
    field = center_oe + np.linspace(-6 * half_width, 6 * half_width, 801)
    displacement = field - center_oe
    signal = 0.01 + 2 * half_width**2 * displacement / (displacement**2 + half_width**2) ** 2
    if noise:
        peak = 3 * math.sqrt(3) / (8 * half_width)
        signal = signal + np.random.default_rng(seed).normal(0.0, noise * peak, field.size)
    path.write_text(
        "\n".join(f"{b:.10f},{s:.15e}" for b, s in zip(field, signal, strict=True)),
        encoding="utf-8",
    )


def write_in_plane_dataset(
    directory: Path,
    *,
    g_factor: float = 2.05,
    effective_field_t: float = 0.9,
    fourfold_field_t: float = -0.015,
    linewidth: Callable[[float], float] | None = None,
    modulation_rms_oe: float | None = None,
) -> Path:
    """Write in-plane sweeps whose resonance fields and linewidths are known in advance."""
    directory.mkdir(parents=True)
    if linewidth is None:
        slope = damping_slope_oe_per_ghz(0.004, g_factor)
        linewidth = lambda f: 12.0 + slope * f  # noqa: E731
    suffix = "" if modulation_rms_oe is None else f"-{modulation_rms_oe:.1f}OeRMS"
    for frequency in FREQUENCIES_GHZ:
        center = in_plane_resonance_oe(frequency, g_factor, effective_field_t, fourfold_field_t)
        write_sweep(
            directory / f"film-IP-{frequency * 1000:05d}MHz{suffix}-sweep.csv",
            center,
            linewidth(frequency),
        )
    return directory


def test_in_plane_pipeline_recovers_known_properties(tmp_path: Path) -> None:
    """g, Beff,⊥, B4 and α stated up front are recovered through the full pipeline."""
    result = analyze_dataset(write_in_plane_dataset(tmp_path / "ip"))

    kittel, linewidth = result["kittel_fit"], result["linewidth_fit"]
    assert result["fit_error"] is None
    assert kittel["g_factor"] == pytest.approx(2.05, abs=1e-3)
    assert kittel["effective_perpendicular_field_t"] == pytest.approx(0.9, abs=1e-3)
    assert kittel["fourfold_field_t"] == pytest.approx(-0.015, abs=5e-4)
    assert linewidth["damping"] == pytest.approx(0.004, rel=0.01)
    assert linewidth["intercept_oe"] == pytest.approx(12.0, abs=0.1)
    assert linewidth["damping_resolved"] is True
    for key in ("g_factor_sigma", "effective_perpendicular_field_sigma_t"):
        assert kittel[key] is not None and kittel[key] >= 0
    assert linewidth["damping_sigma"] is not None and linewidth["damping_sigma"] >= 0
    assert kittel["at_bound"] == []
    assert not any(point["low_quality"] for point in result["measurements"])


def test_in_plane_negative_resonance_gets_an_explanation(tmp_path: Path) -> None:
    """A signed-field sweep must not surface scipy's raw 'x0 is infeasible' text."""
    directory = write_in_plane_dataset(tmp_path / "mixed")
    negative = directory / "film-IP-04000MHz-negative.csv"
    write_sweep(negative, -700.0, 20.0)

    result = analyze_dataset(directory)

    assert result["kittel_fit"] is None
    assert "infeasible" not in result["fit_error"]
    assert "positive resonance fields" in result["fit_error"]
    assert result["measurements"][0]["resonance_field_oe"] == pytest.approx(-700, abs=0.5)
    recovered = analyze_dataset(directory, excluded_measurement_ids=[negative.name])
    assert recovered["fit_error"] is None
    assert recovered["kittel_fit"]["g_factor"] == pytest.approx(2.05, abs=1e-3)


def test_decreasing_linewidth_keeps_the_kittel_fit(tmp_path: Path) -> None:
    """A slightly negative linewidth slope makes damping unavailable, not g and Beff,⊥."""
    directory = write_in_plane_dataset(tmp_path / "flat", linewidth=lambda f: 30.0 - 0.05 * f)

    result = analyze_dataset(directory)

    assert result["fit_error"] is None
    assert result["kittel_fit"]["g_factor"] == pytest.approx(2.05, abs=1e-3)
    assert result["linewidth_fit"] is None
    assert "decreases" in result["linewidth_fit_error"]


def test_mirror_solution_is_reported_for_a_negative_effective_field(tmp_path: Path) -> None:
    """Beff,⊥ = −0.1 T, B4 = 0 has the exact mirror Beff,⊥ = +0.1 T, B4 = −0.1 T.

    The bounds pick the mirror with R² = 1, so no parameter is at a bound. The pipeline
    must name the other solution instead of presenting the pick as a measurement.
    """
    directory = write_in_plane_dataset(tmp_path / "pma", effective_field_t=-0.1, fourfold_field_t=0)

    result = analyze_dataset(directory)

    kittel = result["kittel_fit"]
    assert kittel["effective_perpendicular_field_t"] == pytest.approx(0.1, abs=1e-3)
    assert kittel["fourfold_field_t"] == pytest.approx(-0.1, abs=1e-3)
    assert kittel["mirror_effective_perpendicular_field_t"] == pytest.approx(-0.1, abs=1e-3)
    assert kittel["mirror_fourfold_field_t"] == pytest.approx(0.0, abs=1e-3)
    mirror_warnings = [w for w in result["warnings"] if "mirror solution" in w]
    assert len(mirror_warnings) == 1
    assert "-0.1" in mirror_warnings[0]


def test_mirror_outside_the_fourfold_range_is_not_reported(tmp_path: Path) -> None:
    """Beff,⊥ = 0.9 T, B4 = −0.015 T: the mirror needs B4 = 0.885 T > 0.5 T, so it is ruled out."""
    result = analyze_dataset(write_in_plane_dataset(tmp_path / "ip"))

    assert result["kittel_fit"]["mirror_effective_perpendicular_field_t"] is None
    assert not any("mirror solution" in warning for warning in result["warnings"])


def test_poor_resonance_fits_are_flagged_but_kept(tmp_path: Path) -> None:
    """Sweeps with resonance R² < 0.98 are flagged for inspection, never silently excluded."""
    directory = write_in_plane_dataset(tmp_path / "noisy")
    noisy = directory / "film-IP-05000MHz-sweep.csv"
    center = in_plane_resonance_oe(5, 2.05, 0.9, -0.015)
    write_sweep(noisy, center, 20.0, noise=0.4, seed=3)

    result = analyze_dataset(directory)

    flagged = [p["measurement_id"] for p in result["measurements"] if p["low_quality"]]
    assert flagged == [noisy.name]
    assert result["measurements"][0]["resonance_r_squared"] < 0.98
    assert result["included_measurement_count"] == len(result["measurements"])
    assert any("0.98" in warning for warning in result["warnings"])


@pytest.mark.parametrize(("modulation_rms_oe", "warned"), [(2.0, True), (0.5, False)])
def test_modulation_broadening_condition_is_checked(
    tmp_path: Path, modulation_rms_oe: float, warned: bool
) -> None:
    """Peak-to-peak modulation 2√2·H_rms is compared with ΔHpp/3 for every sweep."""
    directory = write_in_plane_dataset(
        tmp_path / "mod",
        linewidth=lambda f: 10.0 + 0.2 * f,  # 11–15.8 Oe, so ΔHpp/3 ≤ 5.3 Oe
        modulation_rms_oe=modulation_rms_oe,
    )

    result = analyze_dataset(directory)

    for point in result["measurements"]:
        assert point["modulation_rms_oe"] == modulation_rms_oe
        assert point["modulation_pp_oe"] == pytest.approx(2 * math.sqrt(2) * modulation_rms_oe)
        assert point["modulation_warning"] is warned
    assert any("modulation" in warning for warning in result["warnings"]) is warned


def test_summary_states_the_result_in_plain_sentences(tmp_path: Path) -> None:
    """A clean dataset gets a two-part result statement and says no warnings were raised."""
    result = analyze_dataset(write_in_plane_dataset(tmp_path / "clean"))

    summary = result["summary"]
    assert len(summary) == 3
    assert summary[0].startswith(
        "From 13 included sweeps, the in-plane Kittel fit gives g = 2.0500"
    )
    assert "B4 = -0.0150" in summary[0]
    assert summary[1].startswith("The Gilbert damping is α = 0.004")
    assert summary[2] == "No quality warnings were raised for the included sweeps."


def test_summary_says_when_damping_is_not_established(tmp_path: Path) -> None:
    """Scattered linewidths: the summary must not present α as a result."""
    directory = write_in_plane_dataset(
        tmp_path / "scatter",
        linewidth=lambda f: 20.0 + 0.3 * f + (10.0 if (f // 2) % 2 else -10.0),
    )

    result = analyze_dataset(directory)

    assert result["linewidth_fit"]["damping_established"] is False
    assert "is not established" in result["summary"][1]
    assert result["summary"][2].startswith("Read the ")


def test_summary_explains_a_missing_fit(tmp_path: Path) -> None:
    """When no property fit is possible, the summary says so and gives the reason."""
    directory = write_in_plane_dataset(tmp_path / "few")
    ids = sorted(path.name for path in directory.glob("*.csv"))

    result = analyze_dataset(directory, excluded_measurement_ids=ids[:-3])

    assert result["kittel_fit"] is None
    assert result["summary"][0] == (
        "No magnetic properties are reported yet for these 3 included sweeps."
    )
    assert result["summary"][1] == result["fit_error"]
