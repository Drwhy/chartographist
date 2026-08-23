import select
import sys
import time
import traceback

import core
from core.persistence import SaveFormatError
from core.simulation_engine import SimulationEngine
from core.translator import Translator
from render.render_engine import RenderEngine
from render.ui_bestiary import print_bestiary_summary, FAUNA_TAB, SPECIES_TAB, RELIGION_TAB, GUIDE_TAB, SETTLEMENTS_TAB, CHRONICLES_TAB, DIPLOMACY_TAB

# --- GLOBAL CONFIGURATION ---
WIDTH, HEIGHT = 60, 30
MAX_CYCLES = 2000
TICK_SPEED = 0.15  # Slightly accelerated to witness expansion


def check_input():
    """Returns a pressed key without blocking, or None."""
    if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        return sys.stdin.read(1)
    return None


def handle_bestiary_input(key, state):
    """Applique une commande clavier à l'état de l'overlay d'inspection."""
    if key in ("b", "B"):
        state["active"] = not state["active"]
        state["page"] = 0
        return
    if not state["active"]:
        return

    tabs = {
        "f": FAUNA_TAB,
        "s": SPECIES_TAB,
        "r": RELIGION_TAB,
        "i": GUIDE_TAB,
        "c": SETTLEMENTS_TAB,
        "h": CHRONICLES_TAB,
        "d": DIPLOMACY_TAB,
    }
    normalized = key.lower()
    if normalized in tabs:
        state["tab"] = tabs[normalized]
        state["page"] = 0
    elif normalized == "n":
        state["page"] += 1
    elif normalized == "p":
        state["page"] = max(0, state["page"] - 1)


def main():
    core.init_terminal()
    engine = None
    options = None
    seed = None

    try:
        options = core.load_launch_options()
        if options.load_path:
            try:
                engine = SimulationEngine.load(options.load_path)
            except (OSError, SaveFormatError) as error:
                print(Translator.translate(
                    "system.load_error",
                    file_path=options.load_path,
                    error=error,
                ))
                return
            config = engine.config
            world, stats = engine.world, engine.stats
            seed = stats["seed"]
            load_message = Translator.translate(
                "system.load_success",
                file_path=options.load_path,
            )
            stats["logs"].append(load_message)
            engine.record_chronicle(load_message, category="system")
        else:
            config = options.config
            seed = options.seed
            engine = SimulationEngine.create(config, seed, WIDTH, HEIGHT)
            world, stats = engine.world, engine.stats

        renderer = RenderEngine(WIDTH, HEIGHT, config)
        bestiary_state = {'active': False, 'tab': FAUNA_TAB, 'page': 0}

        renderer.draw_frame(world, stats, reveal=True)
        while world['cycle'] < MAX_CYCLES:
            engine.step()

            key = check_input()
            if key:
                handle_bestiary_input(key, bestiary_state)

            if bestiary_state['active']:
                renderer.draw_bestiary(world, bestiary_state)
            else:
                renderer.draw_frame(world, stats)
            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        print("\033[?25h")
        print(f"\n{Translator.translate('system.user_interrupt')}")
    except Exception:
        core.restore_terminal()
        traceback.print_exc()
    finally:
        core.restore_terminal()
        if engine is not None:
            if options and options.save_path:
                try:
                    engine.save(options.save_path)
                    print(Translator.translate(
                        "system.save_success",
                        file_path=options.save_path,
                    ))
                except (OSError, SaveFormatError) as error:
                    print(Translator.translate(
                        "system.save_error",
                        file_path=options.save_path,
                        error=error,
                    ))
            _print_final_summary(engine.config, engine.world, engine.stats, seed)


def _print_final_summary(config, world, stats, seed):
    from entities.constructs.city import City
    from entities.constructs.village import Village
    from entities.species.animal.base import Animal

    all_entities = [entity for entity in world['entities'] if not entity.is_expired]
    cities = [entity for entity in all_entities if isinstance(entity, City)]
    villages = [entity for entity in all_entities if isinstance(entity, Village)]
    fauna = [entity for entity in all_entities if isinstance(entity, Animal)]

    world_name = config.get('world_name', 'WORLD').upper()
    print("\n" + "═" * 50)
    print(Translator.translate("ui.chronicles_title", world_name=world_name))
    print(Translator.translate("ui.end_year", year=stats['year']))
    print(Translator.translate("ui.cities_count", count=len(cities)))
    print(Translator.translate("ui.villages_count", count=len(villages)))
    print(Translator.translate("ui.fauna_count", count=len(fauna)))
    print(Translator.translate("ui.seed_info", seed=seed))
    print("═" * 50 + "\n")
    print_bestiary_summary(config, world)


if __name__ == "__main__":
    main()
