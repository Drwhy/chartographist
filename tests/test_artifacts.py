import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.artifacts import ArtifactRegistry
from core.entities import Entity, EntityManager
from core.translator import Translator


ROOT = Path(__file__).resolve().parents[1]


def artifacts_config(**overrides):
    settings = {
        "enabled": True,
        "max_artifacts": 8,
        "max_history_per_artifact": 4,
        "promotion_quality": 1.5,
        "max_promotions_per_order": 1,
        "loot_per_engagement": 1,
        "eligible_items": ["stone_tool"],
        "renown_per_event": 2.0,
        "max_renown": 100.0,
        "prestige_per_renown": 0.1,
    }
    settings.update(overrides)
    return {
        "artifacts": settings,
        "history": {"enabled": True, "max_facts": 16, "max_links": 8},
    }


def artifact_world():
    return {
        "width": 8,
        "height": 4,
        "cycle": 3,
        "entities": EntityManager(),
        "chronicles": [],
        "next_chronicle_id": 1,
    }


class ArtifactRegistryTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_disabled_registry_does_not_mutate_legacy_world(self):
        world = artifact_world()
        registry = ArtifactRegistry(world, {"artifacts": {"enabled": False}})
        self.assertIsNone(registry.create("stone_tool", quality=2.0))
        self.assertEqual(registry.summary(), {"enabled": False})
        self.assertNotIn("artifacts", world)

    def test_creation_is_idempotent_queryable_and_defensive(self):
        world = artifact_world()
        registry = ArtifactRegistry(world, artifacts_config())
        created = registry.create(
            "stone_tool", quality=1.8, creator_id=7,
            material_ids=["stone", "wood", "stone"], inscription="Aube",
            holder_kind="settlement", holder_id=11, location=[2, 1],
            source_key="production:11:4:stone_tool",
        )
        duplicate = registry.create(
            "stone_tool", quality=9.0,
            source_key="production:11:4:stone_tool",
        )
        self.assertEqual(created["artifact_id"], duplicate["artifact_id"])
        self.assertEqual(created["material_ids"], ["stone", "wood"])
        self.assertEqual(created["holder"], {"kind": "settlement", "id": 11})
        self.assertEqual(registry.query(holder_id=11, item_id="stone_tool"), [created])
        created["provenance"].append({"corrupted": True})
        self.assertNotIn("corrupted", registry.get(1)["provenance"][-1])

    def test_capacity_is_bounded_and_ids_are_monotonic(self):
        world = artifact_world()
        registry = ArtifactRegistry(world, artifacts_config(max_artifacts=1))
        first = registry.create("stone_tool", quality=2.0, source_key="one")
        dropped = registry.create("stone_tool", quality=2.0, source_key="two")
        self.assertEqual(first["artifact_id"], 1)
        self.assertIsNone(dropped)
        self.assertEqual(world["artifacts"]["next_artifact_id"], 2)
        self.assertEqual(registry.summary()["dropped_artifacts"], 1)

    def test_transfers_preserve_identity_and_bound_provenance(self):
        registry = ArtifactRegistry(
            artifact_world(), artifacts_config(max_history_per_artifact=3)
        )
        artifact = registry.create(
            "stone_tool", quality=2.0,
            holder_kind="settlement", holder_id=1,
        )
        registry.transfer(artifact["artifact_id"], "gift", "entity", 8, location=[3, 1])
        registry.transfer(artifact["artifact_id"], "trade", "settlement", 2)
        registry.transfer(artifact["artifact_id"], "inheritance", "entity", 9)
        registry.transfer(artifact["artifact_id"], "lost", None, None, location=[4, 2])
        current = registry.get(artifact["artifact_id"])
        self.assertEqual(current["status"], "lost")
        self.assertEqual(current["holder"], {"kind": None, "id": None})
        self.assertEqual(current["location"], [4, 2])
        self.assertEqual(
            [event["event_type"] for event in current["provenance"]],
            ["trade", "inheritance", "lost"],
        )
        registry.transfer(artifact["artifact_id"], "recovered", "settlement", 5)
        self.assertEqual(registry.get(artifact["artifact_id"])["status"], "active")

    def test_events_build_renown_and_holder_prestige_without_randomness(self):
        registry = ArtifactRegistry(artifact_world(), artifacts_config())
        artifact = registry.create(
            "stone_tool", quality=2.0,
            holder_kind="settlement", holder_id=3,
        )
        registry.record_event(
            artifact["artifact_id"], "battle_used", actor_ids=[3],
            importance=4, facts={"campaign_id": 2},
        )
        current = registry.get(artifact["artifact_id"])
        self.assertEqual(current["renown"], 10.0)
        self.assertEqual(registry.prestige_bonus(3), 1.0)
        self.assertEqual(registry.summary()["total_renown"], 10.0)

    def test_creation_and_transfer_emit_structured_chronicles(self):
        world = artifact_world()
        registry = ArtifactRegistry(world, artifacts_config())
        artifact = registry.create(
            "stone_tool", quality=2.0, creator_id=4,
            holder_kind="settlement", holder_id=1,
        )
        registry.transfer(
            artifact["artifact_id"], "gift", "entity", 9,
            caused_by=[world["chronicles"][0]["chronicle_id"]],
        )
        created, transferred = world["chronicles"]
        self.assertEqual(created["event_type"], "artifact_created")
        self.assertEqual(created["objects"][0]["object_id"], "artifact:1")
        self.assertEqual(transferred["event_type"], "artifact_transferred")
        self.assertEqual(transferred["facts"]["reason"], "gift")
        self.assertEqual(transferred["caused_by"], [created["chronicle_id"]])
        self.assertNotIn("MISSING_TEXT", transferred["message"])


class ArtifactIntegrationTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_completed_high_quality_item_is_promoted_conservatively(self):
        from core.production import advance_settlement_production

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(artifacts_config())
        config["materials"]["enabled"] = True
        config["materials"]["initial_stock"] = {"plank": 2}
        config["materials"]["targets"] = {"stone_tool": 1}
        recipe = next(
            item for item in config["materials"]["recipes"]
            if item["id"] == "repair_stone_tool"
        )
        recipe["cycles"] = 1
        recipe["quality_skill_scale"] = 1.0
        config["materials"].pop("food_chain")
        config["materials"]["recipes"] = [recipe]
        worker = SimpleNamespace(
            entity_id=71, is_dead=False,
            character={"skills": {"construction": 100}},
        )
        settlement = SimpleNamespace(
            entity_id=12, pos=[2, 1], citizens=[worker],
            config=config, food_stock=10.0,
        )
        world = artifact_world()
        world["entities"].add(settlement)
        result = advance_settlement_production(settlement, world)
        artifacts = ArtifactRegistry(world, config).query(holder_id=12)
        self.assertEqual(result["artifacts"], [artifacts[0]["artifact_id"]])
        self.assertEqual(artifacts[0]["creator_id"], 71)
        self.assertEqual(artifacts[0]["quality"], 2.0)
        self.assertEqual(artifacts[0]["material_ids"], ["plank"])
        self.assertEqual(settlement.stockpile["goods"].get("stone_tool", 0), 0)

    def test_battle_pillages_a_losers_artifact(self):
        from core.warfare import WarfareSystem
        from tests.test_warfare import settlement, war_world, warfare_config

        first, second = settlement(1, 0, population=30), settlement(2, 5, population=10)
        world = war_world(first, second)
        config = warfare_config(casualty_rate=0.5)
        config.update(artifacts_config())
        artifact = ArtifactRegistry(world, config).create(
            "stone_tool", quality=2.0,
            holder_kind="settlement", holder_id=2,
        )
        system = WarfareSystem(world, config)
        system.declare_war(1, 2, cause="revenge", objective="secure_frontier")
        system.advance()
        pillaged = ArtifactRegistry(world, config).get(artifact["artifact_id"])
        self.assertEqual(pillaged["holder"], {"kind": "settlement", "id": 1})
        self.assertEqual(pillaged["provenance"][-1]["event_type"], "loot")

    def test_renown_influences_claims_and_pilgrimage_attraction(self):
        from core.migration import MigrationSystem
        from core.territory import TerritorySystem

        config = artifacts_config(prestige_per_renown=0.1)
        config["territory"] = {
            "enabled": True,
            "base_power": 1.0,
            "population_scale": 0.0,
            "fortification_scale": 0.0,
        }
        config["migration"] = {
            "enabled": True,
            "settlement_capacity": 100,
            "food_attractiveness": 0.0,
            "capacity_attractiveness": 0.0,
            "distance_penalty": 0.0,
        }
        source = SimpleNamespace(
            entity_id=1, pos=[0, 0], citizens=[],
            food_stock=0.0, max_food=100.0, known_cities=[],
        )
        destination = SimpleNamespace(
            entity_id=2, pos=[1, 0], citizens=[],
            food_stock=0.0, max_food=100.0, known_cities=[],
        )
        world = artifact_world()
        world["entities"].add(source)
        world["entities"].add(destination)
        ArtifactRegistry(world, config).create(
            "stone_tool", quality=10.0,
            holder_kind="settlement", holder_id=2,
        )

        territory = TerritorySystem(world, config)
        self.assertEqual(territory._source_power(source), 1.0)
        self.assertEqual(territory._source_power(destination), 2.0)
        ranked = MigrationSystem(world, config).rank_destinations(source)
        self.assertEqual(ranked[0]["factors"]["artifacts"], 1.0)

    def test_engine_api_checkpoint_and_system_visibility(self):
        from core.simulation_engine import SimulationEngine

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(artifacts_config())
        engine = SimulationEngine.create(config, 1601, 8, 6)
        holder = Entity(1, 1, "A ", 10, 0)
        holder.entity_id = 711
        holder.config = config
        engine.world["entities"].add(holder)
        artifact = engine.create_artifact(
            "stone_tool", quality=2.0, creator_id=711,
            holder_kind="settlement", holder_id=711,
        )
        snapshot = next(
            item for item in engine.get_systems_snapshot() if item["id"] == "artifacts"
        )
        self.assertEqual(engine.get_artifact(artifact["artifact_id"]), artifact)
        self.assertEqual(engine.get_artifacts(holder_id=711), [artifact])
        inspected = engine.inspect_entity(711)
        self.assertEqual(inspected["artifacts"]["held"], [artifact])
        self.assertEqual(inspected["artifacts"]["created"], [artifact])
        self.assertEqual(snapshot["state"]["artifacts"], 1)
        self.assertGreater(snapshot["state"]["total_renown"], 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifacts.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.get_artifact(artifact["artifact_id"]), artifact)

    def test_template_and_validator_cover_artifact_configuration(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["artifacts"]["enabled"])
        self.assertIs(validate_config(config), config)
        all_config = json.loads(
            (ROOT / "template-all.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all_config["artifacts"]["enabled"])
        self.assertLessEqual(all_config["artifacts"]["promotion_quality"], 1.0)
        self.assertIn("plank", all_config["artifacts"]["eligible_items"])
        invalid = copy.deepcopy(config)
        invalid["artifacts"]["max_artifacts"] = 0
        invalid["artifacts"]["promotion_quality"] = True
        invalid["artifacts"]["eligible_items"] = ["stone_tool", 3]
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)
        self.assertIn("range:artifacts.max_artifacts:positive", caught.exception.errors)
        self.assertIn("type:artifacts.promotion_quality:int|float", caught.exception.errors)
        self.assertIn("type:artifacts.eligible_items:list[str]", caught.exception.errors)


if __name__ == "__main__":
    unittest.main()
