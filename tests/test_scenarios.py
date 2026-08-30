import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.entities import EntityManager
from core.logger import GameLogger
from core.translator import Translator


ROOT = Path(__file__).resolve().parents[1]


def base_config():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


def world_with_entities(*entities, cycle=0):
    return {"cycle": cycle, "entities": EntityManager(), "chronicles": [], "next_chronicle_id": 1}


class ScenarioCompositionTests(unittest.TestCase):
    def test_layers_compose_in_order_without_mutating_inputs(self):
        from core.scenarios import compose_config

        base = {"world_name": "Base", "economy": {"enabled": True, "food_reserve": 50}, "fauna": [{"species": "wolf"}]}
        mod = {"mod": {"id": "hard-market"}, "patch": {"economy": {"food_reserve": 80}}, "append": {"fauna": [{"species": "lynx"}]}}
        scenario = {"scenario": {"id": "survival", "title_key": "scenarios.survival.title", "objectives": []}, "patch": {"world_name": "Survival"}}
        original = copy.deepcopy((base, mod, scenario))

        composed = compose_config(base, scenario=scenario, mods=[mod])

        self.assertEqual(composed["world_name"], "Survival")
        self.assertEqual(composed["economy"], {"enabled": True, "food_reserve": 80})
        self.assertEqual([item["species"] for item in composed["fauna"]], ["wolf", "lynx"])
        self.assertEqual((base, mod, scenario), original)
        self.assertEqual(composed["active_mods"], ["hard-market"])

    def test_bundled_scenario_and_mod_compose_into_valid_runtime_config(self):
        from core.config_validator import validate_config
        from core.scenarios import load_config_layers

        composed = load_config_layers(
            ROOT / "template.json",
            scenario_path=ROOT / "scenarios" / "fragile_frontier.json",
            mod_paths=[ROOT / "mods" / "highland_bison.json"],
        )

        self.assertIs(validate_config(composed), composed)
        self.assertEqual(composed["scenario"]["id"], "fragile_frontier")
        self.assertIn("highland_bison", composed["active_mods"])
        self.assertIn("bison", {animal["species"] for animal in composed["fauna"]})
    def test_duplicate_mod_ids_and_data_identifiers_are_rejected(self):
        from core.scenarios import ScenarioValidationError, compose_config

        duplicate_ids = [{"mod": {"id": "same"}}, {"mod": {"id": "same"}}]
        with self.assertRaises(ScenarioValidationError) as error:
            compose_config({}, mods=duplicate_ids)
        self.assertEqual(error.exception.code, "duplicate_mod_id:same")

        base = {"fauna": [{"species": "wolf"}]}
        duplicate_species = {"mod": {"id": "wolves"}, "append": {"fauna": [{"species": "wolf"}]}}
        with self.assertRaises(ScenarioValidationError) as error:
            compose_config(base, mods=[duplicate_species])
        self.assertEqual(error.exception.code, "duplicate_data_id:fauna:wolf")

    def test_json_layers_load_without_executing_code(self):
        from core.scenarios import load_config_layers

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_path = root / "base.json"
            mod_path = root / "mod.json"
            scenario_path = root / "scenario.json"
            base_path.write_text(json.dumps({"world_name": "Base", "fauna": []}), encoding="utf-8")
            mod_path.write_text(json.dumps({"mod": {"id": "safe"}, "patch": {"max_fauna": 3}}), encoding="utf-8")
            scenario_path.write_text(json.dumps({"scenario": {"id": "short", "objectives": []}}), encoding="utf-8")

            result = load_config_layers(base_path, scenario_path=scenario_path, mod_paths=[mod_path])

        self.assertEqual(result["max_fauna"], 3)
        self.assertEqual(result["scenario"]["id"], "short")


class ScenarioRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)

    def setUp(self):
        GameLogger.get_new_logs()

    def test_service_initializes_lazily_and_returns_defensive_summary(self):
        from core.scenarios import ScenarioService

        world = world_with_entities()
        config = {"scenario": {"id": "sandbox", "title_key": "scenarios.sandbox.title", "objectives": []}}
        service = ScenarioService(world, config)
        summary = service.summary()
        summary["status"] = "corrupted"

        self.assertEqual(world["scenario"]["id"], "sandbox")
        self.assertEqual(service.summary()["status"], "active")

    def test_objectives_win_once_and_emit_localized_structured_log(self):
        from core.scenarios import ScenarioService

        world = world_with_entities(cycle=11)
        config = {"scenario": {"id": "survive", "title_key": "scenarios.survive.title", "objectives": [{"id": "one_year", "metric": "cycle", "operator": ">=", "target": 12}]}}
        service = ScenarioService(world, config)
        self.assertEqual(service.advance()["status"], "active")
        world["cycle"] = 12
        self.assertEqual(service.advance()["status"], "won")
        service.advance()

        logs = GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(len(logs))
        self.assertEqual(len(logs), 1)
        self.assertNotIn("MISSING_TEXT", logs[0])
        self.assertEqual(metadata[0]["category"], "scenario")

    def test_any_defeat_condition_has_priority_over_victory(self):
        from core.scenarios import ScenarioService

        world = world_with_entities(cycle=12)
        config = {"scenario": {"id": "fragile", "objectives": [{"id": "survive", "metric": "cycle", "operator": ">=", "target": 12}], "defeat_conditions": [{"id": "extinction", "metric": "population", "operator": "<=", "target": 0}]}}

        self.assertEqual(ScenarioService(world, config).advance()["status"], "lost")

    def test_validator_rejects_unknown_metrics_operators_and_duplicate_objectives(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = base_config()
        invalid_scenarios = (
            {"id": "bad", "objectives": [{"id": "x", "metric": "python", "operator": ">=", "target": 1}]},
            {"id": "bad", "objectives": [{"id": "x", "metric": "cycle", "operator": "exec", "target": 1}]},
            {"id": "bad", "objectives": [{"id": "x", "metric": "cycle", "operator": ">=", "target": 1}, {"id": "x", "metric": "cycle", "operator": ">=", "target": 2}]},
        )
        for scenario in invalid_scenarios:
            invalid = copy.deepcopy(config)
            invalid["scenario"] = scenario
            with self.subTest(scenario=scenario), self.assertRaises(ConfigValidationError):
                validate_config(invalid)


class ScenarioEngineAndCliTests(unittest.TestCase):
    def setUp(self):
        from core.random_service import RandomService
        RandomService.initialize(1357)
        GameLogger.get_new_logs()

    def make_engine(self, scenario):
        import numpy as np
        from core.grid_service import SpatialGrid
        from core.influence import InfluenceSystem
        from core.simulation_engine import SimulationEngine
        world = {"width": 3, "height": 3, "cycle": 0, "elev": np.full((3, 3), 0.2), "riv": np.zeros((3, 3)), "entities": EntityManager(), "grid": SpatialGrid(3, 3, 2), "influence": InfluenceSystem(3, 3, {})}
        return SimulationEngine(world, {"year": 0, "month": 1, "seed": 1357, "logs": []}, {"scenario": scenario})

    def test_engine_applies_initial_climate_once_and_exposes_summary(self):
        scenario = {"id": "dry_start", "initial": {"climate": {"drought_severity": 0.7}}, "objectives": []}
        engine = self.make_engine(scenario)
        summary = engine.get_scenario_summary()
        summary["status"] = "corrupt"
        engine.world["climate"]["drought_severity"] = 0.2
        from core.scenarios import ScenarioService
        ScenarioService(engine.world, engine.config)
        self.assertEqual(engine.get_scenario_summary()["status"], "active")
        self.assertEqual(engine.world["climate"]["drought_severity"], 0.2)

    def test_engine_cycle_evaluates_scenario_and_records_chronicle(self):
        scenario = {"id": "instant", "objectives": [{"id": "first", "metric": "cycle", "operator": ">=", "target": 1}]}
        engine = self.make_engine(scenario)
        with (mock.patch("core.simulation_engine.entities_spawn.spawn_system"), mock.patch("core.simulation_engine.EventManager.update")):
            engine.step()
        self.assertEqual(engine.get_scenario_summary()["status"], "won")
        self.assertEqual(len(engine.get_chronicles(category="scenario")), 1)

    def test_checkpoint_preserves_completed_scenario_state(self):
        from core.simulation_engine import SimulationEngine
        scenario = {"id": "saved", "objectives": [{"id": "start", "metric": "cycle", "operator": ">=", "target": 0}]}
        engine = self.make_engine(scenario)
        from core.scenarios import ScenarioService
        ScenarioService(engine.world, engine.config).advance()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.chart"
            engine.save(path)
            restored = SimulationEngine.load(path)
        self.assertEqual(restored.get_scenario_summary()["status"], "won")
        self.assertEqual(restored.get_scenario_summary()["finished_cycle"], 0)

    def test_header_renders_localized_scenario_progress(self):
        import contextlib
        import io
        from render.ui_header import render_header
        scenario = {"id": "frontier", "title_key": "scenarios.frontier.title", "objectives": [{"id": "first", "metric": "cycle", "operator": ">=", "target": 12}]}
        engine = self.make_engine(scenario)
        expected_titles = {"fr": "Frontière fragile", "en": "Fragile Frontier", "es": "Frontera frágil"}
        for language, title in expected_titles.items():
            previous = Path.cwd()
            try:
                os.chdir(ROOT)
                Translator.load(language)
            finally:
                os.chdir(previous)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                render_header(3, engine.world, engine.stats, engine.config)
            self.assertIn(title, output.getvalue())
            self.assertNotIn("MISSING_TEXT", output.getvalue())
    def test_cli_reports_invalid_layer_with_localized_config_error(self):
        import contextlib
        import io
        from core.scenarios import ScenarioValidationError
        from core.system import load_launch_options

        output = io.StringIO()
        with (
            mock.patch("sys.argv", ["chartographist", "--seed", "7", "--mod", "broken.json"]),
            mock.patch("core.system.load_config_layers", side_effect=ScenarioValidationError("invalid_json:broken.json")),
            contextlib.redirect_stdout(output),
        ):
            options = load_launch_options()

        self.assertEqual(options.config, {})
        self.assertNotIn("MISSING_TEXT", output.getvalue())
        self.assertIn("broken.json", output.getvalue())
    def test_cli_composes_repeated_mods_then_scenario(self):
        from core.system import load_launch_options
        composed = base_config()
        composed["active_mods"] = ["a", "b"]
        with (mock.patch("sys.argv", ["chartographist", "--seed", "7", "--template", "base.json", "--mod", "a.json", "--mod", "b.json", "--scenario", "s.json"]), mock.patch("core.system.load_config_layers", return_value=composed) as loader):
            options = load_launch_options()
        loader.assert_called_once_with("base.json", scenario_path="s.json", mod_paths=("a.json", "b.json"))
        self.assertEqual(options.config["active_mods"], ["a", "b"])
        self.assertEqual(options.scenario_path, "s.json")
        self.assertEqual(options.mod_paths, ("a.json", "b.json"))
if __name__ == "__main__":
    unittest.main()
