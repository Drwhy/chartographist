import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.random_service import RandomService
from core.simulation_engine import SimulationEngine
from core.translator import Translator
from tests.test_factions import conflict_config


ROOT = Path(__file__).resolve().parents[1]


def template_config():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


def enabled_config():
    config = template_config()
    config["politics"] = copy.deepcopy(conflict_config()["politics"])
    return config


class PoliticsEngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_politics_is_opt_in_and_engine_advances_it_once_per_cycle(self):
        legacy = template_config()
        legacy["politics"]["enabled"] = False
        legacy_engine = SimulationEngine.create(legacy, 1311, 12, 8)
        self.assertNotIn("politics", legacy_engine.world)

        engine = SimulationEngine.create(enabled_config(), 1311, 12, 8)
        RandomService.initialize(1311)
        engine.step()
        first = copy.deepcopy(engine.world["politics"])
        engine.get_political_summary()
        self.assertEqual(RandomService.get_seed(), 1311)

        summary = engine.get_political_summary()

        self.assertTrue(summary["enabled"])
        self.assertGreater(summary["settlements"], 0)
        self.assertGreater(summary["factions"], 1)
        self.assertIn("average_legitimacy", summary)
        self.assertEqual(
            {
                state["last_advanced_cycle"]
                for state in engine.world["politics"]["settlements"].values()
            },
            {1},
        )
        self.assertEqual(first, engine.world["politics"])

    def test_checkpoint_preserves_factions_offices_proposals_and_next_ids(self):
        engine = SimulationEngine.create(enabled_config(), 1313, 12, 8)
        engine.run(2)
        before = copy.deepcopy(engine.world["politics"])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "politics.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)

        self.assertEqual(resumed.world["politics"], before)
        self.assertEqual(
            resumed.get_political_summary(),
            engine.get_political_summary(),
        )

    def test_metrics_visibility_and_inspection_expose_political_effects(self):
        engine = SimulationEngine.create(enabled_config(), 1317, 12, 8)
        engine.step()

        metrics = engine.get_metrics_snapshot()
        systems = engine.get_systems_snapshot()
        settlement = next(
            entity
            for entity in engine.world["entities"]
            if hasattr(entity, "citizens") and not entity.is_expired
        )
        inspection = engine.inspect_entity(settlement.entity_id)
        politics_system = next(
            system for system in systems if system["id"] == "politics"
        )

        self.assertIn("politics", metrics["flows"])
        self.assertTrue(politics_system["enabled"])
        self.assertEqual(
            politics_system["state"]["factions"],
            engine.get_political_summary()["factions"],
        )
        self.assertIn("institution", inspection["politics"])
        self.assertIn("active_policies", inspection["politics"])

    def test_template_and_validator_cover_data_driven_politics(self):
        from core.config_validator import ConfigValidationError, validate_config

        template = template_config()
        self.assertFalse(template["politics"]["enabled"])
        self.assertTrue(template["politics"]["faction_types"])
        self.assertTrue(template["politics"]["governments"])
        self.assertTrue(template["politics"]["policies"])
        self.assertIs(validate_config(template), template)

        invalid = enabled_config()
        invalid["politics"]["governments"][0]["offices"].append(
            copy.deepcopy(
                invalid["politics"]["governments"][0]["offices"][0]
            )
        )
        invalid["politics"]["policies"][0]["supports"] = ["unknown_objective"]

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn(
            "duplicate:politics.office:steward",
            caught.exception.errors,
        )
        self.assertIn(
            "reference:politics.policy.market_charter.supports:unknown_objective",
            caught.exception.errors,
        )


if __name__ == "__main__":
    unittest.main()
