import random
from .population import grow_population
from .colonization import expand_civilization
from .infrastructure import build_roads
from .events import RANDOM_INCIDENTS

def evolve_world(width, height, elevation, river_map, plates, structures, road_map, cycle):
    """
    Chef d'orchestre de l'évolution temporelle.
    Retourne : (structures_mises_à_jour, nouveaux_logs, nouveaux_colons)
    """
    new_logs = []

    # 1. Évolution interne (Village -> Cité)
    # Renvoie une liste de messages [str, str...]
    pop_logs = grow_population(structures)
    new_logs.extend(pop_logs)

    # 2. Expansion et Migration (Cité -> Création de colons)
    # On déballe le tuple : migration_logs (list de str), settlers (list d'objets)
    migration_logs, newly_spawned_settlers = expand_civilization(width, height, elevation, structures)
    new_logs.extend(migration_logs)

    # 3. Infrastructure (Routes)
    # On ne construit pas à chaque tour pour laisser le temps aux colons de voyager
    if cycle % 5 == 0:
        build_roads(width, height, elevation, structures, road_map)

    # 4. Aléas historiques (Catastrophes et Incidents)
    for prob, func, etype in RANDOM_INCIDENTS:
        if random.random() < prob:
            if etype == "map":
                # Événement global (ex: éruption volcanique)
                res = func(width, height, elevation, structures)
                if res: new_logs.append(res)
            elif etype == "city" and structures:
                # Événement ciblé (ex: peste)
                pos = random.choice(list(structures.keys()))
                res = func(structures, pos)
                if res: new_logs.append(res)

    # On retourne les 3 éléments nécessaires au main.py
    return structures, new_logs, newly_spawned_settlers