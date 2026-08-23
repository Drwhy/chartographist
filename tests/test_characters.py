import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.entities import EntityManager
from core.random_service import RandomService
from entities.species.human.base import Human


ROOT = Path(__file__).resolve().parents[1]


def character_config(**overrides):
    settings = {
        "enabled": True,
        "memory_limit": 4,
        "memory_decay_rate": 0.1,
        "notability_threshold": 20.0,
        "decision_interval": 1,
        "need_growth": {
            "security": 1.0,
            "belonging": 1.0,
            "status": 1.0,
            "faith": 0.5,
            "wealth": 1.0,
            "fatigue": 3.0,
        },
    }
    settings.update(overrides)
    return {"characters": settings}


def culture():
    return {"name": "Test", "naming": {"prefixes": ["Al"], "suffixes_person": ["a"]}}


def human(config=None, name="Ada"):
    RandomService.initialize(123)
    resolved = character_config() if config is None else config
    return Human(0, 0, culture(), resolved, 1, name=name)


def character_world(person=None):
    manager = EntityManager()
    if person is not None:
        manager.add(person)
    return {
        "width": 1,
        "height": 1,
        "cycle": 0,
        "elev": [[0.2]],
        "riv": [[0]],
        "road": [["  "]],
        "entities": manager,
        "chronicles": [],
        "next_chronicle_id": 1,
        "next_relation_id": 1,
        "diplomacy": {},
    }


class PopulationCohortTests(unittest.TestCase):
    def test_cohorts_aggregate_ordinary_citizens_without_removing_them(self):
        from core.characters import PopulationCohort, cohort_snapshots

        config = character_config()
        citizens = [human(config, "Ada"), human(config, "Bea"), human(config, "Cia")]
        citizens[0].age = 8
        citizens[1].age = 32
        citizens[2].age = 70
        settlement = SimpleNamespace(entity_id=90, citizens=citizens)
        original = list(settlement.citizens)

        snapshots = cohort_snapshots(settlement)

        self.assertEqual(settlement.citizens, original)
        self.assertEqual(sum(item["count"] for item in snapshots), 3)
        self.assertTrue(all(PopulationCohort.from_dict(item).count > 0 for item in snapshots))
        json.dumps(snapshots)

    def test_cohort_rejects_invalid_counts(self):
        from core.characters import PopulationCohort

        with self.assertRaises(ValueError):
            PopulationCohort(1, 2, "Test", "adult", "Human", -1)


class NeedsAndSkillsTests(unittest.TestCase):
    def test_needs_are_bounded_and_advance_once_per_cycle(self):
        from core.characters import CharacterService
        from core.needs import satisfy_need

        person = human()
        world = character_world(person)
        service = CharacterService(person, character_config())
        world["cycle"] = 1

        self.assertTrue(service.advance(world))
        first = copy.deepcopy(person.character["needs"])
        self.assertFalse(service.advance(world))
        self.assertEqual(person.character["needs"], first)
        satisfy_need(person, "fatigue", 999)
        self.assertEqual(person.character["needs"]["fatigue"], 0.0)

        world["cycle"] = 2
        service.advance(world)
        self.assertTrue(all(0 <= value <= 100 for value in person.character["needs"].values()))

    def test_skill_practice_has_diminishing_returns_and_is_bounded(self):
        from core.skills import practice_skill

        person = human()
        first = practice_skill(person, "agriculture", 20)
        second = practice_skill(person, "agriculture", 20)
        for _ in range(100):
            practice_skill(person, "agriculture", 20)

        self.assertGreater(first, second)
        self.assertLessEqual(person.character["skills"]["agriculture"], 100)
        with self.assertRaises(KeyError):
            practice_skill(person, "alchemy", 1)

    def test_old_character_is_migrated_deterministically_without_random_draw(self):
        from core.characters import CharacterService

        person = human({})
        self.assertFalse(hasattr(person, "character"))
        before = RandomService.get_state()

        first = CharacterService(person, character_config()).snapshot()
        second = CharacterService(person, character_config()).snapshot()

        self.assertEqual(before, RandomService.get_state())
        self.assertEqual(first, second)
        self.assertEqual(first["version"], 1)


class PersonalMemoryTests(unittest.TestCase):
    def test_memory_is_bounded_by_importance_and_reinforces_matching_fact(self):
        from core.memory import MemoryBook

        person = human()
        book = MemoryBook(person, character_config(memory_limit=2))
        book.remember("trade", cycle=1, target_id=2, intensity=10, reliability=0.5)
        first = book.remember("raid", cycle=2, target_id=3, intensity=70, reliability=1.0)
        reinforced = book.remember("raid", cycle=3, target_id=3, intensity=20, reliability=1.0)
        book.remember("rescue", cycle=4, target_id=4, intensity=90, reliability=1.0)

        memories = book.snapshot()
        self.assertEqual(first["memory_id"], reinforced["memory_id"])
        self.assertEqual(len(memories), 2)
        self.assertEqual({item["kind"] for item in memories}, {"raid", "rescue"})
        json.dumps(memories)

    def test_successful_trade_creates_personal_memory_and_practice(self):
        from core.skills import skill_value
        from entities.species.human.trader import Trader
        from tests.test_economy import economy_config, settlement

        config = character_config()
        config.update(economy_config())
        origin = settlement("Origin", 11, 120, 200, config, treasury=50)
        target = settlement("Target", 22, 10, 100, config, treasury=100)
        trader = Trader(0, 0, culture(), config, origin)
        trader.target_city = target
        trader._establish_connection = lambda world: None
        trader._spread_religion = lambda: None
        before_skill = skill_value(trader, "commerce")
        world = {"cycle": 5}

        trader._do_trade(world)

        self.assertEqual(trader.character["memories"][0]["kind"], "trade")
        self.assertEqual(trader.character["memories"][0]["target_id"], 22)
        self.assertGreater(skill_value(trader, "commerce"), before_skill)


    def test_raid_creates_experienced_memory_for_survivors(self):
        from entities.species.human.soldier import Soldier

        config = character_config()
        citizens = [human(config, name=f"Citizen {index}") for index in range(4)]
        home = SimpleNamespace(
            entity_id=700,
            x=0,
            y=0,
            name="Home",
            food_stock=0,
            is_expired=False,
        )
        target = SimpleNamespace(
            entity_id=701,
            pos=(1, 1),
            name="Target",
            citizens=citizens,
            food_stock=100,
            is_expired=False,
        )
        soldier = Soldier(0, 0, culture(), config, home, target)
        soldier.strength = 0.2
        world = character_world()
        world["cycle"] = 7

        soldier._raid_city(world)

        survivors = [citizen for citizen in citizens if not citizen.is_dead]
        self.assertEqual(len(survivors), 3)
        for survivor in survivors:
            memory = survivor.character["memories"][0]
            self.assertEqual(memory["kind"], "raid")
            self.assertEqual(memory["target_id"], soldier.entity_id)
            self.assertEqual(memory["position"], [1, 1])
            self.assertEqual(memory["source"], "experienced")
            self.assertGreater(memory["fear"], 0)
            self.assertGreater(memory["grievance"], 0)
    def test_memory_decay_and_opinion_are_bounded(self):
        from core.memory import MemoryBook

        person = human()
        book = MemoryBook(person, character_config(memory_decay_rate=0.5))
        book.remember(
            "raid", cycle=1, target_id=8, intensity=80, reliability=1.0,
            sentiment=-1.0, fear=0.8, grievance=0.9,
        )

        before = book.opinion(8)
        book.decay()
        after = book.opinion(8)

        self.assertLess(abs(after["trust"]), abs(before["trust"]))
        self.assertGreater(before["fear"], 0)
        self.assertGreater(before["grievance"], 0)
        self.assertTrue(all(-100 <= value <= 100 for value in after.values()))


class UtilityDecisionTests(unittest.TestCase):
    def test_same_profession_can_choose_different_actions_and_explain_top_three(self):
        from core.characters import CharacterService

        worker = human(name="Worker")
        tired = human(name="Tired")
        worker.character["needs"].update({"status": 80.0, "wealth": 80.0, "fatigue": 0.0})
        tired.character["needs"].update({"status": 5.0, "wealth": 5.0, "fatigue": 100.0})
        world = character_world()

        work_choice = CharacterService(worker, character_config()).decide(world)
        rest_choice = CharacterService(tired, character_config()).decide(world)

        self.assertEqual(work_choice["selected"], "work")
        self.assertEqual(rest_choice["selected"], "rest")
        self.assertEqual(len(work_choice["options"]), 3)
        self.assertIn("drivers", work_choice["options"][0])
        self.assertGreaterEqual(
            work_choice["options"][0]["score"],
            work_choice["options"][1]["score"],
        )

    def test_decision_cadence_is_staggered_by_stable_entity_id(self):
        from core.characters import CharacterService

        config = character_config(decision_interval=3)
        person = human(config)
        person.character["needs"]["fatigue"] = 100.0
        world = character_world(person)
        due_cycle = (-person.entity_id) % 3
        if due_cycle == 0:
            due_cycle = 3
        off_cycle = 1 if due_cycle != 1 else 2

        world["cycle"] = off_cycle
        self.assertTrue(CharacterService(person, config).prepare_action(world))
        self.assertEqual(person.character["last_decision"]["selected"], None)

        world["cycle"] = due_cycle
        self.assertFalse(CharacterService(person, config).prepare_action(world))
        self.assertEqual(person.character["last_decision"]["selected"], "rest")


    def test_past_raid_changes_future_decision_without_randomness(self):
        from core.characters import CharacterService
        from core.memory import MemoryBook

        person = human()
        person.character["needs"].update({"status": 20.0, "wealth": 20.0, "security": 0.0})
        world = character_world(person)
        service = CharacterService(person, character_config())
        before_random = RandomService.get_state()
        before = service.decide(world)

        MemoryBook(person, character_config()).remember(
            "raid", cycle=1, target_id=99, intensity=100, reliability=1.0,
            sentiment=-1.0, fear=1.0, grievance=1.0,
        )
        after = service.decide(world)

        self.assertEqual(before_random, RandomService.get_state())
        self.assertNotEqual(before["selected"], "seek_safety")
        self.assertEqual(after["selected"], "seek_safety")


class NotabilityAndIntegrationTests(unittest.TestCase):
    def test_promotion_preserves_identity_and_archival_keeps_history(self):
        from core.characters import NotabilityService
        from core.memory import MemoryBook

        person = human()
        world = character_world(person)
        identity = person.entity_id
        service = NotabilityService(world, character_config())
        MemoryBook(person, character_config()).remember(
            "rescue", cycle=4, target_id=88, intensity=80, reliability=1.0
        )

        promoted = service.promote(person, "role_accession", importance=30)
        self.assertEqual(person.entity_id, identity)
        self.assertTrue(promoted["is_notable"])
        self.assertIn(str(identity), world["notables"])

        person.is_dead = True
        service.archive(person, cycle=12)
        self.assertNotIn(str(identity), world["notables"])
        self.assertEqual(world["notable_archive"][str(identity)]["entity_id"], identity)
        self.assertEqual(
            world["notable_archive"][str(identity)]["reasons"][0]["kind"],
            "role_accession",
        )
        archived_character = world["notable_archive"][str(identity)]["character"]
        self.assertEqual(archived_character["memories"][0]["kind"], "rescue")
        person.character["memories"].clear()
        self.assertEqual(archived_character["memories"][0]["kind"], "rescue")

    def test_active_monthly_integration_can_rest_and_practice_work(self):
        from core.characters import CharacterService
        from core.skills import skill_value

        person = human()
        world = character_world(person)
        person.character["needs"]["fatigue"] = 100.0
        world["cycle"] = 1
        before = person.character["needs"]["fatigue"]

        acted = CharacterService(person, character_config()).prepare_action(world)
        self.assertFalse(acted)
        self.assertLess(person.character["needs"]["fatigue"], before)

        person.character["needs"].update({"fatigue": 0.0, "status": 90.0, "wealth": 90.0})
        before_skill = skill_value(person, "agriculture")
        CharacterService(person, character_config()).record_practice("agriculture", 5)
        self.assertGreater(skill_value(person, "agriculture"), before_skill)

    def test_active_tired_mobile_human_rests_before_legacy_ai(self):
        person = human()
        world = character_world(person)
        calls = []
        person.think = lambda current_world: calls.append("think")
        person.perform_action = lambda current_world: calls.append("act")
        person.character["needs"]["fatigue"] = 100.0
        world["cycle"] = 1

        person.update(world, {"year": 0})

        self.assertEqual(calls, [])
        self.assertLess(person.character["needs"]["fatigue"], 100.0)

        legacy = human({}, name="Legacy")
        legacy_calls = []
        legacy.think = lambda current_world: legacy_calls.append("think")
        legacy.perform_action = lambda current_world: legacy_calls.append("act")
        legacy.update(character_world(legacy), {"year": 0})
        self.assertEqual(legacy_calls, ["think", "act"])


    def test_tired_settlement_citizen_skips_work_in_active_mode(self):
        from entities.constructs.city import City

        config = character_config()
        person = human(config)
        calls = []
        person.work = lambda city, world: calls.append("work")
        person.character["needs"]["fatigue"] = 100.0
        city = SimpleNamespace(
            citizens=[person],
            food_stock=10,
            max_food=20,
            config=config,
        )
        world = character_world()
        world["cycle"] = 1

        City._update_citizens(city, world)

        self.assertEqual(calls, [])
        self.assertEqual(world["metrics"]["flows"]["characters"]["rests"], 1)

    def test_starved_notable_is_archived_before_settlement_cleanup(self):
        from core.characters import NotabilityService
        from entities.constructs.city import City

        config = character_config()
        person = human(config)
        person.hunger = 95
        person.work = lambda city, world: None
        city = SimpleNamespace(
            entity_id=700,
            citizens=[person],
            food_stock=0,
            max_food=20,
            config=config,
            is_expired=False,
        )
        world = character_world()
        world["entities"].add(city)
        world["cycle"] = 1
        NotabilityService(world, config).promote(person, "rescue", importance=40)

        City._update_citizens(city, world)

        self.assertTrue(person.is_dead)
        self.assertIn(str(person.entity_id), world["notable_archive"])


    def test_character_inspection_finds_nested_citizen_and_is_defensive(self):
        from core.characters import NotabilityService
        from core.inspection import inspect_entity

        person = human()
        settlement = SimpleNamespace(
            entity_id=500,
            pos=(0, 0),
            citizens=[person],
            culture={"name": "Test"},
            food_stock=10,
            max_food=20,
            is_expired=False,
        )
        world = character_world()
        world["entities"].add(settlement)
        NotabilityService(world, character_config()).promote(
            person, "role_accession", importance=30
        )

        result = inspect_entity(world, person.entity_id)
        result["entity"]["character"]["needs"]["hunger"] = -1

        self.assertEqual(result["owner_entity_id"], 500)
        self.assertTrue(result["entity"]["character"]["notability"]["is_notable"])
        self.assertGreaterEqual(person.character["needs"]["hunger"], 0)

    def test_professional_promotion_transfers_personal_state_defensively(self):
        from core.characters import transfer_character_state
        from entities.species.human.farmer import Farmer

        config = character_config()
        source = human(config, "Source")
        source.character["skills"]["agriculture"] = 42.0
        source.character["memories"].append({
            "memory_id": 1,
            "kind": "harvest",
            "intensity": 50.0,
            "reliability": 1.0,
        })
        promoted = Farmer(0, 0, culture(), config, name=source.name, age=source.age)
        promoted.preserve_identity_from(source)

        transfer_character_state(source, promoted, config)
        promoted.character["skills"]["agriculture"] = 50.0

        self.assertEqual(promoted.entity_id, source.entity_id)
        self.assertEqual(source.character["skills"]["agriculture"], 42.0)
        self.assertEqual(promoted.character["memories"][0]["kind"], "harvest")

    def test_child_inherits_bounded_traits_and_partial_parental_skills(self):
        from core.characters import inherit_character_state

        config = character_config()
        first = human(config, "First")
        second = human(config, "Second")
        child = human(config, "Child")
        first.character["traits"]["ambition"] = 1.0
        second.character["traits"]["ambition"] = 0.0
        first.character["skills"]["agriculture"] = 60.0
        second.character["skills"]["agriculture"] = 40.0

        inherit_character_state(child, first, second, config)

        self.assertEqual(child.character["traits"]["ambition"], 0.5)
        self.assertEqual(child.character["skills"]["agriculture"], 5.0)
        self.assertEqual(child.character["household_id"], first.family_name)


    def test_notability_metrics_count_promotions_archives_and_active_state(self):
        from core.characters import NotabilityService
        from core.simulation_metrics import SimulationMetrics

        person = human()
        world = character_world(person)
        service = NotabilityService(world, character_config())
        service.promote(person, "rescue", importance=40)

        promoted = SimulationMetrics(world).snapshot()
        self.assertEqual(promoted["state"]["notables"], 1)
        self.assertEqual(promoted["flows"]["characters"]["promotions"], 1)

        person.is_dead = True
        service.archive(person, cycle=9)
        self.assertEqual(service.archive(person, cycle=10), {})
        archived = SimulationMetrics(world).snapshot()
        self.assertEqual(archived["state"]["notables"], 0)
        self.assertEqual(archived["state"]["archived_notables"], 1)
        self.assertEqual(archived["flows"]["characters"]["archives"], 1)


    def test_checkpoint_preserves_character_memory_and_notable_registry(self):
        from core.characters import NotabilityService
        from core.memory import MemoryBook
        from core.simulation_engine import SimulationEngine

        config = character_config()
        person = human(config)
        world = character_world(person)
        stats = {"year": 0, "logs": []}
        engine = SimulationEngine(world, stats, config)
        MemoryBook(person, config).remember(
            "rescue", cycle=1, target_id=7, intensity=80, reliability=1.0,
            sentiment=1.0,
        )
        NotabilityService(world, config).promote(person, "rescue", importance=40)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "characters.save"
            engine.save(path)
            restored = SimulationEngine.load(path)

        restored_person = next(iter(restored.world["entities"]))
        self.assertEqual(restored_person.character, person.character)
        self.assertEqual(restored.world["notables"], world["notables"])


class CharacterConfigurationTests(unittest.TestCase):
    def test_template_keeps_calibrated_character_simulation_opt_in(self):
        from core.config_validator import validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        validate_config(config)

        self.assertFalse(config["characters"]["enabled"])
        self.assertEqual(config["characters"]["memory_limit"], 24)

    def test_validator_rejects_invalid_character_values(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config["characters"] = {
            "enabled": "yes",
            "memory_limit": 0,
            "memory_decay_rate": 2,
            "notability_threshold": -1,
            "decision_interval": 0,
        }

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(config)

        self.assertIn("type:characters.enabled:bool", caught.exception.errors)
        self.assertIn("range:characters.memory_limit:positive", caught.exception.errors)
        self.assertIn("range:characters.memory_decay_rate:0_1", caught.exception.errors)
        self.assertIn("range:characters.notability_threshold:nonnegative", caught.exception.errors)
        self.assertIn("range:characters.decision_interval:positive", caught.exception.errors)


if __name__ == "__main__":
    unittest.main()
