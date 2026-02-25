import random
from .civilizations import grow_population, build_roads, expand_civilization # <-- Ajout ici
from .events import RANDOM_EVENTS

def evolve_world(width, height, elevation, river_map, plates, structures, road_map, cycle):
    new_logs = []

    # 1. Croissance (Village -> Cité)
    new_logs.extend(grow_population(structures))

    # 2. EXPANSION (Migration : Cité -> Nouveau Village)
    # On passe la config des cultures au cas où, mais ici on utilise la culture mère
    migration_logs = expand_civilization(width, height, elevation, structures, None)
    new_logs.extend(migration_logs)

    # 3. Routes
    if cycle % 5 == 0:
        build_roads(width, height, elevation, structures, road_map)

    # 4. Événements
    for pos in list(structures.keys()):
        for probability, event_func in RANDOM_EVENTS:
            if random.random() < probability:
                log = event_func(structures, pos)
                if log: new_logs.append(log)

    return structures, new_logs