import json
import pickle
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def knowledge_config(**overrides):
    values = {
        "enabled": True,
        "perception_radius": 5.0,
        "observation_interval": 1,
        "max_facts": 32,
        "reliability_decay": 0.01,
        "transmission_decay": 0.1,
        "distance_decay": 0.01,
        "minimum_reliability": 0.05,
    }
    values.update(overrides)
    return {"knowledge": values}


def settlement(entity_id, pos, *, population=10, config=None):
    return SimpleNamespace(
        entity_id=entity_id,
        name=f"City {entity_id}",
        pos=pos,
        population=population,
        food_stock=50,
        max_food=100,
        is_expired=False,
        known_cities=set(),
        config=config or knowledge_config(),
    )


class KnowledgeServiceTests(unittest.TestCase):
    def test_isolated_settlement_only_observes_sites_inside_its_radius(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config(perception_radius=4)
        observer = settlement(1, (0, 0), config=config)
        nearby = settlement(2, (3, 0), config=config)
        distant = settlement(3, (20, 0), config=config)
        world = {"cycle": 7, "entities": [observer, nearby, distant]}

        service = KnowledgeService(observer, config)
        service.observe(world)

        self.assertEqual(
            [entity.entity_id for entity in service.known_settlements(world)],
            [2],
        )
        self.assertNotIn(distant.entity_id, service.known_subject_ids("settlement"))

    def test_legacy_known_cities_are_migrated_to_structured_facts(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        observer = settlement(1, (0, 0), config=config)
        observer.known_cities = {8, 4}

        facts = KnowledgeService(observer, config).snapshot()["facts"]

        self.assertEqual([fact["subject_id"] for fact in facts], [4, 8])
        self.assertTrue(all(fact["source_type"] == "legacy" for fact in facts))
        self.assertTrue(all(fact["reliability"] == 0.5 for fact in facts))

    def test_transmission_loses_reliability_and_preserves_source_chain(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config(transmission_decay=0.1, distance_decay=0.02)
        source = settlement(1, (0, 0), config=config)
        target = settlement(2, (5, 0), config=config)
        source_book = KnowledgeService(source, config)
        source_book.learn(
            kind="threat",
            subject_id=99,
            claim="danger",
            value="high",
            cycle=10,
            source_id=99,
            source_type="observed",
            reliability=1.0,
            position=(9, 9),
        )

        transferred = source_book.transmit_to(target, cycle=12, distance=5)
        received = KnowledgeService(target, config).query(kind="threat")[0]

        self.assertEqual(transferred, 1)
        self.assertEqual(received["origin_source_id"], 99)
        self.assertEqual(received["source_id"], source.entity_id)
        self.assertEqual(received["source_type"], "reported")
        self.assertEqual(received["transmissions"], 1)
        self.assertAlmostEqual(received["reliability"], 0.8)

    def test_communities_can_keep_conflicting_reports_about_one_subject(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        first = settlement(1, (0, 0), config=config)
        second = settlement(2, (0, 0), config=config)
        KnowledgeService(first, config).learn(
            kind="reputation",
            subject_id=9,
            claim="intent",
            value="friendly",
            cycle=2,
            source_id=4,
            source_type="reported",
            reliability=0.7,
        )
        KnowledgeService(second, config).learn(
            kind="reputation",
            subject_id=9,
            claim="intent",
            value="hostile",
            cycle=2,
            source_id=5,
            source_type="reported",
            reliability=0.7,
        )

        self.assertEqual(
            KnowledgeService(first, config).best_fact(
                "reputation", 9, claim="intent"
            )["value"],
            "friendly",
        )
        self.assertEqual(
            KnowledgeService(second, config).best_fact(
                "reputation", 9, claim="intent"
            )["value"],
            "hostile",
        )

    def test_decay_prunes_obsolete_facts_and_bounds_storage(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config(
            max_facts=2,
            reliability_decay=0.5,
            minimum_reliability=0.2,
        )
        owner = settlement(1, (0, 0), config=config)
        service = KnowledgeService(owner, config)
        for subject_id, reliability in ((2, 1.0), (3, 0.8), (4, 0.1)):
            service.learn(
                kind="site",
                subject_id=subject_id,
                claim="exists",
                value=True,
                cycle=0,
                source_id=1,
                source_type="observed",
                reliability=reliability,
            )

        service.advance({"cycle": 2, "entities": [owner]})

        facts = service.snapshot()["facts"]
        self.assertLessEqual(len(facts), 2)
        self.assertTrue(all(fact["reliability"] >= 0.2 for fact in facts))

    def test_snapshot_survives_pickle_and_is_defensive(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        owner = settlement(1, (0, 0), config=config)
        service = KnowledgeService(owner, config)
        service.learn(
            kind="site",
            subject_id=2,
            claim="exists",
            value=True,
            cycle=1,
            source_id=1,
            source_type="observed",
            reliability=1,
        )

        restored = pickle.loads(pickle.dumps(owner))
        snapshot = KnowledgeService(restored, config).snapshot()
        snapshot["facts"][0]["value"] = False

        self.assertTrue(KnowledgeService(restored, config).snapshot()["facts"][0]["value"])

    def test_inspection_exposes_world_truth_separately_from_owner_knowledge(self):
        from core.inspection import inspect_entity
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        owner = settlement(1, (0, 0), config=config)
        target = settlement(2, (2, 0), population=99, config=config)
        world = {"cycle": 3, "entities": [owner, target]}
        KnowledgeService(owner, config).observe(world)

        result = inspect_entity(world, owner.entity_id)

        self.assertEqual(result["entity"]["population"], 10)
        self.assertEqual(result["knowledge"]["facts"][0]["subject_id"], 2)
        self.assertEqual(result["knowledge"]["facts"][0]["value"]["population"], 99)

    def test_template_and_validator_define_safe_opt_in_settings(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertIs(validate_config(config), config)
        self.assertFalse(config["knowledge"]["enabled"])

        config["knowledge"]["perception_radius"] = -1
        config["knowledge"]["transmission_decay"] = 2
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(config)

        self.assertIn(
            "range:knowledge.perception_radius:non_negative",
            caught.exception.errors,
        )
        self.assertIn(
            "range:knowledge.transmission_decay:0_1",
            caught.exception.errors,
        )


    def test_checkpoint_preserves_facts_and_migrates_legacy_known_cities(self):
        from core.knowledge import KnowledgeService
        from core.simulation_engine import SimulationEngine

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config["knowledge"]["enabled"] = True
        engine = SimulationEngine.create(config, seed=1212, width=24, height=12)
        settlements = [
            entity for entity in engine.world["entities"]
            if hasattr(entity, "population") and not entity.is_expired
        ]
        owner, target = settlements[:2]
        KnowledgeService(owner, config).learn(
            kind="reputation",
            subject_id=target.entity_id,
            claim="intent",
            value="friendly",
            cycle=2,
            source_id=target.entity_id,
            source_type="reported",
            reliability=0.75,
        )
        owner.known_cities.add(target.entity_id)
        owner.knowledge.pop("legacy_known_cities_migrated", None)
        owner_id = owner.entity_id
        target_id = target.entity_id
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.chart"
            engine.save(path)
            restored = SimulationEngine.load(path)

        facts = restored.inspect_entity(owner_id)["knowledge"]["facts"]
        self.assertTrue(any(
            fact["kind"] == "reputation" and fact["value"] == "friendly"
            for fact in facts
        ))
        self.assertTrue(any(
            fact["kind"] == "settlement" and fact["subject_id"] == target_id
            for fact in facts
        ))

    def test_legacy_city_migration_runs_only_once(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        owner = settlement(1, (0, 0), config=config)
        owner.known_cities = {2}
        service = KnowledgeService(owner, config)
        self.assertEqual(len(service.query(kind="settlement")), 1)

        owner.knowledge["facts"].clear()
        reloaded = KnowledgeService(owner, config)

        self.assertEqual(reloaded.query(kind="settlement"), [])

    def test_newer_claim_from_same_origin_replaces_its_old_version(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        owner = settlement(1, (0, 0), config=config)
        service = KnowledgeService(owner, config)
        for cycle, value in ((1, "friendly"), (2, "hostile")):
            service.learn(
                kind="reputation",
                subject_id=9,
                claim="intent",
                value=value,
                cycle=cycle,
                source_id=4,
                source_type="reported",
                reliability=0.8,
            )

        facts = service.query(kind="reputation", subject_id=9, claim="intent")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["value"], "hostile")

    def test_transfer_mode_and_personality_modify_received_belief(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config(transmission_decay=0.1, distance_decay=0)
        source = settlement(1, (0, 0), config=config)
        trusting = settlement(2, (0, 0), config=config)
        cautious = settlement(3, (0, 0), config=config)
        trusting.character = {"traits": {"empathy": 1.0, "prudence": 0.0}}
        cautious.character = {"traits": {"empathy": 0.0, "prudence": 1.0}}
        book = KnowledgeService(source, config)
        book.learn(
            kind="map_tile",
            subject_id=4,
            claim="survey",
            value={"terrain": "forest"},
            cycle=1,
            source_id=source.entity_id,
            source_type="observed",
            reliability=1.0,
            position=(4, 0),
        )

        book.transmit_to(trusting, cycle=2, distance=0, transfer_type="sold")
        book.transmit_to(cautious, cycle=2, distance=0, transfer_type="stolen")
        trusted = KnowledgeService(trusting, config).query(kind="map_tile")[0]
        doubted = KnowledgeService(cautious, config).query(kind="map_tile")[0]

        self.assertEqual(trusted["source_type"], "sold")
        self.assertEqual(doubted["source_type"], "stolen")
        self.assertGreater(trusted["belief_modifier"], 1.0)
        self.assertLess(doubted["belief_modifier"], 1.0)
        self.assertGreater(trusted["reliability"], doubted["reliability"])

if __name__ == "__main__":
    unittest.main()
