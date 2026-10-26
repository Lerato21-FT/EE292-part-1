"""Independent numerical and HTTP checks for perpendicular FMR analysis."""

import asyncio
import io
import math
import os
from pathlib import Path

import httpx
import pytest

from app import api
from app.dataset_store import DatasetStore
from app.pipeline import analyze_dataset


def write_perpendicular_dataset(tmp_path: Path) -> Path:
    """Write narrow derivative sweeps from independently specified physical values."""
    directory = tmp_path / "perpendicular"
    directory.mkdir()
    g_factor, effective_field_t, damping = 2.12, -0.4, 0.0002
    for frequency in range(14, 30, 2):
        center = (frequency / (13.99624555 * g_factor) + effective_field_t) * 10000
        linewidth = 8 + 2 * damping / (math.sqrt(3) * g_factor * 13.99624555) * 10000 * frequency
        half_width = linewidth * math.sqrt(3) / 2
        rows = []
        for index in range(801):
            field = center - 100 + index * 0.25
            displacement = field - center
            signal = (
                0.02
                + 0.00001 * displacement
                + 3 * 2 * half_width**2 * displacement / (displacement**2 + half_width**2) ** 2
            )
            rows.append(f"{field:.12f},{signal:.15f}")
        (directory / f"sample-OOP-{frequency * 1000}MHz-sweep.csv").write_text(
            "\n".join(reversed(rows)), encoding="utf-8"
        )
    return directory


def write_mixed_field_dataset(tmp_path: Path) -> Path:
    """Add a known negative resonance in a sweep spanning both field signs."""
    directory = write_perpendicular_dataset(tmp_path)
    half_width = 10 * math.sqrt(3) / 2
    rows = []
    for index in range(6001):
        field = -1500 + index * 0.5
        displacement = field + 700
        signal = (
            0.02 + 3 * 2 * half_width**2 * displacement / (displacement**2 + half_width**2) ** 2
        )
        rows.append(f"{field:.12f},{signal:.15f}")
    (directory / "sample-OOP-12000MHz-negative.csv").write_text("\n".join(rows), encoding="utf-8")
    return directory


def test_mixed_field_pipeline_returns_points_before_fits_are_available(tmp_path: Path) -> None:
    """A negative fitted resonance remains inspectable and can be excluded to recover fits."""
    directory = write_mixed_field_dataset(tmp_path)
    result = analyze_dataset(directory, geometry="out_of_plane")
    assert result["kittel_fit"] is None
    assert result["linewidth_fit"] is None
    assert "nonnegative" in result["fit_error"]
    first = result["measurements"][0]
    assert first["resonance_field_oe"] == pytest.approx(-700, abs=0.1)
    recovered = analyze_dataset(
        directory, geometry="out_of_plane", excluded_measurement_ids=[first["measurement_id"]]
    )
    assert recovered["fit_error"] is None
    assert recovered["kittel_fit"]["g_factor"] == pytest.approx(2.12, abs=0.001)
    assert recovered["linewidth_fit"]["damping"] == pytest.approx(0.0002, rel=0.01)


def test_mixed_field_upload_allows_inspection_exclusion_and_restoration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accept valid signed-field CSVs and recover known properties through the HTTP API."""
    directory = write_mixed_field_dataset(tmp_path)
    monkeypatch.setattr(
        api, "DATASET_STORE", DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path / "uploads")
    )

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/datasets?geometry=out_of_plane",
                files=[
                    ("files", (p.name, p.read_bytes(), "text/csv")) for p in directory.iterdir()
                ],
            )
            assert response.status_code == 200, response.text
            original = (await client.get("/api/analysis")).json()
            assert len(original["measurements"]) == 9
            assert original["kittel_fit"] is None
            assert original["linewidth_fit"] is None
            assert "nonnegative" in original["fit_error"]
            first = original["measurements"][0]
            trace = (await client.get(f"/api/measurements/{first['measurement_id']}")).json()
            assert min(trace["field_oe"]) < 0 < max(trace["field_oe"])
            assert trace["resonance_field_oe"] == pytest.approx(-700, abs=0.1)
            recovered = await client.get(
                "/api/analysis", params={"excluded_measurement_ids": first["measurement_id"]}
            )
            assert recovered.status_code == 200
            assert recovered.json()["fit_error"] is None
            assert recovered.json()["kittel_fit"]["g_factor"] == pytest.approx(2.12, abs=0.001)
            assert recovered.json()["linewidth_fit"]["damping"] == pytest.approx(0.0002, rel=0.01)
            assert (await client.get("/api/analysis")).json() == original

    asyncio.run(exercise())


def test_unfittable_raw_sweep_remains_accessible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Finite CSV samples remain available even when they cannot define a resonance fit."""
    monkeypatch.setattr(
        api, "DATASET_STORE", DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path)
    )
    directory = write_perpendicular_dataset(tmp_path)
    filename = "sample-OOP-12000MHz-flat-field.csv"

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        ) as client:
            upload = await client.post(
                "/api/datasets?geometry=out_of_plane",
                files=[("files", (filename, b"100,1\n" * 8, "text/csv"))]
                + [("files", (p.name, p.read_bytes(), "text/csv")) for p in directory.iterdir()],
            )
            assert upload.status_code == 200, upload.text
            analysis = (await client.get("/api/analysis")).json()
            assert analysis["kittel_fit"] is None
            assert analysis["included_measurement_count"] == 9
            assert "Resonance fitting failed" in analysis["fit_error"]
            assert analysis["measurements"][0]["resonance_field_oe"] is None
            assert "distinct" in analysis["measurements"][0]["extraction_error"]
            trace = (await client.get(f"/api/measurements/{filename}")).json()
            assert trace["field_oe"] == [100.0] * 8
            assert trace["fit_signal"] == []
            assert "distinct" in trace["extraction_error"]
            recovered = (
                await client.get("/api/analysis", params={"excluded_measurement_ids": filename})
            ).json()
            assert recovered["fit_error"] is None
            assert recovered["included_measurement_count"] == 8
            assert recovered["kittel_fit"]["g_factor"] == pytest.approx(2.12, abs=0.001)
            assert recovered["linewidth_fit"]["damping"] == pytest.approx(0.0002, rel=0.01)

    asyncio.run(exercise())


@pytest.fixture
def perpendicular_dataset(tmp_path: Path) -> Path:
    """Supply independent perpendicular sweeps to numerical and API tests."""
    return write_perpendicular_dataset(tmp_path)


def _check_result(result: dict) -> None:
    assert result["geometry"] == "out_of_plane"
    assert result["kittel_fit"]["g_factor"] == pytest.approx(2.12, abs=0.001)
    assert result["kittel_fit"]["effective_perpendicular_field_t"] == pytest.approx(-0.4, abs=0.001)
    assert result["kittel_fit"]["fourfold_field_t"] is None
    assert result["linewidth_fit"]["damping"] == pytest.approx(0.0002, rel=0.01)
    assert result["linewidth_fit"]["intercept_oe"] == pytest.approx(8, abs=0.01)
    assert result["kittel_fit"]["r_squared"] > 0.9999
    for point in result["kittel_fit"]["curve"]:
        expected = 13.99624555 * 2.12 * (point["field_oe"] / 10000 + 0.4)
        assert point["frequency_ghz"] == pytest.approx(expected, abs=0.001)
    for point in result["measurements"]:
        expected = (
            8 + 2 * 0.0002 / (math.sqrt(3) * 2.12 * 13.99624555) * 10000 * point["frequency_ghz"]
        )
        assert point["linewidth_pp_oe"] == pytest.approx(expected, abs=0.01)


def test_perpendicular_pipeline_recovers_known_results(perpendicular_dataset: Path):
    result = analyze_dataset(perpendicular_dataset, geometry="out_of_plane")
    _check_result(result)
    assert result["initial_perpendicular_field_t"] == -0.4
    assert result["initial_linewidth_pp_oe"] == 10


def test_perpendicular_upload_analysis_and_trace(
    perpendicular_dataset: Path, tmp_path: Path, monkeypatch
):
    store = DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path / "uploads")
    monkeypatch.setattr(api, "DATASET_STORE", store)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        ) as client:
            files = [
                ("files", (f"folder/{p.name}", p.read_bytes(), "text/csv"))
                for p in perpendicular_dataset.glob("*.csv")
            ]
            uploaded = await client.post(
                "/api/datasets?geometry=out_of_plane"
                "&initial_perpendicular_field_t=-0.3&initial_linewidth_pp_oe=12",
                files=files,
            )
            assert uploaded.status_code == 200, uploaded.text
            assert uploaded.json()["geometry"] == "out_of_plane"
            response = await client.get("/api/analysis")
            assert response.status_code == 200, response.text
            _check_result(response.json())
            assert response.json()["initial_perpendicular_field_t"] == -0.3
            assert response.json()["initial_linewidth_pp_oe"] == 12
            first = response.json()["measurements"][0]
            trace = await client.get(f"/api/measurements/{first['measurement_id']}")
            assert trace.status_code == 200
            assert trace.json()["linewidth_pp_oe"] == pytest.approx(
                first["linewidth_pp_oe"], abs=0.001
            )
            rejected = await client.post(
                "/api/datasets?geometry=out_of_plane",
                files=[("files", ("bad.csv", io.BytesIO(b"1,2\n" * 8), "text/csv"))],
            )
            assert rejected.status_code == 422
            retained = await client.get("/api/analysis")
            _check_result(retained.json())
            assert retained.json()["initial_perpendicular_field_t"] == -0.3
            assert retained.json()["initial_linewidth_pp_oe"] == 12

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "query",
    [
        "geometry=sideways",
        "geometry=out_of_plane&initial_perpendicular_field_t=nan",
        "geometry=out_of_plane&initial_linewidth_pp_oe=0",
        "geometry=in_plane&initial_perpendicular_field_t=-0.4",
    ],
)
def test_invalid_analysis_settings_are_rejected(query: str):
    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        ) as client:
            return await client.get(f"/api/analysis?{query}")

    assert asyncio.run(request()).status_code == 422


def test_perpendicular_fit_rejects_nonphysical_points():
    from app.pipeline import fit_out_of_plane_kittel

    with pytest.raises(ValueError, match="positive"):
        fit_out_of_plane_kittel([1000, 2000, 3000, 4000], [14, 0, 18, 20])
    with pytest.raises(ValueError, match="distinct"):
        fit_out_of_plane_kittel([1000] * 4, [14, 16, 18, 20])
