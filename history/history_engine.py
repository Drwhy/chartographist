from .population import grow_population
from .colonization import expand_civilization
from .infrastructure import build_roads
from .events import RANDOM_INCIDENTS # On renomme pour plus de clarté
import random

def evolve_world(width, height, elevation, river_map, plates, structures, road_map, cycle):
    new_logs = []

    # --- MÉCANIQUES SYSTÉMIQUES (Toujours actives) ---
    new_logs.extend(grow_population(structures))
    new_logs.extend(expand_civilization(width, height, elevation, structures))

    if cycle % 5 == 0:
        build_roads(width, height, elevation, structures, road_map)

    # --- INCIDENTS ALÉATOIRES (Le "Destin") ---
    for prob, func, etype in RANDOM_INCIDENTS:
        if random.random() < prob:
            if etype == "map":
                # Événement qui nécessite la connaissance de la carte
                res = func(width, height, elevation, structures)
                if res: new_logs.append(res)
            elif etype == "city" and structures:
                # Événement qui frappe une ville au hasard
                pos = random.choice(list(structures.keys()))
                res = func(structures, pos)
                if res: new_logs.append(res)

    return structures, new_logs