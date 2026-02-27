import time
import sys
import traceback
import core
import history
import entities.spawn_system as entities_spawn
from render.render_engine import RenderEngine
from core.logger import GameLogger
from core.random_service import RandomService

# --- CONFIGURATION GLOBALE ---
WIDTH, HEIGHT = 60, 30
MAX_CYCLES = 2000
TICK_SPEED = 0.15  # Légèrement accéléré pour voir l'expansion

def main():
    # 1. INITIALISATION DU TERMINAL ET DES DONNÉES
    # On prépare le terminal (cache le curseur, nettoie l'écran)
    core.init_terminal()
    config, seed = core.load_arguments()

    # On initialise le service central ici
    RandomService.initialize(seed)

    # Création du monde et du dictionnaire de statistiques
    # world['entities'] est un EntityManager
    world, stats = core.assemble_world(WIDTH, HEIGHT, config, seed)

    # Initialisation du moteur de rendu modulaire
    renderer = RenderEngine(WIDTH, HEIGHT, config)

    try:
        # Affichage de la genèse (Radial Reveal)
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < MAX_CYCLES:
            world['cycle'] += 1
            # Convention : 1 cycle = 10 ans dans l'histoire du monde
            stats['year'] = world['cycle'] * 10

            # --- A. ÉVOLUTION DES INFRASTRUCTURES ---
            # Gère principalement le tracé passif des routes
            world['road'], new_logs = history.evolve_world(
                WIDTH,
                HEIGHT,
                world['road'],
                world['entities'],
                world['cycle']
            )
            stats['logs'].extend(new_logs)

            # --- B. SYSTÈME DE SPAWN DYNAMIQUE ---
            # Renouvelle la faune sauvage (Loups, Ours)
            # Les humains ne spawnent plus ici (ils naissent des cités/villages)
            entities_spawn.spawn_system(world, config)

            # --- C. MISE À JOUR DES ENTITÉS (IA) ---
            # On travaille sur une copie de la liste pour éviter les erreurs de mutation
            all_entities = list(world['entities'])

            for entity in all_entities:
                # Sécurité : on ne traite pas les entités déjà marquées pour suppression
                if getattr(entity, 'is_expired', False):
                    continue

                try:
                    # Chaque entité (City, Settler, Wolf, Hunter) exécute sa propre logique
                    entity.update(world, stats)
                except Exception as e:
                    # Système de Log de Bug robuste
                    tb = traceback.extract_tb(e.__traceback__)
                    filename, line, func, text = tb[-1]
                    pos = getattr(entity, 'pos', 'Inconnue')

                    error_msg = (
                        f"⚠️ [BUG] {type(entity).__name__} à {pos} | "
                        f"Erreur: '{str(e)}' | "
                        f"Fichier: {filename.split('/')[-1]} (Ligne {line})"
                    )
                    stats['logs'].append(error_msg)

            # --- D. SYNCHRONISATION DES LOGS ---
            # On récupère les messages envoyés au GameLogger (ex: fondations de villes)
            stats['logs'].extend(GameLogger.get_new_logs())

            # --- E. NETTOYAGE (PRÉ-RENDU) ---
            # Indispensable pour que le RenderEngine ne dessine pas des entités mortes
            world['entities'].remove_dead()

            # --- F. RENDU GRAPHIQUE ---
            # Utilise la nouvelle structure ui_header, ui_map, ui_logs
            renderer.draw_frame(world, stats)

            # Contrôle du rythme
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        # Sortie propre sur Ctrl+C
        print("\033[?25h") # Réaffiche le curseur
        print("\n🛑 Simulation interrompue par l'utilisateur.")

    except Exception:
        # En cas de crash critique, on restaure le terminal avant d'afficher l'erreur
        core.restore_terminal()
        traceback.print_exc()

    finally:
        # Nettoyage final systématique
        core.restore_terminal()

        # --- BILAN FINAL ---
        structs = [e for e in world['entities'] if getattr(e, 'type', '') == 'construct']
        cities = [e for e in structs if getattr(e, 'subtype', '') == 'city']
        villages = [e for e in structs if getattr(e, 'subtype', '') == 'village']
        fauna = [e for e in world['entities'] if getattr(e, 'type', '') == 'animal']

        print("\n" + "═" * 50)
        print(f" 📜 CHRONIQUES DE {config.get('world_name', 'WORLD').upper()}")
        print(f" 📅 Fin de la simulation : An {stats['year']}")
        print(f" 🏙️  Cités fondées : {len(cities)}")
        print(f" 🏠 Villages actifs : {len(villages)}")
        print(f" 🐾 Faune restante : {len(fauna)}")
        print(f" 🌱 Seed utilisée : {seed}")
        print("═" * 50 + "\n")

if __name__ == "__main__":
    main()