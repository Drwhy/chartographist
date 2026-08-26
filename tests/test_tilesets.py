import copy
from pathlib import Path
import unittest

from core.tilesets import (
    STANDARD_VISUAL_KEYS,
    TilesetValidationError,
    load_tileset_manifest,
    validate_tileset_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "web/assets/tilesets/classic/tileset.json"


class TilesetContractTests(unittest.TestCase):
    def test_classic_tileset_is_versioned_licensed_and_covers_standard_keys(self):
        manifest = load_tileset_manifest(MANIFEST)
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["id"], "classic")
        self.assertEqual(manifest["image"], "atlas.png")
        self.assertEqual((manifest["tile_width"], manifest["tile_height"]), (156, 156))
        self.assertEqual((manifest["columns"], manifest["rows"]), (8, 8))
        self.assertTrue(manifest["license"]["name"])
        self.assertTrue(manifest["license"]["source"])
        self.assertEqual(manifest["fallback"], "fallback.unknown")
        self.assertTrue(STANDARD_VISUAL_KEYS.issubset(manifest["sprites"]))

    def test_manifest_rejects_paths_bounds_missing_coverage_and_license(self):
        manifest = load_tileset_manifest(MANIFEST)
        invalid_manifests = []
        unsafe = copy.deepcopy(manifest)
        unsafe["image"] = "../atlas.png"
        invalid_manifests.append(unsafe)
        outside = copy.deepcopy(manifest)
        outside["sprites"]["terrain.volcano"] = {"x": 8, "y": 0}
        invalid_manifests.append(outside)
        uncovered = copy.deepcopy(manifest)
        del uncovered["sprites"]["terrain.volcano"]
        invalid_manifests.append(uncovered)
        unlicensed = copy.deepcopy(manifest)
        unlicensed["license"] = {}
        invalid_manifests.append(unlicensed)
        wrong_size = copy.deepcopy(manifest)
        wrong_size["tile_width"] = 0
        invalid_manifests.append(wrong_size)
        for candidate in invalid_manifests:
            with self.subTest(candidate=candidate):
                with self.assertRaises(TilesetValidationError):
                    validate_tileset_manifest(
                        candidate,
                        image_size=(1248, 1248),
                        expected_id="classic",
                    )

    def test_manifest_and_png_dimensions_must_agree(self):
        manifest = load_tileset_manifest(MANIFEST)
        changed = copy.deepcopy(manifest)
        changed["tile_width"] = 155
        with self.assertRaises(TilesetValidationError):
            validate_tileset_manifest(
                changed,
                image_size=(1248, 1248),
                expected_id="classic",
            )


if __name__ == "__main__":
    unittest.main()
