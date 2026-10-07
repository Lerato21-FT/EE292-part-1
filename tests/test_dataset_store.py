import io
import os
from pathlib import Path

import pytest


def _sample_uploads() -> list[tuple[str, io.BytesIO]]:
    data_directory = Path(os.environ["FMR_DATA_DIR"])
    return [
        (path.name, io.BytesIO(path.read_bytes()))
        for path in sorted(data_directory.glob("*.csv"))
    ]


def test_successful_upload_becomes_active_dataset(tmp_path: Path):
    from app.dataset_store import DatasetStore

    initial_directory = Path(os.environ["FMR_DATA_DIR"])
    store = DatasetStore(initial_directory, tmp_path)

    measurement_count = store.replace_from_upload(_sample_uploads())

    assert measurement_count == 49
    with store.active_directory() as directory:
        assert directory != initial_directory
        assert len(list(directory.glob("*.csv"))) == 49


def test_upload_accepts_uppercase_csv_extension(tmp_path: Path):
    from app.dataset_store import DatasetStore

    store = DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path)
    uploads = [
        (f"{filename[:-4]}.CSV", source)
        for filename, source in _sample_uploads()
    ]

    assert store.replace_from_upload(uploads) == 49


def test_invalid_upload_leaves_previous_dataset_active(tmp_path: Path):
    from app.dataset_store import DatasetStore

    initial_directory = Path(os.environ["FMR_DATA_DIR"])
    store = DatasetStore(initial_directory, tmp_path)

    with pytest.raises(ValueError, match="frequency"):
        store.replace_from_upload([("bad-name.csv", io.BytesIO(b"900,1\n" * 8))])

    with store.active_directory() as directory:
        assert directory == initial_directory
