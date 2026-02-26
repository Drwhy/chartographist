import random
from entities.registry import CIV_UNITS, WILD_SPECIES

def spawn_system(world, config):
    """
    Système de génération unifié.
    Gère l'apparition des Humains (depuis les Constructs)
    et de la Faune (depuis le terrain).
    """
    manager = world['entities']

    # 1. RECENSEMENT DES DOMICILES ACTIFS
    # On identifie où se trouvent déjà des unités pour respecter la règle "un par foyer"
    # On récupère les home_pos de toutes les entités mobiles (Actors)
    active_homes = {getattr(e, 'home_pos', None) for e in manager if hasattr(e, 'home_pos')}
    # On retire None de l'ensemble
    active_homes.discard(None)

    # 2. SPAWN CIVILISATION (Hunters & Settlers)
    # On cherche tous les Constructs civils sur la carte
    civ_constructs = [e for e in manager if getattr(e, 'type', '') == 'construct']

    for construct in civ_constructs:
        # Données de base pour le spawn
        pos = (construct.x, construct.y)
        # On prépare un dictionnaire de compatibilité pour les méthodes try_spawn existantes
        construct_data = {
            'type': getattr(construct, 'subtype', 'village'),
            'culture': construct.culture
        }

        # On tente de spawn chaque type d'unité enregistrée (@register_civ)
        for unit_class in CIV_UNITS:
            # La règle de l'unité unique par foyer est vérifiée dans le try_spawn de la classe
            new_unit = unit_class.try_spawn(pos, construct_data, world, config, active_homes)

            if new_unit:
                manager.add(new_unit)
                # Une seule unité par construct par tour maximum
                break

    # 3. SPAWN SAUVAGE (Loups, Ours, etc.)
    # On limite la population totale pour les performances
    current_animals = [e for e in manager if getattr(e, 'type', '') == 'animal']
    max_animals = config.get('simulation', {}).get('max_fauna', 100)

    if len(current_animals) < max_animals:
        # On tente plusieurs spawn par tour pour peupler le monde
        for _ in range(5):
            rx = random.randint(0, world['width'] - 1)
            ry = random.randint(0, world['height'] - 1)

            for species_class in WILD_SPECIES:
                new_animal = species_class.try_spawn(rx, ry, world, config)
                if new_animal:
                    manager.add(new_animal)
                    break # On a créé un animal à cette position, on passe à l'essai suivant