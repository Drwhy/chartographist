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
INTERWOVEN_MANIFEST = ROOT / "web/assets/tilesets/interwoven/tileset.json"
INTERWOVEN_SHEET_INFO = {
    "terrain": (1248, 1248, True),
    "entities": (1536, 1024, True),
    "ocean": (1254, 1254, False),
    "beach": (1254, 1254, False),
}


class TilesetContractTests(unittest.TestCase):
    def validate_interwoven(self, manifest):
        return validate_tileset_manifest(
            manifest,
            image_size=(1248, 1248),
            sheet_image_info=INTERWOVEN_SHEET_INFO,
            expected_id="interwoven",
        )

    def test_manifest_rejects_paths_bounds_missing_coverage_and_license(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
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
                    self.validate_interwoven(candidate)

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
        self.assertEqual(
            manifest["sheets"]["ocean"]["image"],
            "ocean.png",
        )
        self.assertFalse(manifest["sheets"]["ocean"]["alpha"])
        ocean = manifest["sprites"]["terrain.ocean"]
        self.assertEqual(
            (ocean["x"], ocean["y"], ocean["sheet"], ocean["scale"]),
            (0, 0, "ocean", 1.0),
        )
        self.assertEqual(
            manifest["sheets"]["beach"]["image"],
            "beach.png",
        )
        self.assertFalse(manifest["sheets"]["beach"]["alpha"])
        for key in ("terrain.shore", "terrain.beach"):
            beach = manifest["sprites"][key]
            self.assertEqual(
                (beach["x"], beach["y"], beach["sheet"], beach["scale"]),
                (0, 0, "beach", 1.0),
            )


    def test_edge_blending_is_optional_and_strictly_validated(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        without_blending = copy.deepcopy(manifest)
        del without_blending["edge_blending"]
        normalized = self.validate_interwoven(without_blending)
        self.assertEqual(normalized["edge_blending"], {"mode": "none"})
        valid = copy.deepcopy(manifest)
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
                    self.validate_interwoven(candidate)

    def test_interwoven_separates_full_tiles_from_transparent_entity_sprites(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)

        self.assertEqual(manifest["sheets"]["terrain"]["image"], "atlas.png")
        self.assertEqual(
            manifest["sheets"]["entities"]["image"],
            "entities.png",
        )
        self.assertTrue(manifest["sheets"]["entities"]["alpha"])
        terrain = manifest["sprites"]["terrain.grassland"]
        fisherman = manifest["sprites"]["entity.human.fisherman"]
        boat = manifest["sprites"]["entity.vehicle.boat"]
        self.assertEqual((terrain["sheet"], terrain["scale"]), ("terrain", 1.0))
        self.assertEqual(fisherman["sheet"], "entities")
        self.assertLess(fisherman["scale"], 1.0)
        self.assertEqual(
            (fisherman["anchor_x"], fisherman["anchor_y"]),
            (0.5, 1.0),
        )
        self.assertEqual(boat["sheet"], "entities")

        invalid = copy.deepcopy(manifest)
        invalid["sprites"]["entity.human.fisherman"]["sheet"] = "missing"
        with self.assertRaises(TilesetValidationError):
            validate_tileset_manifest(
                invalid,
                image_size=(1248, 1248),
                sheet_image_info={
                    "terrain": (1248, 1248, True),
                    "entities": (1536, 1024, True),
                },
                expected_id="interwoven",
            )

    def test_manifest_and_png_dimensions_must_agree(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        changed = copy.deepcopy(manifest)
        changed["tile_width"] = 155
        with self.assertRaises(TilesetValidationError):
            self.validate_interwoven(changed)


if __name__ == "__main__":
    unittest.main()
