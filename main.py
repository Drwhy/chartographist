import time
from render import RenderEngine
from core.system import init_terminal, restore_terminal, load_arguments
from core.world_factory import assemble_world
import history, fauna

WIDTH, HEIGHT = 60, 30
TICK_SPEED = 1.0

def main():
    # 1. SETUP
    init_terminal()
    config, seed = load_arguments()
    renderer = RenderEngine(WIDTH, HEIGHT, config)

    # 2. CREATION
    world, stats = assemble_world(WIDTH, HEIGHT, config, seed)

    # 3. LOOP
    try:
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < 1000:
            world['cycle'] += 1
            stats['year'] = world['cycle'] * 10

            # Moteurs de simulation
            world['civ'], new_logs = history.evolve_world(
                WIDTH, HEIGHT, world['elev'], world['riv'], None,
                world['civ'], world['road'], world['cycle']
            )
            stats['logs'].extend(new_logs)

            world['fauna'] = fauna.update_fauna(
                WIDTH, HEIGHT, world['elev'], world['civ'],
                world['fauna'], config["fauna"]
            )

            renderer.draw_frame(world, stats)
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        pass
    finally:
        restore_terminal()
        print(f"\nFin des chroniques à l'An {stats['year']}.")

if __name__ == "__main__":
    main()