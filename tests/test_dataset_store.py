import io
import os
from pathlib import Path

import pytest


def _sample_uploads() -> list[tuple[str, io.BytesIO]]:
    data_directory = Path(os.environ["FMR_DATA_DIR"])
    return [
        (path.name, io.BytesIO(path.read_bytes())) for path in sorted(data_directory.glob("*.csv"))
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
    uploads = [(f"{filename[:-4]}.CSV", source) for filename, source in _sample_uploads()]

    assert store.replace_from_upload(uploads) == 49


def test_invalid_upload_leaves_previous_dataset_active(tmp_path: Path):
    from app.dataset_store import DatasetStore

    initial_directory = Path(os.environ["FMR_DATA_DIR"])
    store = DatasetStore(initial_directory, tmp_path)

    with pytest.raises(ValueError, match="frequency"):
        store.replace_from_upload([("bad-name.csv", io.BytesIO(b"900,1\n" * 8))])

    with store.active_directory() as directory:
        assert directory == initial_directory


VALID_SWEEP = b"".join(f"{900 + i},{i % 3}\n".encode() for i in range(8))


@pytest.mark.parametrize(
    ("uploads", "message"),
    [
        ([], "Select a folder"),
        ([("", VALID_SWEEP)], "valid filename"),
        ([("folder/..", VALID_SWEEP)], "valid filename"),
        ([("notes-05000MHz.txt", VALID_SWEEP)], "Only CSV"),
        ([("a/s-05000MHz.csv", VALID_SWEEP), ("b/s-05000MHz.CSV", VALID_SWEEP)], "Duplicate"),
        ([("s-05000MHz.csv", b"")], "empty"),
    ],
)
def test_unsafe_or_ambiguous_uploads_are_rejected(
    tmp_path: Path, uploads: list[tuple[str, bytes]], message: str
) -> None:
    """Every upload-boundary rejection keeps the previous dataset and leaves no staged files."""
    from app.dataset_store import DatasetStore

    initial = Path(os.environ["FMR_DATA_DIR"])
    store = DatasetStore(initial, tmp_path / "uploads")
    with pytest.raises(ValueError, match=message):
        store.replace_from_upload([(name, io.BytesIO(data)) for name, data in uploads])
    with store.active_directory() as directory:
        assert directory == initial
    assert not list((tmp_path / "uploads").glob("fmr-dataset-*"))


@pytest.mark.parametrize("name", ["../../escape-05000MHz.csv", "..\\..\\escape-05000MHz.csv"])
def test_path_components_cannot_escape_the_staging_directory(tmp_path: Path, name: str) -> None:
    """Folder and traversal components are stripped; only the basename is written."""
    from app.dataset_store import DatasetStore

    store = DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path / "uploads")
    store.replace_from_upload([(name, io.BytesIO(VALID_SWEEP))])

    with store.active_directory() as directory:
        assert [p.name for p in directory.iterdir()] == ["escape-05000MHz.csv"]
        assert directory.parent == tmp_path / "uploads"
    assert not list(tmp_path.glob("escape*"))


def test_file_count_limit_is_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import dataset_store

    monkeypatch.setattr(dataset_store, "MAX_UPLOAD_FILES", 2)
    store = dataset_store.DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path)
    uploads = [(f"s-0{index}000MHz.csv", io.BytesIO(VALID_SWEEP)) for index in range(5, 8)]
    with pytest.raises(ValueError, match="no more than 2 files"):
        store.replace_from_upload(uploads)


def test_total_size_limit_is_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import dataset_store

    monkeypatch.setattr(dataset_store, "MAX_UPLOAD_BYTES", len(VALID_SWEEP) + 10)
    store = dataset_store.DatasetStore(Path(os.environ["FMR_DATA_DIR"]), tmp_path / "uploads")
    uploads = [(f"s-0{index}000MHz.csv", io.BytesIO(VALID_SWEEP)) for index in range(5, 7)]
    with pytest.raises(ValueError, match="may not exceed"):
        store.replace_from_upload(uploads)
    assert not list((tmp_path / "uploads").glob("fmr-dataset-*"))


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("sample-OOP-14000MHz.csv", b"1,nan\n" * 8, "non-finite"),
        ("sample-OOP-14000MHz.csv", b"1,wat\n" * 8, "non-numeric"),
        ("sample-OOP-14000MHz.csv", b"1,2\n" * 7, "eight"),
        ("sample-OOP-00000MHz.csv", b"1,2\n" * 8, "positive"),
    ],
)
def test_structurally_invalid_upload_preserves_active_dataset(
    tmp_path: Path, filename: str, content: bytes, message: str
) -> None:
    """Separating model fitting from upload validation must retain CSV integrity checks."""
    from app.dataset_store import DatasetStore

    initial = Path(os.environ["FMR_DATA_DIR"])
    store = DatasetStore(initial, tmp_path)
    with pytest.raises(ValueError, match=message):
        store.replace_from_upload([(filename, io.BytesIO(content))], geometry="out_of_plane")
    with store.active_directory() as directory:
        assert directory == initial
