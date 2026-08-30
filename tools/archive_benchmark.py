"""Mesures reproductibles du coût des archives de présentation."""

from pathlib import Path
from statistics import median
from time import perf_counter
import tracemalloc

from core.history_archive import (
    ArchiveFormatError,
    HistoryArchiveReader,
    HistoryArchiveRecorder,
)


def benchmark_archive(snapshots, destination, *, lookup_revisions=None):
    """Enregistre une histoire puis mesure son ouverture et ses recherches.

    Le rapport reste sérialisable en JSON afin de pouvoir être conservé avec
    les résultats des campagnes de stabilisation.
    """
    path = Path(destination)
    owns_trace = not tracemalloc.is_tracing()
    trace_stopped = False
    if owns_trace:
        tracemalloc.start()

    recorder = HistoryArchiveRecorder(path)
    count = 0
    record_started = perf_counter()
    try:
        for value in snapshots:
            recorder.record(value)
            count += 1
        if count == 0:
            recorder.abort()
            raise ArchiveFormatError("empty_archive")
        recorder.finalize()
        record_seconds = perf_counter() - record_started
        _, peak_memory_bytes = tracemalloc.get_traced_memory()
        if owns_trace:
            tracemalloc.stop()
            trace_stopped = True

        reader_started = perf_counter()
        reader = HistoryArchiveReader(path)
        reader_open_seconds = perf_counter() - reader_started

        if lookup_revisions is None:
            bounds = reader.bounds()
            first = bounds["first_revision"]
            last = bounds["last_revision"]
            revisions = (first, first + (last - first) // 2, last)
        else:
            revisions = tuple(lookup_revisions)

        lookup_durations = []
        for revision in revisions:
            lookup_started = perf_counter()
            reader.snapshot_at_revision(revision)
            lookup_durations.append((perf_counter() - lookup_started) * 1000.0)

        return {
            "revisions": count,
            "archive_bytes": path.stat().st_size,
            "record_seconds": record_seconds,
            "record_ms_per_revision": record_seconds * 1000.0 / count,
            "reader_open_seconds": reader_open_seconds,
            "lookups": {
                "count": len(revisions),
                "revisions": list(revisions),
                "median_ms": (
                    median(lookup_durations) if lookup_durations else 0.0
                ),
                "maximum_ms": (
                    max(lookup_durations) if lookup_durations else 0.0
                ),
            },
            "peak_memory_bytes": peak_memory_bytes,
        }
    except BaseException:
        recorder.abort()
        raise
    finally:
        if owns_trace and not trace_stopped:
            tracemalloc.stop()
