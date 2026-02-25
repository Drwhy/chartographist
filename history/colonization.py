import random
import math
from core.names import get_name_by_culture
from fauna.species.human.settler import Settler

def seed_civilization(width, height, elevation, riv, plates, config_cultures):
    """Initialise les premiers foyers de population sur la carte."""
    initial_civ = {}
    num_seeds = random.randint(5, 8)
    attempts = 0
    while len(initial_civ) < num_seeds and attempts < 100:
        attempts += 1
        rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)
        h = elevation[ry][rx]

        # On cherche des zones habitables (pas trop haut, pas dans l'eau)
        is_fertile = 0 < h < 0.5
        is_near_water = riv[ry][rx] > 0 or any(
            elevation[ny][nx] < 0 for ny, nx in [(ry-1, rx), (ry+1, rx), (ry, rx-1), (ry, rx+1)]
            if 0 <= ny < height and 0 <= nx < width
        )

        if is_fertile and (is_near_water or random.random() < 0.1):
            local_culture = random.choice(config_cultures)
            city_name = get_name_by_culture(local_culture)

            initial_civ[(rx, ry)] = {
                "name": city_name,
                "type": "village",
                "culture": local_culture,
                "age": 0,
                "population": random.randint(500, 1500)
            }
    return initial_civ

def expand_civilization(width, height, elevation, structures):
    """Logique d'expansion : les cités envoient des colons fonder de nouveaux villages."""
    logs = []
    new_settlers = []

    # Seules les cités (établies) peuvent coloniser
    current_cities = [pos for pos, s in structures.items() if s["type"] == "city"]

    for pos in current_cities:
        # Faible chance par tour de lancer une expédition
        if random.random() < 0.008:
            cx, cy = pos
            # Distance de colonisation
            dist, angle = random.randint(5, 10), random.uniform(0, 6.28)
            nx, ny = int(cx + math.cos(angle) * dist), int(cy + math.sin(angle) * dist)

            # Vérification des limites et du terrain (pas d'eau)
            if 0 <= nx < width and 0 <= ny < height:
                if elevation[ny][nx] >= 0 and (nx, ny) not in structures:
                    parent = structures[pos]
                    culture_data = parent["culture"]

                    # 1. On génère le nom du futur village AVANT de créer le colon
                    future_name = get_name_by_culture(culture_data)

                    # 2. On instancie le Settler
                    # Note : Vérifie que l'ordre des arguments (pos, target, culture)
                    # correspond bien au __init__ de ta classe Settler
                    settler = Settler(pos, (nx, ny), culture_data)

                    # 3. FIX : On attache le nom à l'objet pour que l'engine le trouve
                    settler.target_name = future_name

                    new_settlers.append(settler)
                    logs.append(f"👨‍👩‍👧‍👦 {parent['name']} envoie des pionniers fonder {future_name}.")

    return logs, new_settlers