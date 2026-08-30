import math
import time
import sys
from core.presentation import VisualCellResolver
from core.random_service import RandomService
from core.translator import Translator

def get_char_at(x, y, world_data, config, entity_map=None):
    """Rend le glyphe issu du résolveur sémantique commun."""
    resolver = VisualCellResolver(world_data, config, entity_map=entity_map)
    return resolver.resolve(x, y)["glyph"]


def render_map(width, height, world_data, config):
    """Renders the map grid line by line."""
    resolver = VisualCellResolver(world_data, config)
    for y in range(height):
        line = "".join(
            resolver.resolve(x, y)["glyph"] for x in range(width)
        )
        print(line)

def radial_reveal(renderer, world_data, stats):
    """Radial genesis animation."""
    width, height = renderer.width, renderer.height
    world_data['width'], world_data['height'] = width, height

    current_display = [["  " for _ in range(width)] for _ in range(height)]
    coords = [(x, y) for y in range(height) for x in range(width)]
    center = (width // 2, height // 2)

    # Sort by distance from center with a bit of random jitter for organic feel
    coords.sort(key=lambda c: math.dist(c, center) + RandomService.uniform(-1, 1))

    resolver = VisualCellResolver(world_data, renderer.config)
    for i, (x, y) in enumerate(coords):
        current_display[y][x] = resolver.resolve(x, y)["glyph"]
        if i % 15 == 0 or i == len(coords) - 1:
            sys.stdout.write("\033[H")
            print(Translator.translate("ui.genesis", seed=stats['seed']))
            for row in current_display:
                print("".join(row))
            sys.stdout.flush()
            time.sleep(0.005)