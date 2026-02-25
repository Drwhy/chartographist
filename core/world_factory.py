# core/world_factory.py
import random
import geo
import history
import fauna

def assemble_world(width, height, config, seed_val):
    """Orchestre la création de tous les composants du monde."""
    elev, plates = geo.generate_geology(width, height, seed_val)

    # Attribution culturelle aux plaques
    for p in plates:
        p["culture"] = random.choice(config["cultures"])

    riv = geo.simulate_hydrology(width, height, elev)
    initial_civ = history.seed_civilization(width, height, elev, riv, plates, config["cultures"])

    world = {
        'elev': elev,
        'riv': riv,
        'civ': initial_civ,
        'road': [["  " for _ in range(width)] for _ in range(height)],
        'fauna': [],
        'cycle': 0
    }

    world['fauna'] = fauna.init_fauna(width, height, elev, world['civ'], config["fauna"])

    stats = {
        'year': 0,
        'logs': [f"L'ère de {config.get('world_name', 'Terra')} commence."],
        'seed': seed_val
    }

    return world, stats