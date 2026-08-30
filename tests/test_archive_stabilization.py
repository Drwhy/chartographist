import tempfile
import unittest
from pathlib import Path

from tests.test_history_archive import presentation_snapshot


class ArchiveStabilizationTests(unittest.TestCase):
    def test_reader_rejects_a_physically_truncated_archive(self):
        from core.history_archive import (
            ArchiveFormatError,
            HistoryArchiveReader,
            HistoryArchiveRecorder,
        )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "truncated.chartarchive"
            recorder = HistoryArchiveRecorder(destination)
            recorder.record(presentation_snapshot(1))
            recorder.finalize()
            payload = destination.read_bytes()
            destination.write_bytes(payload[:-16])

            with self.assertRaisesRegex(ArchiveFormatError, "invalid_archive"):
                HistoryArchiveReader(destination)


if __name__ == "__main__":
    unittest.main()
