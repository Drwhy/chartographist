from entities.registry import STRUCTURE_TYPES
from entities.species.animal.base import Animal
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

    # 1. FAUNA REGULATION — fully data-driven from template.json fauna list
    _spawn_fauna(world, config, width, height)

def _spawn_fauna(world, config, width, height):
    """Spawns wild species based on fauna definitions in template.json."""
    max_fauna = config.get("max_fauna", 20)
    current_fauna = sum(1 for e in world['entities'] if isinstance(e, Animal) and not e.is_expired)

    fauna_list = config.get("fauna", [])
    if current_fauna < max_fauna and fauna_list:
        species_data = RandomService.choice(fauna_list)

        spawn_x = RandomService.randint(0, width - 1)
        spawn_y = RandomService.randint(0, height - 1)

        new_animal = Animal.try_spawn(spawn_x, spawn_y, world, config, species_data)

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
        if mother_city.religion and mother_city.religion.dominant:
            dominant = mother_city.religion.dominant
            tmpl = _find_template(dominant)
            emoji = tmpl.get("emoji", "🙏") if tmpl else "🙏"
            god = tmpl.get("god", "") if tmpl else ""
            domain_key = tmpl.get("domain", "") if tmpl else ""
            domain = Translator.translate(f"domains.{domain_key}.name") if domain_key else ""
            GameLogger.log(Translator.translate(
                "events.religion_city_worships",
                emoji=emoji, name=mother_city.name,
                religion=dominant, god=god, domain=domain
            ))