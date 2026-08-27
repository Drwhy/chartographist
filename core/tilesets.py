"""Validation stricte des thèmes de sprites indépendants de la simulation."""

import json
from pathlib import Path
import re
import struct


TILESET_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 256 * 1024
_SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_SAFE_IMAGE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}\.png$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

STANDARD_VISUAL_KEYS = frozenset({
    "terrain.volcano",
    "terrain.peak",
    "terrain.high_mountain",
    "terrain.mountain",
    "terrain.sand",
    "terrain.glaciated",
    "terrain.boreal_forest",
    "terrain.temperate_forest",
    "terrain.autumn_forest",
    "terrain.tropical_forest",
    "terrain.grassland",
    "terrain.tundra",
    "terrain.desert",
    "terrain.cactus",
    "hydrology.river",
    "infrastructure.road",
    "site.battlefield",
    "site.ruins",
    "site.sanctuary",
    "site.mine",
    "entity.structure.city",
    "entity.structure.village",
    "entity.structure.ruins",
    "entity.structure",
    "entity.human.farmer",
    "entity.human.fisherman",
    "entity.human.hunter",
    "entity.human.settler",
    "entity.human.soldier",
    "entity.human.trader",
    "entity.human",
    "entity.animal.wolf",
    "entity.animal.bear",
    "entity.animal.deer",
    "entity.animal.eagle",
    "entity.animal.shark",
    "entity.animal.fish",
    "entity.animal.rabbit",
    "entity.animal",
    "entity.special.ufo",
    "entity.special",
    "fallback.unknown",
})


class TilesetValidationError(ValueError):
    """Signale un manifeste non sûr, incohérent ou incomplet."""


def load_tileset_manifest(path):
    """Charge et valide un manifeste ainsi que les dimensions de son PNG."""
    manifest_path = Path(path)
    try:
        if manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
            raise TilesetValidationError("manifest_too_large")
        source = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(source, object_pairs_hook=_unique_object)
    except TilesetValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TilesetValidationError("manifest_unreadable") from error
    if not isinstance(manifest, dict):
        raise TilesetValidationError("manifest_type")
    image = manifest.get("image")
    if not isinstance(image, str) or not _SAFE_IMAGE.fullmatch(image):
        raise TilesetValidationError("image_path")
    size = _read_png_size(manifest_path.parent / image)
    return validate_tileset_manifest(
        manifest,
        image_size=size,
        expected_id=manifest_path.parent.name,
    )


def validate_tileset_manifest(manifest, *, image_size, expected_id=None):
    """Retourne une copie normalisée après validation complète du contrat."""
    if not isinstance(manifest, dict):
        raise TilesetValidationError("manifest_type")
    identifier = manifest.get("id")
    if not isinstance(identifier, str) or not _SAFE_IDENTIFIER.fullmatch(identifier):
        raise TilesetValidationError("id")
    if expected_id is not None and identifier != str(expected_id):
        raise TilesetValidationError("directory_id")
    if manifest.get("schema_version") != TILESET_SCHEMA_VERSION:
        raise TilesetValidationError("schema_version")
    image = manifest.get("image")
    if not isinstance(image, str) or not _SAFE_IMAGE.fullmatch(image):
        raise TilesetValidationError("image_path")

    tile_width = _positive_int(manifest.get("tile_width"), "tile_width")
    tile_height = _positive_int(manifest.get("tile_height"), "tile_height")
    width, height = image_size
    if (
        type(width) is not int
        or type(height) is not int
        or width <= 0
        or height <= 0
        or width % tile_width
        or height % tile_height
    ):
        raise TilesetValidationError("image_dimensions")
    columns = width // tile_width
    rows = height // tile_height
    if manifest.get("columns") != columns or manifest.get("rows") != rows:
        raise TilesetValidationError("grid_dimensions")

    license_data = manifest.get("license")
    if not isinstance(license_data, dict):
        raise TilesetValidationError("license")
    for field in ("name", "source"):
        if not isinstance(license_data.get(field), str) or not license_data[field].strip():
            raise TilesetValidationError(f"license_{field}")
    name_key = manifest.get("name_key")
    if name_key is not None and (
        not isinstance(name_key, str)
        or not re.fullmatch(r"web\.tileset_[a-z0-9_]{1,64}", name_key)
    ):
        raise TilesetValidationError("name_key")

    sprites = manifest.get("sprites")
    if not isinstance(sprites, dict) or not sprites:
        raise TilesetValidationError("sprites")
    normalized_sprites = {}
    for key, coordinates in sprites.items():
        if not isinstance(key, str) or not key or len(key) > 96:
            raise TilesetValidationError("sprite_key")
        if not isinstance(coordinates, dict) or set(coordinates) != {"x", "y"}:
            raise TilesetValidationError(f"sprite_coordinates:{key}")
        x = _coordinate(coordinates.get("x"), columns, key)
        y = _coordinate(coordinates.get("y"), rows, key)
        normalized_sprites[key] = {"x": x, "y": y}

    fallback = manifest.get("fallback")
    if not isinstance(fallback, str) or fallback not in normalized_sprites:
        raise TilesetValidationError("fallback")
    missing = STANDARD_VISUAL_KEYS - normalized_sprites.keys()
    if missing:
        raise TilesetValidationError(f"coverage:{sorted(missing)[0]}")
    edge_blending = _edge_blending(manifest.get("edge_blending"))

    return {
        "schema_version": TILESET_SCHEMA_VERSION,
        "id": identifier,
        "name": str(manifest.get("name") or identifier),
        "name_key": name_key,
        "image": image,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "columns": columns,
        "rows": rows,
        "fallback": fallback,
        "license": {
            "name": license_data["name"].strip(),
            "source": license_data["source"].strip(),
        },
        "sprites": normalized_sprites,
        "edge_blending": edge_blending,
    }


def discover_tilesets(root):
    """Découvre uniquement les manifestes valides dans des dossiers directs."""
    directory = Path(root)
    if not directory.is_dir():
        return []
    manifests = []
    for child in sorted(directory.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or not _SAFE_IDENTIFIER.fullmatch(child.name):
            continue
        try:
            manifests.append(load_tileset_manifest(child / "tileset.json"))
        except TilesetValidationError:
            continue
    return manifests


def _read_png_size(path):
    try:
        with Path(path).open("rb") as stream:
            header = stream.read(24)
    except OSError as error:
        raise TilesetValidationError("image_unreadable") from error
    if len(header) != 24 or header[:8] != _PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise TilesetValidationError("image_format")
    return struct.unpack(">II", header[16:24])


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TilesetValidationError(f"duplicate_key:{key}")
        result[key] = value
    return result


def _positive_int(value, field):
    if type(value) is not int or value <= 0 or value > 4096:
        raise TilesetValidationError(field)
    return value


def _coordinate(value, maximum, key):
    if type(value) is not int or not 0 <= value < maximum:
        raise TilesetValidationError(f"sprite_bounds:{key}")
    return value


def _edge_blending(value):
    if value is None:
        return {"mode": "none"}
    if not isinstance(value, dict) or value.get("mode") != "interlaced":
        raise TilesetValidationError("edge_blending")
    if set(value) != {"mode", "depth", "opacity"}:
        raise TilesetValidationError("edge_blending")
    depth = value["depth"]
    opacity = value["opacity"]
    if (
        isinstance(depth, bool)
        or not isinstance(depth, (int, float))
        or not 0 < float(depth) <= 0.5
        or isinstance(opacity, bool)
        or not isinstance(opacity, (int, float))
        or not 0 < float(opacity) <= 1
    ):
        raise TilesetValidationError("edge_blending")
    return {
        "mode": "interlaced",
        "depth": float(depth),
        "opacity": float(opacity),
    }
