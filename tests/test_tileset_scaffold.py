import tempfile
import unittest
from pathlib import Path

from core.tilesets import load_tileset_manifest


class TilesetScaffoldTests(unittest.TestCase):
    def test_scaffold_creates_a_loadable_partial_multilayer_theme(self):
        from tools.tileset_scaffold import create_minimal_tileset

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "minimal-example"

            manifest_path = create_minimal_tileset(destination)
            manifest = load_tileset_manifest(manifest_path)

            self.assertEqual(manifest["id"], "minimal-example")
            self.assertEqual(manifest["coverage"], "partial")
            self.assertEqual(set(manifest["sheets"]), {"terrain", "entities"})
            self.assertFalse(manifest["sheets"]["terrain"]["alpha"])
            self.assertTrue(manifest["sheets"]["entities"]["alpha"])
            self.assertEqual(
                set(manifest["sprites"]),
                {
                    "terrain.grassland",
                    "entity.human",
                    "fallback.unknown",
                },
            )
            self.assertTrue((destination / "terrain.png").is_file())
            self.assertTrue((destination / "entities.png").is_file())

    def test_scaffold_refuses_unsafe_ids_and_existing_destinations(self):
        from tools.tileset_scaffold import create_minimal_tileset

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for identifier in ("../escape", "Uppercase", "", "x" * 33):
                with self.subTest(identifier=identifier):
                    with self.assertRaises(ValueError):
                        create_minimal_tileset(root / "theme", identifier=identifier)

            destination = root / "safe-theme"
            create_minimal_tileset(destination)
            with self.assertRaises(FileExistsError):
                create_minimal_tileset(destination)

    def test_modding_guide_references_existing_validated_entry_points(self):
        root = Path(__file__).resolve().parents[1]
        guide = (root / "GUIDE_TILESETS.md").read_text(encoding="utf-8")

        self.assertIn("create_minimal_tileset", guide)
        self.assertIn('coverage: "partial"', guide)
        self.assertIn("<base>.<direction>.<state>.frame_N", guide)
        self.assertIn("__chartographistPerformance.report()", guide)
        self.assertIn("__chartographistPerformance.benchmark(3000)", guide)
        self.assertIn("--width 120 --height 60", guide)
        self.assertIn("FPS actifs **≥ 50**", guide)
        self.assertIn("pipeline **≤ 75 ms**", guide)
        roadmap = (root / "ROADMAP_EMERGENCE.md").read_text(encoding="utf-8")
        self.assertNotIn("modding et stabilisation restent à réaliser", roadmap)
        for path in (
            "tools/tileset_scaffold.py",
            "tools/presentation_benchmark.py",
            "core/tilesets.py",
        ):
            self.assertIn(path, guide)
            self.assertTrue((root / path).is_file())


if __name__ == "__main__":
    unittest.main()
