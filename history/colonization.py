import random
import math
from core.names import get_name_by_culture
def seed_civilization(width, height, elevation, riv, plates, config_cultures):
    initial_civ = {}
    num_seeds = random.randint(5, 8)
    attempts = 0
    while len(initial_civ) < num_seeds and attempts < 100:
        attempts += 1
        rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)
        h = elevation[ry][rx]

        is_fertile = 0 < h < 0.5
        is_near_water = riv[ry][rx] > 0 or any(
            elevation[ny][nx] < 0 for ny, nx in [(ry-1, rx), (ry+1, rx), (ry, rx-1), (ry, rx+1)]
            if 0 <= ny < height and 0 <= nx < width
        )

        if is_fertile and (is_near_water or random.random() < 0.1):
            local_culture = random.choice(config_cultures)
            # Logique simplifiée pour la culture via plaques
            if isinstance(plates, list) and isinstance(plates[0], list):
                plate_id = plates[ry][rx]
                # On pourrait chercher la culture spécifique à la plaque ici

            city_name = get_name_by_culture(local_culture)
            initial_civ[(rx, ry)] = {
                "name": city_name, "type": "village", "culture": local_culture,
                "age": 0, "population": random.randint(500, 1500)
            }
    return initial_civ

def expand_civilization(width, height, elevation, structures):
    logs = []
    current_cities = [pos for pos, s in structures.items() if s["type"] == "city"]
    for pos in current_cities:
        if random.random() < 0.005:
            cx, cy = pos
            dist, angle = random.randint(3, 5), random.uniform(0, 6.28)
            nx, ny = int(cx + math.cos(angle) * dist), int(cy + math.sin(angle) * dist)

            if 0 <= nx < width and 0 <= ny < height:
                if elevation[ny][nx] >= 0 and (nx, ny) not in structures:
                    parent = structures[pos]
                    structures[(nx, ny)] = {
                        "name": f"Nouveau {parent['name']}",
                        "type": "village",
                        "culture": parent["culture"],
                        "age": 0
                    }
                    logs.append(f"Des colons de {parent['name']} ont fondé un village.")
    return logs