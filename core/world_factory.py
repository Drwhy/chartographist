import random
from .geo import generate_geology, simulate_hydrology
from .culture import initialize_civilizations

def assemble_world(width, height, config, seed_val):
    random.seed(seed_val)

    elevation, plates = generate_geology(width, height, seed_val)
    rivers = simulate_hydrology(width, height, elevation)

    # On initialise les structures (Villes)
    initial_civ = initialize_civilizations(width, height, elevation, config)

    world = {
        'width': width, 'height': height, 'seed': seed_val, 'cycle': 0,
        'elev': elevation,
        'riv': rivers,
        'plates': plates,
        'civ': initial_civ,
        # TRÈS IMPORTANT : Initialiser avec "  " et pas None
        'road': [["  " for _ in range(width)] for _ in range(height)],
        'fauna': [],
        'settlers': [],
        'hunters': []
    }

    stats = {
        'year': 0,
        'logs': ["📜 L'aube d'une nouvelle ère commence..."],
        'seed': seed_val
    }
    return world, stats