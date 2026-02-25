import sys, time, random
import geo, culture, history, fauna
from render import RenderEngine

# --- Configuration Globale ---
WIDTH, HEIGHT = 60, 30
MAX_CYCLES = 1000
TICK_SPEED = 1

def main():
    # 1. Préparation du Terminal
    # Effacement et masquage du curseur
    sys.stdout.write("\033[2J\033[H\033[?25l")

    # 2. Chargement des données externes
    # On gère les arguments : python main.py [template.json] [seed]
    template_path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else "template.json"
    config = culture.load_template(template_path)
    seed_val = sys.argv[2] if len(sys.argv) > 2 else random.randint(0, 99999)

    # 3. Initialisation du moteur de rendu
    renderer = RenderEngine(WIDTH, HEIGHT, config)

    # 4. Génération de la Géographie (Le socle du monde)
    elev, plates = geo.generate_geology(WIDTH, HEIGHT, seed_val)

    # Attribution d'une culture par défaut à chaque plaque tectonique
    for p in plates:
        p["culture"] = random.choice(config["cultures"])

    # Simulation de l'eau (Rivières)
    riv = geo.simulate_hydrology(WIDTH, HEIGHT, elev)

    # 5. Création des premières colonies (La Genèse)
    initial_civ = history.seed_civilization(WIDTH, HEIGHT, elev, riv, plates, config["cultures"])

    # 6. État initial de la simulation (Le Modèle)
    world = {
        'elev': elev,
        'riv': riv,
        'civ': initial_civ,
        'road': [["  " for _ in range(WIDTH)] for _ in range(HEIGHT)],
        'fauna': [],
        'cycle': 0
    }

    # Initialisation de la population sauvage
    world['fauna'] = fauna.init_fauna(WIDTH, HEIGHT, elev, world['civ'], config["fauna"])

    # Statistiques de bord
    stats = {
        'year': 0,
        'logs': [f"L'ère de {config.get('world_name', 'Terra')} commence."],
        'seed': seed_val
    }

    try:
        # --- PHASE 1 : RÉVÉLATION (Effet Visuel) ---
        renderer.draw_frame(world, stats, reveal=True)

        # --- PHASE 2 : ÉVOLUTION TEMPORELLE ---
        for c in range(1, MAX_CYCLES + 1):
            world['cycle'] = c
            stats['year'] = c * 10

            # A. Évolution de la Civilisation (Cités, Guerres, Routes)
            # Utilise history/history_engine.py via history/__init__.py
            world['civ'], new_logs = history.evolve_world(
                WIDTH, HEIGHT, elev, riv, plates,
                world['civ'], world['road'], c
            )
            stats['logs'].extend(new_logs)

            # B. Évolution de la Faune (Mouvements, Naissances)
            world['fauna'] = fauna.update_fauna(
                WIDTH, HEIGHT, elev, world['civ'],
                world['fauna'], config["fauna"]
            )

            # C. Rendu Graphique
            renderer.draw_frame(world, stats)

            # D. Latence de cycle
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        # Sortie propre avec Ctrl+C
        pass
    finally:
        # Rétablir le terminal
        sys.stdout.write("\033[?25h\n")
        print(f"\nSimulation interrompue à l'An {stats['year']}.")
        print("Les chroniques de ce monde ont été sauvegardées dans votre mémoire.")

if __name__ == "__main__":
    main()