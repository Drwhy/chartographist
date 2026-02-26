import random
import math
from core.names import get_name_by_culture
from entities.species.human.settler import Settler

def seed_civilization(width, height, elevation, riv, plates, config_cultures):
    """
    Initialise les premiers foyers de population sur la carte au début de la simulation.
    Autorise désormais l'implantation en montagne.
    """
    initial_civ = {}
    # On génère entre 5 et 8 points de départ
    num_seeds = random.randint(5, 8)
    attempts = 0

    while len(initial_civ) < num_seeds and attempts < 200:
        attempts += 1
        rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)
        h = elevation[ry][rx]

        # --- CRITÈRES D'HABITABILITÉ ---
        # h < 0 : Ocean/Shore | h > 0 : Terre ferme
        # On autorise désormais jusqu'à h = 0.95 (presque le sommet des volcans)
        is_land = 0 <= h < 0.95

        # Vérification de proximité de l'eau (rivière ou mer adjacente)
        is_near_water = riv[ry][rx] > 0 or any(
            elevation[ny][nx] < 0 for ny, nx in [
                (ry-1, rx), (ry+1, rx), (ry, rx-1), (ry, rx+1)
            ] if 0 <= ny < height and 0 <= nx < width
        )

        # --- LOGIQUE D'IMPLANTATION ---
        # Un village peut s'installer si :
        # 1. C'est une plaine fertile avec de l'eau (h < 0.4)
        # 2. OU c'est une montagne isolée (h > 0.6), façon monastère ou citadelle
        can_settle = False
        if is_land:
            if h < 0.4 and (is_near_water or random.random() < 0.1):
                can_settle = True
            elif h >= 0.4 and random.random() < 0.05: # Plus rare en montagne
                can_settle = True

        if can_settle and (rx, ry) not in initial_civ:
            local_culture = random.choice(config_cultures)
            city_name = get_name_by_culture(local_culture)

            # Si le village est très haut, on peut ajuster son nom
            if h > 0.7:
                city_name = f"Pic de {city_name}"
            elif h > 0.4:
                city_name = f"Mont {city_name}"

            initial_civ[(rx, ry)] = {
                "name": city_name,
                "type": "village", # Tout commence comme un village
                "culture": local_culture,
                "age": 0,
                "population": random.randint(800, 2000)
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