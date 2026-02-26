import time
import sys
import traceback
import core
import history
import entities.spawn_system as entities_spawn
from render.render_engine import RenderEngine

# --- CONFIGURATION ---
WIDTH, HEIGHT = 60, 30
MAX_CYCLES = 2000
TICK_SPEED = 0.2  # On accélère un peu pour voir l'action

def main():
    # 1. INITIALISATION
    core.init_terminal()
    config, seed = core.load_arguments()

    # world contient world['entities'] (le Manager)
    world, stats = core.assemble_world(WIDTH, HEIGHT, config, seed)

    # CRUCIAL : On lie stats à world pour que les entités puissent logger
    world['stats'] = stats
    if 'logs' not in stats:
        stats['logs'] = []

    renderer = RenderEngine(WIDTH, HEIGHT, config)

    try:
        # Affichage de la genèse (radial reveal)
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < MAX_CYCLES:
            world['cycle'] += 1
            stats['year'] = world['cycle'] * 10

            # --- A. ÉVOLUTION DU MONDE (Structures & Routes) ---
            # history_engine ne gère plus les colons, seulement l'évolution village -> city
            world['civ'], new_logs, _ = history.evolve_world(
                WIDTH, HEIGHT, world['elev'], world['riv'], None,
                world['civ'], world['road'], world['cycle']
            )
            stats['logs'].extend(new_logs)

            # --- B. SYSTÈME DE SPAWN (Génération auto) ---
            # Utilise le Registre pour Hunters, Settlers, Wolves, Bears...
            entities_spawn.spawn_system(world, config)

            # --- C. MISE À JOUR DES AGENTS (IA & Chasse) ---
            # On utilise list() pour éviter les erreurs de modification pendant l'itération
            for entity in list(world['entities']):
                try:
                    # L'update appelle think() et perform_action()
                    entity.update(world, stats)
                except Exception as e:
                    stats['logs'].append(f"⚠️ Erreur entité {type(entity).__name__}: {e}")

            # --- D. NETTOYAGE ---
            # Retire les entités dont is_expired = True (après une attaque par ex.)
            world['entities'].remove_dead()

            # --- E. RENDU ---
            renderer.draw_frame(world, stats)

            # Rythme de la simulation
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        print("\n🛑 Simulation interrompue par l'utilisateur.")
    except Exception:
        # En cas de gros crash, on restaure le terminal proprement pour voir l'erreur
        core.restore_terminal()
        traceback.print_exc()
    finally:
        core.restore_terminal()
        print(f"\n📜 Chroniques terminées à l'An {stats['year']}.")
        print(f"📊 Statistiques finales : {len(world['civ'])} structures | {len(world['entities'])} agents.")
        print(f"🌱 Seed : {seed}")

if __name__ == "__main__":
    main()