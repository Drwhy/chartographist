from entities.registry import WILD_SPECIES, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from core.religion import _find_template

def spawn_system(world, config):
    """
    Manages the dynamic spawning of mobile entities.
    Note: Primary Cities are excluded from this system; they only emerge
    through initial seeding or the evolution of existing villages.
    """
    width = world['width']
    height = world['height']

    # 1. FAUNA REGULATION (Wolves, Bears, etc.)
    _spawn_fauna(world, config, width, height)

def _spawn_fauna(world, config, width, height):
    """Handles spawning of wild species registered via @register_wild."""
    max_fauna = config.get("max_fauna", 20)
    current_fauna = len([e for e in world['entities'] if getattr(e, 'type', '') == 'animal'])

    if current_fauna < max_fauna:
        # Attempt to spawn a random species from the global wild species registry
        if WILD_SPECIES:
            species_class = RandomService.choice(WILD_SPECIES)

            # Select a random point on the map
            spawn_x = RandomService.randint(0, width - 1)
            spawn_y = RandomService.randint(0, height - 1)

            # The species class handles its own environmental conditions (biome, probability)
            new_animal = species_class.try_spawn(spawn_x, spawn_y, world, config)

            if new_animal:
                world['entities'].add(new_animal)

def seed_initial_cities(world, config):
    """
    SPECIAL INITIALIZATION: Places mother cities while avoiding collisions.
    Ensures viable starting conditions for the world's civilizations.
    """
    num_cities = config.get("initial_cities", 3)
    cities_placed = 0
    attempts = 0
    from entities.constructs.city import City

    while cities_placed < num_cities and attempts < 100:
        attempts += 1
        spawn_x = RandomService.randint(0, world['width'] - 1)
        spawn_y = RandomService.randint(0, world['height'] - 1)

        # 1. Terrain Validation
        h = world['elev'][spawn_y][spawn_x]
        # Cities prefer stable land near water sources
        is_habitable_land = 0.1 < h < 0.4
        is_near_river = world['riv'][spawn_y][spawn_x] > 0

        if not (is_habitable_land and is_near_river):
            continue

        # 2. OVERLAP PREVENTION: Is the tile occupied?
        if any(entity.x == spawn_x and entity.y == spawn_y for entity in world['entities']):
            continue

        # 3. Foundation logic
        culture = RandomService.choice(config['cultures'])
        mother_city = City(spawn_x, spawn_y, culture, config)
        world['entities'].add(mother_city)

        cities_placed += 1
        GameLogger.log(
            Translator.translate("entities.city_founded", name=mother_city.name, x=spawn_x, y=spawn_y)
        )
        # Log the founding religion
        if hasattr(mother_city, 'religion') and mother_city.religion and mother_city.religion.dominant:
            dominant = mother_city.religion.dominant
            tmpl = _find_template(dominant)
            emoji = tmpl.get("emoji", "🙏") if tmpl else "🙏"
            god = tmpl.get("god", "") if tmpl else ""
            domain = tmpl.get("domain", "") if tmpl else ""
            GameLogger.log(Translator.translate(
                "events.religion_city_worships",
                emoji=emoji, name=mother_city.name,
                religion=dominant, god=god, domain=domain
            ))