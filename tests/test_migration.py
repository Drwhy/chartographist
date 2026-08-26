import copy
import json
import tempfile
import unittest
from pathlib import Path
from core.logger import GameLogger
from core.translator import Translator
from types import SimpleNamespace

from core.migration import MigrationSystem
from core.random_service import RandomService


def migration_config(**overrides):
    settings = {
        "enabled": True,
        "advance_interval": 1,
        "departure_threshold": 1.0,
        "hunger_food_ratio": 0.25,
        "hunger_weight": 4.0,
        "war_weight": 3.0,
        "climate_weight": 2.0,
        "persecution_weight": 2.0,
        "opportunity_departure_weight": 1.0,
        "food_attractiveness": 3.0,
        "capacity_attractiveness": 2.0,
        "knowledge_bonus": 2.0,
        "family_bonus": 2.0,
        "distance_penalty": 0.1,
        "settlement_capacity": 20,
        "cohort_size": 3,
        "minimum_population": 1,
        "max_history": 16,
        "integration_rate": 0.2,
        "discrimination_penalty": 0.25,
    }
    settings.update(overrides)
    return {"migration": settings}


def person(entity_id, culture="A", family="Vale", notable=False):
    return SimpleNamespace(
        entity_id=entity_id,
        culture={"name": culture},
        family_name=family,
        faith=SimpleNamespace(primary="river"),
        skills={"trade": {"level": 2}},
        disease="fever" if entity_id == 2 else None,
        memories=[{"kind": "famine"}],
        character={"notability": {"is_notable": notable}},
        pos=[0, 0],
        is_dead=False,
    )


def settlement(entity_id, x, food, citizens, culture="A"):
    return SimpleNamespace(
        entity_id=entity_id,
        name=f"S{entity_id}",
        pos=[x, 0],
        citizens=list(citizens),
        food_stock=float(food),
        max_food=100.0,
        culture={"name": culture},
        known_cities=set(),
        is_expired=False,
    )


def migration_world(*settlements):
    return {
        "width": 10,
        "height": 2,
        "cycle": 1,
        "entities": list(settlements),
        "diplomacy": {},
        "next_relation_id": 1,
        "climate": {"drought_severity": 0.0, "flood_severity": 0.0},
        "notables": {},
    }


class MigrationSystemTests(unittest.TestCase):
    def test_disabled_system_preserves_people_and_legacy_world(self):
        source = settlement(1, 0, 0, [person(1), person(2)])
        destination = settlement(2, 4, 100, [person(3)])
        world = migration_world(source, destination)

        system = MigrationSystem(world, {"migration": {"enabled": False}})

        self.assertFalse(system.advance())
        self.assertEqual(len(source.citizens), 2)
        self.assertNotIn("migration", world)

    def test_hunger_moves_a_bounded_cohort_with_a_notable_and_carried_identity(self):
        Translator.load("fr")
        GameLogger.get_new_logs()
        source = settlement(
            1,
            0,
            0,
            [person(1), person(2, notable=True), person(3), person(4), person(5)],
        )
        destination = settlement(2, 4, 100, [person(10, family="Vale")])
        source.known_cities.add(2)
        world = migration_world(source, destination)
        RandomService.initialize(1451)
        before = RandomService.get_state()
        system = MigrationSystem(world, migration_config())

        self.assertTrue(system.advance())
        logs = GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(len(logs))[0]
        self.assertTrue(any("migrent" in message for message in logs))
        self.assertTrue(all("MISSING_TEXT" not in message for message in logs))
        cohort = system.summary()["recent_cohorts"][0]

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(len(source.citizens), 2)
        self.assertEqual(len(destination.citizens), 4)
        self.assertEqual(cohort["count"], 3)
        self.assertEqual(cohort["origin_id"], 1)
        self.assertEqual(cohort["destination_id"], 2)
        self.assertGreater(cohort["causes"]["hunger"], 0)
        self.assertIn(2, cohort["notable_ids"])
        self.assertEqual(cohort["carried"]["cultures"], ["A"])
        self.assertEqual(cohort["carried"]["faiths"], ["river"])
        self.assertIn("trade", cohort["carried"]["skills"])
        self.assertEqual(cohort["carried"]["diseases"], ["fever"])
        self.assertEqual(cohort["carried"]["stories"], ["famine"])
        self.assertTrue(all(citizen.pos == destination.pos for citizen in destination.citizens[-3:]))
        self.assertEqual(metadata["event_type"], "migration_cohort")
        self.assertEqual(
            [actor["role"] for actor in metadata["actors"]],
            ["origin", "destination", "migrant"],
        )
        self.assertEqual(metadata["facts"]["cohort_id"], cohort["cohort_id"])

    def test_destination_ranking_uses_capacity_knowledge_and_family_networks(self):
        source = settlement(1, 0, 0, [person(1), person(2), person(3)])
        known_family = settlement(2, 5, 50, [person(10, family="Vale")])
        rich_unknown = settlement(3, 1, 100, [person(11, family="Other")])
        source.known_cities.add(2)
        world = migration_world(source, known_family, rich_unknown)
        system = MigrationSystem(
            world,
            migration_config(knowledge_bonus=5.0, family_bonus=5.0),
        )

        ranked = system.rank_destinations(source)

        self.assertEqual(ranked[0]["settlement_id"], 2)
        self.assertIn("knowledge", ranked[0]["factors"])
        self.assertIn("family", ranked[0]["factors"])

    def test_war_climate_and_persecution_are_visible_departure_causes(self):
        source = settlement(1, 0, 100, [person(1), person(2), person(3)])
        source.migration_persecution = 0.5
        destination = settlement(2, 4, 100, [person(4)])
        world = migration_world(source, destination)
        world["climate"]["drought_severity"] = 0.5
        world["diplomacy"]["1:2"] = {
            "first_id": 1,
            "second_id": 2,
            "status": "war",
        }
        system = MigrationSystem(world, migration_config(departure_threshold=0.5))

        causes = system.departure_causes(source)

        self.assertEqual(causes["war"], 3.0)
        self.assertEqual(causes["climate"], 1.0)
        self.assertEqual(causes["persecution"], 1.0)

    def test_diaspora_tracks_culture_integration_and_returnees(self):
        source = settlement(1, 0, 0, [person(1), person(2), person(3)])
        destination = settlement(2, 4, 100, [person(4, culture="B")], culture="B")
        world = migration_world(source, destination)
        system = MigrationSystem(world, migration_config(minimum_population=0))

        system.advance()
        summary = copy.deepcopy(system.summary())

        self.assertEqual(summary["diasporas"]["2"]["A"]["population"], 3)
        self.assertEqual(summary["diasporas"]["2"]["A"]["integration"], 0.15)
        self.assertEqual(summary["total_migrants"], 3)


ROOT = Path(__file__).resolve().parents[1]


class MigrationIntegrationTests(unittest.TestCase):
    def test_template_is_opt_in_and_validator_checks_migration_bounds(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["migration"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["migration"]["cohort_size"] = 0
        invalid["migration"]["integration_rate"] = 1.5
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:migration.cohort_size:positive", caught.exception.errors)
        self.assertIn("range:migration.integration_rate:0_1", caught.exception.errors)

    def test_engine_advances_persists_and_exposes_migration_effects(self):
        from core.simulation_engine import SimulationEngine

        legacy = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        legacy_engine = SimulationEngine.create(legacy, 1461, 12, 8)
        legacy_engine.step()
        self.assertNotIn("migration", legacy_engine.world)

        config = copy.deepcopy(legacy)
        config["migration"].update(
            {
                "enabled": True,
                "advance_interval": 1,
                "departure_threshold": 0.0,
                "cohort_size": 1,
            }
        )
        engine = SimulationEngine.create(config, 1463, 12, 8)
        engine.step()
        summary = engine.get_migration_summary()
        system = next(
            item for item in engine.get_systems_snapshot()
            if item["id"] == "migration"
        )
        settlement = next(
            entity for entity in engine.world["entities"]
            if hasattr(entity, "citizens") and not entity.is_expired
        )
        inspection = engine.inspect_entity(settlement.entity_id)

        self.assertGreater(summary["total_migrants"], 0)
        self.assertTrue(system["enabled"])
        self.assertEqual(system["state"], summary)
        self.assertIn("migration", inspection)

        before = copy.deepcopy(engine.world["migration"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.world["migration"], before)
        self.assertEqual(resumed.get_migration_summary(), summary)


if __name__ == "__main__":
    unittest.main()

