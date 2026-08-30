import tempfile
import unittest
from pathlib import Path
from unittest import mock


def snapshot(revision):
    return {
        "schema_version": 1,
        "revision": revision,
        "cycle": revision * 2,
        "clock": {"year": 1, "month": revision},
        "world": {
            "name": "Benchmark",
            "seed": 17,
            "width": 2,
            "height": 1,
        },
        "cells": [
            {"x": 0, "y": 0, "terrain_key": "grassland"},
            {"x": 1, "y": 0, "terrain_key": "sand", "value": revision},
        ],
        "logs": [],
        "panels": {},
    }


class ArchiveBenchmarkTests(unittest.TestCase):
    def test_benchmark_reports_storage_recording_lookup_and_memory(self):
        from tools.archive_benchmark import benchmark_archive

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "benchmark.chartarchive"
            report = benchmark_archive(
                (snapshot(revision) for revision in range(1, 7)),
                destination,
                lookup_revisions=(1, 3, 6),
            )

            self.assertEqual(report["revisions"], 6)
            self.assertEqual(report["lookups"]["count"], 3)
            self.assertEqual(report["lookups"]["revisions"], [1, 3, 6])
            self.assertGreater(report["archive_bytes"], 0)
            self.assertGreaterEqual(report["record_seconds"], 0.0)
            self.assertGreaterEqual(report["record_ms_per_revision"], 0.0)
            self.assertGreaterEqual(report["reader_open_seconds"], 0.0)
            self.assertGreaterEqual(report["lookups"]["median_ms"], 0.0)
            self.assertGreaterEqual(report["lookups"]["maximum_ms"], 0.0)
            self.assertGreater(report["peak_memory_bytes"], 0)
            self.assertTrue(destination.is_file())

    def test_memory_tracing_stops_before_reader_latency_is_measured(self):
        import tools.archive_benchmark as benchmark

        events = []
        reader_type = benchmark.HistoryArchiveReader
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "benchmark.chartarchive"
            with (
                mock.patch.object(
                    benchmark.tracemalloc,
                    "is_tracing",
                    return_value=False,
                ),
                mock.patch.object(
                    benchmark.tracemalloc,
                    "start",
                    side_effect=lambda: events.append("trace-start"),
                ),
                mock.patch.object(
                    benchmark.tracemalloc,
                    "get_traced_memory",
                    return_value=(64, 128),
                ),
                mock.patch.object(
                    benchmark.tracemalloc,
                    "stop",
                    side_effect=lambda: events.append("trace-stop"),
                ),
                mock.patch.object(
                    benchmark,
                    "HistoryArchiveReader",
                    side_effect=lambda path: (
                        events.append("reader") or reader_type(path)
                    ),
                ),
            ):
                benchmark.benchmark_archive([snapshot(1)], destination)

        self.assertLess(events.index("trace-stop"), events.index("reader"))

    def test_benchmark_rejects_an_empty_history_without_leaving_an_archive(self):
        from core.history_archive import ArchiveFormatError
        from tools.archive_benchmark import benchmark_archive

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "empty.chartarchive"

            with self.assertRaisesRegex(ArchiveFormatError, "empty_archive"):
                benchmark_archive([], destination)

            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
