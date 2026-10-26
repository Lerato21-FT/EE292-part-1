import math
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from test_out_of_plane import write_perpendicular_dataset

from app.pipeline import (
    BOHR_MAGNETON_OVER_PLANCK_GHZ_PER_T,
    OE_TO_TESLA,
    _coefficient_of_determination,
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

    assert fit.damping == pytest.approx(expected_damping, rel=1e-10)
    assert fit.slope_oe_per_ghz == pytest.approx(slope_oe_per_ghz, rel=1e-10)
    assert fit.r_squared == pytest.approx(1.0)


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
