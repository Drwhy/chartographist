from .geo import generate_geology, simulate_hydrology
from core.entities import EntityManager
from entities.constructs.city import City  # Changement : On commence par des Cités
from core.random_service import RandomService
from core.logger import GameLogger
from core.translator import Translator

def assemble_world(width, height, config, seed_val):
    """
    Initialise la structure géologique et les systèmes de données du monde.
    Le peuplement (Villes, Animaux) se fait APRÈS dans world_factory.
    """

    # 1. GÉNÉRATION GÉOLOGIQUE
    elevation, plates = generate_geology(width, height)
    rivers = simulate_hydrology(width, height, elevation)

    # 2. CONSTRUCTION DU DICTIONNAIRE WORLD
    world = {
        'width': width,
        'height': height,
        'seed': seed_val,
        'cycle': 0,
        'elev': elevation,
        'riv': rivers,
        'plates': plates,
        # Grille de routes vide
        'road': [["  " for _ in range(width)] for _ in range(height)],
        # Gestionnaire d'entités vide au départ
        'entities': EntityManager()
    }
    msg = Translator.translate("system.world_init", seed_val=seed_val)
    # 3. INITIALISATION DES STATISTIQUES
    stats = {
        'year': 0,
        'seed': seed_val,
        'logs': [msg]
    }

    return world, stats