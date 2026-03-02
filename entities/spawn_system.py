from entities.registry import WILD_SPECIES, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService

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
            species_class = RandomService.choice(WILD_SPECIES)

            # On choisit un point au hasard sur la carte
            rx, ry = RandomService.randint(0, width - 1), RandomService.randint(0, height - 1)

            # La classe gère elle-même ses conditions (biome, probabilité)
            new_animal = species_class.try_spawn(rx, ry, world, config)

            if new_animal:
                world['entities'].add(new_animal)

def seed_initial_cities(world, config):
    """
    FONCTION SPÉCIALE : Pose les cités mères en évitant les collisions.
    """
    num_cities = config.get("initial_cities", 3)
    cities_placed = 0
    attempts = 0
    from entities.constructs.city import City
    while cities_placed < num_cities and attempts < 100:
        attempts += 1
        rx, ry = RandomService.randint(0, world['width'] - 1), RandomService.randint(0, world['height'] - 1)

        # 1. Vérification du terrain
        h = world['elev'][ry][rx]
        is_land = 0.1 < h < 0.4
        is_near_river = world['riv'][ry][rx] > 0

        if not (is_land and is_near_river):
            continue

        # 2. SÉCURITÉ ANTI-CHEVAUCHEMENT : Personne sur cette case ?
        # On vérifie si une entité occupe déjà exactement ces coordonnées
        if any(e.x == rx and e.y == ry for e in world['entities']):
            continue

        # OPTIONNEL : On peut aussi imposer une distance minimale entre les cités mères
        # if any(math.dist((rx, ry), e.pos) < 10 for e in world['entities'] if isinstance(e, City)):
        #     continue

        # 3. Fondation
        culture = RandomService.choice(config['cultures'])
        mother_city = City(rx, ry, culture, config)
        world['entities'].add(mother_city)

        cities_placed += 1
        GameLogger.log(f"🏛️  La cité primordiale de {mother_city.name} a été fondée en ({rx}, {ry}).")