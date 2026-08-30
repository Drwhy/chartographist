"""Génère un thème multicouche minimal sans dépendance externe."""

import binascii
import json
from pathlib import Path
import re
import struct
import zlib


_SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def create_minimal_tileset(destination, *, identifier=None):
    """Crée un exemple partiel chargeable dans un nouveau dossier."""
    root = Path(destination)
    theme_id = root.name if identifier is None else identifier
    if not isinstance(theme_id, str) or not _SAFE_IDENTIFIER.fullmatch(theme_id):
        raise ValueError("unsafe tileset identifier")
    root.mkdir(parents=True, exist_ok=False)

    _write_terrain(root / "terrain.png")
    _write_entities(root / "entities.png")
    manifest = {
        "schema_version": 1,
        "id": theme_id,
        "name": "Minimal Multilayer Example",
        "image": "terrain.png",
        "tile_width": 16,
        "tile_height": 16,
        "columns": 2,
        "rows": 1,
        "default_sheet": "terrain",
        "coverage": "partial",
        "sheets": {
            "terrain": {
                "image": "terrain.png",
                "tile_width": 16,
                "tile_height": 16,
                "columns": 2,
                "rows": 1,
                "alpha": False,
            },
            "entities": {
                "image": "entities.png",
                "tile_width": 16,
                "tile_height": 16,
                "columns": 1,
                "rows": 1,
                "alpha": True,
                "scale": 0.75,
                "anchor_x": 0.5,
                "anchor_y": 1.0,
            },
        },
        "fallback": "fallback.unknown",
        "license": {
            "name": "CC0-1.0",
            "source": "Generated locally by tools.tileset_scaffold",
        },
        "sprites": {
            "terrain.grassland": {"x": 0, "y": 0, "sheet": "terrain"},
            "fallback.unknown": {"x": 1, "y": 0, "sheet": "terrain"},
            "entity.human": {
                "x": 0,
                "y": 0,
                "sheet": "entities",
                "auto_mirror": True,
            },
        },
    }
    manifest_path = root / "tileset.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _write_terrain(path):
    rows = []
    for y in range(16):
        row = bytearray()
        for x in range(32):
            if x < 16:
                color = (68, 111, 58) if (x + y) % 4 else (84, 132, 70)
            else:
                color = (185, 45, 154) if (x + y) % 4 else (44, 20, 52)
            row.extend(color)
        rows.append(bytes(row))
    _write_png(path, 32, 16, 2, rows)


def _write_entities(path):
    rows = []
    for y in range(16):
        row = bytearray()
        for x in range(16):
            visible = (
                (5 <= x <= 10 and 3 <= y <= 12)
                or (3 <= x <= 12 and 9 <= y <= 14)
            )
            row.extend((224, 190, 105, 255) if visible else (0, 0, 0, 0))
        rows.append(bytes(row))
    _write_png(path, 16, 16, 6, rows)


def _write_png(path, width, height, color_type, rows):
    raw = b"".join(b"\x00" + row for row in rows)
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    payload = (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, level=9))
        + _chunk(b"IEND", b"")
    )
    Path(path).write_bytes(payload)


def _chunk(kind, payload):
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)
