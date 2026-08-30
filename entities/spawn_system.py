from entities.registry import STRUCTURE_TYPES
from entities.species.animal.base import Animal
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from core.religion import _find_template
from core.simulation_metrics import SimulationMetrics


def spawn_system(world, config):
    """
    Manages the dynamic spawning of mobile entities.
    Note: Primary Cities are excluded from this system; they only emerge
    through initial seeding or the evolution of existing villages.
    """
    width = world['width']
    height = world['height']
    _spawn_fauna(world, config, width, height)


def _spawn_fauna(world, config, width, height):
    """Spawn at most one wild animal within the configured capacity."""
    from core.resources import resources_enabled
    from core.ecology_limits import can_add_fauna, population_limits_enabled

    fauna_list = config.get("fauna", [])
    if population_limits_enabled(config):
        candidates = [
            species_data for species_data in fauna_list
            if can_add_fauna(world, config, species_data)
        ]
    else:
        max_fauna = config.get("max_fauna", 20)
        current_fauna = sum(
            1 for entity in world["entities"]
            if isinstance(entity, Animal) and not entity.is_expired
        )
        candidates = fauna_list if current_fauna < max_fauna else []

    if not candidates:
        return

    random_stream = "ecology" if resources_enabled(config) else None
    species_data = RandomService.choice(candidates, stream=random_stream)
    spawn_x = RandomService.randint(0, width - 1, stream=random_stream)
    spawn_y = RandomService.randint(0, height - 1, stream=random_stream)
    new_animal = Animal.try_spawn(spawn_x, spawn_y, world, config, species_data)
    if new_animal and can_add_fauna(world, config, species_data, spawn_x, spawn_y):
        world["entities"].add(new_animal)
        SimulationMetrics(world).record_fauna("spawned")

def _is_habitable_city_site(world, x, y):
    elevation = world['elev'][y][x]
    return 0.1 < elevation < 0.4 and world['riv'][y][x] > 0


def _is_occupied(world, x, y):
    return any(
        entity.x == x and entity.y == y
        for entity in world['entities']
        if not getattr(entity, "is_expired", False)
    )


def _ranked_city_sites(world):
    """Return viable unoccupied sites in a stable habitability order."""
    candidates = []
    for y in range(world['height']):
        for x in range(world['width']):
            if not _is_habitable_city_site(world, x, y) or _is_occupied(world, x, y):
                continue
            elevation = float(world['elev'][y][x])
            river = float(world['riv'][y][x])
            candidates.append((-river, abs(elevation - 0.25), y, x))
    candidates.sort()
    return [(x, y) for _, _, y, x in candidates]


def _found_city(world, config, x, y):
    from entities.constructs.city import City

    culture = RandomService.choice(config['cultures'])
    mother_city = City(x, y, culture, config)
    world['entities'].add(mother_city)
    GameLogger.log(
        Translator.translate("entities.city_founded", name=mother_city.name, x=x, y=y)
    )
    if mother_city.religion and mother_city.religion.dominant:
        dominant = mother_city.religion.dominant
        template = _find_template(dominant)
        emoji = template.get("emoji", chr(0x1F64F)) if template else chr(0x1F64F)
        god = template.get("god", "") if template else ""
        domain_key = template.get("domain", "") if template else ""
        domain = Translator.translate(f"domains.{domain_key}.name") if domain_key else ""
        GameLogger.log(Translator.translate(
            "events.religion_city_worships",
            emoji=emoji,
            name=mother_city.name,
            religion=dominant,
            god=god,
            domain=domain,
        ))
    return mother_city


def seed_initial_cities(world, config):
    """
    Preserve the historical random placement, then use a deterministic fallback.

    The returned report makes partial initialization explicit for headless callers.
    """
    requested = max(0, int(config.get("initial_cities", 3)))
    placed = 0
    attempts = 0

    while placed < requested and attempts < 100:
        attempts += 1
        spawn_x = RandomService.randint(0, world['width'] - 1)
        spawn_y = RandomService.randint(0, world['height'] - 1)
        if not _is_habitable_city_site(world, spawn_x, spawn_y):
            continue
        if _is_occupied(world, spawn_x, spawn_y):
            continue
        _found_city(world, config, spawn_x, spawn_y)
        placed += 1

    fallback_used = placed < requested
    if fallback_used:
        for spawn_x, spawn_y in _ranked_city_sites(world):
            if placed >= requested:
                break
            _found_city(world, config, spawn_x, spawn_y)
            placed += 1

    status = "complete" if placed == requested else "insufficient_habitable_sites"
    metrics = SimulationMetrics(world).storage["initialization"]
    metrics.update({
        "requested_settlements": requested,
        "placed_settlements": placed,
        "fallback_used": fallback_used,
        "status": status,
    })

    if status != "complete":
        GameLogger.log(
            Translator.translate(
                "system.initial_settlement_shortfall",
                requested=requested,
                placed=placed,
            ),
            category="system",
        )

    return {
        "requested": requested,
        "placed": placed,
        "attempts": attempts,
        "fallback_used": fallback_used,
        "status": status,
    }
