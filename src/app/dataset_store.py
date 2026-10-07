"""Manage the active dataset and safely stage uploaded measurements."""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.pipeline import analyze_dataset, list_measurement_files

LOGGER = logging.getLogger(__name__)
MAX_UPLOAD_FILES = 1000
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 64 * 1024


class DatasetStore:
    """Keep an immutable active dataset and replace it with validated uploads."""

    def __init__(self, initial_directory: Path, upload_root: Path = Path("/tmp")) -> None:
        self._active_directory = initial_directory
        self._uploaded_directory: Path | None = None
        self._upload_root = upload_root
        self._lock = threading.RLock()

    @contextmanager
    def active_directory(self) -> Iterator[Path]:
        """Hold the dataset stable while a request reads or analyzes it."""
        with self._lock:
            yield self._active_directory

    def replace_from_upload(self, uploads: list[tuple[str, BinaryIO]]) -> int:
        """Validate uploaded CSV sweeps, then atomically make them active."""
        with self._lock:
            if not uploads:
                raise ValueError("Select a folder containing CSV measurements.")
            if len(uploads) > MAX_UPLOAD_FILES:
                raise ValueError(f"A dataset may contain no more than {MAX_UPLOAD_FILES} files.")

            self._upload_root.mkdir(parents=True, exist_ok=True)
            candidate_directory = Path(
                tempfile.mkdtemp(prefix="fmr-dataset-", dir=self._upload_root)
            )
            committed = False
            try:
                self._write_uploads(candidate_directory, uploads)
                measurements = list_measurement_files(candidate_directory)
                analyze_dataset(candidate_directory)

                previous_upload = self._uploaded_directory
                self._active_directory = candidate_directory
                self._uploaded_directory = candidate_directory
                committed = True
                if previous_upload is not None:
                    self._remove_directory(previous_upload)
                return len(measurements)
            finally:
                if not committed:
                    self._remove_directory(candidate_directory)

    def _write_uploads(
        self, destination: Path, uploads: list[tuple[str, BinaryIO]]
    ) -> None:
        """Write bounded, flat CSV files, rejecting unsafe or ambiguous names."""
        total_bytes = 0
        filenames: set[str] = set()
        for supplied_name, source in uploads:
            normalized_name = supplied_name.replace("\\", "/")
            filename = PurePosixPath(normalized_name).name
            if not filename or filename in {".", ".."}:
                raise ValueError("Every uploaded file must have a valid filename.")
            if not filename.lower().endswith(".csv"):
                raise ValueError(f"Only CSV files can be uploaded: {filename}.")
            filename = f"{filename[:-4]}.csv"
            if filename in filenames:
                raise ValueError(f"Duplicate CSV filename in upload: {filename}.")
            filenames.add(filename)

            target = destination / filename
            file_bytes = 0
            with target.open("wb") as output:
                while chunk := source.read(UPLOAD_CHUNK_BYTES):
                    file_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_BYTES:
                        raise ValueError(
                            f"An uploaded dataset may not exceed "
                            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                        )
                    output.write(chunk)
            if file_bytes == 0:
                raise ValueError(f"Uploaded CSV file is empty: {filename}.")

    @staticmethod
    def _remove_directory(directory: Path) -> None:
        """Remove a staged dataset, logging cleanup failures explicitly."""
        try:
            shutil.rmtree(directory)
        except OSError:
            LOGGER.warning(
                "Could not remove temporary upload directory %s.", directory, exc_info=True
            )
