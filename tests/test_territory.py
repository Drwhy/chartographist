import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.territory import TerritorySystem


def territory_config(**overrides):
    settings = {
        "enabled": True,
        "advance_interval": 1,
        "max_radius": 5,
        "base_power": 5.0,
        "population_scale": 1.0,
        "distance_decay": 0.5,
        "road_multiplier": 1.5,
        "fortification_scale": 2.0,
        "contest_margin": 2.0,
        "strategic_resource_bonus": 4.0,
        "territorial_tension": 0.5,
        "strategic_resources": ["surface_water"],
    }
    settings.update(overrides)
    return {"territory": settings}


def settlement(entity_id, x, y, population, fortification=0.0):
    return SimpleNamespace(
        entity_id=entity_id,
        pos=[x, y],
        citizens=[object() for _ in range(population)],
        fortification_strength=fortification,
        is_expired=False,
    )


def world_with(*settlements, width=7, height=5):
    return {
        "width": width,
        "height": height,
        "cycle": 1,
        "entities": list(settlements),
        "road": [["  " for _ in range(width)] for _ in range(height)],
        "resources": {
            "grids": {
                "surface_water": {
                    "stock": [[0.0 for _ in range(width)] for _ in range(height)],
                }
            }
        },
        "diplomacy": {},
        "next_relation_id": 1,
    }


class TerritorySystemTests(unittest.TestCase):
    def test_disabled_system_preserves_legacy_world(self):
        world = world_with(settlement(1, 1, 1, 5))

        system = TerritorySystem(world, {"territory": {"enabled": False}})

        self.assertFalse(system.enabled)
        self.assertFalse(system.advance())
        self.assertNotIn("territory", world)

    def test_claims_propagate_by_population_distance_roads_and_fortifications(self):
        first = settlement(1, 0, 2, 8)
        second = settlement(2, 6, 2, 3, fortification=4.0)
        world = world_with(first, second)
        world["road"][2][2] = "=="
        system = TerritorySystem(world, territory_config())

        self.assertTrue(system.advance())
        near_first = system.tile_snapshot(1, 2)
        road_reach = system.tile_snapshot(2, 2)
        near_fort = system.tile_snapshot(5, 2)

        self.assertEqual(near_first["owner_id"], 1)
        self.assertEqual(near_fort["owner_id"], 2)
        self.assertGreater(
            next(c["score"] for c in road_reach["claimants"] if c["settlement_id"] == 1),
            8.0,
        )
        self.assertGreater(
            next(c["score"] for c in near_fort["claimants"] if c["settlement_id"] == 2),
            next(c["score"] for c in near_fort["claimants"] if c["settlement_id"] == 1),
        )

    def test_close_claims_create_contested_tiles_and_visible_borders(self):
        world = world_with(
            settlement(10, 1, 2, 5),
            settlement(20, 5, 2, 5),
        )
        system = TerritorySystem(world, territory_config(contest_margin=3.0))

        system.advance()
        center = system.tile_snapshot(3, 2)
        summary = system.summary()

        self.assertTrue(center["contested"])
        self.assertIsNone(center["owner_id"])
        self.assertEqual([10, 20], [c["settlement_id"] for c in center["claimants"]])
        self.assertGreater(summary["contested_tiles"], 0)
        self.assertEqual(summary["borders"][0]["first_id"], 10)
        self.assertEqual(summary["borders"][0]["second_id"], 20)

    def test_strategic_dispute_creates_one_diplomatic_grievance_per_cycle(self):
        world = world_with(
            settlement(1, 1, 2, 5),
            settlement(2, 5, 2, 5),
        )
        world["resources"]["grids"]["surface_water"]["stock"][2][3] = 10.0
        system = TerritorySystem(world, territory_config(contest_margin=3.0))

        system.advance()
        first_state = copy.deepcopy(world["territory"])
        relation = world["diplomacy"]["1:2"]

        self.assertIn("surface_water", system.tile_snapshot(3, 2)["strategic_resources"])
        self.assertEqual(relation["tension"], 0.5)
        self.assertEqual(relation["reasons"][-1]["kind"], "territorial_dispute")
        self.assertFalse(system.advance())
        self.assertEqual(world["territory"], first_state)
        self.assertEqual(len(relation["reasons"]), 1)


ROOT = Path(__file__).resolve().parents[1]


def template_config():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


class TerritoryIntegrationTests(unittest.TestCase):
    def test_template_is_opt_in_and_validator_checks_territory_contract(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = template_config()
        self.assertFalse(config["territory"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["territory"]["max_radius"] = -1
        invalid["territory"]["strategic_resources"] = "surface_water"
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:territory.max_radius:non_negative", caught.exception.errors)
        self.assertIn("type:territory.strategic_resources:list", caught.exception.errors)

    def test_engine_advances_persists_and_exposes_territory(self):
        from core.simulation_engine import SimulationEngine

        legacy = template_config()
        legacy_engine = SimulationEngine.create(legacy, 1401, 12, 8)
        legacy_engine.step()
        self.assertNotIn("territory", legacy_engine.world)

        config = template_config()
        config["territory"]["enabled"] = True
        engine = SimulationEngine.create(config, 1403, 12, 8)
        config["territory"]["advance_interval"] = 1
        engine.step()

        summary = engine.get_territory_summary()
        systems = engine.get_systems_snapshot()
        territory_entry = next(item for item in systems if item["id"] == "territory")
        settlement = next(
            entity
            for entity in engine.world["entities"]
            if hasattr(entity, "citizens") and not entity.is_expired
        )
        inspection = engine.inspect_entity(settlement.entity_id)
        tile = engine.get_tile_territory(*settlement.pos)

        self.assertTrue(summary["enabled"])
        self.assertGreater(summary["claimed_tiles"], 0)
        self.assertEqual(tile["owner_id"], settlement.entity_id)
        self.assertTrue(territory_entry["enabled"])
        self.assertEqual(territory_entry["state"], summary)
        self.assertGreater(inspection["territory"]["owned_tiles"], 0)

        before = copy.deepcopy(engine.world["territory"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "territory.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.world["territory"], before)
        self.assertEqual(resumed.get_territory_summary(), summary)


if __name__ == "__main__":
    unittest.main()

