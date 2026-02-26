import random
from entities.registry import WILD_SPECIES, CIV_UNITS

def spawn_system(world, config):
    manager = world['entities']
    stats = world.get('stats', {})

    # 1. --- SPAWN DES HUMAINS ---
    active_homes = [getattr(e, 'home_pos', None) for e in manager]
    for pos, data in world['civ'].items():
        for unit_class in CIV_UNITS: # Utilise le registre auto-rempli
            new_unit = unit_class.try_spawn(pos, data, world, config, active_homes)
            if new_unit:
                manager.add(new_unit)
                break

    # 2. --- SPAWN DE LA FAUNE ---
    current_animals = [e for e in manager if getattr(e, 'type', '') == "animal"]
    if len(current_animals) < 100:
        rx = random.randint(0, world['width'] - 1)
        ry = random.randint(0, world['height'] - 1)

        for species_class in WILD_SPECIES: # Utilise le registre auto-rempli
            new_animal = species_class.try_spawn(rx, ry, world, config)
            if new_animal:
                manager.add(new_animal)
                break