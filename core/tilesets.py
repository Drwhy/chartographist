"""Validation stricte des thèmes de sprites indépendants de la simulation."""

import binascii
import json
from pathlib import Path
import re
import struct


TILESET_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_IMAGE_BYTES = 64 * 1024 * 1024
_MAX_IMAGE_DIMENSION = 8192
_MAX_IMAGE_PIXELS = 64 * 1024 * 1024
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
    "entity.vehicle.boat",
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
    image_info = _read_png_info(manifest_path.parent / image)
    sheet_image_info = {}
    sheets = manifest.get("sheets")
    if sheets is not None:
        if not isinstance(sheets, dict):
            raise TilesetValidationError("sheets")
        for identifier, definition in sheets.items():
            if (
                not isinstance(identifier, str)
                or not _SAFE_IDENTIFIER.fullmatch(identifier)
                or not isinstance(definition, dict)
            ):
                raise TilesetValidationError("sheets")
            sheet_image = definition.get("image")
            if (
                not isinstance(sheet_image, str)
                or not _SAFE_IMAGE.fullmatch(sheet_image)
            ):
                raise TilesetValidationError("image_path")
            sheet_image_info[identifier] = _read_png_info(
                manifest_path.parent / sheet_image
            )
    return validate_tileset_manifest(
        manifest,
        image_size=image_info[:2],
        sheet_image_info=sheet_image_info,
        expected_id=manifest_path.parent.name,
    )


def validate_tileset_manifest(
    manifest, *, image_size, sheet_image_info=None, expected_id=None
):
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
    sheets, default_sheet = _sprite_sheets(
        manifest, image_size, sheet_image_info
    )
    normalized_sprites = {}
    coverage = manifest.get("coverage", "complete")
    if coverage not in {"complete", "partial"} or type(coverage) is not str:
        raise TilesetValidationError("coverage")
    for key, coordinates in sprites.items():
        if not isinstance(key, str) or not key or len(key) > 96:
            raise TilesetValidationError("sprite_key")
        if not isinstance(coordinates, dict) or not {"x", "y"}.issubset(
            coordinates
        ):
            raise TilesetValidationError(f"sprite_coordinates:{key}")
        if set(coordinates) - {
            "x", "y", "sheet", "scale", "anchor_x", "anchor_y", "rotation",
            "auto_mirror",
        }:
            raise TilesetValidationError(f"sprite_coordinates:{key}")
        sheet_id = coordinates.get("sheet", default_sheet)
        if not isinstance(sheet_id, str) or sheet_id not in sheets:
            raise TilesetValidationError(f"sprite_sheet:{key}")
        sheet = sheets[sheet_id]
        x = _coordinate(coordinates.get("x"), sheet["columns"], key)
        y = _coordinate(coordinates.get("y"), sheet["rows"], key)
        scale = _ratio(
            coordinates.get("scale", sheet["scale"]),
            "sprite_scale",
        )
        anchor_x = _anchor(
            coordinates.get("anchor_x", sheet["anchor_x"]),
            "sprite_anchor",
        )
        anchor_y = _anchor(
            coordinates.get("anchor_y", sheet["anchor_y"]),
            "sprite_anchor",
        )
        rotation = coordinates.get("rotation", 0)
        if type(rotation) is not int or rotation not in {0, 90, 180, 270}:
            raise TilesetValidationError(f"sprite_rotation:{key}")
        auto_mirror = coordinates.get("auto_mirror", False)
        if type(auto_mirror) is not bool:
            raise TilesetValidationError(f"sprite_auto_mirror:{key}")
        if key.startswith("entity.") and scale < 1 and not sheet["alpha"]:
            raise TilesetValidationError(f"sprite_alpha:{key}")
        normalized_sprites[key] = {
            "x": x,
            "y": y,
            "sheet": sheet_id,
            "scale": scale,
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            "rotation": rotation,
            "auto_mirror": auto_mirror,
        }

    fallback = manifest.get("fallback")
    if not isinstance(fallback, str) or fallback not in normalized_sprites:
        raise TilesetValidationError("fallback")
    missing = STANDARD_VISUAL_KEYS - normalized_sprites.keys()
    if coverage == "complete" and missing:
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
        "coverage": coverage,
        "license": {
            "name": license_data["name"].strip(),
            "source": license_data["source"].strip(),
        },
        "sprites": normalized_sprites,
        "sheets": sheets,
        "default_sheet": default_sheet,
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


def _sprite_sheets(manifest, image_size, sheet_image_info):
    definitions = manifest.get("sheets")
    if definitions is None:
        width, height = image_size
        return {
            "default": {
                "image": manifest["image"],
                "tile_width": manifest["tile_width"],
                "tile_height": manifest["tile_height"],
                "columns": width // manifest["tile_width"],
                "rows": height // manifest["tile_height"],
                "alpha": True,
                "scale": 1.0,
                "anchor_x": 0.5,
                "anchor_y": 0.5,
            },
        }, "default"
    if not isinstance(definitions, dict) or not definitions:
        raise TilesetValidationError("sheets")
    image_info = sheet_image_info or {}
    sheets = {}
    for identifier, definition in definitions.items():
        if (
            not isinstance(identifier, str)
            or not _SAFE_IDENTIFIER.fullmatch(identifier)
            or not isinstance(definition, dict)
        ):
            raise TilesetValidationError("sheets")
        image = definition.get("image")
        if not isinstance(image, str) or not _SAFE_IMAGE.fullmatch(image):
            raise TilesetValidationError("image_path")
        tile_width = _positive_int(
            definition.get("tile_width"), "sheet_tile_width"
        )
        tile_height = _positive_int(
            definition.get("tile_height"), "sheet_tile_height"
        )
        info = image_info.get(identifier)
        if info is None and image == manifest["image"]:
            info = (*image_size, bool(definition.get("alpha", True)))
        if not isinstance(info, (tuple, list)) or len(info) != 3:
            raise TilesetValidationError("sheet_image")
        width, height, has_alpha = info
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
        if (
            definition.get("columns") != columns
            or definition.get("rows") != rows
        ):
            raise TilesetValidationError("grid_dimensions")
        alpha = definition.get("alpha", False)
        if not isinstance(alpha, bool) or (alpha and not has_alpha):
            raise TilesetValidationError("sheet_alpha")
        sheets[identifier] = {
            "image": image,
            "tile_width": tile_width,
            "tile_height": tile_height,
            "columns": columns,
            "rows": rows,
            "alpha": alpha,
            "scale": _ratio(definition.get("scale", 1.0), "sheet_scale"),
            "anchor_x": _anchor(
                definition.get("anchor_x", 0.5), "sheet_anchor"
            ),
            "anchor_y": _anchor(
                definition.get("anchor_y", 0.5), "sheet_anchor"
            ),
        }
    default_sheet = manifest.get("default_sheet", next(iter(sheets)))
    if not isinstance(default_sheet, str) or default_sheet not in sheets:
        raise TilesetValidationError("default_sheet")
    return sheets, default_sheet


def _read_png_info(path):
    try:
        image_path = Path(path)
        if image_path.stat().st_size > _MAX_IMAGE_BYTES:
            raise TilesetValidationError("image_too_large")
        with image_path.open("rb") as stream:
            header = stream.read(29)
    except TilesetValidationError:
        raise
    except OSError as error:
        raise TilesetValidationError("image_unreadable") from error
    if len(header) != 29 or header[:8] != _PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise TilesetValidationError("image_format")
    width, height = struct.unpack(">II", header[16:24])
    depth, color, compression, filtering, interlace = header[24:29]
    if (
        width <= 0
        or height <= 0
        or width > _MAX_IMAGE_DIMENSION
        or height > _MAX_IMAGE_DIMENSION
        or width * height > _MAX_IMAGE_PIXELS
    ):
        raise TilesetValidationError("image_dimensions")
    if (
        depth != 8
        or color not in {2, 6}
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        raise TilesetValidationError("image_encoding")
    _validate_png_chunks(image_path)
    return width, height, color == 6


def _validate_png_chunks(path):
    """Vérifie structure et CRC en flux, sans décoder les pixels."""
    seen_header = False
    seen_data = False
    seen_end = False
    try:
        with Path(path).open("rb") as stream:
            if stream.read(8) != _PNG_SIGNATURE:
                raise TilesetValidationError("image_format")
            while not seen_end:
                length_bytes = stream.read(4)
                kind = stream.read(4)
                if len(length_bytes) != 4 or len(kind) != 4:
                    raise TilesetValidationError("image_truncated")
                length = struct.unpack(">I", length_bytes)[0]
                if length > _MAX_IMAGE_BYTES:
                    raise TilesetValidationError("image_chunk")
                if not seen_header and (kind != b"IHDR" or length != 13):
                    raise TilesetValidationError("image_format")
                if kind[0] < 97 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
                    raise TilesetValidationError("image_chunk")

                checksum = binascii.crc32(kind)
                remaining = length
                while remaining:
                    block = stream.read(min(64 * 1024, remaining))
                    if not block:
                        raise TilesetValidationError("image_truncated")
                    checksum = binascii.crc32(block, checksum)
                    remaining -= len(block)
                expected = stream.read(4)
                if len(expected) != 4:
                    raise TilesetValidationError("image_truncated")
                if (checksum & 0xFFFFFFFF) != struct.unpack(">I", expected)[0]:
                    raise TilesetValidationError("image_crc")

                seen_header = seen_header or kind == b"IHDR"
                if kind == b"IDAT" and length:
                    seen_data = True
                if kind == b"IEND":
                    if length != 0 or stream.read(1):
                        raise TilesetValidationError("image_format")
                    seen_end = True
    except TilesetValidationError:
        raise
    except OSError as error:
        raise TilesetValidationError("image_unreadable") from error
    if not (seen_header and seen_data and seen_end):
        raise TilesetValidationError("image_truncated")


def _read_png_size(path):
    return _read_png_info(path)[:2]


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


def _ratio(value, field):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.1 <= float(value) <= 1
    ):
        raise TilesetValidationError(field)
    return float(value)


def _anchor(value, field):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= float(value) <= 1
    ):
        raise TilesetValidationError(field)
    return float(value)


def _coordinate(value, maximum, key):
    if type(value) is not int or not 0 <= value < maximum:
        raise TilesetValidationError(f"sprite_bounds:{key}")
    return value


def _edge_blending(value):
    if value is None:
        return {"mode": "none"}
    if not isinstance(value, dict):
        raise TilesetValidationError("edge_blending")
    mode = value.get("mode")
    if mode == "interlaced":
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
    if mode != "puzzle" or set(value) != {"mode", "depth", "teeth"}:
        raise TilesetValidationError("edge_blending")
    depth = value["depth"]
    teeth = value["teeth"]
    if (
        isinstance(depth, bool)
        or not isinstance(depth, (int, float))
        or not 0 < float(depth) <= 0.5
        or type(teeth) is not int
        or not 2 <= teeth <= 16
    ):
        raise TilesetValidationError("edge_blending")
    return {
        "mode": "puzzle",
        "depth": float(depth),
        "teeth": teeth,
    }
