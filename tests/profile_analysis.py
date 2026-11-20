"""Time one exclude/restore analysis on the bundled data, cold and warm, and profile it.

Run with `make profile`. "Cold" clears any cached per-sweep fits first; "warm" repeats
the same request after one priming call, which is what an exclusion click does.
Prints medians of five runs and the top functions by cumulative time for one cold run.
"""

import cProfile
import io
import os
import pstats
import statistics
import time
from pathlib import Path

from app import pipeline

RUNS = 5


def clear_cache() -> None:
    """Drop cached resonance fits, when the pipeline has a cache."""
    clear = getattr(pipeline, "clear_resonance_cache", None)
    if clear is not None:
        clear()


def timed(directory: Path, excluded: list[str]) -> float:
    """Return the wall time of one analysis with the given exclusions."""
    start = time.perf_counter()
    pipeline.analyze_dataset(directory, excluded_measurement_ids=excluded)
    return time.perf_counter() - start


def main() -> None:
    """Print cold and warm medians, their ratio, and a short cProfile listing."""
    directory = Path(os.environ["FMR_DATA_DIR"])
    excluded = [pipeline.list_measurement_files(directory)[0][0]]
    cold = []
    for _ in range(RUNS):
        clear_cache()
        cold.append(timed(directory, excluded))
    clear_cache()
    pipeline.analyze_dataset(directory)
    warm = [timed(directory, excluded) for _ in range(RUNS)]
    cold_median, warm_median = statistics.median(cold), statistics.median(warm)
    print(f"cache available: {hasattr(pipeline, 'clear_resonance_cache')}")
    print(f"cold exclusion analysis: median {cold_median:.3f} s ({min(cold):.3f}-{max(cold):.3f})")
    print(f"warm exclusion analysis: median {warm_median:.3f} s ({min(warm):.3f}-{max(warm):.3f})")
    print(f"cold / warm: {cold_median / warm_median:.1f}x")

    clear_cache()
    profiler = cProfile.Profile()
    profiler.runcall(pipeline.analyze_dataset, directory, excluded_measurement_ids=excluded)
    listing = io.StringIO()
    pstats.Stats(profiler, stream=listing).sort_stats("cumulative").print_stats(8)
    print(listing.getvalue())


if __name__ == "__main__":
    main()
