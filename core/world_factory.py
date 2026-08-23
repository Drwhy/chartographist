from .geo import generate_geology, simulate_hydrology
from core.entities import EntityManager
from entities.constructs.city import City
from core.random_service import RandomService
from core.logger import GameLogger
from core.translator import Translator
from core.influence import InfluenceSystem
from core.chronicles import ChronicleBook

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
        'chronicles': [],
        'next_chronicle_id': 1,
        'diplomacy': {},
        'next_relation_id': 1,
        'climate': {
            'season': 'winter',
            'season_index': 0,
            'temperature_anomaly': 0.0,
            'precipitation_anomaly': 0.0,
            'drought_severity': 0.0,
            'flood_severity': 0.0,
            'last_update_cycle': 0,
        },
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

    ChronicleBook(world).record(
        init_msg,
        cycle=0,
        year=0,
        month=1,
        category="system",
    )
    return world, stats