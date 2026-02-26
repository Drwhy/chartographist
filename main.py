import time, random, sys, traceback
# Imports de ton architecture
import core
import history
import entities.spawn_system as entities_spawn
from render.render_engine import RenderEngine
from core.logger import GameLogger

# --- CONFIGURATION ---
WIDTH, HEIGHT = 60, 30  # Ajuste selon la taille de ton terminal
MAX_CYCLES = 2000
TICK_SPEED = 0.3

def main():
    # 1. INITIALISATION DU TERMINAL ET DES DONNÉES
    core.init_terminal()
    config, seed = core.load_arguments()

    # world contient désormais world['entities'] qui gère TOUT (Villages, Loups, Colons)
    world, stats = core.assemble_world(WIDTH, HEIGHT, config, seed)

    # On s'assure que stats['logs'] est bien initialisé pour l'affichage
    if 'logs' not in stats:
        stats['logs'] = []

    renderer = RenderEngine(WIDTH, HEIGHT, config)

    try:
        # Affichage de la genèse (Radial Reveal)
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < MAX_CYCLES:
            world['cycle'] += 1
            stats['year'] = world['cycle'] * 10

            # --- A. ÉVOLUTION PASSIVE (Routes uniquement) ---
            # Les villages et cités évoluent désormais via leur propre méthode .update()
            # On ne passe plus world['civ'] car il est intégré dans world['entities']
            world['road'], new_logs = history.evolve_world(
                WIDTH,
                HEIGHT,
                world['road'],
                world['entities'], # On passe le manager au lieu de world['civ']
                world['cycle']
            )
            stats['logs'].extend(new_logs)

            # --- B. SYSTÈME DE SPAWN ---
            # Gère l'apparition de la faune sauvage et des nouvelles unités humaines
            entities_spawn.spawn_system(world, config)

            # --- C. MISE À JOUR UNIFIÉE DES ENTITÉS ---
            # On crée une copie de la liste pour éviter les erreurs lors des naissances/morts
            all_entities = list(world['entities'])

            for entity in all_entities:
                try:
                    # Ici, tout le monde travaille :
                    # - Le Village tente de devenir une City
                    # - Le Loup cherche une proie
                    # - Le Colon avance ou fonde un foyer
                    entity.update(world, stats)
                except Exception as e:
                        # 1. On extrait la dernière ligne de l'erreur (où le bug a eu lieu)
                        tb = traceback.extract_tb(e.__traceback__)
                        filename, line, func, text = tb[-1]

                        # 2. On récupère la position et l'ID de l'entité pour le contexte
                        pos = getattr(entity, 'pos', 'Inconnue')

                        # 3. On crée un log ultra-détaillé
                        error_msg = (
                            f"⚠️ [BUG] {type(entity).__name__} à {pos} | "
                            f"Erreur: '{str(e)}' | "
                            f"Fichier: {filename.split('/')[-1]} (Ligne {line}) | "
                            f"Code: {text}"
                        )

                        stats['logs'].append(error_msg)
            stats['logs'].extend(GameLogger.get_new_logs())
            # --- D. NETTOYAGE DES MORTS ---
            # Supprime les entités ayant .is_expired = True (proies mangées, colons arrivés, etc.)
            world['entities'].remove_dead()

            # --- E. RENDU GRAPHIQUE ---
            renderer.draw_frame(world, stats)

            # Rythme de la simulation
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        print("\n🛑 Simulation interrompue par l'utilisateur.")
    except Exception:
        # Restauration du terminal pour afficher l'erreur proprement
        core.restore_terminal()
        traceback.print_exc()
    finally:
        core.restore_terminal()

        # Statistiques finales basées sur le nouveau système
        structs = [e for e in world['entities'] if e.type == 'construct']
        agents = [e for e in world['entities'] if e.type in ['actor', 'animal']]

        print("\n" + "="*40)
        print(f"📜 Chroniques terminées à l'An {stats['year']}.")
        print(f"📊 Bilan : {len(structs)} Structures | {len(agents)} Agents vivants.")
        print(f"🌱 Seed de génération : {seed}")
        print("="*40 + "\n")

if __name__ == "__main__":
    main()