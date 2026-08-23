import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.simulation_engine import SimulationEngine
from core.translator import Translator


ROOT = Path(__file__).resolve().parents[1]


class TraceGrid:
    def __init__(self, trace):
        self.trace = trace

    def clear(self):
        self.trace.append("grid.clear")

    def add_entity(self, entity):
        self.trace.append(f"grid.add:{entity.name}")


class TraceInfluence:
    def __init__(self, trace):
        self.trace = trace

    def update(self):
        self.trace.append("influence.update")


class TraceEntity:
    def __init__(self, name, trace, expired=False):
        self.name = name
        self.trace = trace
        self.is_expired = expired
        self.pos = (2, 3)

    def process_turn(self, world, stats):
        self.trace.append(f"entity.turn:{self.name}")

    def update_influence(self, world):
        self.trace.append(f"entity.influence:{self.name}")

    def check_vital_signs(self, world):
        self.trace.append(f"entity.vitals:{self.name}")

    def process_long_term_logic(self, world):
        self.trace.append(f"entity.long:{self.name}")


class BrokenEntity(TraceEntity):
    def process_turn(self, world, stats):
        self.trace.append(f"entity.turn:{self.name}")
        raise RuntimeError("broken turn")


class TraceEntityManager:
    def __init__(self, entities, trace):
        self.entities = list(entities)
        self.trace = trace

    def __iter__(self):
        return iter(self.entities)

    def remove_dead(self):
        self.trace.append("entities.cleanup")
        before = len(self.entities)
        self.entities = [entity for entity in self.entities if not entity.is_expired]
        return before - len(self.entities)


class SimulationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Translator.load("fr")

    def make_engine(self, cycle=0, entities=None):
        trace = []
        manager = TraceEntityManager(entities or [], trace)
        world = {
            "width": 8,
            "height": 6,
            "cycle": cycle,
            "entities": manager,
            "grid": TraceGrid(trace),
            "influence": TraceInfluence(trace),
        }
        stats = {"year": 0, "seed": 42, "logs": []}
        return SimulationEngine(world, stats, {"max_fauna": 0}), trace

    def engine_patches(self, trace, logs=None):
        return (
            mock.patch(
                "core.simulation_engine.entities_spawn.spawn_system",
                side_effect=lambda world, config: trace.append("spawn.update"),
            ),
            mock.patch(
                "core.simulation_engine.EventManager.update",
                side_effect=lambda world, stats, config: trace.append("events.update"),
            ),
            mock.patch(
                "core.simulation_engine.GameLogger.get_new_logs",
                return_value=list(logs or []),
            ),
        )

    def test_step_preserves_order_and_medium_tick_contract(self):
        active_trace = []
        active = TraceEntity("active", active_trace)
        expired = TraceEntity("expired", active_trace, expired=True)
        engine, trace = self.make_engine(cycle=9, entities=[active, expired])
        active.trace = trace
        expired.trace = trace

        spawn_patch, event_patch, logger_patch = self.engine_patches(trace, ["queued log"])
        with spawn_patch, event_patch, logger_patch:
            result = engine.step()

        self.assertEqual(result, 10)
        self.assertEqual(engine.stats["year"], 0)
        self.assertEqual(engine.stats["month"], 11)
        self.assertEqual(engine.stats["logs"], ["queued log"])
        self.assertEqual(
            trace,
            [
                "grid.clear",
                "grid.add:active",
                "spawn.update",
                "influence.update",
                "entity.turn:active",
                "entity.influence:active",
                "entity.vitals:active",
                "events.update",
                "entities.cleanup",
            ],
        )

    def test_slow_tick_runs_only_on_cycle_multiples_of_one_hundred(self):
        entity = TraceEntity("historian", [])
        engine, trace = self.make_engine(cycle=99, entities=[entity])
        entity.trace = trace
        spawn_patch, event_patch, logger_patch = self.engine_patches(trace)

        with spawn_patch, event_patch, logger_patch:
            engine.step()

        self.assertIn("entity.long:historian", trace)
        self.assertEqual(engine.world["cycle"], 100)

    def test_entity_error_is_localized_and_does_not_abort_cycle(self):
        broken = BrokenEntity("broken", [])
        healthy = TraceEntity("healthy", [])
        engine, trace = self.make_engine(entities=[broken, healthy])
        broken.trace = trace
        healthy.trace = trace
        spawn_patch, event_patch, logger_patch = self.engine_patches(trace)

        with spawn_patch, event_patch, logger_patch:
            engine.step()

        self.assertIn("entity.turn:healthy", trace)
        self.assertIn("events.update", trace)
        self.assertEqual(len(engine.stats["logs"]), 1)
        self.assertIn("BrokenEntity", engine.stats["logs"][0])
        self.assertIn("broken turn", engine.stats["logs"][0])
        self.assertNotIn("MISSING_TEXT", engine.stats["logs"][0])

    def test_run_advances_requested_number_of_cycles_without_rendering(self):
        engine, trace = self.make_engine()
        spawn_patch, event_patch, logger_patch = self.engine_patches(trace)

        with spawn_patch, event_patch, logger_patch:
            world, stats = engine.run(3)

        self.assertIs(world, engine.world)
        self.assertIs(stats, engine.stats)
        self.assertEqual(world["cycle"], 3)
        self.assertEqual(trace.count("events.update"), 3)

    def test_create_initializes_all_simulation_services(self):
        config = {"fauna": [{"species": "base"}]}
        world = {"entities": TraceEntityManager([], []), "cycle": 0}
        stats = {"year": 0, "seed": 123, "logs": []}
        grid = object()
        generated = [{"species": "generated"}]

        with (
            mock.patch("core.simulation_engine.RandomService.initialize") as random_init,
            mock.patch("core.simulation_engine.init_religion_data") as religion_init,
            mock.patch("core.simulation_engine.init_species_data") as species_init,
            mock.patch("core.simulation_engine.generate_fauna", return_value=generated),
            mock.patch("core.simulation_engine.assemble_world", return_value=(world, stats)) as assemble,
            mock.patch("core.simulation_engine.SpatialGrid", return_value=grid),
            mock.patch("core.simulation_engine.entities_spawn.seed_initial_cities") as seed_cities,
        ):
            engine = SimulationEngine.create(config, 123, width=20, height=10)

        random_init.assert_called_once_with(123)
        religion_init.assert_called_once_with(config)
        species_init.assert_called_once_with(config)
        assemble.assert_called_once_with(20, 10, config, 123)
        seed_cities.assert_called_once_with(world, config)
        self.assertEqual(config["fauna"], [{"species": "base"}, generated[0]])
        self.assertIs(world["grid"], grid)
        self.assertIs(engine.world, world)
        self.assertIs(engine.stats, stats)

    def test_main_delegates_simulation_cycles_to_headless_engine(self):
        import main as application

        world = {"cycle": 0, "entities": TraceEntityManager([], [])}
        stats = {"year": 0, "seed": 321, "logs": []}
        engine = mock.Mock()
        engine.world = world
        engine.stats = stats

        def advance_cycle():
            world["cycle"] += 1
            stats["year"] = 0
            stats["month"] = 2
            return world["cycle"]

        engine.step.side_effect = advance_cycle
        renderer = mock.Mock()
        config = {"world_name": "Headless Test", "fauna": []}
        options = SimpleNamespace(
            config=config,
            seed=321,
            load_path=None,
            save_path=None,
        )

        with (
            mock.patch.object(application.core, "init_terminal"),
            mock.patch.object(application.core, "restore_terminal"),
            mock.patch.object(application.core, "load_launch_options", return_value=options),
            mock.patch.object(application.SimulationEngine, "create", return_value=engine) as create,
            mock.patch.object(application, "RenderEngine", return_value=renderer),
            mock.patch.object(application, "check_input", return_value=None),
            mock.patch.object(application.time, "sleep"),
            mock.patch.object(application, "print_bestiary_summary"),
            mock.patch.object(application, "MAX_CYCLES", 1),
            mock.patch("builtins.print"),
        ):
            application.main()

        create.assert_called_once_with(config, 321, application.WIDTH, application.HEIGHT)
        engine.step.assert_called_once_with()
        renderer.draw_frame.assert_any_call(world, stats, reveal=True)
        renderer.draw_frame.assert_any_call(world, stats)

    def test_engine_module_has_no_terminal_or_render_dependency(self):
        source_path = ROOT / "core" / "simulation_engine.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertTrue({"render", "time", "select", "sys"}.isdisjoint(imports))


if __name__ == "__main__":
    unittest.main()
