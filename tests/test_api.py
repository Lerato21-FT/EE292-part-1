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
