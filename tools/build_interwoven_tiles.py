"""Construit les feuilles climatiques et les atlas connectés Interwoven."""

from argparse import ArgumentParser
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance


TILE_SIZE = 156
TERRAINS_PER_ROW = 7
SEASON_ROWS = 2
VARIANTS = (
    "winter",
    "spring",
    "summer",
    "autumn",
    "drought",
    "flood",
    "heatwave",
    "cold_snap",
)


def _source_tiles(path):
    source = Image.open(path).convert("RGB")
    tiles = []
    for row in range(SEASON_ROWS):
        top = round(row * source.height / SEASON_ROWS)
        bottom = round((row + 1) * source.height / SEASON_ROWS)
        for column in range(TERRAINS_PER_ROW):
            left = round(column * source.width / TERRAINS_PER_ROW)
            right = round((column + 1) * source.width / TERRAINS_PER_ROW)
            width = right - left
            height = bottom - top
            side = min(width, height)
            crop_left = left + (width - side) // 2
            crop_top = top + (height - side) // 2
            tile = source.crop((
                crop_left,
                crop_top,
                crop_left + side,
                crop_top + side,
            ))
            tiles.append(tile.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS))
    return tiles


def _tint(tile, color, opacity, saturation=1.0, contrast=1.0):
    adjusted = ImageEnhance.Color(tile).enhance(saturation)
    adjusted = ImageEnhance.Contrast(adjusted).enhance(contrast)
    overlay = Image.new("RGB", adjusted.size, color)
    return Image.blend(adjusted, overlay, opacity)


def build_climate_sheet(sources, destination):
    seasons = {name: _source_tiles(path) for name, path in sources.items()}
    variants = {
        "winter": seasons["winter"],
        "spring": seasons["spring"],
        "summer": seasons["summer"],
        "autumn": seasons["autumn"],
        "drought": [
            _tint(tile, (181, 126, 55), 0.25, saturation=0.7, contrast=1.08)
            for tile in seasons["summer"]
        ],
        "flood": [
            _tint(tile, (54, 104, 125), 0.22, saturation=0.8, contrast=0.92)
            for tile in seasons["spring"]
        ],
        "heatwave": [
            _tint(tile, (226, 126, 42), 0.18, saturation=1.05, contrast=1.08)
            for tile in seasons["summer"]
        ],
        "cold_snap": [
            _tint(tile, (190, 224, 239), 0.18, saturation=0.75, contrast=1.04)
            for tile in seasons["winter"]
        ],
    }
    sheet = Image.new(
        "RGBA",
        (TERRAINS_PER_ROW * TILE_SIZE, len(VARIANTS) * SEASON_ROWS * TILE_SIZE),
    )
    for variant_index, variant in enumerate(VARIANTS):
        for terrain_index, tile in enumerate(variants[variant]):
            column = terrain_index % TERRAINS_PER_ROW
            source_row = terrain_index // TERRAINS_PER_ROW
            row = variant_index * SEASON_ROWS + source_row
            sheet.paste(tile.convert("RGBA"), (column * TILE_SIZE, row * TILE_SIZE))
    sheet.save(destination)


RIVER_CONNECTIONS = (
    ("vertical", ("n", "s")),
    ("horizontal", ("e", "w")),
    ("corner_ne", ("n", "e")),
    ("corner_nw", ("n", "w")),
    ("corner_se", ("s", "e")),
    ("corner_sw", ("s", "w")),
    ("fork_north", ("n", "e", "w")),
    ("fork_east", ("n", "e", "s")),
    ("fork_south", ("e", "s", "w")),
    ("fork_west", ("n", "s", "w")),
    ("cross", ("n", "e", "s", "w")),
)


def _river_tile(connections):
    scale = 4
    side = TILE_SIZE * scale
    center = side // 2
    endpoints = {
        "n": (center, -scale),
        "e": (side + scale, center),
        "s": (center, side + scale),
        "w": (-scale, center),
    }
    image = Image.new("RGBA", (side, side))
    draw = ImageDraw.Draw(image)
    paths = [[(center, center), endpoints[direction]] for direction in connections]
    for path in paths:
        draw.line(path, fill=(33, 62, 51, 215), width=58 * scale)
    for path in paths:
        draw.line(path, fill=(37, 123, 170, 255), width=42 * scale)
    draw.ellipse(
        (center - 25 * scale, center - 25 * scale,
         center + 25 * scale, center + 25 * scale),
        fill=(37, 123, 170, 255),
    )
    for path in paths:
        draw.line(path, fill=(102, 190, 210, 190), width=7 * scale)
    return image.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)


def build_river_sheet(destination):
    columns = 4
    rows = 3
    sheet = Image.new("RGBA", (columns * TILE_SIZE, rows * TILE_SIZE))
    for index, (_, connections) in enumerate(RIVER_CONNECTIONS):
        sheet.paste(
            _river_tile(connections),
            ((index % columns) * TILE_SIZE, (index // columns) * TILE_SIZE),
        )
    sheet.save(destination)


def build_generated_grid(source_path, destination, *, columns, rows, tile_size):
    """Normalise une planche ImageGen sur une grille exacte et transparente."""
    source = Image.open(source_path).convert("RGBA")
    sheet = Image.new("RGBA", (columns * tile_size, rows * tile_size))
    for row in range(rows):
        top = round(row * source.height / rows)
        bottom = round((row + 1) * source.height / rows)
        for column in range(columns):
            left = round(column * source.width / columns)
            right = round((column + 1) * source.width / columns)
            tile = source.crop((left, top, right, bottom)).resize(
                (tile_size, tile_size),
                Image.Resampling.LANCZOS,
            )
            sheet.alpha_composite(tile, (column * tile_size, row * tile_size))
    sheet.save(destination)


def build_water_sheet(ocean_path, shore_path, destination):
    ocean = Image.open(ocean_path).convert("RGB").resize(
        (TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS
    )
    shore = Image.open(shore_path).convert("RGB").resize(
        (TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS
    )
    variants = {
        "winter": (
            _tint(ocean, (160, 205, 225), 0.22, saturation=0.72),
            _tint(shore, (220, 229, 223), 0.28, saturation=0.62),
        ),
        "spring": (
            _tint(ocean, (55, 135, 165), 0.08, saturation=0.95),
            _tint(shore, (187, 164, 102), 0.08, saturation=0.95),
        ),
        "summer": (
            _tint(ocean, (16, 105, 148), 0.10, saturation=1.08),
            _tint(shore, (221, 181, 86), 0.12, saturation=1.05),
        ),
        "autumn": (
            _tint(ocean, (58, 105, 123), 0.12, saturation=0.82),
            _tint(shore, (174, 132, 73), 0.16, saturation=0.88),
        ),
        "drought": (
            _tint(ocean, (35, 84, 101), 0.22, saturation=0.70, contrast=1.08),
            _tint(shore, (183, 126, 55), 0.28, saturation=0.72, contrast=1.08),
        ),
        "flood": (
            _tint(ocean, (40, 132, 171), 0.20, saturation=1.08),
            _tint(shore, (55, 126, 151), 0.34, saturation=0.82),
        ),
        "heatwave": (
            _tint(ocean, (22, 100, 119), 0.18, saturation=0.88),
            _tint(shore, (226, 142, 50), 0.22, saturation=1.03),
        ),
        "cold_snap": (
            _tint(ocean, (188, 225, 238), 0.30, saturation=0.56, contrast=1.04),
            _tint(shore, (226, 236, 235), 0.35, saturation=0.48, contrast=1.04),
        ),
    }
    sheet = Image.new("RGBA", (2 * TILE_SIZE, len(VARIANTS) * TILE_SIZE))
    for row, variant in enumerate(VARIANTS):
        for column, tile in enumerate(variants[variant]):
            sheet.paste(tile.convert("RGBA"), (column * TILE_SIZE, row * TILE_SIZE))
    sheet.save(destination)


def main():
    parser = ArgumentParser()
    for season in ("winter", "spring", "summer", "autumn"):
        parser.add_argument(f"--{season}", type=Path, required=True)
    parser.add_argument("--climate-out", type=Path, required=True)
    parser.add_argument("--rivers-out", type=Path, required=True)
    parser.add_argument("--river-source", type=Path)
    parser.add_argument("--road-source", type=Path)
    parser.add_argument("--roads-out", type=Path)
    parser.add_argument("--cultures-source", type=Path)
    parser.add_argument("--cultures-out", type=Path)
    parser.add_argument("--ocean", type=Path, required=True)
    parser.add_argument("--shore", type=Path, required=True)
    parser.add_argument("--water-out", type=Path, required=True)
    args = parser.parse_args()
    sources = {season: getattr(args, season) for season in (
        "winter", "spring", "summer", "autumn"
    )}
    build_climate_sheet(sources, args.climate_out)
    if args.river_source is None:
        build_river_sheet(args.rivers_out)
    else:
        build_generated_grid(
            args.river_source,
            args.rivers_out,
            columns=4,
            rows=3,
            tile_size=TILE_SIZE,
        )
    if bool(args.road_source) != bool(args.roads_out):
        parser.error("--road-source and --roads-out must be provided together")
    if args.road_source:
        build_generated_grid(
            args.road_source,
            args.roads_out,
            columns=4,
            rows=3,
            tile_size=TILE_SIZE,
        )
    if bool(args.cultures_source) != bool(args.cultures_out):
        parser.error("--cultures-source and --cultures-out must be provided together")
    if args.cultures_source:
        build_generated_grid(
            args.cultures_source,
            args.cultures_out,
            columns=4,
            rows=2,
            tile_size=256,
        )
    build_water_sheet(args.ocean, args.shore, args.water_out)


if __name__ == "__main__":
    main()
