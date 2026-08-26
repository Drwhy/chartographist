import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.diplomacy import DiplomacyRegistry, world_diplomatic_summary
from core.peace import PeaceSystem
from core.warfare import WarfareSystem
from tests.test_warfare import settlement, war_world, warfare_config

from core.territory import TerritorySystem
from tests.test_territory import territory_config

def peace_config(**overrides):
    settings = {
        "enabled": True,
        "transfer_territory": True,
        "tribute_food_ratio": 0.25,
        "tribute_base": 10.0,
        "commercial_rights": 10.0,
        "postwar_tension": 5.0,
        "refugee_rate": 0.5,
        "max_treaties": 16,
    }
    settings.update(overrides)
    config = warfare_config()
    config["peace"] = settings
    return config


def ended_campaign():
    return {
        "campaign_id": 7,
        "attacker_id": 1,
        "defender_id": 2,
        "cause": "territorial_dispute",
        "objective": "control_resource:surface_water",
        "started_cycle": 1,
        "ended_cycle": 4,
        "winner_id": 1,
        "end_reason": "military_defeat",
        "costs": {
            "food": 8.0,
            "casualties": 10,
            "prisoners": 3,
            "raided_food": 2.0,
        },
        "armies": {
            "1": {"settlement_id": 1, "strength": 4},
            "2": {"settlement_id": 2, "strength": 1},
        },
    }


class PeaceSystemTests(unittest.TestCase):
    def setUp(self):
        self.winner = settlement(1, 0, population=10, food=10)
        self.loser = settlement(2, 5, population=10, food=100)
        self.world = war_world(self.winner, self.loser)
        self.world["territory"] = {
            "revision": 1,
            "tiles": {
                "3,0": {
                    "x": 3,
                    "y": 0,
                    "owner_id": None,
                    "contested": True,
                    "strategic_resources": ["surface_water"],
                    "claimants": [
                        {"settlement_id": 1, "score": 5},
                        {"settlement_id": 2, "score": 5},
                    ],
                }
            },
            "borders": [],
            "contested_tiles": 1,
        }
        DiplomacyRegistry(self.world).transition(
            1, 2, "war", reason="territorial_dispute"
        )

    def test_disabled_peace_preserves_legacy_world(self):
        system = PeaceSystem(self.world, {"peace": {"enabled": False}})
        self.assertIsNone(system.conclude(ended_campaign()))
        self.assertNotIn("peace", self.world)

    def test_treaty_applies_territory_tribute_hostages_and_commercial_rights(self):
        system = PeaceSystem(self.world, peace_config())

        treaty = system.conclude(ended_campaign())
        relation = DiplomacyRegistry(self.world).get(1, 2)
        tile = self.world["territory"]["tiles"]["3,0"]

        self.assertEqual(treaty["cause"], "territorial_dispute")
        self.assertEqual(treaty["objective"], "control_resource:surface_water")
        self.assertEqual(treaty["terms"]["territory"], ["3,0"])
        self.assertEqual(treaty["terms"]["tribute_food"], 25.0)
        self.world["cycle"] = 2
        territory = TerritorySystem(self.world, territory_config(contest_margin=3.0))
        territory.advance()
        self.assertEqual(territory.tile_snapshot(3, 0)["owner_id"], 1)
        self.assertFalse(territory.tile_snapshot(3, 0)["contested"])
        self.assertEqual(treaty["terms"]["hostages"], 3)
        self.assertEqual(self.winner.food_stock, 35.0)
        self.assertEqual(self.loser.food_stock, 75.0)
        self.assertEqual(tile["owner_id"], 1)
        self.assertFalse(tile["contested"])
        self.assertEqual(relation["status"], "truce")
        self.assertEqual(relation["interdependence"], 10.0)

    def test_consequences_include_veterans_refugees_debts_and_grievances(self):
        self.loser.food_stock = 2.0
        system = PeaceSystem(self.world, peace_config(tribute_base=20.0))

        treaty = system.conclude(ended_campaign())
        consequences = treaty["consequences"]

        self.assertEqual(consequences["veterans"]["1"], 4)
        self.assertEqual(consequences["refugees"], 5)
        self.assertEqual(consequences["debt"], 18.0)
        self.assertEqual(consequences["ruins"], 1)
        self.assertEqual(consequences["grievance"], "postwar_settlement")
        self.assertGreater(
            DiplomacyRegistry(self.world).get(1, 2)["tension"],
            0,
        )

    def test_conclusion_is_idempotent_and_diplomacy_exposes_causal_peace(self):
        system = PeaceSystem(self.world, peace_config())
        first = system.conclude(ended_campaign())
        state = copy.deepcopy(self.world["peace"])
        second = system.conclude(ended_campaign())
        diplomacy = world_diplomatic_summary(self.world)

        self.assertEqual(first, second)
        self.assertEqual(self.world["peace"], state)
        self.assertEqual(diplomacy["peace"]["treaties"], 1)
        self.assertEqual(
            diplomacy["peace"]["last_treaty"]["end_reason"],
            "military_defeat",
        )

    def test_warfare_automatically_concludes_peace_when_supply_collapses(self):
        config = peace_config(max_treaties=4)
        config["warfare"].update(
            {
                "max_supply_cost": 1.0,
                "unsupplied_morale_loss": 90.0,
                "retreat_morale": 20.0,
            }
        )
        system = WarfareSystem(self.world, config)
        system.declare_war(1, 2, cause="revenge", objective="punitive_raid")

        system.advance()

        self.assertEqual(len(self.world["peace"]["treaties"]), 1)
        self.assertEqual(
            self.world["peace"]["treaties"][0]["end_reason"],
            "supply_collapse",
        )


ROOT = Path(__file__).resolve().parents[1]


class PeaceIntegrationTests(unittest.TestCase):
    def test_template_is_opt_in_and_validator_checks_peace_bounds(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["peace"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["peace"]["refugee_rate"] = -0.1
        invalid["peace"]["max_treaties"] = 0
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:peace.refugee_rate:0_1", caught.exception.errors)
        self.assertIn("range:peace.max_treaties:positive", caught.exception.errors)

    def test_engine_persists_and_exposes_treaties_and_consequences(self):
        from core.simulation_engine import SimulationEngine

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config["peace"]["enabled"] = True
        engine = SimulationEngine.create(config, 1491, 12, 8)
        settlements = [
            entity
            for entity in engine.world["entities"]
            if hasattr(entity, "citizens") and not entity.is_expired
        ][:2]
        first_id, second_id = (entity.entity_id for entity in settlements)
        DiplomacyRegistry(engine.world).transition(
            first_id,
            second_id,
            "war",
            reason="succession",
        )
        campaign = ended_campaign()
        campaign.update(
            {
                "attacker_id": first_id,
                "defender_id": second_id,
                "winner_id": first_id,
                "armies": {
                    str(first_id): {"settlement_id": first_id, "strength": 4},
                    str(second_id): {"settlement_id": second_id, "strength": 1},
                },
            }
        )
        PeaceSystem(engine.world, config).conclude(campaign)
        summary = engine.get_peace_summary()
        system = next(
            item for item in engine.get_systems_snapshot()
            if item["id"] == "peace"
        )
        inspection = engine.inspect_entity(first_id)

        self.assertEqual(summary["treaties"], 1)
        self.assertTrue(system["enabled"])
        self.assertEqual(system["state"], summary)
        self.assertIn("peace", inspection)

        before = copy.deepcopy(engine.world["peace"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "peace.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.world["peace"], before)
        self.assertEqual(resumed.get_peace_summary(), summary)


if __name__ == "__main__":
    unittest.main()

