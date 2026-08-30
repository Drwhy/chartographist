import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

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
    "climate": (1092, 2496, True),
    "rivers": (624, 468, True),
    "roads": (624, 468, True),
    "cultures": (1024, 512, True),
    "water_climate": (312, 1248, True),
}


def _rgba_alpha_rows(path):
    data = path.read_bytes()
    offset = 8
    compressed = bytearray()
    width = height = None
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
            if (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise AssertionError("expected non-interlaced 8-bit RGBA PNG")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    stride = width * 4
    rows = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = raw[cursor:cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(encoded):
            left = row[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (
                    abs(estimate - left),
                    abs(estimate - above),
                    abs(estimate - upper_left),
                )
                predictor = (left, above, upper_left)[distances.index(min(distances))]
            else:
                raise AssertionError(f"unsupported PNG filter {filter_type}")
            row[index] = (value + predictor) & 255
        rows.append(row[3::4])
        previous = row
    return width, height, rows


def _sprite_edge_connections(path, column, row, rotation=0):
    width, height, alpha = _rgba_alpha_rows(path)
    tile_size = 156
    if width % tile_size or height % tile_size:
        raise AssertionError("unexpected connected-sheet dimensions")
    left = column * tile_size
    top = row * tile_size
    bands = {
        "n": sum(
            alpha[top + y][left + x] > 64
            for y in range(8) for x in range(48, 108)
        ),
        "e": sum(
            alpha[top + y][left + x] > 64
            for x in range(148, 156) for y in range(48, 108)
        ),
        "s": sum(
            alpha[top + y][left + x] > 64
            for y in range(148, 156) for x in range(48, 108)
        ),
        "w": sum(
            alpha[top + y][left + x] > 64
            for x in range(8) for y in range(48, 108)
        ),
    }
    connections = {direction for direction, count in bands.items() if count > 80}
    order = ("n", "e", "s", "w")
    turns = rotation // 90
    return {order[(order.index(direction) + turns) % 4] for direction in connections}


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

    def test_partial_coverage_is_explicit_and_keeps_the_fallback(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        partial = copy.deepcopy(manifest)
        partial["coverage"] = "partial"
        partial["sprites"] = {
            key: value for key, value in partial["sprites"].items()
            if key in {"terrain.grassland", "fallback.unknown"}
        }

        normalized = self.validate_interwoven(partial)

        self.assertEqual(normalized["coverage"], "partial")
        self.assertEqual(
            set(normalized["sprites"]),
            {"terrain.grassland", "fallback.unknown"},
        )
        for invalid in ("optional", "", True, None):
            with self.subTest(coverage=invalid):
                changed = copy.deepcopy(partial)
                changed["coverage"] = invalid
                with self.assertRaises(TilesetValidationError):
                    self.validate_interwoven(changed)

    def test_png_budgets_reject_hostile_dimensions_and_encoding(self):
        def png_header(width, height, *, depth=8, color=6, interlace=0):
            payload = struct.pack(
                ">IIBBBBB", width, height, depth, color, 0, 0, interlace
            )
            return (
                b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", len(payload))
                + b"IHDR"
                + payload
            )

        manifest = {
            "schema_version": 1,
            "id": "hostile",
            "name": "Hostile",
            "image": "atlas.png",
            "tile_width": 1,
            "tile_height": 1,
            "columns": 1,
            "rows": 1,
            "coverage": "partial",
            "fallback": "fallback.unknown",
            "license": {"name": "Test", "source": "local"},
            "sprites": {"fallback.unknown": {"x": 0, "y": 0}},
        }
        hostile_headers = (
            png_header(100_000, 1),
            png_header(1, 100_000),
            png_header(1, 1, depth=16),
            png_header(1, 1, color=3),
            png_header(1, 1, interlace=1),
            png_header(1, 1),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "hostile"
            root.mkdir()
            (root / "tileset.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            for header in hostile_headers:
                with self.subTest(header=header[16:26]):
                    (root / "atlas.png").write_bytes(header)
                    with self.assertRaises(TilesetValidationError):
                        load_tileset_manifest(root / "tileset.json")

    def test_interwoven_tileset_has_square_tiles_and_opt_in_edge_blending(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)

        self.assertEqual(manifest["id"], "interwoven")
        self.assertEqual(manifest["name_key"], "web.tileset_interwoven")
        self.assertEqual(manifest["tile_width"], manifest["tile_height"])
        self.assertEqual((manifest["columns"], manifest["rows"]), (8, 8))
        self.assertEqual(
            manifest["edge_blending"],
            {"mode": "puzzle", "depth": 0.04, "teeth": 4},
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

    def test_interwoven_has_climate_variants_and_connected_rivers(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        terrain_keys = (
            "volcano", "peak", "high_mountain", "mountain", "sand",
            "glaciated", "boreal_forest", "temperate_forest",
            "autumn_forest", "tropical_forest", "grassland", "tundra",
            "desert", "cactus",
        )
        for terrain in terrain_keys:
            for variant in ("winter", "spring", "summer", "autumn"):
                with self.subTest(terrain=terrain, variant=variant):
                    self.assertIn(f"terrain.{terrain}.{variant}", manifest["sprites"])
        for variant in (
            "vertical", "horizontal", "corner_ne", "corner_nw",
            "corner_se", "corner_sw", "fork_north", "fork_east",
            "fork_south", "fork_west", "cross",
        ):
            self.assertIn(f"hydrology.river.{variant}", manifest["sprites"])
            self.assertIn(f"infrastructure.road.{variant}", manifest["sprites"])

        climate = manifest["sheets"]["climate"]
        rivers = manifest["sheets"]["rivers"]
        self.assertEqual((climate["tile_width"], climate["tile_height"]), (156, 156))
        self.assertEqual((rivers["tile_width"], rivers["tile_height"]), (156, 156))
        self.assertTrue(rivers["alpha"])
        roads = manifest["sheets"]["roads"]
        self.assertEqual((roads["tile_width"], roads["tile_height"]), (156, 156))
        self.assertTrue(roads["alpha"])
        expected_corners = {
            "corner_ne": 0,
            "corner_se": 90,
            "corner_sw": 180,
            "corner_nw": 270,
        }
        for variant, rotation in expected_corners.items():
            sprite = manifest["sprites"][f"infrastructure.road.{variant}"]
            self.assertEqual((sprite["x"], sprite["y"]), (2, 0))
            self.assertEqual(sprite["rotation"], rotation)
        water_climate = manifest["sheets"]["water_climate"]
        self.assertEqual(
            (water_climate["tile_width"], water_climate["tile_height"]),
            (156, 156),
        )
        for terrain in ("ocean", "shore"):
            for variant in (
                "winter", "spring", "summer", "autumn",
                "drought", "flood", "heatwave", "cold_snap",
            ):
                with self.subTest(water=terrain, variant=variant):
                    self.assertIn(
                        f"terrain.{terrain}.{variant}",
                        manifest["sprites"],
                    )

    def test_connected_network_sprites_reach_exact_declared_edges(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        expected = {
            "vertical": {"n", "s"},
            "horizontal": {"e", "w"},
            "corner_ne": {"n", "e"},
            "corner_nw": {"n", "w"},
            "corner_se": {"s", "e"},
            "corner_sw": {"s", "w"},
            "fork_north": {"n", "e", "w"},
            "fork_east": {"n", "e", "s"},
            "fork_south": {"e", "s", "w"},
            "fork_west": {"n", "s", "w"},
            "cross": {"n", "e", "s", "w"},
        }
        assets = INTERWOVEN_MANIFEST.parent
        for layer, sheet_name in (
            ("hydrology.river", "rivers.png"),
            ("infrastructure.road", "roads.png"),
        ):
            for variant, connections in expected.items():
                with self.subTest(layer=layer, variant=variant):
                    sprite = manifest["sprites"][f"{layer}.{variant}"]
                    self.assertEqual(
                        _sprite_edge_connections(
                            assets / sheet_name,
                            sprite["x"],
                            sprite["y"],
                            sprite["rotation"],
                        ),
                        connections,
                    )

    def test_interwoven_has_centered_cultural_settlements(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)

        cultures = manifest["sheets"]["cultures"]
        self.assertEqual((cultures["tile_width"], cultures["tile_height"]), (256, 256))
        self.assertTrue(cultures["alpha"])
        for column, culture in enumerate(("empire", "sultanat", "dynastie", "clans")):
            for row, structure in enumerate(("city", "village")):
                with self.subTest(culture=culture, structure=structure):
                    sprite = manifest["sprites"][
                        f"entity.structure.{structure}.{culture}"
                    ]
                    self.assertEqual((sprite["x"], sprite["y"]), (column, row))
                    self.assertEqual(sprite["sheet"], "cultures")
                    self.assertEqual((sprite["anchor_x"], sprite["anchor_y"]), (0.5, 0.5))
                    self.assertLessEqual(sprite["scale"], 0.7)

        for key in ("entity.structure.city", "entity.structure.village"):
            sprite = manifest["sprites"][key]
            self.assertEqual((sprite["anchor_x"], sprite["anchor_y"]), (0.5, 0.5))
            self.assertLessEqual(sprite["scale"], 0.7)


    def test_edge_blending_is_optional_and_strictly_validated(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        without_blending = copy.deepcopy(manifest)
        del without_blending["edge_blending"]
        normalized = self.validate_interwoven(without_blending)
        self.assertEqual(normalized["edge_blending"], {"mode": "none"})
        valid = copy.deepcopy(manifest)
        valid["edge_blending"] = {"mode": "puzzle", "depth": 0.2, "teeth": 8}
        invalid_values = [
            {"mode": "blur", "depth": 0.2, "opacity": 0.5},
            {"mode": "puzzle", "depth": 0, "teeth": 6},
            {"mode": "puzzle", "depth": 0.6, "teeth": 6},
            {"mode": "puzzle", "depth": 0.2, "teeth": 1},
            {"mode": "puzzle", "depth": 0.2, "teeth": 17},
            {"mode": "puzzle", "depth": 0.2},
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
        self.assertEqual((terrain["sheet"], terrain["scale"]), ("climate", 1.0))
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

    def test_sprite_rotation_accepts_only_quarter_turns(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        for invalid_rotation in (45, -90, 360, 90.5, "90", True):
            with self.subTest(rotation=invalid_rotation):
                changed = copy.deepcopy(manifest)
                changed["sprites"]["infrastructure.road.corner_ne"][
                    "rotation"
                ] = invalid_rotation
                with self.assertRaises(TilesetValidationError):
                    self.validate_interwoven(changed)

    def test_interwoven_mobile_entities_enable_strict_auto_mirroring(self):
        manifest = load_tileset_manifest(INTERWOVEN_MANIFEST)
        for key in (
            "entity.human.fisherman",
            "entity.human.hunter",
            "entity.human.settler",
            "entity.human.soldier",
            "entity.human.trader",
            "entity.animal.wolf",
            "entity.animal.bear",
            "entity.animal.deer",
            "entity.animal.rabbit",
        ):
            self.assertTrue(manifest["sprites"][key]["auto_mirror"], key)
        self.assertFalse(
            manifest["sprites"]["entity.structure.city"]["auto_mirror"]
        )

        changed = copy.deepcopy(manifest)
        changed["sprites"]["entity.human.trader"]["auto_mirror"] = "yes"
        with self.assertRaises(TilesetValidationError):
            self.validate_interwoven(changed)


if __name__ == "__main__":
    unittest.main()
