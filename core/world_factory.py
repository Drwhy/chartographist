from .geo import generate_geology, simulate_hydrology
from .entities import EntityManager
from entities.constructs.city import City  # Changement : On commence par des Cités
from core.random_service import RandomService

def assemble_world(width, height, config, seed_val):
    """
    Initialise le monde avec une géologie complexe et place les Cités Primordiales.
    C'est le SEUL moment où des Cités apparaissent 'gratuitement'.
    """

    # 1. GÉNÉRATION DU TERRAIN (LOGIQUE GÉOLOGIQUE)
    # -------------------------------------------
    elevation, plates = generate_geology(width, height)
    rivers = simulate_hydrology(width, height, elevation)

    # 2. INITIALISATION DU GESTIONNAIRE D'ENTITÉS
    # -------------------------------------------
    entity_manager = EntityManager()

    # 3. PLACEMENT DES CITÉS PRIMORDIALES (LES CAPITALES)
    # --------------------------------------------------
    cultures = config.get("cultures", [])

    # On itère sur les cultures définies dans le template.json
    for c_data in cultures:
        placed = False
        attempts = 0

        # On cherche un site de prestige pour chaque capitale
        while not placed and attempts < 300:
            # On évite les bords extrêmes de la map
            rx = RandomService.randint(10, width - 11)
            ry = RandomService.randint(10, height - 11)

            h = elevation[ry][rx]
            is_near_water = rivers[ry][rx] > 0

            # Critères d'implantation d'une Capitale :
            # Plaine fertile (0.1 < h < 0.3) et OBLIGATOIREMENT près de l'eau
            if 0.1 < h < 0.3 and is_near_water:
                # Création de la Cité (objet City)
                # Elle pourra ensuite générer des Settlers pour créer des Villages
                new_city = City(rx, ry, c_data, config)
                entity_manager.add(new_city)
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
        # Initialisation de la grille de routes vide
        'road': [["  " for _ in range(width)] for _ in range(height)],

        # Système d'entités unifié (EntityManager)
        'entities': entity_manager
    }

    # 5. INITIALISATION DES STATISTIQUES
    # ----------------------------------
    stats = {
        'year': 0,
        'logs': [
            f"🌍 Le monde s'est éveillé (Seed: {seed_val})",
            "🏛️ Les Cités Primordiales ont érigé leurs premiers monuments."
        ],
        'seed': seed_val
    }

    return world, stats