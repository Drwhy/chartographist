import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.config_validator import ConfigValidationError, validate_config
from core.entities import EntityManager
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.constructs.base import Construct
from entities.constructs.city import City
from entities.constructs.village import Village
from entities.species.human.trader import Trader


ROOT = Path(__file__).resolve().parents[1]


def economy_config(**overrides):
    values = {
        "enabled": True,
        "initial_treasury": 200.0,
        "base_food_price": 2.0,
        "min_food_price": 0.5,
        "max_food_price": 5.0,
        "food_reserve": 40,
        "trade_capacity": 20,
    }
    values.update(overrides)
    return {"economy": values}


def settlement(name, entity_id, food, max_food, config, treasury=None):
    value = SimpleNamespace(
        name=name,
        entity_id=entity_id,
        food_stock=food,
        max_food=max_food,
        config=config,
        pos=(entity_id, 0),
        is_expired=False,
        known_cities=set(),
        religion=None,
    )
    if treasury is not None:
        value.economy = {
            "treasury": float(treasury),
            "food_imported": 0,
            "food_exported": 0,
            "trade_spent": 0.0,
            "trade_earned": 0.0,
            "transactions": 0,
            "last_food_price": 0.0,
        }
    return value


def trader_between(origin, target, bonus=0):
    trader = Trader.__new__(Trader)
    trader.entity_id = 999
    trader.home_city = origin
    trader.base_city = origin
    trader.target_city = target
    trader.visited_cities = set()
    trader.trades_since_home = 0
    trader._returning_home = False
    trader.faith_bonus = lambda key: bonus
    trader.species_trait = lambda key: 0
    trader._establish_connection = lambda world: None
    trader._spread_religion = lambda: None
    return trader


class EconomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)

    def setUp(self):
        RandomService.initialize(321)
        GameLogger.get_new_logs()

    def test_economy_is_initialized_lazily_and_price_tracks_scarcity(self):
        from core.economy import ensure_economy, food_price

        scarce = settlement("Scarce", 1, 10, 100, economy_config())
        abundant = settlement("Abundant", 2, 90, 100, economy_config())

        scarce_account = ensure_economy(scarce)
        self.assertIs(scarce_account, ensure_economy(scarce))
        self.assertEqual(scarce_account["treasury"], 200.0)
        self.assertGreater(food_price(scarce), food_price(abundant))
        self.assertGreaterEqual(food_price(abundant), 0.5)
        self.assertLessEqual(food_price(scarce), 5.0)

    def test_food_trade_conserves_food_and_wealth_and_updates_ledgers(self):
        from core.economy import ensure_economy, execute_food_trade

        config = economy_config()
        origin = settlement("Origin", 1, 120, 200, config, treasury=50)
        target = settlement("Target", 2, 10, 100, config, treasury=100)
        total_food = origin.food_stock + target.food_stock
        total_wealth = ensure_economy(origin)["treasury"] + ensure_economy(target)["treasury"]

        transaction = execute_food_trade(origin, target, capacity=20)

        self.assertEqual(transaction.quantity, 20)
        self.assertEqual(origin.food_stock + target.food_stock, total_food)
        self.assertAlmostEqual(
            ensure_economy(origin)["treasury"] + ensure_economy(target)["treasury"],
            total_wealth,
        )
        self.assertEqual(ensure_economy(origin)["food_exported"], 20)
        self.assertEqual(ensure_economy(target)["food_imported"], 20)
        self.assertEqual(ensure_economy(origin)["transactions"], 1)
        self.assertGreater(transaction.value, 0)

    def test_food_trade_is_noop_without_exportable_surplus(self):
        from core.economy import execute_food_trade

        config = economy_config(food_reserve=40)
        origin = settlement("Origin", 1, 40, 100, config, treasury=50)
        target = settlement("Target", 2, 0, 100, config, treasury=100)

        transaction = execute_food_trade(origin, target, capacity=20)

        self.assertEqual(transaction.quantity, 0)
        self.assertEqual(origin.food_stock, 40)
        self.assertEqual(target.food_stock, 0)
        self.assertEqual(transaction.value, 0)

    def test_trader_uses_market_transfer_and_emits_linked_metadata(self):
        config = economy_config()
        origin = settlement("Origin", 11, 120, 200, config, treasury=50)
        target = settlement("Target", 22, 10, 100, config, treasury=100)
        trader = trader_between(origin, target, bonus=2)

        Trader._do_trade(trader, {})
        logs = GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(1)[0]

        self.assertEqual(origin.food_stock, 98)
        self.assertEqual(target.food_stock, 32)
        self.assertIn("22", logs[0])
        self.assertNotIn("MISSING_TEXT", logs[0])
        self.assertEqual(metadata["category"], "economy")
        self.assertEqual(metadata["entity_ids"], [11, 22, 999])

    def test_trader_preserves_legacy_food_bonus_without_economy_section(self):
        config = {}
        origin = settlement("Legacy A", 31, 50, 100, config)
        target = settlement("Legacy B", 32, 20, 100, config)
        trader = trader_between(origin, target, bonus=3)

        Trader._do_trade(trader, {})

        self.assertEqual(origin.food_stock, 50)
        self.assertEqual(target.food_stock, 33)

    def test_village_evolution_transfers_economic_account(self):
        config = dict(self.template)
        config.update(economy_config())
        settlement_value = Construct.__new__(Construct)
        settlement_value.entity_id = 404
        settlement_value._pos = [1, 1]
        settlement_value.culture = config["cultures"][0]
        settlement_value.config = config
        settlement_value.name = "Continuum"
        settlement_value.citizens = []
        settlement_value.food_stock = 80
        settlement_value.religion = None
        settlement_value.is_expired = False
        settlement_value.economy = {
            "treasury": 345.0,
            "food_imported": 4,
            "food_exported": 9,
            "trade_spent": 12.0,
            "trade_earned": 27.0,
            "transactions": 3,
            "last_food_price": 1.5,
        }
        world = {"entities": EntityManager()}

        Village._evolve_to_city(settlement_value, world)
        evolved = next(iter(world["entities"]))

        self.assertIs(evolved.economy, settlement_value.economy)
        self.assertEqual(evolved.economy["treasury"], 345.0)

    def test_inspection_and_terminal_line_expose_economic_snapshot(self):
        from core.economy import ensure_economy
        from core.inspection import inspect_entity
        from render.ui_bestiary import _settlement_economy_line

        entity = Construct.__new__(Construct)
        entity.entity_id = 77
        entity._pos = [2, 3]
        entity.char = "C"
        entity.speed = 1.0
        entity.is_expired = False
        entity.name = "Marché"
        entity.food_stock = 30
        entity.max_food = 100
        entity.config = economy_config()
        ensure_economy(entity)["treasury"] = 456.0
        world = {"entities": EntityManager()}
        world["entities"].add(entity)

        snapshot = inspect_entity(world, 77)["entity"]["economy"]
        rendered = _settlement_economy_line(entity)

        self.assertEqual(snapshot["treasury"], 456.0)
        self.assertIn("456", rendered)
        self.assertNotIn("MISSING_TEXT", rendered)

    def test_world_economic_summary_aggregates_active_markets(self):
        from core.economy import ensure_economy, world_economic_summary
        from core.simulation_engine import SimulationEngine

        config = economy_config()
        first = settlement("A", 1, 80, 100, config, treasury=120)
        second = settlement("B", 2, 20, 100, config, treasury=30)
        expired = settlement("Ruined", 3, 50, 100, config, treasury=999)
        expired.is_expired = True
        ensure_economy(first)["food_exported"] = 12
        ensure_economy(second)["food_imported"] = 12
        manager = EntityManager()
        for entity in (first, second, expired):
            manager.add(entity)
        world = {"entities": manager}

        summary = world_economic_summary(world)
        engine = SimulationEngine(world, {"year": 0, "logs": []}, config)

        self.assertEqual(summary["active_markets"], 2)
        self.assertEqual(summary["treasury"], 150.0)
        self.assertEqual(summary["food_imported"], 12)
        self.assertEqual(summary["food_exported"], 12)
        self.assertEqual(engine.get_economic_summary(), summary)
    def test_city_expansion_requires_and_spends_treasury_when_economy_is_enabled(self):
        from core.economy import ensure_economy

        config = economy_config(settler_treasury_cost=50)
        city = Construct.__new__(City)
        city.citizens = [object(), object(), object(), object()]
        city.settler_threshold = 3
        city.settler_cooldown = 0
        city.settler_cost = 1
        city.config = config
        city.economy = {
            "treasury": 49.0,
            "food_imported": 0,
            "food_exported": 0,
            "trade_spent": 0.0,
            "trade_earned": 0.0,
            "transactions": 0,
            "last_food_price": 0.0,
        }
        city._can_world_support_new_settler = lambda world: True
        spawned = []
        city._spawn_settler = lambda world: spawned.append(True)

        City._manage_expansion(city, {})
        self.assertEqual(len(city.citizens), 4)
        self.assertEqual(spawned, [])
        self.assertEqual(ensure_economy(city)["treasury"], 49.0)

        ensure_economy(city)["treasury"] = 50.0
        City._manage_expansion(city, {})
        self.assertEqual(len(city.citizens), 3)
        self.assertEqual(spawned, [True])
        self.assertEqual(ensure_economy(city)["treasury"], 0.0)

    def test_config_validator_rejects_invalid_economy_values(self):
        invalid = dict(self.template)
        invalid["economy"] = {
            "enabled": "yes",
            "trade_capacity": 0,
            "food_reserve": -1,
            "base_food_price": "expensive",
        }

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:economy.enabled:bool", caught.exception.errors)
        self.assertIn("range:economy.trade_capacity:positive", caught.exception.errors)
        self.assertIn("range:economy.food_reserve:non_negative", caught.exception.errors)
        self.assertIn("type:economy.base_food_price:int|float", caught.exception.errors)
    def test_config_validator_rejects_invalid_economy_section(self):
        invalid = dict(self.template)
        invalid["economy"] = []

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:economy:dict", caught.exception.errors)


if __name__ == "__main__":
    unittest.main()