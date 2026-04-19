import math
import time
import sys
from core.random_service import RandomService

def get_char_at(x, y, world_data, config, entity_map=None):
    """
    Pure rendering logic based on Z-Index layers.
    Business intelligence is delegated to entity classes.
    """
    # 1. ENTITY LAYER (Highest priority)
    if entity_map is not None:
        entity = entity_map.get((x, y))
        if entity:
            return entity.char
    else:
        entities_at_pos = [e for e in world_data['entities'] if e.pos == (x, y) and not e.is_expired]
        if entities_at_pos:
            return max(entities_at_pos, key=lambda e: e.z_index).char

    # 2. INFRASTRUCTURE & HYDROLOGY LAYER
    # Roads and rivers are world data layers beneath entities
    h = world_data['elev'][y][x]
    rd = world_data['road'][y][x]
    r = world_data['riv'][y][x]

    if rd and rd != "  " and h >= 0:
        return rd
    if r > 0 and h >= 0:
        return config.get("water", {}).get("river", "~~")

    # 3. TERRAIN LAYER (The background map)
    cycle = world_data.get('cycle', 0)
    return _calculate_complex_biome(x, y, h, cycle, world_data['width'], world_data['height'], config)

def _calculate_complex_biome(x, y, h, cycle, width, height, config):
    """
    Calculates the biome based on altitude, latitude, and seasonal tilt.
    """
    biomes = config.get("biomes", {})
    water = config.get("water", {})

    # --- TEMPERATURE CALCULATION ---
    # Latitude (colder at poles, warmer at equator)
    dist_to_equator = abs(y - (height // 2)) / (height // 2)
    # Axial tilt (simulates seasonal cycles over time)
    tilt = math.sin(cycle * 0.15)

    # Combined formula: Latitude + Season + Altitude (higher = colder)
    temp = (dist_to_equator * 0.6) + (tilt * (y / height - 0.5) * 0.5) + (h * 0.4)

    # --- ELEVATION THRESHOLDS (Verticality) ---
    if h > 0.90: return biomes.get("volcano", "🌋")
    if h > 0.85 or temp > 0.8: return biomes.get("peak", "❄️")
    if h > 0.55: return biomes.get("high_mountain", "🏔️")
    if h > 0.35: return biomes.get("mountain", "⛰️")

    # --- WATER THRESHOLDS ---
    if h < -0.15: return water.get("ocean", "🌊")
    if h < 0: return water.get("shore", "💧")
    if h < 0.05: return biomes.get("sand", "🏖️")

    # --- CLIMATE DISTRIBUTION (Vegetation) ---
    if temp > 0.65:
        return biomes.get("boreal_forest", "🌲") if h > 0.2 else biomes.get("glaciated", "❄️")

    if temp > 0.45:
        # Autumn forest if specific conditions are met
        if h > 0.2 and 0.48 < temp < 0.55:
            return biomes.get("autumn_forest", "🍂")
        return biomes.get("temperate_forest", "🌳")

    if temp < 0.25 and h > 0.12:
        return biomes.get("tropical_forest", "🌴")

    # FALLBACK: Default Grassland
    return biomes.get("grassland", "🌿")

def render_map(width, height, world_data, config):
    """Renders the map grid line by line."""
    entity_map = {}
    for e in world_data['entities']:
        if not e.is_expired:
            pos = e.pos
            if pos not in entity_map or e.z_index > entity_map[pos].z_index:
                entity_map[pos] = e

    for y in range(height):
        line = "".join([get_char_at(x, y, world_data, config, entity_map) for x in range(width)])
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

    for i, (x, y) in enumerate(coords):
        current_display[y][x] = get_char_at(x, y, world_data, renderer.config)
        if i % 15 == 0 or i == len(coords) - 1:
            sys.stdout.write("\033[H")
            print(f"--- 📜 GENESIS: {stats['seed']} ---")
            for row in current_display:
                print("".join(row))
            sys.stdout.flush()
            time.sleep(0.005)