import select
import sys
import time
import traceback

import core
from core.persistence import SaveFormatError
from core.simulation_engine import SimulationEngine
from core.simulation_host import SimulationHost
from core.translator import Translator
from render.render_engine import RenderEngine
from render.ui_bestiary import print_bestiary_summary, FAUNA_TAB, SPECIES_TAB, RELIGION_TAB, GUIDE_TAB, SETTLEMENTS_TAB, CHRONICLES_TAB, DIPLOMACY_TAB, SYSTEMS_TAB, WHY_TAB

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
        "y": SYSTEMS_TAB,
        "w": WHY_TAB,
    }
    normalized = key.lower()
    if normalized in tabs:
        state["tab"] = tabs[normalized]
        state["page"] = 0
    elif state.get("tab") == WHY_TAB and normalized in {"1", "2", "3", "4"}:
        state["why_filter"] = {
            "1": "all",
            "2": "warfare",
            "3": "artifacts",
            "4": "legends",
        }[normalized]
        state["page"] = 0
    elif normalized == "n":
        state["page"] += 1
    elif normalized == "p":
        state["page"] = max(0, state["page"] - 1)


def main():
    engine = None
    options = None
    seed = None

    options = core.load_launch_options()
    if getattr(options, "archive_path", None):
        _run_archive_mode(options)
        return
    if getattr(options, "renderer", "terminal") == "web":
        _run_web_mode(options)
        return
    core.init_terminal()
    try:
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
            engine = SimulationEngine.create(
                config,
                seed,
                getattr(options, "width", WIDTH),
                getattr(options, "height", HEIGHT),
            )
            world, stats = engine.world, engine.stats

        renderer = RenderEngine(
            world.get("width", getattr(options, "width", WIDTH)),
            world.get("height", getattr(options, "height", HEIGHT)),
            config,
        )
        bestiary_state = {'active': False, 'tab': FAUNA_TAB, 'page': 0}
        presentation_config = config.get("presentation", {})
        max_commands = presentation_config.get("max_commands", 64) \
            if isinstance(presentation_config, dict) else 64

        host = SimulationHost(
            engine,
            tick_interval=getattr(options, "tick_speed", TICK_SPEED),
            save_path=options.save_path,
            max_commands=max_commands,
            snapshot_factory=_terminal_publication,
        )

        renderer.draw_frame(world, stats, reveal=True)
        while world['cycle'] < MAX_CYCLES:
            host.tick()

            key = check_input()
            if key:
                handle_bestiary_input(key, bestiary_state)

            if bestiary_state['active']:
                renderer.draw_bestiary(world, bestiary_state)
            else:
                renderer.draw_frame(world, stats)
            time.sleep(host.tick_interval)

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


def _run_archive_mode(options):
    """Ouvre une archive portable en lecture seule, sans créer de moteur."""
    print(Translator.translate(
        "system.archive_opening",
        file_path=options.archive_path,
        host=options.web_host,
        port=options.web_port,
    ))
    try:
        from core.history_archive import ArchiveFormatError
        from core.web_server import run_archive_web_server
        run_archive_web_server(
            options.archive_path,
            address=options.web_host,
            port=options.web_port,
        )
    except ModuleNotFoundError as error:
        if error.name != "aiohttp":
            raise
        print(Translator.translate("system.web_dependency_error"))
    except (OSError, ArchiveFormatError) as error:
        print(Translator.translate(
            "system.archive_open_error",
            file_path=options.archive_path,
            error=error,
        ))


def _run_web_mode(options):
    """Lance l'adaptateur web sans initialiser le terminal ANSI."""
    engine = None
    recorder = None
    recording_completed = False
    try:
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
            load_message = Translator.translate(
                "system.load_success",
                file_path=options.load_path,
            )
            engine.stats["logs"].append(load_message)
            engine.record_chronicle(load_message, category="system")
        else:
            engine = SimulationEngine.create(
                options.config,
                options.seed,
                getattr(options, "width", WIDTH),
                getattr(options, "height", HEIGHT),
            )

        archive_record_path = getattr(options, "archive_record_path", None)
        if archive_record_path:
            from core.history_archive import (
                ArchiveFormatError,
                HistoryArchiveRecorder,
            )
            try:
                recorder = HistoryArchiveRecorder(archive_record_path)
            except (OSError, ArchiveFormatError) as error:
                print(Translator.translate(
                    "system.archive_record_error",
                    file_path=archive_record_path,
                    error=error,
                ))
                return
            print(Translator.translate(
                "system.archive_recording",
                file_path=archive_record_path,
            ))

        presentation = engine.config.get("presentation", {})
        maximum = (
            presentation.get("max_commands", 64)
            if isinstance(presentation, dict) else 64
        )
        host = SimulationHost(
            engine,
            tick_interval=options.tick_speed,
            max_commands=maximum,
            save_path=options.save_path,
            snapshot_consumers=(
                () if recorder is None else (recorder.record,)
            ),
        )
        print(Translator.translate(
            "system.web_start",
            host=options.web_host,
            port=options.web_port,
        ))
        try:
            from core.web_server import run_web_server
            run_web_server(
                host,
                address=options.web_host,
                port=options.web_port,
            )
            recording_completed = True
        except KeyboardInterrupt:
            recording_completed = True
            raise
        except ModuleNotFoundError as error:
            if error.name != "aiohttp":
                raise
            print(Translator.translate("system.web_dependency_error"))
    finally:
        if recorder is not None:
            if recording_completed:
                try:
                    recorder.finalize()
                    print(Translator.translate(
                        "system.archive_record_success",
                        file_path=options.archive_record_path,
                    ))
                except (OSError, ArchiveFormatError) as error:
                    print(Translator.translate(
                        "system.archive_record_error",
                        file_path=options.archive_record_path,
                        error=error,
                    ))
            else:
                recorder.abort()
        if engine is not None and options.save_path:
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


def _terminal_publication(engine, revision):
    """Publication minimale : le terminal lit encore directement le moteur."""
    return {
        "schema_version": 1,
        "revision": int(revision),
        "cycle": int(engine.world.get("cycle", 0)),
    }

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
