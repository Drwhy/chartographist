import random
# Imports internes (assure-toi que ces modules existent dans ton core)
from .geo import generate_geology, simulate_hydrology
from .entities import EntityManager
from history.colonization import seed_civilization

def assemble_world(width, height, config, seed_val):
    """
    Initialise la structure de données maîtresse (Le Monde).
    Cette version est hybride : elle supporte l'ancien système de listes
    et le nouveau système d'EntityManager.
    """
    random.seed(seed_val)

    # 1. GÉNÉRATION DU TERRAIN (GÉOLOGIE ET HYDROLOGIE)
    # ------------------------------------------------
    # On génère la carte de base (élévation et plaques tectoniques)
    elevation, plates = generate_geology(width, height, seed_val)

    # On simule le passage de l'eau
    rivers = simulate_hydrology(width, height, elevation)

    # 2. INITIALISATION DES SYSTÈMES D'ENTITÉS
    # ----------------------------------------
    # Le futur : Un gestionnaire unique
    entity_manager = EntityManager()

    # 3. GÉNÉRATION DES CIVILISATIONS INITIALES
    # -----------------------------------------
    # On place les premières cités selon les cultures du template.json
    initial_civ = seed_civilization(width, height, elevation, rivers, plates, config.get("cultures", []))

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

        # Données de Civilisation
        'civ': initial_civ,
        'road': [[None for _ in range(width)] for _ in range(height)],

        # --- SYSTÈME D'ENTITÉS ---
        'entities': entity_manager,  # La nouvelle fondation

        # COMPATIBILITÉ : On garde ces listes pour éviter les KeyError immédiats
        # On les videra progressivement au fur et à mesure de la migration.
        'fauna': [],
        'settlers': [],
        'hunters': []
    }

    # 5. INITIALISATION DES STATISTIQUES
    # ----------------------------------
    stats = {
        'year': 0,
        'logs': ["📜 Les fondations du monde ont été posées."],
        'seed': seed_val,
        'deaths': 0,
        'births': len(initial_civ)
    }

    return world, stats