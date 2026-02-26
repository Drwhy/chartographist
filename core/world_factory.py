import random
from .geo import generate_geology, simulate_hydrology
from .entities import EntityManager
from entities.constructs.village import Village # Import du fichier spécifique

def assemble_world(width, height, config, seed_val):
    """
    Initialise le monde en intégrant les structures (Constructs)
    directement dans le EntityManager.
    """
    random.seed(seed_val)

    # 1. GÉNÉRATION DU TERRAIN (LOGIQUE GÉOLOGIQUE)
    # -------------------------------------------
    # On conserve tes fonctions spécialisées pour le réalisme
    elevation, plates = generate_geology(width, height, seed_val)
    rivers = simulate_hydrology(width, height, elevation)

    # 2. INITIALISATION DU GESTIONNAIRE D'ENTITÉS
    # -------------------------------------------
    entity_manager = EntityManager()

    # 3. PLACEMENT DES CULTURES INITIALES (CONSTRUCTS)
    # ------------------------------------------------
    # On remplace seed_civilization par une logique de placement d'objets
    cultures = config.get("cultures", {})

    for c_data in cultures:
        placed = False
        attempts = 0

        # On cherche un site propice pour chaque culture
        while not placed and attempts < 200:
            rx = random.randint(10, width - 11)
            ry = random.randint(10, height - 11)

            h = elevation[ry][rx]
            is_near_water = rivers[ry][rx] > 0

            # Critères : Terre ferme, plaine, idéalement près d'une rivière
            if 0.1 < h < 0.4:
                # Si on est près de l'eau ou qu'on a fait trop d'essais
                if is_near_water or attempts > 150:
                    # On crée l'entité Construct Village
                    new_village = Village(rx, ry, c_data, config)
                    entity_manager.add(new_village)
                    placed = True

            attempts += 1

    # 4. CONSTRUCTION DU DICTIONNAIRE WORLD
    # -------------------------------------
    world = {
        'width': width,
        'height': height,
        'seed': seed_val,
        'cycle': 0,

        # Données de Terrain
        'elev': elevation,
        'riv': rivers,
        'plates': plates,
        'road': [["  " for _ in range(width)] for _ in range(height)],

        # --- SYSTÈME D'ENTITÉS UNIFIÉ ---
        # Plus de world['civ'], tout est ici (Villages, Loups, Chasseurs)
        'entities': entity_manager
    }

    # 5. INITIALISATION DES STATISTIQUES
    # ----------------------------------
    stats = {
        'year': 0,
        'logs': [
            f"📜 Les plaques tectoniques se sont figées (Seed: {seed_val})",
            "🏠 Les premiers foyers ont été bâtis sur des terres fertiles."
        ],
        'seed': seed_val
    }

    return world, stats