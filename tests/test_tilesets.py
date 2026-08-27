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
INTERWOVEN_MANIFEST = ROOT / "web/assets/tilesets/interwoven/tileset.json"


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

    def test_interwoven_tileset_has_square_tiles_and_opt_in_edge_blending(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)

        self.assertEqual(manifest["id"], "interwoven")
        self.assertEqual(manifest["name_key"], "web.tileset_interwoven")
        self.assertEqual(manifest["tile_width"], manifest["tile_height"])
        self.assertEqual((manifest["columns"], manifest["rows"]), (8, 8))
        self.assertEqual(
            manifest["edge_blending"],
            {"mode": "interlaced", "depth": 0.18, "opacity": 0.72},
        )
        self.assertTrue(STANDARD_VISUAL_KEYS.issubset(manifest["sprites"]))

    def test_edge_blending_is_optional_and_strictly_validated(self):
        classic = load_tileset_manifest(MANIFEST)
        self.assertEqual(classic["edge_blending"], {"mode": "none"})

        valid = copy.deepcopy(classic)
        valid["edge_blending"] = {
            "mode": "interlaced",
            "depth": 0.2,
            "opacity": 0.5,
        }
        invalid_values = [
            {"mode": "blur", "depth": 0.2, "opacity": 0.5},
            {"mode": "interlaced", "depth": 0, "opacity": 0.5},
            {"mode": "interlaced", "depth": 0.6, "opacity": 0.5},
            {"mode": "interlaced", "depth": 0.2, "opacity": 0},
            {"mode": "interlaced", "depth": 0.2, "opacity": 1.1},
            {"mode": "interlaced", "depth": 0.2},
        ]
        for edge_blending in invalid_values:
            with self.subTest(edge_blending=edge_blending):
                candidate = copy.deepcopy(valid)
                candidate["edge_blending"] = edge_blending
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
