import time
import core, history, fauna
from render import RenderEngine

WIDTH, HEIGHT = 60, 30
MAX_CYCLES = 1000
TICK_SPEED = 0.5

def main():
    core.init_terminal()
    config, seed = core.load_arguments()
    world, stats = core.assemble_world(WIDTH, HEIGHT, config, seed)
    renderer = RenderEngine(WIDTH, HEIGHT, config)

    try:
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < MAX_CYCLES:
            world['cycle'] += 1
            stats['year'] = world['cycle'] * 10

            # A. Évolution systémique (Villes & Migration)
            world['civ'], new_logs, new_settlers = history.evolve_world(
                WIDTH, HEIGHT, world['elev'], world['riv'], None,
                world['civ'], world['road'], world['cycle']
            )
            stats['logs'].extend(new_logs)
            world['settlers'].extend(new_settlers)

            # B. Évolution des agents humains (Mouvement, Chasse, Fondation)
            history.update_population(world, stats)

            # C. Évolution de la faune
            world['fauna'] = fauna.update_fauna(
                WIDTH, HEIGHT, world['elev'], world['civ'],
                world['fauna'], config["fauna"]
            )

            renderer.draw_frame(world, stats)
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        pass
    finally:
        core.restore_terminal()
        print(f"\nChroniques interrompues à l'An {stats['year']}. Seed: {seed}")

if __name__ == "__main__":
    main()