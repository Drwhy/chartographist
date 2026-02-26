import random
from entities.registry import WILD_SPECIES, STRUCTURE_TYPES
from core.logger import GameLogger
from entities.species.human.hunter import Hunter

def spawn_system(world, config):
    """
    Gère l'apparition dynamique des entités mobiles.
    Les cités sont EXCLUES : elles ne naissent que par évolution de villages.
    """
    width = world['width']
    height = world['height']

    # 1. RÉGULATION DE LA FAUNE (Loups, Ours, etc.)
    _spawn_fauna(world, config, width, height)

def _spawn_fauna(world, config, width, height):
    """Gère le spawn des animaux enregistrés via @register_wild."""
    max_fauna = config.get("max_fauna", 20)
    current_fauna = len([e for e in world['entities'] if getattr(e, 'type', '') == 'animal'])

    if current_fauna < max_fauna:
        # On tente de faire apparaître une espèce au hasard parmi celles enregistrées
        if WILD_SPECIES:
            species_class = random.choice(WILD_SPECIES)

            # On choisit un point au hasard sur la carte
            rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)

            # La classe gère elle-même ses conditions (biome, probabilité)
            new_animal = species_class.try_spawn(rx, ry, world, config)

            if new_animal:
                world['entities'].add(new_animal)

def seed_initial_cities(world, config):
    """
    FONCTION SPÉCIALE : Appelé une seule fois au début par world_factory.
    C'est le seul moment où des cités apparaissent 'gratuitement'.
    """
    num_cities = config.get("initial_cities", 3)
    cities_placed = 0
    attempts = 0

    from entities.constructs.city import City

    while cities_placed < num_cities and attempts < 100:
        rx, ry = random.randint(0, world['width'] - 1), random.randint(0, world['height'] - 1)

        # Conditions idéales : Plaine (élévation basse mais positive) et rivière
        is_land = world['elev'][ry][rx] > 0.1 and world['elev'][ry][rx] < 0.4
        is_near_river = world['riv'][ry][rx] > 0

        if is_land and is_near_river:
            culture = random.choice(config['cultures'])
            mother_city = City(rx, ry, culture, config)
            world['entities'].add(mother_city)

            cities_placed += 1
            GameLogger.log(f"🏛️  La cité primordiale de {mother_city.name} a été fondée.")

        attempts += 1