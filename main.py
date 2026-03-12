import time, select, sys, traceback, core, history
import entities.spawn_system as entities_spawn
from render.render_engine import RenderEngine
from core.logger import GameLogger
from core.random_service import RandomService
from events.event_manager import EventManager
from core.translator import Translator

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
    show_heatmap = False

    # Create the world and the statistics dictionary
    # world['entities'] is an EntityManager instance
    world, stats = core.assemble_world(WIDTH, HEIGHT, config, seed)
    entities_spawn.seed_initial_cities(world, config)

    # Initialize the modular rendering engine
    renderer = RenderEngine(WIDTH, HEIGHT, config)

    try:
        # Display the Genesis (Radial Reveal effect)
        renderer.draw_frame(world, stats, reveal=True)

        while world['cycle'] < MAX_CYCLES:
            world['cycle'] += 1
            # Convention: 1 cycle = 10 years in the world's history
            stats['year'] = world['cycle'] * 10

            # --- B. DYNAMIC SPAWN SYSTEM ---
            # Renews wild fauna (Wolves, Bears)
            # Humans no longer spawn here (they are born from cities/villages)
            entities_spawn.spawn_system(world, config)

            # Handle influence / heat decay
            world['influence'].update()

            # --- C. ENTITY UPDATES (AI) ---
            # Work on a copy of the list to avoid mutation errors during iteration
            all_entities = list(world['entities'])

            for entity in all_entities:
                # Security: skip entities already marked for removal
                if getattr(entity, 'is_expired', False):
                    continue

                try:
                    # Every entity (City, Settler, Wolf, Hunter) executes its own logic
                    entity.process_turn(world, stats)
                    entity.update_influence(world)
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

            # Update global events (Plagues, Abductions, etc.)
            EventManager.update(world, stats, config)

            # --- D. LOG SYNCHRONIZATION ---
            # Retrieve messages sent to the GameLogger (e.g., city foundations)
            stats['logs'].extend(GameLogger.get_new_logs())

            # --- E. CLEANUP (PRE-RENDERING) ---
            # Essential so the RenderEngine doesn't draw dead entities
            world['entities'].remove_dead()

            # --- F. GRAPHICAL RENDERING ---
            # Uses the structure: ui_header, ui_map, ui_logs
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
        # Systematic final cleanup
        core.restore_terminal()

        # --- FINAL SUMMARY BASED ON CLASSES ---
        # Import specific classes for final counting
        from entities.constructs.city import City
        from entities.constructs.village import Village
        from entities.registry import WILD_SPECIES

        # Use isinstance to handle inheritance properly
        all_entities = [e for e in world['entities'] if not e.is_expired]

        cities = [e for e in all_entities if isinstance(e, City)]
        villages = [e for e in all_entities if isinstance(e, Village)]

        # Fauna groups all classes present in the WILD_SPECIES registry
        fauna = [e for e in all_entities if type(e) in WILD_SPECIES]

        # --- FINAL CHRONICLES ---
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