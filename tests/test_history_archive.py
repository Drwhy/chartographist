import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import warnings
import zipfile


def manifest(**overrides):
    value = {
        "format": "chartographist-archive",
        "version": 1,
        "presentation_schema_version": 1,
        "world": {
            "name": "Test World",
            "seed": 1701,
            "width": 4,
            "height": 3,
        },
        "revisions": {
            "first": 1,
            "last": 2,
            "keyframe_interval": 60,
        },
        "capabilities": ["snapshots", "deltas"],
    }
    value.update(overrides)
    return value


def archive_with_members(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Duplicate name:")
            for name, payload in entries:
                archive.writestr(name, payload)


def presentation_snapshot(revision, terrain="grassland"):
    return {
        "schema_version": 1,
        "revision": revision,
        "cycle": revision,
        "clock": {"year": revision // 12, "month": revision % 12 + 1},
        "world": {
            "name": "Recorded World",
            "seed": 1702,
            "width": 2,
            "height": 1,
        },
        "cells": [
            {"x": 0, "y": 0, "terrain_key": terrain},
            {"x": 1, "y": 0, "terrain_key": "sand"},
        ],
        "logs": [],
        "panels": {},
    }


class HistoryArchiveFormatTests(unittest.TestCase):
    def test_writer_creates_canonical_valid_archive_with_hashes(self):
        from core.history_archive import load_archive_manifest, write_archive

        members = {
            "segments/000000000001-000000000002.ndjson": b'{"delta":1}\n',
            "keyframes/000000000001.json": b'{"snapshot":1}',
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"

            written = write_archive(destination, manifest(), members)
            loaded = load_archive_manifest(destination)

            self.assertEqual(loaded, written)
            self.assertEqual(
                [entry["name"] for entry in loaded["members"]],
                sorted(members),
            )
            self.assertTrue(all(len(entry["sha256"]) == 64 for entry in loaded["members"]))
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["manifest.json", *sorted(members)],
                )

    def test_writer_is_reproducible_for_equivalent_input_order(self):
        from core.history_archive import write_archive

        first_members = {
            "segments/000000000001-000000000002.ndjson": b"{}\n",
            "keyframes/000000000001.json": b"{}",
        }
        second_members = dict(reversed(list(first_members.items())))
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.chartarchive"
            second_path = Path(directory) / "second.chartarchive"

            write_archive(
                first_path,
                manifest(capabilities=["snapshots", "deltas"]),
                first_members,
            )
            write_archive(
                second_path,
                manifest(capabilities=["deltas", "snapshots"]),
                second_members,
            )

            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

    def test_writer_is_atomic_when_replacement_fails(self):
        from core.history_archive import write_archive

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"
            destination.write_bytes(b"previous")

            with mock.patch(
                "core.history_archive.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with self.assertRaises(OSError):
                    write_archive(
                        destination,
                        manifest(),
                        {"keyframes/000000000001.json": b"{}"},
                    )

            self.assertEqual(destination.read_bytes(), b"previous")
            self.assertEqual(
                [path.name for path in Path(directory).iterdir()],
                ["history.chartarchive"],
            )

    def test_writer_flushes_archive_before_atomic_replacement(self):
        from core.history_archive import write_archive

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"
            with mock.patch("core.history_archive.os.fsync") as synchronize:
                write_archive(
                    destination,
                    manifest(
                        revisions={
                            "first": 1,
                            "last": 1,
                            "keyframe_interval": 60,
                        }
                    ),
                    {"keyframes/000000000001.json": b"{}"},
                )

            synchronize.assert_called_once()

    def test_writer_enforces_archive_and_member_count_limits(self):
        from core import history_archive
        from core.history_archive import ArchiveFormatError, write_archive

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "limited.chartarchive"
            members = {
                "keyframes/000000000001.json": b"{}",
                "segments/000000000001-000000000002.ndjson": b"{}\n",
            }
            with mock.patch.object(history_archive, "MAX_MEMBERS", 2):
                with self.assertRaises(ArchiveFormatError) as raised:
                    write_archive(destination, manifest(), members)
            self.assertEqual(raised.exception.code, "member_limit")

            with mock.patch.object(history_archive, "MAX_ARCHIVE_BYTES", 1):
                with self.assertRaises(ArchiveFormatError) as raised:
                    write_archive(
                        destination,
                        manifest(),
                        {"keyframes/000000000001.json": b"{}"},
                    )
            self.assertEqual(raised.exception.code, "archive_too_large")
            self.assertFalse(destination.exists())

    def test_manifest_capabilities_are_non_empty_unique_strings(self):
        from core.history_archive import ArchiveFormatError, write_archive

        invalid_capabilities = [[], ["snapshots", "snapshots"], ["snapshots", 1]]
        with tempfile.TemporaryDirectory() as directory:
            for index, capabilities in enumerate(invalid_capabilities):
                with self.subTest(capabilities=capabilities):
                    value = manifest(capabilities=capabilities)
                    with self.assertRaises(ArchiveFormatError) as raised:
                        write_archive(
                            Path(directory) / f"invalid-{index}.chartarchive",
                            value,
                            {"keyframes/000000000001.json": b"{}"},
                        )
                    self.assertEqual(raised.exception.code, "manifest_invalid")

    def test_reader_rejects_unsafe_and_duplicate_members(self):
        from core.history_archive import ArchiveFormatError, load_archive_manifest

        cases = {
            "unsafe_member": [
                ("manifest.json", b"{}"),
                ("../escape.json", b"{}"),
            ],
            "duplicate_member": [
                ("manifest.json", b"{}"),
                ("manifest.json", b"{}"),
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            for expected, entries in cases.items():
                with self.subTest(expected=expected):
                    path = Path(directory) / f"{expected}.chartarchive"
                    archive_with_members(path, entries)
                    with self.assertRaises(ArchiveFormatError) as raised:
                        load_archive_manifest(path)
                    self.assertEqual(raised.exception.code, expected)

    def test_reader_rejects_invalid_json_and_duplicate_manifest_keys(self):
        from core.history_archive import ArchiveFormatError, load_archive_manifest

        cases = {
            "manifest_invalid_json": b"{",
            "manifest_duplicate_key": b'{"format":"a","format":"b"}',
        }
        with tempfile.TemporaryDirectory() as directory:
            for expected, payload in cases.items():
                with self.subTest(expected=expected):
                    path = Path(directory) / f"{expected}.chartarchive"
                    archive_with_members(path, [("manifest.json", payload)])
                    with self.assertRaises(ArchiveFormatError) as raised:
                        load_archive_manifest(path)
                    self.assertEqual(raised.exception.code, expected)

    def test_reader_rejects_unsupported_version_and_invalid_bounds(self):
        from core.history_archive import ArchiveFormatError, write_archive

        cases = {
            "unsupported_version": manifest(version=2),
            "manifest_invalid": manifest(
                world={"name": "Large", "seed": 1, "width": 1000, "height": 1000}
            ),
            "revision_limit": manifest(
                revisions={"first": 1, "last": 100002, "keyframe_interval": 60}
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            for expected, value in cases.items():
                with self.subTest(expected=expected):
                    path = Path(directory) / f"{expected}.chartarchive"
                    with self.assertRaises(ArchiveFormatError) as raised:
                        write_archive(
                            path,
                            value,
                            {"keyframes/000000000001.json": b"{}"},
                        )
                    self.assertEqual(raised.exception.code, expected)

    def test_reader_rejects_member_and_expansion_limits(self):
        from core import history_archive
        from core.history_archive import ArchiveFormatError, load_archive_manifest

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "limits.chartarchive"
            archive_with_members(
                path,
                [("manifest.json", b"{}"), ("keyframes/000000000001.json", b"12345")],
            )
            with mock.patch.object(history_archive, "MAX_MEMBER_BYTES", 4):
                with self.assertRaises(ArchiveFormatError) as raised:
                    load_archive_manifest(path)
            self.assertEqual(raised.exception.code, "member_too_large")

            with mock.patch.object(history_archive, "MAX_EXPANDED_BYTES", 6):
                with self.assertRaises(ArchiveFormatError) as raised:
                    load_archive_manifest(path)
            self.assertEqual(raised.exception.code, "expanded_too_large")

    def test_reader_rejects_excessive_compression_ratio(self):
        from core import history_archive
        from core.history_archive import ArchiveFormatError, load_archive_manifest

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratio.chartarchive"
            archive_with_members(
                path,
                [("manifest.json", b"{}"), ("keyframes/000000000001.json", b"0" * 4096)],
            )
            with mock.patch.object(history_archive, "MAX_COMPRESSION_RATIO", 2):
                with self.assertRaises(ArchiveFormatError) as raised:
                    load_archive_manifest(path)
            self.assertEqual(raised.exception.code, "compression_ratio")

    def test_reader_detects_manifest_member_or_checksum_mismatch(self):
        from core.history_archive import ArchiveFormatError, load_archive_manifest

        base = manifest()
        base["members"] = [{
            "name": "keyframes/000000000001.json",
            "size": 2,
            "sha256": "0" * 64,
        }]
        with tempfile.TemporaryDirectory() as directory:
            checksum_path = Path(directory) / "checksum.chartarchive"
            archive_with_members(
                checksum_path,
                [("manifest.json", json.dumps(base).encode()), ("keyframes/000000000001.json", b"{}")],
            )
            with self.assertRaises(ArchiveFormatError) as raised:
                load_archive_manifest(checksum_path)
            self.assertEqual(raised.exception.code, "checksum_mismatch")

            base["members"] = []
            mismatch_path = Path(directory) / "mismatch.chartarchive"
            archive_with_members(
                mismatch_path,
                [("manifest.json", json.dumps(base).encode()), ("keyframes/000000000001.json", b"{}")],
            )
            with self.assertRaises(ArchiveFormatError) as raised:
                load_archive_manifest(mismatch_path)
            self.assertEqual(raised.exception.code, "member_mismatch")


class HistoryArchiveRecorderTests(unittest.TestCase):
    def test_recorder_writes_keyframes_and_bounded_delta_segments(self):
        from core.history_archive import HistoryArchiveRecorder, load_archive_manifest

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "recorded.chartarchive"
            recorder = HistoryArchiveRecorder(destination, keyframe_interval=60)
            for revision in range(1, 66):
                terrain = "tundra" if revision % 2 else "grassland"
                recorder.record(presentation_snapshot(revision, terrain))
            written = recorder.finalize()

            self.assertEqual(load_archive_manifest(destination), written)
            self.assertEqual(
                written["revisions"],
                {"first": 1, "last": 65, "keyframe_interval": 60},
            )
            with zipfile.ZipFile(destination) as archive:
                names = archive.namelist()
                self.assertIn("keyframes/000000000001.json", names)
                self.assertIn("keyframes/000000000061.json", names)
                first_segment = archive.read(
                    "segments/000000000001-000000000060.ndjson"
                ).splitlines()
                second_segment = archive.read(
                    "segments/000000000061-000000000065.ndjson"
                ).splitlines()
            self.assertEqual((len(first_segment), len(second_segment)), (59, 4))

    def test_recorder_is_defensive_and_does_not_consume_randomness(self):
        from core.history_archive import HistoryArchiveRecorder
        from core.random_service import RandomService

        RandomService.initialize(1703)
        before = RandomService.get_state()
        snapshot = presentation_snapshot(1)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "recorded.chartarchive"
            recorder = HistoryArchiveRecorder(destination)
            recorder.record(snapshot)
            snapshot["cells"][0]["terrain_key"] = "tampered"
            recorder.finalize()

            with zipfile.ZipFile(destination) as archive:
                stored = json.loads(
                    archive.read("keyframes/000000000001.json")
                )
        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(stored["cells"][0]["terrain_key"], "grassland")

    def test_recorder_rejects_revision_gaps_and_aborts_context_on_error(self):
        from core.history_archive import ArchiveFormatError, HistoryArchiveRecorder

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "recorded.chartarchive"
            with self.assertRaises(ArchiveFormatError) as raised:
                with HistoryArchiveRecorder(destination) as recorder:
                    recorder.record(presentation_snapshot(1))
                    recorder.record(presentation_snapshot(3))

            self.assertEqual(raised.exception.code, "revision_sequence")
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_recorder_finalizes_completed_cycles_on_keyboard_interrupt(self):
        from core.history_archive import HistoryArchiveRecorder, load_archive_manifest

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "interrupted.chartarchive"
            with self.assertRaises(KeyboardInterrupt):
                with HistoryArchiveRecorder(destination) as recorder:
                    recorder.record(presentation_snapshot(1))
                    recorder.record(presentation_snapshot(2))
                    raise KeyboardInterrupt()

            loaded = load_archive_manifest(destination)
            self.assertEqual(loaded["revisions"]["last"], 2)


class HistoryArchiveReaderTests(unittest.TestCase):
    def _record_history(self, destination):
        from core.history_archive import HistoryArchiveRecorder

        recorder = HistoryArchiveRecorder(destination, keyframe_interval=3)
        for revision in range(1, 7):
            snapshot = presentation_snapshot(
                revision,
                "tundra" if revision >= 4 else "grassland",
            )
            if revision == 4:
                snapshot["panels"]["chronicles"] = [{
                    "chronicle_id": 7,
                    "cycle": 4,
                    "category": "climate",
                    "message": "A cold front arrived.",
                }]
            recorder.record(snapshot)
        recorder.finalize()

    def test_reader_reconstructs_revision_cycle_and_temporal_bounds(self):
        from core.history_archive import HistoryArchiveReader

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"
            self._record_history(destination)
            reader = HistoryArchiveReader(destination)

            self.assertEqual(reader.bounds(), {
                "first_revision": 1,
                "last_revision": 6,
                "first_cycle": 1,
                "last_cycle": 6,
            })
            self.assertEqual(reader.snapshot_at_revision(2)["revision"], 2)
            self.assertEqual(
                reader.snapshot_at_cycle(5)["cells"][0]["terrain_key"],
                "tundra",
            )

    def test_reader_reuses_keyframes_validated_during_indexing(self):
        from core.history_archive import HistoryArchiveReader

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"
            self._record_history(destination)
            reader = HistoryArchiveReader(destination)

            with mock.patch.object(
                reader, "_read_member", wraps=reader._read_member
            ) as read_member:
                snapshot = reader.snapshot_at_revision(4)

            self.assertEqual(snapshot["revision"], 4)
            read_member.assert_not_called()

    def test_reader_returns_defensive_snapshots_without_consuming_randomness(self):
        from core.history_archive import HistoryArchiveReader
        from core.random_service import RandomService

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"
            self._record_history(destination)
            reader = HistoryArchiveReader(destination)
            RandomService.initialize(1713)
            before = RandomService.get_state()

            first = reader.snapshot_at_revision(4)
            first["cells"][0]["terrain_key"] = "tampered"
            second = reader.snapshot_at_revision(4)

            self.assertEqual(RandomService.get_state(), before)
            self.assertEqual(second["cells"][0]["terrain_key"], "tundra")

    def test_reader_indexes_timeline_events_and_compares_revisions(self):
        from core.history_archive import HistoryArchiveReader

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "history.chartarchive"
            self._record_history(destination)
            reader = HistoryArchiveReader(destination)

            events = reader.timeline_events(start_cycle=4, end_cycle=4)
            comparison = reader.compare(2, 5)

            self.assertEqual([event["chronicle_id"] for event in events], [7])
            self.assertEqual(comparison["from_revision"], 2)
            self.assertEqual(comparison["to_revision"], 5)
            self.assertEqual(comparison["changed_cell_count"], 1)
            self.assertEqual(
                comparison["changed_cells"][0]["before"]["terrain_key"],
                "grassland",
            )
            self.assertEqual(
                comparison["changed_cells"][0]["after"]["terrain_key"],
                "tundra",
            )

    def test_reader_rejects_incomplete_timelines_and_out_of_bounds_queries(self):
        from core.history_archive import (
            ArchiveFormatError,
            HistoryArchiveReader,
            write_archive,
        )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "incomplete.chartarchive"
            write_archive(
                destination,
                manifest(
                    world=presentation_snapshot(1)["world"],
                    revisions={
                    "first": 1,
                    "last": 2,
                    "keyframe_interval": 60,
                }),
                {"keyframes/000000000001.json": json.dumps(
                    presentation_snapshot(1)
                ).encode("utf-8")},
            )
            with self.assertRaises(ArchiveFormatError) as raised:
                HistoryArchiveReader(destination)
            self.assertEqual(raised.exception.code, "timeline_incomplete")

            valid = Path(directory) / "valid.chartarchive"
            self._record_history(valid)
            reader = HistoryArchiveReader(valid)
            for query in (
                lambda: reader.snapshot_at_revision(0),
                lambda: reader.snapshot_at_cycle(99),
                lambda: reader.compare(5, 2),
            ):
                with self.subTest(query=query):
                    with self.assertRaises(ArchiveFormatError) as raised:
                        query()
                    self.assertEqual(raised.exception.code, "revision_out_of_bounds")

    def test_reader_rejects_out_of_bounds_delta_cells_during_indexing(self):
        from core.history_archive import (
            ArchiveFormatError,
            HistoryArchiveReader,
            write_archive,
        )

        first = presentation_snapshot(1)
        delta = {
            "schema_version": 1,
            "from_revision": 1,
            "to_revision": 2,
            "cycle": 2,
            "resync": False,
            "cells": [{"x": 99, "y": 0, "terrain_key": "tundra"}],
            "clock": {"year": 0, "month": 2},
            "logs": [],
            "panels": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "unsafe.chartarchive"
            write_archive(
                destination,
                manifest(
                    world=first["world"],
                    revisions={
                        "first": 1,
                        "last": 2,
                        "keyframe_interval": 60,
                    },
                ),
                {
                    "keyframes/000000000001.json": json.dumps(first).encode(),
                    "segments/000000000001-000000000002.ndjson": (
                        json.dumps(delta).encode() + b"\n"
                    ),
                },
            )
            with self.assertRaises(ArchiveFormatError) as raised:
                HistoryArchiveReader(destination)
            self.assertEqual(raised.exception.code, "timeline_invalid")


if __name__ == "__main__":
    unittest.main()
