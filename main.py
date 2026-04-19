import time, select, sys, traceback, core, history
import entities.spawn_system as entities_spawn
from render.render_engine import RenderEngine
from core.logger import GameLogger
from core.random_service import RandomService
from events.event_manager import EventManager
from core.translator import Translator
from core.religion import init_religion_data

# --- GLOBAL CONFIGURATION ---
WIDTH, HEIGHT = 60, 30
MAX_CYCLES = 2000
TICK_SPEED = 0.15  # Slightly accelerated to witness expansion

def check_input():
    """Checks if a key was pressed without blocking the script execution."""
    if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        return sys.stdin.read(1)
    return None

def main():
    # 1. TERMINAL AND DATA INITIALIZATION
    # Prepare the terminal (hide cursor, clear screen)
    core.init_terminal()
    config, seed = core.load_arguments()

    # Initialize the central random service
    RandomService.initialize(seed)

    # Initialize religion data from config (generates one religion per culture)
    init_religion_data(config)

    # Create the world and the statistics dictionary
    # world['entities'] is an EntityManager instance
    world, stats = core.assemble_world(WIDTH, HEIGHT, config, seed)

    # Initialize the Spatial Grid in the world object (if not already done in assemble_world)
    from core.grid_service import SpatialGrid
    world['grid'] = SpatialGrid(WIDTH, HEIGHT, cell_size=10)

    entities_spawn.seed_initial_cities(world, config)

    # Initialize the modular rendering engine
    renderer = RenderEngine(WIDTH, HEIGHT, config)

    try:
        # Display the Genesis (Radial Reveal effect)
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < MAX_CYCLES:
            world['cycle'] += 1
            # 1 Cycle = 1 Month
            # Calculate years and current month index
            total_months = world['cycle']
            stats['year'] = total_months // 12
            stats['month'] = (total_months % 12) + 1  # 1 to 12

            # --- A. GRID REFRESH ---
            # Rebuild the spatial partitioning grid at the start of every cycle
            world['grid'].clear()
            for entity in world['entities']:
                if not getattr(entity, 'is_expired', False):
                    world['grid'].add_entity(entity)

            # --- B. DYNAMIC SPAWN SYSTEM ---
            # Renews wild fauna (Wolves, Bears, etc.)
            entities_spawn.spawn_system(world, config)

            # --- C. INFLUENCE & HEATMAP DECAY (MEDIUM TICK) ---
            # We update the heatmap every 10 cycles to save CPU
            if world['cycle'] % 10 == 0:
                world['influence'].update()

            # --- D. ENTITY UPDATES (DIFFERENTIATED TICKS) ---
            all_entities = list(world['entities'])

            for entity in all_entities:
                if getattr(entity, 'is_expired', False):
                    continue

                try:
                    # --- FAST TICK (Every Cycle) ---
                    # Movement, immediate AI decisions, and combat
                    entity.process_turn(world, stats)

                    # --- MEDIUM TICK (Every 10 Cycles) ---
                    # Hunger, energy consumption, and local influence updates
                    if world['cycle'] % 10 == 0:
                        entity.update_influence(world)
                        if hasattr(entity, 'check_vital_signs'):
                            entity.check_vital_signs(world)

                    # --- SLOW TICK (Every 100 Cycles) ---
                    # Complex emergence: Births, plagues, cultural drift, and long-term memory
                    if world['cycle'] % 100 == 0:
                        if hasattr(entity, 'process_long_term_logic'):
                            entity.process_long_term_logic(world)

                except Exception as e:
                    # Robust Bug Logging System
                    tb = traceback.extract_tb(e.__traceback__)
                    filename, line, func, text = tb[-1]
                    pos = getattr(entity, 'pos', 'Unknown')

                    error_msg = (
                        f"⚠️ [BUG] {type(entity).__name__} at {pos} | "
                        f"Error: '{str(e)}' | "
                        f"File: {filename.split('/')[-1]} (Line {line})"
                    )
                    stats['logs'].append(error_msg)

            # --- E. GLOBAL EVENTS ---
            # Events like Volcanoes or UFOs are checked every cycle
            EventManager.update(world, stats, config)

            # --- F. LOG SYNCHRONIZATION ---
            stats['logs'].extend(GameLogger.get_new_logs())

            # --- G. CLEANUP & RENDERING ---
            # Remove entities flagged as is_expired before drawing
            world['entities'].remove_dead()
            renderer.draw_frame(world, stats)

            # Rhythm control
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        print("\033[?25h") # Restore the cursor
        print(f"\n{Translator.translate('system.user_interrupt')}")
    except Exception:
        # On critical crash, restore terminal state before showing error
        core.restore_terminal()
        traceback.print_exc()

    finally:
        # Final terminal restoration and summary display
        core.restore_terminal()

        from entities.constructs.city import City
        from entities.constructs.village import Village
        from entities.species.animal.base import Animal

        all_entities = [e for e in world['entities'] if not e.is_expired]
        cities = [e for e in all_entities if isinstance(e, City)]
        villages = [e for e in all_entities if isinstance(e, Village)]
        fauna = [e for e in all_entities if isinstance(e, Animal)]

        world_name = config.get('world_name', 'WORLD').upper()
        print("\n" + "═" * 50)
        print(Translator.translate("ui.chronicles_title", world_name=world_name))
        print(Translator.translate("ui.end_year", year=stats['year']))
        print(Translator.translate("ui.cities_count", count=len(cities)))
        print(Translator.translate("ui.villages_count", count=len(villages)))
        print(Translator.translate("ui.fauna_count", count=len(fauna)))
        print(Translator.translate("ui.seed_info", seed=seed))
        print("═" * 50 + "\n")

if __name__ == "__main__":
    main()