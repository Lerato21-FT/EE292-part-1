import asyncio
import os
from pathlib import Path

import httpx

from app import api
from app.dataset_store import DatasetStore


def test_dataset_upload_endpoint_activates_uploaded_measurements(tmp_path: Path, monkeypatch):
    data_directory = Path(os.environ["FMR_DATA_DIR"])
    monkeypatch.setattr(api, "DATASET_STORE", DatasetStore(data_directory, tmp_path))
    upload_files = [
        ("files", (path.name, path.read_bytes(), "text/csv"))
        for path in sorted(data_directory.glob("*.csv"))
    ]

    async def post_upload_and_list_measurements():
        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            upload_response = await client.post("/api/datasets", files=upload_files)
            measurements_response = await client.get("/api/measurements")
            return upload_response, measurements_response

    upload_response, measurements_response = asyncio.run(post_upload_and_list_measurements())
    assert upload_response.status_code == 200
    assert upload_response.json() == {"measurement_count": 49, "geometry": "in_plane"}
    assert len(measurements_response.json()) == 49


def test_analysis_api_validates_linked_exclusions_and_preserves_traces(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        api, "DATASET_STORE", DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path)
    )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        ) as client:
            original = (await client.get("/api/analysis")).json()
            ids = [point["measurement_id"] for point in original["measurements"]]
            excluded = await client.get(
                "/api/analysis", params={"excluded_measurement_ids": ids[0]}
            )
            assert excluded.status_code == 200
            result = excluded.json()
            assert result["included_measurement_count"] == 48
            assert result["measurements"][0]["excluded"] is True
            assert (await client.get(f"/api/measurements/{ids[0]}")).status_code == 200
            for selection in (["missing.csv"], [ids[0]] * 2, ids[:-3], [""], ["x" * 256]):
                rejected = await client.get(
                    "/api/analysis", params=[("excluded_measurement_ids", i) for i in selection]
                )
                assert rejected.status_code == 422, rejected.text
            assert (await client.get("/api/analysis")).json() == original

    asyncio.run(exercise())
