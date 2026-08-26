import copy
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

from core.random_service import RandomService


ROOT = Path(__file__).resolve().parents[1]


def template_config():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


def material_config():
    return {
        "materials": {
            "enabled": True,
            "stockpile_capacity": 100,
            "resources": [
                {"id": "raw_food", "unit_weight": 1.0, "decay_rate": 0.1},
            ],
            "items": [
                {"id": "food_ration", "unit_weight": 1.0, "decay_rate": 0.02, "base_value": 2.0},
                {"id": "stone_tool", "unit_weight": 2.0, "decay_rate": 0.0, "base_value": 5.0, "durability": 100},
            ],
            "recipes": [
                {
                    "id": "preserve_food",
                    "inputs": {"raw_food": 2},
                    "tools": ["stone_tool"],
                    "skill": "agriculture",
                    "cycles": 1,
                    "labor": 1.0,
                    "outputs": {"food_ration": 1},
                }
            ],
        }
    }


class MaterialCatalogTests(unittest.TestCase):
    def test_runtime_catalog_is_built_once_per_immutable_configuration(self):
        from core.materials import catalog_validation_errors, runtime_catalog

        config = material_config()
        with mock.patch(
            "core.materials.catalog_validation_errors",
            wraps=catalog_validation_errors,
        ) as validate:
            first = runtime_catalog(config)
            second = runtime_catalog(config)

        self.assertIs(first, second)
        self.assertEqual(validate.call_count, 1)

    def test_missing_section_is_disabled_empty_and_does_not_mutate_config(self):
        from core.materials import MaterialCatalog

        config = {}
        original = copy.deepcopy(config)
        catalog = MaterialCatalog(config)

        self.assertFalse(catalog.enabled)
        self.assertEqual(catalog.snapshot(), {"resources": [], "items": [], "recipes": []})
        self.assertEqual(config, original)

    def test_catalog_queries_and_snapshots_are_defensive_and_use_no_randomness(self):
        from core.materials import MaterialCatalog

        config = material_config()
        RandomService.initialize(1101)
        before = RandomService.get_state()
        catalog = MaterialCatalog(config)

        snapshot = catalog.snapshot()
        snapshot["resources"][0]["id"] = "corrupted"
        recipe = catalog.recipe("preserve_food")
        recipe["inputs"]["raw_food"] = 999

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(catalog.resource("raw_food")["id"], "raw_food")
        self.assertEqual(catalog.recipe("preserve_food")["inputs"], {"raw_food": 2})
        self.assertEqual(catalog.good("food_ration")["kind"], "item")
        with self.assertRaises(KeyError):
            catalog.good("unknown")

    def test_template_is_opt_in_and_material_definitions_are_valid(self):
        from core.config_validator import validate_config
        from core.materials import MaterialCatalog

        config = template_config()

        self.assertIs(validate_config(config), config)
        self.assertFalse(config["materials"]["enabled"])
        self.assertGreater(len(MaterialCatalog(config).snapshot()["recipes"]), 0)
        self.assertIn(
            "repair_stone_tool",
            {recipe["id"] for recipe in config["materials"]["recipes"]},
        )
        granary = config["materials"]["infrastructures"][0]
        self.assertEqual(granary["maintenance"], {"plank": 1})
        self.assertGreater(granary["repair_amount"], 0)
        self.assertEqual(config["materials"]["targets"]["stone_tool"], 1)
        infrastructure_ids = {
            definition["id"]
            for definition in config["materials"]["infrastructures"]
        }
        self.assertEqual(
            infrastructure_ids,
            {"granary", "road", "market", "workshop", "fortification"},
        )

    def test_validator_rejects_duplicates_unknown_references_and_invalid_numbers(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = template_config()
        config["materials"] = material_config()["materials"]
        config["materials"]["items"].append({"id": "raw_food", "unit_weight": 1, "decay_rate": 0, "base_value": 1})
        recipe = config["materials"]["recipes"][0]
        recipe["inputs"] = {"missing": 0}
        recipe["tools"] = ["missing_tool"]
        recipe["cycles"] = 0
        recipe["byproducts"] = {"missing_scrap": 0}
        recipe["quality_skill_scale"] = -1
        recipe["tool_wear"] = 0
        config["economy"]["transport_loss_per_tile"] = 2
        config["materials"]["targets"] = {"missing_target": -1}
        config["materials"]["trade_reserve"] = {"missing_reserve": -1}
        config["materials"]["food_chain"] = {
            "recipe_id": "missing_recipe",
            "raw_good_id": "missing_raw",
            "ration_good_id": "missing_ration",
        }
        config["economy"]["transport_cost_per_tile"] = -1
        config["economy"]["risk_cost_multiplier"] = "high"

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(config)

        self.assertIn("duplicate:materials.good:raw_food", caught.exception.errors)
        self.assertIn("reference:materials.recipes.preserve_food.inputs:missing", caught.exception.errors)
        self.assertIn("range:materials.recipes.preserve_food.inputs.missing:positive", caught.exception.errors)
        self.assertIn("reference:materials.recipes.preserve_food.tools:missing_tool", caught.exception.errors)
        self.assertIn("range:materials.recipes.preserve_food.cycles:positive", caught.exception.errors)
        self.assertIn(
            "reference:materials.recipes.preserve_food.byproducts:missing_scrap",
            caught.exception.errors,
        )
        self.assertIn(
            "range:materials.recipes.preserve_food.byproducts.missing_scrap:positive",
            caught.exception.errors,
        )
        self.assertIn("range:materials.recipes.preserve_food.quality_skill_scale:nonnegative", caught.exception.errors)
        self.assertIn("range:materials.recipes.preserve_food.tool_wear:positive", caught.exception.errors)
        self.assertIn("range:economy.transport_loss_per_tile:0_1", caught.exception.errors)
        self.assertIn("reference:materials.targets:missing_target", caught.exception.errors)
        self.assertIn("range:materials.targets.missing_target:nonnegative", caught.exception.errors)
        self.assertIn("reference:materials.trade_reserve:missing_reserve", caught.exception.errors)
        self.assertIn("range:materials.trade_reserve.missing_reserve:nonnegative", caught.exception.errors)
        self.assertIn("reference:materials.food_chain.recipe_id:missing_recipe", caught.exception.errors)
        self.assertIn("reference:materials.food_chain.raw_good_id:missing_raw", caught.exception.errors)
        self.assertIn("reference:materials.food_chain.ration_good_id:missing_ration", caught.exception.errors)
        self.assertIn("range:economy.transport_cost_per_tile:non_negative", caught.exception.errors)
        self.assertIn("type:economy.risk_cost_multiplier:int|float", caught.exception.errors)

    def test_validator_rejects_invalid_spatial_material_sources(self):
        from core.materials import catalog_validation_errors

        section = material_config()["materials"]
        section["resources"][0]["source"] = {
            "spatial_resource": "ore",
            "stock_per_unit": 0,
            "max_per_cycle": -1,
            "minimum_ratio": 2,
        }

        self.assertEqual(catalog_validation_errors(section), [
            "reference:materials.resources.raw_food.source.spatial_resource:ore",
            "range:materials.resources.raw_food.source.stock_per_unit:positive",
            "range:materials.resources.raw_food.source.max_per_cycle:positive",
            "range:materials.resources.raw_food.source.minimum_ratio:0_1",
        ])

    def test_mods_append_nested_catalog_lists_without_mutating_sources(self):
        from core.scenarios import ScenarioValidationError, compose_config

        base = material_config()
        mod = {
            "mod": {"id": "woodworking"},
            "append": {
                "materials.resources": [{"id": "timber", "unit_weight": 2, "decay_rate": 0.01}],
                "materials.items": [{"id": "plank", "unit_weight": 1, "decay_rate": 0, "base_value": 3}],
                "materials.recipes": [
                    {
                        "id": "saw_plank", "inputs": {"timber": 1},
                        "tools": ["stone_tool"], "skill": "agriculture",
                        "cycles": 2, "labor": 1, "outputs": {"plank": 2},
                    }
                ],
                "materials.infrastructures": [
                    {
                        "id": "workshop",
                        "kit_good_id": "plank",
                        "max_level": 1,
                        "capacity_bonus": 10,
                    }
                ],
            },
        }
        original = copy.deepcopy((base, mod))

        composed = compose_config(base, mods=[mod])

        self.assertEqual((base, mod), original)
        self.assertIn("timber", {value["id"] for value in composed["materials"]["resources"]})
        self.assertEqual(
            composed["materials"]["infrastructures"][0]["id"],
            "workshop",
        )
        duplicate = {
            "mod": {"id": "duplicate"},
            "append": {"materials.items": [copy.deepcopy(base["materials"]["items"][0])]},
        }
        with self.assertRaises(ScenarioValidationError) as caught:
            compose_config(base, mods=[duplicate])
        self.assertEqual(caught.exception.code, "duplicate_data_id:materials.items:food_ration")


class StockpileTests(unittest.TestCase):
    def settlement(self, entity_id, config=None):
        return SimpleNamespace(entity_id=entity_id, config=config or material_config())

    def test_disabled_service_is_noop_and_preserves_legacy_object_shape(self):
        from core.stockpiles import StockpileService

        settlement = SimpleNamespace(entity_id=1)
        service = StockpileService(settlement, {})

        self.assertEqual(service.deposit("anything", 4), 0.0)
        self.assertEqual(service.snapshot()["goods"], {})
        self.assertFalse(hasattr(settlement, "stockpile"))

    def test_stockpile_is_lazy_defensive_weighted_and_capacity_bounded(self):
        from core.stockpiles import StockpileService

        settlement = self.settlement(10)
        service = StockpileService(settlement, settlement.config)

        self.assertEqual(service.deposit("raw_food", 80), 80.0)
        self.assertEqual(service.deposit("stone_tool", 20), 10.0)
        self.assertEqual(service.total_weight(), 100.0)
        self.assertEqual(service.available_weight(), 0.0)
        snapshot = service.snapshot()
        snapshot["goods"]["raw_food"] = -1
        self.assertEqual(service.quantity("raw_food"), 80.0)
        with self.assertRaises(ValueError):
            service.deposit("raw_food", -1)
        with self.assertRaises(KeyError):
            service.deposit("unknown", 1)

    def test_initial_stock_is_applied_exactly_once(self):
        from core.stockpiles import StockpileService

        config = material_config()
        config["materials"]["initial_stock"] = {"stone_tool": 1}
        settlement = self.settlement(15, config)

        first = StockpileService(settlement, config)
        second = StockpileService(settlement, config)

        self.assertEqual(first.quantity("stone_tool"), 1.0)
        self.assertEqual(second.quantity("stone_tool"), 1.0)
        self.assertTrue(second.snapshot()["initial_stock_applied"])
    def test_transfer_is_conservative_and_limited_by_target_capacity(self):
        from core.stockpiles import StockpileService, transfer_goods

        config = material_config()
        source = self.settlement(20, config)
        target = self.settlement(21, config)
        source_stock = StockpileService(source, config)
        target_stock = StockpileService(target, config)
        source_stock.deposit("raw_food", 80)
        target_stock.deposit("raw_food", 30)
        before = source_stock.quantity("raw_food") + target_stock.quantity("raw_food")

        transaction = transfer_goods(source, target, "raw_food", 80, config)

        self.assertEqual(transaction["transferred"], 70.0)
        self.assertEqual(source_stock.quantity("raw_food"), 10.0)
        self.assertEqual(target_stock.quantity("raw_food"), 100.0)
        self.assertEqual(
            source_stock.quantity("raw_food") + target_stock.quantity("raw_food"),
            before,
        )

    def test_decay_runs_once_per_cycle_and_accounts_for_losses(self):
        from core.stockpiles import StockpileService

        settlement = self.settlement(30)
        service = StockpileService(settlement, settlement.config)
        service.deposit("raw_food", 10)
        service.deposit("stone_tool", 1)

        first = service.decay(4)
        repeated = service.decay(4)

        self.assertEqual(first, {"raw_food": 1.0})
        self.assertEqual(repeated, {})
        self.assertEqual(service.quantity("raw_food"), 9.0)
        self.assertEqual(service.quantity("stone_tool"), 1.0)
        self.assertEqual(service.snapshot()["losses"], {"raw_food": 1.0})
        json.dumps(service.snapshot())
class ProductionOrderTests(unittest.TestCase):
    def production_setup(self, *, cycles=2):
        config = material_config()
        config["materials"]["targets"] = {"food_ration": 4}
        config["materials"]["recipes"][0]["cycles"] = cycles
        settlement = SimpleNamespace(entity_id=40, config=config)
        return config, settlement

    def test_shortage_planning_is_idempotent_and_explainable(self):
        from core.production import ProductionService

        config, settlement = self.production_setup()
        service = ProductionService(settlement, config)

        first = service.plan(cycle=3)
        repeated = service.plan(cycle=3)

        self.assertEqual(len(first), 1)
        self.assertEqual(repeated, [])
        self.assertEqual(first[0]["recipe_id"], "preserve_food")
        self.assertEqual(first[0]["reason"], "shortage:food_ration")
        self.assertGreater(first[0]["priority"], 0)
        snapshot = service.snapshot()
        snapshot["orders"][0]["status"] = "corrupted"
        self.assertEqual(service.snapshot()["orders"][0]["status"], "waiting")

    def test_order_waits_for_inputs_and_tools_then_consumes_before_output(self):
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=2)
        stockpile = StockpileService(settlement, config)
        service = ProductionService(settlement, config)
        service.plan(cycle=1)

        waiting_for_input = service.advance(cycle=1)
        stockpile.deposit("raw_food", 4)
        waiting_for_tool = service.advance(cycle=2)
        stockpile.deposit("stone_tool", 1)
        active = service.advance(cycle=3)

        self.assertEqual(waiting_for_input["status"], "waiting")
        self.assertEqual(waiting_for_tool["status"], "waiting")
        self.assertEqual(active["status"], "active")
        self.assertEqual(stockpile.quantity("raw_food"), 2.0)
        self.assertEqual(stockpile.quantity("food_ration"), 0.0)
        completed = service.advance(cycle=4)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(stockpile.quantity("food_ration"), 1.0)
        self.assertEqual(stockpile.quantity("stone_tool"), 1.0)

    def test_tool_durability_is_consumed_and_breakage_blocks_next_order(self):
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=1)
        config["materials"]["items"][1]["durability"] = 2
        config["materials"]["recipes"][0]["inputs"] = {"raw_food": 1}
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 3)
        stockpile.deposit("stone_tool", 1)
        service = ProductionService(settlement, config)

        service.plan(cycle=1)
        first = service.advance(cycle=1)
        service.plan(cycle=2)
        second = service.advance(cycle=2)
        service.plan(cycle=3)
        blocked = service.advance(cycle=3)

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "completed")
        self.assertEqual(stockpile.quantity("stone_tool"), 0.0)
        self.assertEqual(service.tool_durability("stone_tool"), 0.0)
        self.assertEqual(blocked["status"], "waiting")
        self.assertEqual(
            stockpile.quantity("raw_food"),
            1.0,
        )

    def test_blocked_high_priority_order_does_not_starve_feasible_work(self):
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=1)
        config["materials"]["resources"].append({
            "id": "timber", "unit_weight": 2, "decay_rate": 0,
        })
        config["materials"]["recipes"].append({
            "id": "saw_plank",
            "inputs": {"timber": 1},
            "tools": ["stone_tool"],
            "skill": "agriculture",
            "cycles": 1,
            "labor": 1,
            "outputs": {"food_ration": 1},
        })
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 2)
        stockpile.deposit("stone_tool", 1)
        service = ProductionService(settlement, config)
        service.create_order(
            "saw_plank", reason="shortage:plank", priority=2, cycle=1
        )
        service.create_order(
            "preserve_food", reason="shortage:food_ration", priority=1, cycle=1
        )

        result = service.advance(cycle=1)

        self.assertEqual(result["recipe_id"], "preserve_food")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(service.snapshot()["orders"][0]["status"], "waiting")

    def test_skill_accelerates_work_without_randomness(self):
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=2)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 2)
        stockpile.deposit("stone_tool", 1)
        worker = SimpleNamespace(character={"skills": {"agriculture": 100.0}})
        service = ProductionService(settlement, config)
        service.plan(cycle=1)
        RandomService.initialize(1122)
        before = RandomService.get_state()

        result = service.advance(worker=worker, cycle=1)

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["worker_skill"], 100.0)
        self.assertEqual(stockpile.quantity("food_ration"), 1.0)

    def test_policy_multiplier_changes_real_production_progress(self):
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=4)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 2)
        stockpile.deposit("stone_tool", 1)
        settlement.political_modifiers = {
            "labor_efficiency_multiplier": 0.5,
        }
        service = ProductionService(settlement, config)
        service.plan(cycle=1)

        result = service.advance(cycle=1)

        self.assertEqual(result["progress"], 0.5)
    def test_workshop_effect_accelerates_real_production(self):
        from core.infrastructure import InfrastructureService
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=2)
        config["materials"]["items"].append({
            "id": "workshop_kit",
            "unit_weight": 1,
            "decay_rate": 0,
            "base_value": 1,
        })
        config["materials"]["infrastructures"] = [{
            "id": "workshop",
            "kit_good_id": "workshop_kit",
            "max_level": 1,
            "effects": {"production_speed_bonus": 1.0},
        }]
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("workshop_kit", 1)
        InfrastructureService(settlement, config).install_available(cycle=1)
        stockpile.deposit("raw_food", 2)
        stockpile.deposit("stone_tool", 1)
        service = ProductionService(settlement, config)
        service.plan(cycle=1)

        self.assertEqual(service.advance(cycle=1)["status"], "completed")

    def test_quality_byproducts_and_specialization_are_recorded(self):
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.production_setup(cycles=1)
        config["materials"]["items"].append({
            "id": "scrap",
            "unit_weight": 0.1,
            "decay_rate": 0,
            "base_value": 0,
        })
        recipe = config["materials"]["recipes"][0]
        recipe["byproducts"] = {"scrap": 1}
        recipe["quality_skill_scale"] = 0.5
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 2)
        stockpile.deposit("stone_tool", 1)
        worker = SimpleNamespace(
            character={"skills": {"agriculture": 100.0}},
        )
        service = ProductionService(settlement, config)
        service.plan(cycle=1)

        completed = service.advance(worker=worker, cycle=1)

        self.assertEqual(completed["output_quality"], 1.5)
        self.assertEqual(stockpile.quantity("scrap"), 1.0)
        self.assertEqual(service.snapshot()["specialization"], "food_ration")

    def test_disabled_production_preserves_legacy_settlement(self):
        from core.production import ProductionService

        settlement = SimpleNamespace(entity_id=41)
        service = ProductionService(settlement, {})

        self.assertEqual(service.plan(cycle=1), [])
        self.assertIsNone(service.advance(cycle=1))
        self.assertFalse(hasattr(settlement, "production"))
class MaterialFoodChainIntegrationTests(unittest.TestCase):
    def chain_config(self, *, initial_tool=True):
        config = material_config()
        materials = config["materials"]
        materials["targets"] = {"food_ration": 4}
        materials["food_chain"] = {
            "recipe_id": "preserve_food",
            "raw_good_id": "raw_food",
            "ration_good_id": "food_ration",
        }
        materials["recipes"][0].update({
            "inputs": {"raw_food": 2},
            "outputs": {"food_ration": 2},
            "cycles": 1,
        })
        if initial_tool:
            materials["initial_stock"] = {"stone_tool": 1}
        return config

    @staticmethod
    def equivalent_food(settlement, stockpile):
        return (
            settlement.food_stock
            + stockpile.quantity("raw_food")
            + stockpile.quantity("food_ration")
        )

    def test_real_chain_conserves_food_from_staging_through_consumption(self):
        from core.food_balance import consume_food
        from core.production import advance_settlement_production
        from core.stockpiles import StockpileService

        config = self.chain_config()
        worker = SimpleNamespace(
            is_dead=False,
            character={"skills": {"agriculture": 0.0}},
        )
        settlement = SimpleNamespace(
            entity_id=50,
            config=config,
            food_stock=10,
            max_food=100,
            citizens=[worker],
        )
        world = {"cycle": 1}
        stockpile = StockpileService(settlement, config)
        before = self.equivalent_food(settlement, stockpile)

        result = advance_settlement_production(settlement, world)

        self.assertEqual(result["staged"], 2.0)
        self.assertEqual(result["order"]["status"], "completed")
        self.assertEqual(self.equivalent_food(settlement, stockpile), before)
        self.assertEqual(consume_food(settlement, world, 1), 1)
        self.assertEqual(settlement.food_stock, 8)
        self.assertEqual(stockpile.quantity("food_ration"), 1.0)
        self.assertEqual(self.equivalent_food(settlement, stockpile), before - 1)
        self.assertEqual(world["metrics"]["flows"]["food"]["consumed"], 1)

    def test_chain_does_not_stage_without_tool_or_living_worker(self):
        from core.production import advance_settlement_production

        config = self.chain_config(initial_tool=False)
        settlement = SimpleNamespace(
            entity_id=51,
            config=config,
            food_stock=10,
            max_food=100,
            citizens=[SimpleNamespace(is_dead=False, character={"skills": {}})],
        )
        world = {"cycle": 1}

        without_tool = advance_settlement_production(settlement, world)
        settlement.citizens = []
        without_worker = advance_settlement_production(settlement, {"cycle": 2})

        self.assertEqual(without_tool["staged"], 0.0)
        self.assertEqual(without_worker["staged"], 0.0)
        self.assertEqual(settlement.food_stock, 10)
class SettlementProductionHookTests(unittest.TestCase):
    def test_city_and_village_advance_production_once_per_update(self):
        from entities.constructs.city import City
        from entities.constructs.village import Village

        for settlement_type in (City, Village):
            with self.subTest(settlement=settlement_type.__name__):
                settlement = settlement_type.__new__(settlement_type)
                settlement.is_expired = False
                settlement.config = material_config()
                settlement.citizens = [SimpleNamespace(is_dead=False)]
                settlement.religion = None
                with (
                    mock.patch.object(settlement_type, "_update_citizens"),
                    mock.patch.object(settlement_type, "_handle_reproduction"),
                    mock.patch.object(settlement_type, "_check_syncretism"),
                    mock.patch("core.production.advance_settlement_production") as advance,
                ):
                    if settlement_type is City:
                        with (
                            mock.patch.object(City, "_manage_expansion"),
                            mock.patch.object(City, "_manage_trade"),
                            mock.patch.object(City, "_manage_specialization"),
                        ):
                            City.update(settlement, {"cycle": 1}, {})
                    else:
                        Village.update(settlement, {"cycle": 1}, {})

                advance.assert_called_once()
                self.assertIs(advance.call_args.args[0], settlement)

class SpatialMaterialSourcingTests(unittest.TestCase):
    @staticmethod
    def config():
        config = material_config()
        config["resources"] = {
            "enabled": True,
            "forest_regeneration_rate": 0,
        }
        config["materials"]["resources"].append({
            "id": "timber",
            "unit_weight": 2,
            "decay_rate": 0,
            "source": {
                "spatial_resource": "forest_cover",
                "stock_per_unit": 2,
                "max_per_cycle": 3,
                "minimum_ratio": 0.2,
                "skill": "forestry",
            },
        })
        config["materials"]["items"].append({
            "id": "plank",
            "unit_weight": 1,
            "decay_rate": 0,
            "base_value": 3,
        })
        config["materials"]["recipes"].append({
            "id": "saw_plank",
            "inputs": {"timber": 1},
            "tools": ["stone_tool"],
            "skill": "forestry",
            "cycles": 1,
            "labor": 1,
            "outputs": {"plank": 2},
        })
        config["materials"]["initial_stock"] = {"stone_tool": 1}
        config["materials"]["targets"] = {"plank": 10}
        return config

    @staticmethod
    def world(width=1):
        from core.entities import EntityManager

        return {
            "width": width,
            "height": 1,
            "cycle": 1,
            "elev": [[0.2 for _ in range(width)]],
            "riv": [[0 for _ in range(width)]],
            "entities": EntityManager(),
            "diplomacy": {},
        }

    @staticmethod
    def settlement(entity_id, config, pos, *, workers=True):
        citizens = []
        if workers:
            citizens.append(SimpleNamespace(
                is_dead=False,
                character={"skills": {"forestry": 0}},
            ))
        return SimpleNamespace(
            entity_id=entity_id,
            config=config,
            pos=pos,
            citizens=citizens,
            food_stock=0,
            max_food=100,
            is_expired=False,
            culture={"name": "Test"},
        )

    def test_sourcing_is_conservative_idempotent_and_respects_ecological_floor(self):
        from core.production import ProductionService, source_spatial_inputs
        from core.resources import ResourceSystem
        from core.stockpiles import StockpileService

        config = self.config()
        world = self.world()
        forest = ResourceSystem(world, config)
        grid = forest.state["grids"]["forest_cover"]
        grid["capacity"][0][0] = 10
        grid["stock"][0][0] = 10
        settlement = self.settlement(110, config, (0, 0))
        service = ProductionService(settlement, config)
        service.plan(1)

        first = source_spatial_inputs(service, settlement.citizens, world)
        repeated = source_spatial_inputs(service, settlement.citizens, world)
        service.stockpile.withdraw("timber", 1)
        world["cycle"] = 2
        service.plan(2)
        second = source_spatial_inputs(service, settlement.citizens, world)
        service.stockpile.withdraw("timber", 1)
        world["cycle"] = 3
        service.plan(3)
        third = source_spatial_inputs(service, settlement.citizens, world)
        service.stockpile.withdraw("timber", 1)
        world["cycle"] = 4
        service.plan(4)
        fourth = source_spatial_inputs(service, settlement.citizens, world)
        service.stockpile.withdraw("timber", 1)
        world["cycle"] = 5
        service.plan(5)
        exhausted = source_spatial_inputs(service, settlement.citizens, world)

        self.assertEqual(first, {"timber": 1.0})
        self.assertEqual(repeated, {})
        self.assertEqual(second, {"timber": 1.0})
        self.assertEqual(third, {"timber": 1.0})
        self.assertEqual(fourth, {"timber": 1.0})
        self.assertEqual(exhausted, {})
        self.assertEqual(forest.available("forest_cover", 0, 0), 2.0)
        self.assertEqual(StockpileService(settlement, config).quantity("timber"), 0.0)
        self.assertEqual(
            world["metrics"]["flows"]["materials"]["sourced"],
            {"timber": 4.0},
        )

    def test_sourcing_requires_a_living_worker_and_available_capacity(self):
        from core.production import ProductionService, source_spatial_inputs
        from core.resources import ResourceSystem

        config = self.config()
        world = self.world()
        forest = ResourceSystem(world, config)
        before = forest.available("forest_cover", 0, 0)
        settlement = self.settlement(111, config, (0, 0), workers=False)
        service = ProductionService(settlement, config)
        service.plan(1)

        self.assertEqual(source_spatial_inputs(service, [], world), {})
        self.assertEqual(forest.available("forest_cover", 0, 0), before)

    def test_forest_location_enables_planks_while_forestless_location_cannot_produce(self):
        from core.production import advance_settlement_production
        from core.resources import ResourceSystem
        from core.stockpiles import StockpileService

        config = self.config()
        world = self.world(width=2)
        resources = ResourceSystem(world, config)
        forest = resources.state["grids"]["forest_cover"]
        forest["capacity"][0] = [10, 10]
        forest["stock"][0] = [10, 0]
        wooded = self.settlement(112, config, (0, 0))
        barren = self.settlement(113, config, (1, 0))

        wooded_result = advance_settlement_production(wooded, world)
        barren_result = advance_settlement_production(barren, world)

        self.assertEqual(wooded_result["sourced"], {"timber": 1.0})
        self.assertEqual(wooded_result["order"]["status"], "completed")
        self.assertEqual(StockpileService(wooded, config).quantity("plank"), 2.0)
        self.assertEqual(barren_result["sourced"], {})
        self.assertEqual(barren_result["order"]["status"], "waiting")
        self.assertEqual(StockpileService(barren, config).quantity("plank"), 0.0)

class InfrastructureTests(unittest.TestCase):
    @staticmethod
    def config():
        config = material_config()
        materials = config["materials"]
        materials["resources"][0]["decay_rate"] = 0
        materials["items"].append({
            "id": "granary_kit",
            "unit_weight": 1,
            "decay_rate": 0,
            "base_value": 20,
        })
        materials["recipes"].append({
            "id": "build_granary",
            "inputs": {"raw_food": 4},
            "tools": ["stone_tool"],
            "skill": "construction",
            "cycles": 1,
            "labor": 1,
            "outputs": {"granary_kit": 1},
        })
        materials["infrastructures"] = [{
            "id": "granary",
            "kit_good_id": "granary_kit",
            "max_level": 1,
            "capacity_bonus": 50,
        }]
        materials["targets"] = {"granary_kit": 1}
        materials["initial_stock"] = {"stone_tool": 1}
        return config

    @staticmethod
    def settlement(config):
        return SimpleNamespace(
            entity_id=120,
            config=config,
            pos=(0, 0),
            citizens=[SimpleNamespace(
                is_dead=False,
                character={"skills": {"construction": 0}},
            )],
            food_stock=0,
            max_food=100,
            is_expired=False,
            culture={"name": "Test"},
        )

    def test_validator_rejects_invalid_infrastructure_references_and_bounds(self):
        from core.materials import catalog_validation_errors

        section = self.config()["materials"]
        section["infrastructures"] = [
            {
                "id": "granary",
                "kit_good_id": "missing",
                "max_level": 0,
                "capacity_bonus": -1,
            },
            {
                "id": "granary",
                "kit_good_id": "granary_kit",
                "max_level": 1,
                "capacity_bonus": 1,
                "maintenance": {"missing": 1, "raw_food": 0},
                "repair_amount": 0,
                "hazard_damage": {"flood": -1},
            },
        ]

        errors = catalog_validation_errors(section)

        self.assertIn("reference:materials.infrastructures.granary.kit_good_id:missing", errors)
        self.assertIn("range:materials.infrastructures.granary.max_level:positive", errors)
        self.assertIn("range:materials.infrastructures.granary.capacity_bonus:positive", errors)
        self.assertIn("duplicate:materials.infrastructure:granary", errors)
        self.assertIn(
            "reference:materials.infrastructures.granary.maintenance:missing",
            errors,
        )
        self.assertIn(
            "range:materials.infrastructures.granary.maintenance.raw_food:positive",
            errors,
        )
        self.assertIn("range:materials.infrastructures.granary.repair_amount:positive", errors)
        self.assertIn("range:materials.infrastructures.granary.hazard_damage.flood:positive", errors)

    def test_granary_consumes_one_kit_and_increases_capacity_defensively(self):
        from core.infrastructure import InfrastructureService
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config = self.config()
        settlement = self.settlement(config)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("granary_kit", 1)
        service = InfrastructureService(settlement, config)

        installed = service.install_available(cycle=1)
        repeated = service.install_available(cycle=2)
        snapshot = service.snapshot()
        snapshot["levels"]["granary"] = 99
        unnecessary_orders = ProductionService(settlement, config).plan(cycle=3)

        self.assertEqual(installed, {"granary": 1})
        self.assertEqual(repeated, {})
        self.assertEqual(service.level("granary"), 1)
        self.assertEqual(StockpileService(settlement, config).capacity, 150.0)
        self.assertEqual(StockpileService(settlement, config).quantity("granary_kit"), 0.0)
        self.assertEqual(settlement.infrastructure["levels"]["granary"], 1)
        self.assertEqual(unnecessary_orders, [])

    def test_damage_reduces_effective_capacity_and_repair_consumes_materials(self):
        from core.infrastructure import InfrastructureService
        from core.stockpiles import StockpileService

        config = self.config()
        definition = config["materials"]["infrastructures"][0]
        definition["maintenance"] = {"raw_food": 2}
        definition["repair_amount"] = 25
        settlement = self.settlement(config)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("granary_kit", 1)
        service = InfrastructureService(settlement, config)
        service.install_available(cycle=1)
        stockpile.deposit("raw_food", 2)

        damaged = service.damage("granary", 50)
        capacity_after_damage = stockpile.refresh_capacity()
        repaired = service.maintain(cycle=2)
        capacity_after_repair = stockpile.refresh_capacity()

        self.assertEqual(damaged, 50.0)
        self.assertEqual(capacity_after_damage, 125.0)
        self.assertEqual(repaired, {"granary": 25.0})
        self.assertEqual(capacity_after_repair, 137.5)
        self.assertEqual(stockpile.quantity("raw_food"), 0.0)
        self.assertEqual(service.condition("granary"), 75.0)

    def test_settlement_production_automatically_competes_for_repairs(self):
        from core.infrastructure import InfrastructureService
        from core.production import advance_settlement_production
        from core.stockpiles import StockpileService

        config = self.config()
        definition = config["materials"]["infrastructures"][0]
        definition["maintenance"] = {"raw_food": 2}
        definition["repair_amount"] = 25
        settlement = self.settlement(config)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("granary_kit", 1)
        infrastructure = InfrastructureService(settlement, config)
        infrastructure.install_available(cycle=1)
        infrastructure.damage("granary", 50)
        stockpile.deposit("raw_food", 2)

        result = advance_settlement_production(settlement, {"cycle": 2})

        self.assertEqual(result["maintenance"], {"granary": 25.0})
        self.assertEqual(stockpile.quantity("raw_food"), 0.0)
        self.assertEqual(infrastructure.condition("granary"), 75.0)
        self.assertEqual(
            StockpileService(settlement, config).capacity,
            137.5,
        )

    def test_hazard_damage_is_data_driven_and_bounded(self):
        from core.infrastructure import (
            InfrastructureService,
            damage_world_infrastructure,
        )
        from core.stockpiles import StockpileService

        config = self.config()
        definition = config["materials"]["infrastructures"][0]
        definition["hazard_damage"] = {"flood": 40}
        settlement = self.settlement(config)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("granary_kit", 1)
        infrastructure = InfrastructureService(settlement, config)
        infrastructure.install_available(cycle=1)
        world = {"entities": [settlement]}

        damaged = damage_world_infrastructure(
            world, config, "flood", severity=0.5
        )

        self.assertEqual(damaged, {settlement.entity_id: {"granary": 20.0}})
        self.assertEqual(infrastructure.condition("granary"), 80.0)

    def test_infrastructure_effects_scale_with_level_and_condition(self):
        from core.infrastructure import InfrastructureService
        from core.stockpiles import StockpileService
        from entities.constructs.base import Construct

        config = self.config()
        definition = config["materials"]["infrastructures"][0]
        definition["effects"] = {
            "production_speed_bonus": 1.0,
            "transport_cost_reduction": 0.2,
            "transport_loss_reduction": 0.4,
            "defense_bonus": 0.3,
            "trade_capacity_bonus": 2.0,
        }
        settlement = self.settlement(config)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("granary_kit", 1)
        service = InfrastructureService(settlement, config)
        service.install_available(cycle=1)

        self.assertEqual(service.effect("production_speed_bonus"), 1.0)
        self.assertEqual(service.effect("defense_bonus"), 0.3)
        self.assertEqual(Construct.get_defense_power(settlement), 0.3)
        settlement.political_modifiers = {"defense_multiplier": 2.0}
        self.assertEqual(Construct.get_defense_power(settlement), 0.6)
        settlement.political_modifiers = {}
        service.damage("granary", 50)
        self.assertEqual(service.effect("production_speed_bonus"), 0.5)
        self.assertEqual(service.effect("transport_cost_reduction"), 0.1)
        self.assertEqual(service.effect("transport_loss_reduction"), 0.2)
        self.assertEqual(Construct.get_defense_power(settlement), 0.15)

    def test_completed_order_installs_granary_and_records_observable_flow(self):
        from core.production import advance_settlement_production
        from core.stockpiles import StockpileService

        config = self.config()
        settlement = self.settlement(config)
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 4)
        world = {"cycle": 1}

        result = advance_settlement_production(settlement, world)

        self.assertEqual(result["order"]["recipe_id"], "build_granary")
        self.assertEqual(result["order"]["status"], "completed")
        self.assertEqual(result["infrastructure"], {"granary": 1})
        self.assertEqual(StockpileService(settlement, config).quantity("granary_kit"), 0.0)
        self.assertEqual(StockpileService(settlement, config).capacity, 150.0)
        self.assertEqual(
            world["metrics"]["flows"]["materials"]["infrastructure_built"],
            {"granary": 1.0},
        )

class MultiGoodMarketTests(unittest.TestCase):
    def market_config(self):
        config = material_config()
        config["materials"]["targets"] = {"food_ration": 10, "stone_tool": 2}
        config["materials"]["trade_reserve"] = {"food_ration": 2}
        config["economy"] = {
            "enabled": True,
            "initial_treasury": 100,
            "base_food_price": 1,
            "min_food_price": 0.5,
            "max_food_price": 10,
            "food_reserve": 0,
            "trade_capacity": 10,
            "transport_cost_per_tile": 0.1,
            "risk_cost_multiplier": 1.0,
        }
        return config

    @staticmethod
    def market(entity_id, config, treasury, pos=(0, 0)):
        return SimpleNamespace(
            entity_id=entity_id,
            config=config,
            pos=pos,
            economy={"treasury": float(treasury)},
        )

    def test_material_trade_conserves_good_and_money_and_updates_ledgers(self):
        from core.economy import ensure_economy, execute_material_trade
        from core.stockpiles import StockpileService

        config = self.market_config()
        origin = self.market(60, config, 10)
        target = self.market(61, config, 100)
        origin_stock = StockpileService(origin, config)
        target_stock = StockpileService(target, config)
        origin_stock.deposit("food_ration", 10)
        before_goods = origin_stock.quantity("food_ration") + target_stock.quantity("food_ration")
        before_money = ensure_economy(origin)["treasury"] + ensure_economy(target)["treasury"]

        transaction = execute_material_trade(origin, target, "food_ration", capacity=5)

        self.assertEqual(transaction.good_id, "food_ration")
        self.assertEqual(transaction.quantity, 5.0)
        self.assertEqual(
            origin_stock.quantity("food_ration") + target_stock.quantity("food_ration"),
            before_goods,
        )
        self.assertAlmostEqual(
            ensure_economy(origin)["treasury"] + ensure_economy(target)["treasury"],
            before_money,
        )
        self.assertEqual(ensure_economy(origin)["goods_exported"], {"food_ration": 5.0})
        self.assertEqual(ensure_economy(target)["goods_imported"], {"food_ration": 5.0})

    def test_scarcity_price_and_route_selection_favor_profitable_shortage(self):
        from core.economy import material_price, select_material_market
        from core.stockpiles import StockpileService

        config = self.market_config()
        origin = self.market(70, config, 10, (0, 0))
        abundant = self.market(71, config, 100, (1, 0))
        scarce = self.market(72, config, 100, (2, 0))
        StockpileService(origin, config).deposit("stone_tool", 10)
        StockpileService(abundant, config).deposit("stone_tool", 2)

        self.assertGreater(material_price(scarce, "stone_tool"), material_price(abundant, "stone_tool"))
        RandomService.initialize(1177)
        before = RandomService.get_state()
        choice = select_material_market(origin, [abundant, scarce], "stone_tool", capacity=1)

        self.assertEqual(RandomService.get_state(), before)
        self.assertIs(choice["target"], scarce)
        self.assertGreater(choice["expected_profit"], 0)
        self.assertIn("unit_price", choice)
        self.assertIn("transport_cost", choice)

    def test_transport_cost_and_losses_are_applied_and_accounted(self):
        from core.economy import ensure_economy, execute_material_trade
        from core.stockpiles import StockpileService

        config = self.market_config()
        config["economy"]["transport_cost_per_tile"] = 0.2
        config["economy"]["transport_loss_per_tile"] = 0.1
        origin = self.market(73, config, 10, (0, 0))
        target = self.market(74, config, 100, (5, 0))
        origin_stock = StockpileService(origin, config)
        target_stock = StockpileService(target, config)
        origin_stock.deposit("food_ration", 10)
        before_money = (
            ensure_economy(origin)["treasury"]
            + ensure_economy(target)["treasury"]
        )

        transaction = execute_material_trade(
            origin, target, "food_ration", capacity=4
        )

        self.assertEqual(transaction.shipped_quantity, 4.0)
        self.assertEqual(transaction.quantity, 2.0)
        self.assertEqual(transaction.lost_quantity, 2.0)
        self.assertEqual(transaction.transport_cost, 1.0)
        self.assertEqual(origin_stock.quantity("food_ration"), 6.0)
        self.assertEqual(target_stock.quantity("food_ration"), 2.0)
        self.assertEqual(
            ensure_economy(origin)["goods_lost_in_transit"],
            {"food_ration": 2.0},
        )
        self.assertAlmostEqual(
            ensure_economy(origin)["treasury"] + ensure_economy(target)["treasury"],
            before_money,
        )

    def test_real_trader_prefers_configured_material_rations_then_preserves_legacy_food(self):
        from entities.species.human.trader import Trader
        from core.stockpiles import StockpileService
        from tests.test_economy import settlement, trader_between

        config = self.market_config()
        config["materials"]["food_chain"] = {
            "recipe_id": "preserve_food",
            "raw_good_id": "raw_food",
            "ration_good_id": "food_ration",
        }
        origin = settlement("Origin", 90, 80, 100, config, treasury=10)
        target = settlement("Target", 91, 20, 100, config, treasury=100)
        StockpileService(origin, config).deposit("food_ration", 10)
        trader = trader_between(origin, target)
        before_legacy = origin.food_stock + target.food_stock

        origin_world = {}
        Trader._do_trade(trader, origin_world)

        self.assertEqual(StockpileService(origin, config).quantity("food_ration"), 2.0)
        self.assertEqual(StockpileService(target, config).quantity("food_ration"), 8.0)
        self.assertEqual(origin.food_stock + target.food_stock, before_legacy)
        self.assertEqual(origin.economy["goods_exported"], {"food_ration": 8.0})
        self.assertEqual(origin_world["metrics"]["flows"]["materials"]["trades"], 1)
        self.assertEqual(
            origin_world["metrics"]["flows"]["materials"]["traded"],
            {"food_ration": 8.0},
        )
    def test_material_trade_is_noop_below_reserve(self):
        from core.economy import execute_material_trade
        from core.stockpiles import StockpileService

        config = self.market_config()
        origin = self.market(80, config, 10)
        target = self.market(81, config, 100)
        StockpileService(origin, config).deposit("food_ration", 2)

        transaction = execute_material_trade(origin, target, "food_ration", capacity=5)

        self.assertEqual(transaction.quantity, 0.0)
        self.assertEqual(StockpileService(origin, config).quantity("food_ration"), 2.0)
class MaterialObservabilityAndPersistenceTests(unittest.TestCase):
    def observable_settlement(self):
        config = material_config()
        config["materials"]["targets"] = {"food_ration": 4}
        settlement = SimpleNamespace(
            entity_id=100,
            name="Workshop",
            pos=(0, 0),
            is_expired=False,
            culture={"name": "Test"},
            citizens=[],
            food_stock=10,
            max_food=100,
            config=config,
        )
        return config, settlement

    def test_inspection_exposes_defensive_stockpile_and_orders(self):
        from core.entities import EntityManager
        from core.inspection import inspect_entity
        from core.production import ProductionService
        from core.stockpiles import StockpileService

        config, settlement = self.observable_settlement()
        StockpileService(settlement, config).deposit("raw_food", 2)
        ProductionService(settlement, config).plan(cycle=1)
        manager = EntityManager()
        manager.add(settlement)
        world = {"entities": manager, "cycle": 1}

        inspected = inspect_entity(world, settlement.entity_id)
        inspected["entity"]["stockpile"]["goods"]["raw_food"] = -1
        inspected["entity"]["production"]["orders"][0]["status"] = "corrupted"

        self.assertEqual(settlement.stockpile["goods"]["raw_food"], 2.0)
        self.assertEqual(settlement.production["orders"][0]["status"], "waiting")

    def test_metrics_aggregate_material_state_and_causal_flows(self):
        from core.entities import EntityManager
        from core.production import advance_settlement_production
        from core.simulation_metrics import SimulationMetrics

        config, settlement = self.observable_settlement()
        config["materials"]["food_chain"] = {
            "recipe_id": "preserve_food",
            "raw_good_id": "raw_food",
            "ration_good_id": "food_ration",
        }
        config["materials"]["initial_stock"] = {"stone_tool": 1}
        config["materials"]["recipes"][0].update({
            "inputs": {"raw_food": 2}, "outputs": {"food_ration": 2}, "cycles": 1,
        })
        settlement.citizens = [SimpleNamespace(is_dead=False, character={"skills": {}})]
        manager = EntityManager()
        manager.add(settlement)
        world = {"entities": manager, "cycle": 1}

        advance_settlement_production(settlement, world)
        snapshot = SimulationMetrics(world).snapshot()

        self.assertEqual(snapshot["flows"]["materials"]["orders_created"], 1)
        self.assertEqual(snapshot["flows"]["materials"]["orders_completed"], 1)
        self.assertEqual(snapshot["flows"]["materials"]["produced"], {"food_ration": 2.0})
        self.assertEqual(snapshot["state"]["stockpile_goods"]["food_ration"], 2.0)
        self.assertGreater(snapshot["state"]["stockpile_capacity"], 0)

    def test_checkpoint_preserves_active_order_and_stockpile(self):
        from core.production import ProductionService
        from core.infrastructure import InfrastructureService
        from core.simulation_engine import SimulationEngine
        from core.stockpiles import StockpileService

        config = template_config()
        config["materials"]["enabled"] = True
        config["materials"]["recipes"][0]["cycles"] = 2
        engine = SimulationEngine.create(config, seed=1199, width=24, height=12)
        settlement = next(
            entity for entity in engine.world["entities"] if hasattr(entity, "citizens")
        )
        stockpile = StockpileService(settlement, config)
        stockpile.deposit("raw_food", 20)
        service = ProductionService(settlement, config)
        service.plan(cycle=1)
        service.advance(worker=settlement.citizens[0], cycle=1)

        stockpile.deposit("granary_kit", 1)
        InfrastructureService(settlement, config).install_available(cycle=2)
        with tempfile.TemporaryDirectory() as directory:
            save_path = Path(directory) / "materials.save"
            engine.save(save_path)
            restored = SimulationEngine.load(save_path)

        restored_settlement = next(
            entity for entity in restored.world["entities"]
            if getattr(entity, "entity_id", None) == settlement.entity_id
        )
        self.assertEqual(restored_settlement.stockpile, settlement.stockpile)
        self.assertEqual(restored_settlement.production, settlement.production)
        self.assertEqual(restored_settlement.infrastructure, settlement.infrastructure)

if __name__ == "__main__":
    unittest.main()
