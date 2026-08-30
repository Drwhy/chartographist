import os
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.logger import GameLogger
from core.translator import Translator
from entities.constructs.city import City


ROOT = Path(__file__).resolve().parents[1]


def settlement(name, entity_id, culture="Culture"):
    return SimpleNamespace(
        name=name,
        entity_id=entity_id,
        culture={"name": culture},
        enemies=[],
        is_expired=False,
        population=250,
        x=entity_id,
        y=0,
        pos=(entity_id, 0),
    )


class LegacyWarCharacterizationTests(unittest.TestCase):
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

    def test_legacy_war_declaration_remains_mutual_without_diplomacy(self):
        attacker = settlement("A", 11)
        defender = settlement("B", 22, culture="Other")

        City._declare_war(attacker, defender)

        self.assertEqual(attacker.enemies, [defender])
        self.assertEqual(defender.enemies, [attacker])
        self.assertEqual(attacker.war_cooldown, 200)
        self.assertNotIn("MISSING_TEXT", GameLogger.get_new_logs()[0])


class DiplomacyRegistryTests(unittest.TestCase):
    def test_relation_key_is_symmetric_and_uses_stable_ids(self):
        from core.diplomacy import canonical_relation_key

        self.assertEqual(canonical_relation_key(9, 2), "2:9")
        self.assertEqual(canonical_relation_key(2, 9), "2:9")
        with self.assertRaises(ValueError):
            canonical_relation_key(4, 4)

    def test_registry_initializes_old_world_lazily(self):
        from core.diplomacy import DiplomacyRegistry

        world = {"cycle": 7}
        registry = DiplomacyRegistry(world)
        relation = registry.get_or_create(9, 2)

        self.assertEqual(world["next_relation_id"], 2)
        self.assertEqual(list(world["diplomacy"]), ["2:9"])
        self.assertEqual(
            relation,
            {
                "relation_id": 1,
                "first_id": 2,
                "second_id": 9,
                "status": "neutral",
                "trust": 0.0,
                "tension": 0.0,
                "interdependence": 0.0,
                "last_change_cycle": 7,
                "truce_until": None,
                "war_started_cycle": None,
                "reasons": [],
            },
        )

    def test_queries_return_defensive_copies_and_filter_by_entity(self):
        from core.diplomacy import DiplomacyRegistry

        world = {"cycle": 3}
        registry = DiplomacyRegistry(world)
        first = registry.get_or_create(1, 2)
        registry.get_or_create(2, 3)
        registry.get_or_create(4, 5)

        first["reasons"].append({"kind": "external mutation"})
        queried = registry.query(entity_id=2)
        queried[0]["trust"] = 99

        self.assertEqual(len(queried), 2)
        self.assertEqual(registry.get(1, 2)["reasons"], [])
        self.assertEqual(registry.get(1, 2)["trust"], 0.0)
        self.assertIsNone(registry.get(1, 99))

    def test_metric_changes_are_clamped_and_structurally_traced(self):
        from core.diplomacy import DiplomacyRegistry

        world = {"cycle": 12}
        registry = DiplomacyRegistry(world)
        updated = registry.adjust(
            1,
            2,
            trust=140,
            tension=-15,
            interdependence=25,
            reason="trade",
        )

        self.assertEqual(updated["trust"], 100.0)
        self.assertEqual(updated["tension"], 0.0)
        self.assertEqual(updated["interdependence"], 25.0)
        self.assertEqual(updated["last_change_cycle"], 12)
        self.assertEqual(updated["reasons"], [{"cycle": 12, "kind": "trade"}])


class DiplomacyTransitionTests(unittest.TestCase):
    def test_alliance_blocks_direct_war(self):
        from core.diplomacy import DiplomacyRegistry, DiplomacyTransitionError

        world = {"cycle": 20}
        registry = DiplomacyRegistry(world)
        registry.transition(1, 2, "alliance", reason="treaty")

        with self.assertRaises(DiplomacyTransitionError):
            registry.transition(1, 2, "war", reason="aggression")

        self.assertEqual(registry.get(1, 2)["status"], "alliance")

    def test_war_ends_in_timed_truce_that_blocks_hostilities(self):
        from core.diplomacy import DiplomacyRegistry, DiplomacyTransitionError

        world = {"cycle": 30}
        registry = DiplomacyRegistry(world)
        at_war = registry.transition(1, 2, "war", reason="declaration")
        truce = registry.transition(
            1,
            2,
            "truce",
            reason="peace",
            truce_duration=12,
        )

        self.assertEqual(at_war["war_started_cycle"], 30)
        self.assertEqual(truce["status"], "truce")
        self.assertEqual(truce["truce_until"], 42)
        self.assertIsNone(truce["war_started_cycle"])
        with self.assertRaises(DiplomacyTransitionError):
            registry.transition(1, 2, "war", reason="too_soon")

    def test_expired_truce_returns_to_neutral_deterministically(self):
        from core.diplomacy import DiplomacyRegistry

        world = {"cycle": 5}
        registry = DiplomacyRegistry(world)
        registry.transition(1, 2, "war", reason="declaration")
        registry.transition(1, 2, "truce", reason="peace", truce_duration=4)

        world["cycle"] = 8
        self.assertEqual(registry.expire_truces(), [])
        self.assertEqual(registry.get(1, 2)["status"], "truce")

        world["cycle"] = 9
        expired = registry.expire_truces()
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0]["status"], "neutral")
        self.assertIsNone(expired[0]["truce_until"])

    def test_transition_reasons_keep_previous_metric_history(self):
        from core.diplomacy import DiplomacyRegistry

        world = {"cycle": 2}
        registry = DiplomacyRegistry(world)
        registry.adjust(1, 2, trust=5, reason="trade")
        world["cycle"] = 3
        relation = registry.transition(1, 2, "trade_pact", reason="pact")

        self.assertEqual(
            relation["reasons"],
            [
                {"cycle": 2, "kind": "trade"},
                {
                    "cycle": 3,
                    "kind": "pact",
                    "from_status": "neutral",
                    "to_status": "trade_pact",
                },
            ],
        )


def diplomatic_market(name, entity_id, food, treasury, config):
    from core.economy import ensure_economy

    value = SimpleNamespace(
        name=name,
        entity_id=entity_id,
        food_stock=food,
        max_food=200,
        config=config,
        pos=(entity_id, 0),
        is_expired=False,
        known_cities=set(),
        religion=None,
    )
    ensure_economy(value)["treasury"] = float(treasury)
    return value


def trader_between(origin, target):
    from entities.species.human.trader import Trader

    trader = Trader.__new__(Trader)
    trader.entity_id = 999
    trader.home_city = origin
    trader.base_city = origin
    trader.target_city = target
    trader.visited_cities = set()
    trader.trades_since_home = 0
    trader._returning_home = False
    trader.faith_bonus = lambda key: 0
    trader.species_trait = lambda key: 0
    trader._establish_connection = lambda world: None
    trader._spread_religion = lambda: None
    return trader


class DiplomacyTradeIntegrationTests(unittest.TestCase):
    def setUp(self):
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)
        GameLogger.get_new_logs()

    def make_config(self):
        return {
            "economy": {
                "enabled": True,
                "initial_treasury": 100,
                "base_food_price": 1,
                "min_food_price": 0.5,
                "max_food_price": 3,
                "food_reserve": 20,
                "trade_capacity": 10,
            },
            "diplomacy": {
                "enabled": True,
                "trade_trust_gain": 10,
                "trade_interdependence_gain": 5,
                "trade_pact_threshold": 10,
                "alliance_threshold": 50,
                "trade_pact_capacity_multiplier": 2,
            },
        }

    def test_successful_trade_builds_relation_and_trade_pact_bonus(self):
        from core.diplomacy import DiplomacyRegistry

        config = self.make_config()
        origin = diplomatic_market("A", 1, 100, 0, config)
        target = diplomatic_market("B", 2, 0, 100, config)
        trader = trader_between(origin, target)
        world = {"cycle": 4}

        trader._do_trade(world)

        relation = DiplomacyRegistry(world).get(1, 2)
        self.assertEqual(origin.food_stock, 90)
        self.assertEqual(target.food_stock, 10)
        self.assertEqual(relation["trust"], 10.0)
        self.assertEqual(relation["interdependence"], 5.0)
        self.assertEqual(relation["status"], "trade_pact")

        second_trader = trader_between(origin, target)
        second_trader._do_trade(world)
        self.assertEqual(origin.food_stock, 70)
        self.assertEqual(target.food_stock, 30)

    def test_war_blocks_trade_without_changing_resources(self):
        from core.diplomacy import DiplomacyRegistry

        config = self.make_config()
        origin = diplomatic_market("A", 1, 100, 0, config)
        target = diplomatic_market("B", 2, 0, 100, config)
        world = {"cycle": 8}
        DiplomacyRegistry(world).transition(1, 2, "war", reason="declaration")
        trader = trader_between(origin, target)
        before = (
            origin.food_stock,
            target.food_stock,
            origin.economy["treasury"],
            target.economy["treasury"],
        )

        trader._do_trade(world)

        after = (
            origin.food_stock,
            target.food_stock,
            origin.economy["treasury"],
            target.economy["treasury"],
        )
        self.assertEqual(after, before)
        self.assertEqual(DiplomacyRegistry(world).get(1, 2)["status"], "war")
        self.assertNotIn("MISSING_TEXT", GameLogger.get_new_logs()[0])


class DiplomacyWarIntegrationTests(unittest.TestCase):
    def setUp(self):
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)
        GameLogger.get_new_logs()

    def make_cities(self):
        config = {"diplomacy": {"enabled": True, "truce_duration": 12}}
        attacker = settlement("A", 11)
        defender = settlement("B", 22, culture="Other")
        attacker.config = config
        defender.config = config
        attacker.war_cooldown = 0
        defender.war_cooldown = 0
        return attacker, defender

    def test_city_declaration_creates_persistent_war_and_linked_log(self):
        from core.diplomacy import DiplomacyRegistry

        attacker, defender = self.make_cities()
        world = {"cycle": 15}

        declared = City._declare_war(attacker, defender, world)
        GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(1)[0]

        self.assertTrue(declared)
        self.assertEqual(DiplomacyRegistry(world).get(11, 22)["status"], "war")
        self.assertEqual(attacker.enemies, [defender])
        self.assertEqual(defender.enemies, [attacker])
        self.assertEqual(metadata["category"], "diplomacy")
        self.assertEqual(metadata["entity_ids"], [11, 22])

    def test_alliance_and_active_truce_block_city_declaration(self):
        from core.diplomacy import DiplomacyRegistry

        for status in ("alliance", "truce"):
            with self.subTest(status=status):
                attacker, defender = self.make_cities()
                world = {"cycle": 20}
                registry = DiplomacyRegistry(world)
                if status == "alliance":
                    registry.transition(11, 22, "alliance", reason="treaty")
                else:
                    registry.transition(11, 22, "war", reason="old_war")
                    registry.transition(
                        11,
                        22,
                        "truce",
                        reason="peace",
                        truce_duration=12,
                    )

                declared = City._declare_war(attacker, defender, world)

                self.assertFalse(declared)
                self.assertEqual(attacker.enemies, [])
                self.assertEqual(defender.enemies, [])
                self.assertNotIn("MISSING_TEXT", GameLogger.get_new_logs()[-1])


class DiplomacyLifecycleTests(unittest.TestCase):
    def test_engine_migrates_old_world_and_exposes_defensive_headless_api(self):
        from core.entities import EntityManager
        from core.simulation_engine import SimulationEngine

        world = {"cycle": 3, "entities": EntityManager()}
        engine = SimulationEngine(world, {"year": 0, "logs": []}, {})
        engine.world["cycle"] = 4
        from core.diplomacy import DiplomacyRegistry
        DiplomacyRegistry(world).adjust(1, 2, trust=8, reason="trade")

        relation = engine.get_relationship(2, 1)
        relation["trust"] = 99
        summary = engine.get_diplomatic_summary()

        self.assertEqual(engine.get_relationship(1, 2)["trust"], 8.0)
        self.assertEqual(len(engine.get_relationships(entity_id=1)), 1)
        self.assertEqual(summary["relations"], 1)
        self.assertEqual(summary["statuses"]["neutral"], 1)
        self.assertEqual(summary["average_trust"], 8.0)

    def test_war_exhaustion_creates_truce_and_synchronizes_legacy_enemies(self):
        from core.diplomacy import DiplomacyRegistry, advance_diplomacy
        from core.entities import EntityManager

        config = {
            "diplomacy": {
                "enabled": True,
                "war_min_duration": 12,
                "truce_duration": 6,
                "war_exhaustion_rate": 1,
            }
        }
        first = settlement("A", 1)
        second = settlement("B", 2, culture="Other")
        first.config = config
        second.config = config
        first.enemies = [second]
        second.enemies = [first]
        manager = EntityManager()
        manager.add(first)
        manager.add(second)
        world = {"cycle": 0, "entities": manager}
        registry = DiplomacyRegistry(world)
        registry.transition(1, 2, "war", reason="declaration")

        world["cycle"] = 12
        events = advance_diplomacy(world, config)

        relation = registry.get(1, 2)
        self.assertEqual(relation["status"], "truce")
        self.assertEqual(relation["truce_until"], 18)
        self.assertEqual(first.enemies, [])
        self.assertEqual(second.enemies, [])
        self.assertEqual(events[0]["kind"], "truce_started")

    def test_alliance_aid_conserves_food_and_is_limited(self):
        from core.diplomacy import DiplomacyRegistry, advance_diplomacy
        from core.entities import EntityManager

        config = {
            "diplomacy": {
                "enabled": True,
                "alliance_aid_food": 15,
                "alliance_aid_reserve": 40,
            }
        }
        donor = settlement("Donor", 1)
        recipient = settlement("Recipient", 2)
        for city in (donor, recipient):
            city.config = config
            city.max_food = 100
            city.food_stock = 0
        donor.food_stock = 90
        manager = EntityManager()
        manager.add(donor)
        manager.add(recipient)
        world = {"cycle": 12, "entities": manager}
        DiplomacyRegistry(world).transition(1, 2, "alliance", reason="treaty")
        total = donor.food_stock + recipient.food_stock

        events = advance_diplomacy(world, config)

        self.assertEqual(donor.food_stock + recipient.food_stock, total)
        self.assertEqual(donor.food_stock, 75)
        self.assertEqual(recipient.food_stock, 15)
        self.assertEqual(events[0]["quantity"], 15)

    def test_soldier_retreats_when_diplomatic_war_has_ended(self):
        from core.diplomacy import DiplomacyRegistry
        from entities.species.human.soldier import Soldier

        config = {"diplomacy": {"enabled": True}}
        home = settlement("Home", 1)
        target = settlement("Target", 2)
        home.config = config
        target.config = config
        world = {"cycle": 5, "entities": []}
        registry = DiplomacyRegistry(world)
        registry.transition(1, 2, "war", reason="declaration")
        registry.transition(1, 2, "truce", reason="peace", truce_duration=10)
        soldier = Soldier.__new__(Soldier)
        soldier.is_expired = False
        soldier.is_dead = False
        soldier.retreating = False
        soldier.home_city = home
        soldier.target_city = target

        Soldier.think(soldier, world)

        self.assertTrue(soldier.retreating)


class DiplomacyConfigurationAndPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)

    def test_validator_accepts_template_and_rejects_invalid_diplomacy(self):
        import json
        from core.config_validator import ConfigValidationError, validate_config

        template = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertTrue(validate_config(template)["diplomacy"]["enabled"])

        invalid = dict(template)
        invalid["diplomacy"] = {
            "enabled": "yes",
            "trade_trust_gain": -1,
            "trade_pact_threshold": 20,
            "alliance_threshold": 10,
            "truce_duration": 0,
            "trade_pact_capacity_multiplier": 0.5,
        }
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:diplomacy.enabled:bool", caught.exception.errors)
        self.assertIn(
            "range:diplomacy.trade_trust_gain:non_negative",
            caught.exception.errors,
        )
        self.assertIn(
            "range:diplomacy.truce_duration:positive",
            caught.exception.errors,
        )
        self.assertIn(
            "range:diplomacy.trade_pact_capacity_multiplier:min_1",
            caught.exception.errors,
        )
        self.assertIn(
            "range:diplomacy.alliance_threshold:gte_trade_pact_threshold",
            caught.exception.errors,
        )

    def test_validator_rejects_non_mapping_diplomacy_section(self):
        import json
        from core.config_validator import ConfigValidationError, validate_config

        invalid = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        invalid["diplomacy"] = []

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:diplomacy:dict", caught.exception.errors)

    def test_world_factory_initializes_diplomatic_storage_explicitly(self):
        from unittest import mock
        from core.world_factory import assemble_world

        with (
            mock.patch("core.world_factory.generate_geology", return_value=([[0]], [])),
            mock.patch("core.world_factory.simulate_hydrology", return_value=[[0]]),
            mock.patch("core.world_factory.InfluenceSystem"),
        ):
            world, _ = assemble_world(1, 1, {}, 7)

        self.assertEqual(world["diplomacy"], {})
        self.assertEqual(world["next_relation_id"], 1)

    def test_checkpoint_preserves_relations_and_migrates_missing_storage(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock
        from core.diplomacy import DiplomacyRegistry
        from core.simulation_engine import SimulationEngine

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config["max_fauna"] = 0
        engine = SimulationEngine.create(config, 77, width=12, height=12)
        DiplomacyRegistry(engine.world).adjust(1, 2, trust=7, reason="trade")

        with tempfile.TemporaryDirectory() as directory:
            relation_path = Path(directory) / "relation.chart"
            engine.save(relation_path)
            restored = SimulationEngine.load(relation_path)

            self.assertEqual(restored.get_relationship(1, 2)["trust"], 7.0)

            del restored.world["diplomacy"]
            del restored.world["next_relation_id"]
            old_path = Path(directory) / "old.chart"
            restored.save(old_path)
            migrated = SimulationEngine.load(old_path)

        self.assertEqual(migrated.world["diplomacy"], {})
        self.assertEqual(migrated.world["next_relation_id"], 1)


class DiplomacyUiAndChronicleTests(unittest.TestCase):
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

    def test_diplomacy_tab_can_be_selected_and_renders_localized_relations(self):
        from core.diplomacy import DiplomacyRegistry
        from core.entities import EntityManager
        from main import handle_bestiary_input
        from render.ui_bestiary import DIPLOMACY_TAB, _build_diplomacy_entries

        first = settlement("A", 1)
        second = settlement("B", 2)
        manager = EntityManager()
        manager.add(first)
        manager.add(second)
        world = {"cycle": 3, "entities": manager}
        registry = DiplomacyRegistry(world)
        registry.adjust(1, 2, trust=12, interdependence=4, reason="trade")
        registry.transition(1, 2, "trade_pact", reason="threshold")
        state = {"active": True, "tab": "fauna", "page": 5}

        handle_bestiary_input("d", state)
        rendered = "\n".join(_build_diplomacy_entries(world)[0])

        self.assertEqual(state["tab"], DIPLOMACY_TAB)
        self.assertEqual(state["page"], 0)
        self.assertIn("A", rendered)
        self.assertIn("B", rendered)
        self.assertIn("12", rendered)
        self.assertNotIn("MISSING_TEXT", rendered)

    def test_engine_records_truce_as_chronicle_linked_to_both_cities(self):
        from unittest import mock
        from core.diplomacy import DiplomacyRegistry
        from core.entities import EntityManager
        from core.simulation_engine import SimulationEngine

        config = {
            "diplomacy": {
                "enabled": True,
                "war_min_duration": 12,
                "truce_duration": 6,
            },
            "max_fauna": 0,
        }
        manager = EntityManager()
        for entity_id, name in ((1, "A"), (2, "B")):
            entity = settlement(name, entity_id)
            entity.config = config
            entity.process_turn = lambda world, stats: None
            manager.add(entity)
        world = {
            "width": 3,
            "height": 3,
            "cycle": 11,
            "entities": manager,
            "grid": mock.Mock(),
            "influence": mock.Mock(),
        }
        stats = {"year": 0, "seed": 7, "logs": []}
        engine = SimulationEngine(world, stats, config)
        relation = DiplomacyRegistry(world).transition(
            1,
            2,
            "war",
            reason="declaration",
        )
        world["diplomacy"]["1:2"]["war_started_cycle"] = 0

        with (
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            engine.step()

        chronicles = engine.get_chronicles(category="diplomacy", entity_id=1)
        self.assertEqual(len(chronicles), 1)
        self.assertEqual(chronicles[0]["entity_ids"], [1, 2])
        self.assertNotIn("MISSING_TEXT", chronicles[0]["message"])


class DiplomacyInspectionAndHostilityTests(unittest.TestCase):
    def test_hostility_and_tension_increase_war_probability_multiplier(self):
        from core.diplomacy import DiplomacyRegistry, war_probability_multiplier

        world = {"cycle": 1}
        registry = DiplomacyRegistry(world)
        neutral = war_probability_multiplier(world, 1, 2)
        registry.adjust(1, 2, tension=50, reason="border_incident")
        registry.transition(1, 2, "hostile", reason="threshold")
        hostile = war_probability_multiplier(world, 1, 2)

        self.assertEqual(neutral, 1.0)
        self.assertGreater(hostile, neutral)
        self.assertEqual(
            war_probability_multiplier(world, 1, 2),
            hostile,
        )

    def test_entity_inspection_includes_defensive_relationship_copies(self):
        from core.diplomacy import DiplomacyRegistry
        from core.entities import EntityManager
        from core.inspection import inspect_entity

        entity = settlement("A", 1)
        entity.char = "A"
        entity.speed = 0
        manager = EntityManager()
        manager.add(entity)
        world = {"cycle": 2, "entities": manager}
        DiplomacyRegistry(world).adjust(1, 2, trust=6, reason="trade")

        inspection = inspect_entity(world, 1)
        inspection["relationships"][0]["trust"] = 99

        self.assertEqual(len(inspection["relationships"]), 1)
        self.assertEqual(DiplomacyRegistry(world).get(1, 2)["trust"], 6.0)


class DiplomacyLegacyMigrationTests(unittest.TestCase):
    def test_active_legacy_enemies_migrate_to_persistent_war_without_loss(self):
        from core.diplomacy import DiplomacyRegistry, advance_diplomacy
        from core.entities import EntityManager

        config = {"diplomacy": {"enabled": True}}
        first = settlement("A", 1)
        second = settlement("B", 2, culture="Other")
        first.config = config
        second.config = config
        first.enemies = [second]
        second.enemies = [first]
        manager = EntityManager()
        manager.add(first)
        manager.add(second)
        old_world = {"cycle": 1, "entities": manager}

        advance_diplomacy(old_world, config)

        self.assertEqual(DiplomacyRegistry(old_world).get(1, 2)["status"], "war")
        self.assertEqual(first.enemies, [second])
        self.assertEqual(second.enemies, [first])


class DiplomacyLocaleIntegrityTests(unittest.TestCase):
    def test_locale_catalogs_reject_duplicate_json_keys(self):
        import json

        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate locale key: {key}")
                result[key] = value
            return result

        for language in ("fr", "en", "es"):
            with self.subTest(language=language):
                source = (ROOT / f"locales/textes.{language}.json").read_text(
                    encoding="utf-8"
                )
                json.loads(source, object_pairs_hook=unique_pairs)

if __name__ == "__main__":
    unittest.main()