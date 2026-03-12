from .geo import generate_geology, simulate_hydrology
from core.entities import EntityManager
from entities.constructs.city import City
from core.random_service import RandomService
from core.logger import GameLogger
from core.translator import Translator
from core.influence import InfluenceSystem

def assemble_world(width, height, config, seed_val):
    """
    Initializes the geological structure and data systems of the world.
    Populating the world (Cities, Animals) is handled after this initialization.
    """

    # 1. GEOLOGICAL GENERATION
    # Create the heightmap and tectonic plate data
    elevation, plates = generate_geology(width, height)
    # Carve river paths based on the elevation gradient
    rivers = simulate_hydrology(width, height, elevation)

    # 2. WORLD DICTIONARY CONSTRUCTION
    # This acts as the primary container for the entire simulation state
    world = {
        'width': width,
        'height': height,
        'seed': seed_val,
        'cycle': 0,
        'elev': elevation,
        'riv': rivers,
        'plates': plates,
        # Empty road grid initialized with empty space strings
        'road': [["  " for _ in range(width)] for _ in range(height)],
        # Core entity manager for lifeforms and structures
        'entities': EntityManager(),
        # Influence heatmap system for fear and attraction signals
        'influence': InfluenceSystem(width, height, config)
    }

    # 3. STATISTICS AND INITIALIZATION LOGS
    init_msg = Translator.translate("system.world_init", seed_val=seed_val)

    stats = {
        'year': 0,
        'seed': seed_val,
        'logs': [init_msg]
    }

    return world, stats