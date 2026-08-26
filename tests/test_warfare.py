import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.diplomacy import DiplomacyRegistry
from core.random_service import RandomService
from core.warfare import WarfareSystem


def warfare_config(**overrides):
    warfare = {
        "enabled": True,
        "advance_interval": 1,
        "auto_declare": False,
        "war_tension_threshold": 80.0,
        "levy_rate": 0.2,
        "minimum_army": 2,
        "initial_morale": 100.0,
        "command_base": 1.0,
        "supply_per_soldier": 0.1,
        "max_supply_cost": 50.0,
        "unsupplied_morale_loss": 30.0,
        "unsupplied_attrition": 0.25,
        "winter_supply_multiplier": 1.5,
        "engagement_interval": 1,
        "casualty_rate": 0.2,
        "retreat_morale": 20.0,
        "prisoner_rate": 0.1,
        "truce_duration": 12,
        "max_history": 32,
    }
    warfare.update(overrides)
    return {
        "warfare": warfare,
        "pathfinding": {
            "enabled": True,
            "allow_diagonal": False,
            "base_cost": 1.0,
            "elevation_weight": 0.0,
            "road_multiplier": 0.5,
            "weather_weight": 0.0,
            "danger_weight": 0.0,
            "unknown_multiplier": 1.0,
            "max_cache_entries": 16,
            "max_expanded_nodes": 100,
        },
    }


def citizen(entity_id, notable=False):
    return SimpleNamespace(
        entity_id=entity_id,
        is_dead=False,
        character={"notability": {"is_notable": notable}},
        family_name=f"F{entity_id // 2}",
    )


def settlement(entity_id, x, population=20, food=100.0):
    return SimpleNamespace(
        entity_id=entity_id,
        name=f"S{entity_id}",
        pos=[x, 0],
        citizens=[citizen(entity_id * 100 + index) for index in range(population)],
        food_stock=food,
        max_food=200.0,
        is_expired=False,
        config={},
    )


def war_world(first, second, width=6):
    return {
        "width": width,
        "height": 1,
        "cycle": 1,
        "entities": [first, second],
        "road": [["  " for _ in range(width)]],
        "elev": [[0.0 for _ in range(width)]],
        "riv": [[0 for _ in range(width)]],
        "climate": {
            "season": "summer",
            "last_update_cycle": 1,
            "drought_severity": 0.0,
            "flood_severity": 0.0,
        },
        "diplomacy": {},
        "next_relation_id": 1,
        "politics": {
            "settlements": {
                str(first.entity_id): {"institution": {"legitimacy": 60.0}},
                str(second.entity_id): {"institution": {"legitimacy": 60.0}},
            }
        },
    }


class WarfareSystemTests(unittest.TestCase):
    def test_disabled_system_preserves_legacy_world(self):
        world = war_world(settlement(1, 0), settlement(2, 5))
        system = WarfareSystem(world, {"warfare": {"enabled": False}})

        self.assertFalse(system.advance())
        self.assertNotIn("warfare", world)

    def test_declared_war_always_has_a_cause_objective_and_armies(self):
        first, second = settlement(1, 0), settlement(2, 5)
        world = war_world(first, second)
        config = warfare_config()
        first.config = second.config = config
        system = WarfareSystem(world, config)

        campaign = system.declare_war(
            1,
            2,
            cause="territorial_dispute",
            objective="secure_frontier",
        )

        self.assertEqual(campaign["cause"], "territorial_dispute")
        self.assertEqual(campaign["objective"], "secure_frontier")
        self.assertEqual(campaign["status"], "active")
        self.assertEqual(set(campaign["armies"]), {"1", "2"})
        self.assertEqual(DiplomacyRegistry(world).get(1, 2)["status"], "war")

    def test_existing_territorial_war_derives_a_resource_objective_from_evidence(self):
        first, second = settlement(1, 0), settlement(2, 5)
        world = war_world(first, second)
        world["territory"] = {
            "revision": 1,
            "tiles": {
                "3,0": {
                    "contested": True,
                    "strategic_resources": ["surface_water"],
                    "claimants": [
                        {"settlement_id": 1, "score": 5},
                        {"settlement_id": 2, "score": 5},
                    ],
                }
            },
            "borders": [{"first_id": 1, "second_id": 2, "tiles": 1}],
        }
        registry = DiplomacyRegistry(world)
        registry.adjust(1, 2, tension=90, reason="territorial_dispute")
        registry.transition(1, 2, "war", reason="territorial_dispute")
        system = WarfareSystem(world, warfare_config())

        system.advance()
        campaign = system.summary()["active_campaigns"][0]

        self.assertEqual(campaign["cause"], "territorial_dispute")
        self.assertEqual(campaign["objective"], "control_resource:surface_water")
        self.assertIn("contested_tile:3,0", campaign["evidence"])

    def test_isolated_army_loses_supply_morale_and_eventually_retreats(self):
        first, second = settlement(1, 0), settlement(2, 5)
        world = war_world(first, second)
        config = warfare_config(
            max_supply_cost=1.0,
            unsupplied_morale_loss=45.0,
            retreat_morale=20.0,
        )
        system = WarfareSystem(world, config)
        system.declare_war(1, 2, cause="revenge", objective="punitive_raid")

        for cycle in range(1, 5):
            world["cycle"] = cycle
            system.advance()
            if system.summary()["ended_campaigns"]:
                break

        ended = system.summary()["ended_campaigns"][0]
        self.assertEqual(ended["end_reason"], "supply_collapse")
        self.assertTrue(any(not army["supplied"] for army in ended["armies"].values()))
        self.assertEqual(DiplomacyRegistry(world).get(1, 2)["status"], "truce")

    def test_supply_and_battle_cost_food_people_prisoners_and_legitimacy(self):
        first, second = settlement(1, 0, population=30), settlement(2, 5, population=10)
        world = war_world(first, second)
        for x in range(6):
            world["road"][0][x] = "=="
        config = warfare_config(casualty_rate=0.5, prisoner_rate=0.5)
        system = WarfareSystem(world, config)
        system.declare_war(1, 2, cause="succession", objective="install_claimant")
        before_food = first.food_stock + second.food_stock
        before_population = len(first.citizens) + len(second.citizens)
        before_state = copy.deepcopy(world["politics"])
        RandomService.initialize(1471)
        random_before = RandomService.get_state()

        system.advance()
        campaign = system.summary()["active_campaigns"][0]

        self.assertEqual(RandomService.get_state(), random_before)
        self.assertLess(first.food_stock + second.food_stock, before_food)
        self.assertLess(len(first.citizens) + len(second.citizens), before_population)
        self.assertGreater(campaign["costs"]["casualties"], 0)
        self.assertGreaterEqual(campaign["costs"]["prisoners"], 0)
        self.assertLess(
            world["politics"]["settlements"]["2"]["institution"]["legitimacy"],
            before_state["settlements"]["2"]["institution"]["legitimacy"],
        )


ROOT = Path(__file__).resolve().parents[1]


class WarfareIntegrationTests(unittest.TestCase):
    def test_template_is_opt_in_and_validator_checks_warfare_bounds(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["warfare"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["warfare"]["casualty_rate"] = 2.0
        invalid["warfare"]["minimum_army"] = 0
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:warfare.casualty_rate:0_1", caught.exception.errors)
        self.assertIn("range:warfare.minimum_army:positive", caught.exception.errors)

    def test_engine_advances_persists_and_exposes_causal_campaigns(self):
        from core.simulation_engine import SimulationEngine

        legacy = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        legacy_engine = SimulationEngine.create(legacy, 1481, 12, 8)
        self.assertNotIn("warfare", legacy_engine.world)

        config = copy.deepcopy(legacy)
        config["warfare"]["enabled"] = True
        config["warfare"]["advance_interval"] = 1
        config["pathfinding"]["enabled"] = True
        engine = SimulationEngine.create(config, 1483, 12, 8)
        settlements = [
            entity
            for entity in engine.world["entities"]
            if hasattr(entity, "citizens") and not entity.is_expired
        ][:2]
        campaign = engine.declare_war(
            settlements[0].entity_id,
            settlements[1].entity_id,
            cause="territorial_dispute",
            objective="secure_frontier",
        )
        engine.step()
        summary = engine.get_warfare_summary()
        system = next(
            item for item in engine.get_systems_snapshot()
            if item["id"] == "warfare"
        )
        inspection = engine.inspect_entity(settlements[0].entity_id)

        self.assertEqual(campaign["cause"], "territorial_dispute")
        self.assertTrue(system["enabled"])
        self.assertEqual(system["state"], summary)
        self.assertIn("warfare", inspection)

        before = copy.deepcopy(engine.world["warfare"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "warfare.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.world["warfare"], before)
        self.assertEqual(resumed.get_warfare_summary(), summary)


if __name__ == "__main__":
    unittest.main()

