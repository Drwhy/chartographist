import json
import unittest
from unittest import mock
from types import MethodType, SimpleNamespace

from core.entities import EntityManager
from core.random_service import RandomService
from core.simulation_engine import SimulationEngine


def observed_world(*entities, cycle=0):
    manager = EntityManager()
    for entity in entities:
        manager.add(entity)
    return {
        "width": 4,
        "height": 3,
        "cycle": cycle,
        "entities": manager,
        "diplomacy": {},
    }


def settlement(*, population=3, food=30, treasury=75.0, transactions=2):
    citizens = [SimpleNamespace(is_dead=False) for _ in range(population)]
    return SimpleNamespace(
        is_expired=False,
        citizens=citizens,
        food_stock=food,
        max_food=100,
        config={"economy": {"enabled": True}},
        economy={
            "treasury": treasury,
            "food_imported": 4,
            "food_exported": 3,
            "trade_spent": 4.0,
            "trade_earned": 3.0,
            "transactions": transactions,
            "last_food_price": 1.5,
        },
    )


class SimulationMetricsTests(unittest.TestCase):
    def test_service_initializes_serializable_state_and_returns_defensive_snapshots(self):
        from core.simulation_metrics import SimulationMetrics

        city = settlement()
        world = observed_world(city)
        service = SimulationMetrics(world)

        snapshot = service.snapshot()

        self.assertEqual(snapshot["cycle"], 0)
        self.assertEqual(snapshot["state"]["population"], 3)
        self.assertEqual(snapshot["state"]["settlements"], 1)
        self.assertEqual(snapshot["state"]["food_stock"], 30)
        self.assertEqual(snapshot["state"]["treasury"], 75.0)
        self.assertEqual(snapshot["flows"]["food"]["produced"], 0)
        json.dumps(world["metrics"])

        snapshot["state"]["population"] = 999
        snapshot["flows"]["food"]["produced"] = 999
        self.assertEqual(service.snapshot()["state"]["population"], 3)
        self.assertEqual(world["metrics"]["flows"]["food"]["produced"], 0)

    def test_food_and_demographic_flows_accumulate_without_using_randomness(self):
        from core.simulation_metrics import SimulationMetrics

        world = observed_world()
        service = SimulationMetrics(world)
        RandomService.initialize(8128)
        before = RandomService.get_state()

        service.record_food("produced", 12, source="agriculture")
        service.record_food("consumed", 7)
        service.record_demography("births", 2)
        service.record_demography("deaths", 1)
        service.record_activity("combat", "raids", 1)

        self.assertEqual(RandomService.get_state(), before)
        snapshot = service.snapshot()
        self.assertEqual(snapshot["flows"]["food"]["produced"], 12)
        self.assertEqual(snapshot["flows"]["food_sources"]["agriculture"], 12)
        self.assertEqual(snapshot["flows"]["food"]["consumed"], 7)
        self.assertEqual(snapshot["flows"]["demography"], {"births": 2, "deaths": 1})
        self.assertEqual(snapshot["flows"]["combat"]["raids"], 1)

    def test_old_metric_storage_is_migrated_lazily(self):
        from core.simulation_metrics import SimulationMetrics

        world = observed_world()
        world["metrics"] = {"flows": {"food": {"produced": 5}}}

        snapshot = SimulationMetrics(world).snapshot()

        self.assertEqual(snapshot["flows"]["food"]["produced"], 5)
        self.assertIn("consumed", snapshot["flows"]["food"])
        self.assertIn("demography", snapshot["flows"])


class ObservedEngineTests(unittest.TestCase):
    @staticmethod
    def engine(seed):
        city = settlement(population=2, food=10)
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.world = observed_world(city)
        engine.stats = {"year": 0, "logs": []}
        engine.config = {}
        RandomService.initialize(seed)

        def step(self):
            self.world["cycle"] += 1
            city.food_stock += RandomService.randint(1, 3)
            return self.world["cycle"]

        engine.step = MethodType(step, engine)
        return engine

    def test_engine_exposes_defensive_metrics_and_samples_final_cycle(self):
        engine = self.engine(42)

        series = engine.run_observed(5, sample_every=2)

        self.assertEqual([sample["cycle"] for sample in series], [2, 4, 5])
        self.assertEqual(engine.world["cycle"], 5)
        snapshot = engine.get_metrics_snapshot()
        snapshot["state"]["food_stock"] = -1
        self.assertGreater(engine.get_metrics_snapshot()["state"]["food_stock"], 0)

    def test_observation_does_not_change_simulation_or_prng_state(self):
        plain = self.engine(77)
        plain.run(7)
        plain_food = plain.get_metrics_snapshot()["state"]["food_stock"]
        plain_rng = RandomService.get_state()

        observed = self.engine(77)
        observed.run_observed(7, sample_every=3)
        observed_food = observed.get_metrics_snapshot()["state"]["food_stock"]
        observed_rng = RandomService.get_state()

        self.assertEqual(observed_food, plain_food)
        self.assertEqual(observed_rng, plain_rng)

    def test_run_observed_validates_arguments_without_advancing_world(self):
        engine = self.engine(1)

        with self.assertRaises(ValueError):
            engine.run_observed(-1, sample_every=1)
        with self.assertRaises(ValueError):
            engine.run_observed(1, sample_every=0)

        self.assertEqual(engine.world["cycle"], 0)


class ObservatoryBatchTests(unittest.TestCase):
    def test_batch_report_is_json_serializable_and_aggregates_final_samples(self):
        from tools.observatory import run_seed_batch

        report = run_seed_batch(
            seeds=[1, 2, 3],
            cycles=4,
            sample_every=2,
            engine_factory=ObservedEngineTests.engine,
        )

        self.assertEqual(report["settings"], {"cycles": 4, "sample_every": 2, "seeds": [1, 2, 3]})
        self.assertEqual(len(report["runs"]), 3)
        self.assertEqual(report["summary"]["runs"], 3)
        self.assertEqual(report["summary"]["extinction_rate"], 0.0)
        self.assertEqual(report["summary"]["median"]["population"], 2)
        json.dumps(report)

    def test_empty_seed_batch_is_rejected(self):
        from tools.observatory import run_seed_batch

        with self.assertRaises(ValueError):
            run_seed_batch([], 10, 2, ObservedEngineTests.engine)




class InitialSettlementSeedingTests(unittest.TestCase):
    class FakeCity:
        def __init__(self, x, y, culture, config):
            self.x = x
            self.y = y
            self.culture = culture
            self.config = config
            self.name = f"City-{x}-{y}"
            self.religion = None
            self.is_expired = False

    @staticmethod
    def world(elevation, rivers):
        return {
            "width": len(elevation[0]),
            "height": len(elevation),
            "elev": elevation,
            "riv": rivers,
            "entities": EntityManager(),
            "cycle": 0,
        }

    def test_historical_random_placement_is_preserved_when_it_succeeds(self):
        from entities.spawn_system import seed_initial_cities

        world = self.world([[0.2]], [[1]])
        config = {"initial_cities": 1, "cultures": [{"name": "A"}]}

        with (
            mock.patch("entities.constructs.city.City", self.FakeCity),
            mock.patch("entities.spawn_system.RandomService.randint", return_value=0),
            mock.patch("entities.spawn_system.RandomService.choice", side_effect=lambda values: values[0]),
        ):
            report = seed_initial_cities(world, config)

        self.assertEqual(report["placed"], 1)
        self.assertEqual(report["attempts"], 1)
        self.assertFalse(report["fallback_used"])
        city = next(iter(world["entities"]))
        self.assertEqual((city.x, city.y), (0, 0))

    def test_ranked_fallback_places_a_city_after_legacy_attempts_fail(self):
        from entities.spawn_system import seed_initial_cities

        world = self.world(
            [[0.0, 0.0], [0.0, 0.25]],
            [[0, 0], [0, 2]],
        )
        config = {"initial_cities": 1, "cultures": [{"name": "A"}]}

        with (
            mock.patch("entities.constructs.city.City", self.FakeCity),
            mock.patch("entities.spawn_system.RandomService.randint", return_value=0),
            mock.patch("entities.spawn_system.RandomService.choice", side_effect=lambda values: values[0]),
        ):
            report = seed_initial_cities(world, config)

        city = next(iter(world["entities"]))
        self.assertEqual((city.x, city.y), (1, 1))
        self.assertEqual(report["attempts"], 100)
        self.assertEqual(report["placed"], 1)
        self.assertTrue(report["fallback_used"])
        self.assertEqual(report["status"], "complete")
        self.assertEqual(world["metrics"]["initialization"]["placed_settlements"], 1)

    def test_impossible_request_returns_explicit_deterministic_status(self):
        from entities.spawn_system import seed_initial_cities

        world = self.world([[0.0, 0.0]], [[0, 0]])
        config = {"initial_cities": 2, "cultures": [{"name": "A"}]}

        with (
            mock.patch("entities.constructs.city.City", self.FakeCity),
            mock.patch("entities.spawn_system.RandomService.randint", return_value=0),
        ):
            report = seed_initial_cities(world, config)

        self.assertEqual(report["placed"], 0)
        self.assertEqual(report["requested"], 2)
        self.assertTrue(report["fallback_used"])
        self.assertEqual(report["status"], "insufficient_habitable_sites")
        self.assertEqual(len(world["entities"]), 0)



class FaunaPopulationLimitTests(unittest.TestCase):
    @staticmethod
    def species(name="hare"):
        return {
            "species": name,
            "name": name.title(),
            "char": "h",
            "diet": "herbivore",
            "locomotion": "land",
            "energy": 140,
            "max_energy": 150,
            "repro_threshold": 120,
            "spawn": {"elevation_min": 0.0, "elevation_max": 1.0, "chance": 1.0},
        }

    @staticmethod
    def world(*animals):
        manager = EntityManager()
        for animal in animals:
            manager.add(animal)
        return {
            "width": 2,
            "height": 2,
            "cycle": 100,
            "elev": [[0.2, 0.2], [0.2, 0.2]],
            "riv": [[0, 0], [0, 0]],
            "entities": manager,
        }

    def test_enabled_global_capacity_blocks_birth_without_random_draw(self):
        from entities.species.animal.base import Animal

        config = {
            "ecology": {"population_limits": {"enabled": True, "global": 1}},
            "max_fauna": 10,
        }
        parent = Animal(0, 0, config, self.species())
        world = self.world(parent)
        RandomService.initialize(99)
        before = RandomService.get_state()

        parent.process_long_term_logic(world)

        self.assertEqual(len(world["entities"]), 1)
        self.assertEqual(parent.energy, 140)
        self.assertEqual(RandomService.get_state(), before)

    def test_missing_population_limit_section_preserves_legacy_reproduction(self):
        from entities.species.animal.base import Animal

        config = {"max_fauna": 1}
        parent = Animal(0, 0, config, self.species())
        world = self.world(parent)
        RandomService.initialize(2)

        parent.process_long_term_logic(world)

        self.assertEqual(len(world["entities"]), 2)
        self.assertEqual(parent.energy, 70)

    def test_species_capacity_is_shared_by_spawn_and_reproduction(self):
        from core.ecology_limits import can_add_fauna
        from entities.species.animal.base import Animal

        config = {
            "ecology": {
                "population_limits": {
                    "enabled": True,
                    "global": 5,
                    "per_species": {"hare": 1},
                }
            },
            "fauna": [self.species()],
            "max_fauna": 10,
        }
        parent = Animal(0, 0, config, self.species())
        world = self.world(parent)

        self.assertFalse(can_add_fauna(world, config, self.species(), 1, 1))

        RandomService.initialize(7)
        before = RandomService.get_state()
        from entities.spawn_system import _spawn_fauna
        _spawn_fauna(world, config, 2, 2)

        self.assertEqual(len(world["entities"]), 1)
        self.assertEqual(RandomService.get_state(), before)



class PhaseEightConfigurationTests(unittest.TestCase):
    @staticmethod
    def base_config():
        from pathlib import Path

        return json.loads(Path("template.json").read_text(encoding="utf-8"))

    def test_validator_accepts_population_limits_and_rejects_invalid_capacities(self):
        from core.config_validator import ConfigValidationError, validate_config

        valid = self.base_config()
        valid["ecology"] = {
            "population_limits": {
                "enabled": True,
                "global": 20,
                "per_species": {"hare": 4},
                "per_biome": {"grassland": 8},
            }
        }
        validate_config(valid)

        invalid = self.base_config()
        invalid["ecology"] = {
            "population_limits": {
                "enabled": "yes",
                "global": -1,
                "per_species": {"hare": -2},
                "per_biome": [],
            }
        }
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:ecology.population_limits.enabled:bool", caught.exception.errors)
        self.assertIn("range:ecology.population_limits.global:non_negative", caught.exception.errors)
        self.assertIn("range:ecology.population_limits.per_species.hare:non_negative", caught.exception.errors)
        self.assertIn("type:ecology.population_limits.per_biome:dict", caught.exception.errors)

    def test_validator_rejects_invalid_food_balance_values(self):
        from core.config_validator import ConfigValidationError, validate_config

        invalid = self.base_config()
        invalid["food_balance"] = {
            "enabled": True,
            "generic_labor_yield": -1,
            "storage_loss_rate": 1.5,
            "specialization_window": 1,
            "specialization_food_ratio": 2.0,
        }

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:food_balance.generic_labor_yield:non_negative", caught.exception.errors)
        self.assertIn("range:food_balance.storage_loss_rate:0_1", caught.exception.errors)
        self.assertIn("range:food_balance.specialization_window:min_2", caught.exception.errors)
        self.assertIn("range:food_balance.specialization_food_ratio:0_1", caught.exception.errors)


class FoodBalanceTests(unittest.TestCase):
    def test_generic_labor_preserves_legacy_yield_without_food_balance(self):
        from entities.species.human.base import Human

        person = Human.__new__(Human)
        person.config = {}
        city = SimpleNamespace(food_stock=4, max_food=10)

        person.work(city, observed_world())

        self.assertEqual(city.food_stock, 5)

    def test_enabled_food_balance_can_remove_implicit_generic_self_sufficiency(self):
        from entities.species.human.base import Human

        person = Human.__new__(Human)
        person.config = {
            "food_balance": {
                "enabled": True,
                "generic_labor_yield": 0,
            }
        }
        city = SimpleNamespace(food_stock=4, max_food=10)

        world = observed_world()
        person.work(city, world)

        self.assertEqual(city.food_stock, 4)
        self.assertEqual(
            world["metrics"]["flows"]["food_sources"].get("generic_labor", 0),
            0,
        )

    def test_food_helpers_reconcile_created_consumed_and_lost_quantities(self):
        from core.food_balance import add_food, apply_storage_loss, consume_food

        city = SimpleNamespace(
            food_stock=50,
            max_food=100,
            config={
                "food_balance": {
                    "enabled": True,
                    "storage_loss_rate": 0.1,
                }
            },
        )
        world = observed_world()
        RandomService.initialize(321)
        before = RandomService.get_state()

        self.assertEqual(add_food(city, world, 20, source="agriculture"), 20)
        self.assertEqual(consume_food(city, world, 7), 7)
        self.assertEqual(apply_storage_loss(city, world), 6)

        self.assertEqual(city.food_stock, 57)
        self.assertEqual(RandomService.get_state(), before)
        food = world["metrics"]["flows"]["food"]
        self.assertEqual(food["produced"], 20)
        self.assertEqual(food["consumed"], 7)
        self.assertEqual(food["lost"], 6)
        self.assertEqual(world["metrics"]["flows"]["food_sources"]["agriculture"], 20)



class ObservatoryProfilesAndPersistenceTests(unittest.TestCase):
    def test_profiles_cover_short_long_and_midpoint_resume_runs(self):
        from tools.observatory import PROFILES

        self.assertEqual(PROFILES["short"]["cycles"], 120)
        self.assertEqual(PROFILES["long"]["cycles"], 1200)
        self.assertEqual(PROFILES["resume"]["resume_at"], 600)
        self.assertEqual(PROFILES["resume"]["cycles"], 1200)

    def test_csv_export_uses_final_state_without_recomputing_runs(self):
        from tools.observatory import report_to_csv, run_seed_batch

        report = run_seed_batch([4, 5], 2, 1, ObservedEngineTests.engine)
        output = report_to_csv(report)

        self.assertIn("seed,cycle,population,settlements,fauna", output)
        self.assertIn("4,2,2,1,0", output)
        self.assertIn("5,2,2,1,0", output)

    def test_metric_flows_survive_checkpoint_and_old_world_migrates(self):
        import tempfile
        from pathlib import Path

        from core.simulation_metrics import SimulationMetrics

        world = observed_world()
        world.update({
            "elev": [[0.2] * 4 for _ in range(3)],
            "riv": [[0] * 4 for _ in range(3)],
            "chronicles": [],
            "next_chronicle_id": 1,
            "next_relation_id": 1,
        })
        engine = SimulationEngine(world, {"year": 0, "logs": []}, {})
        SimulationMetrics(world).record_food("produced", 9, source="agriculture")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.save"
            engine.save(path)
            restored = SimulationEngine.load(path)

        self.assertEqual(
            restored.get_metrics_snapshot()["flows"]["food"]["produced"],
            9,
        )
        restored.world.pop("metrics")
        self.assertEqual(
            restored.get_metrics_snapshot()["flows"]["food"]["produced"],
            0,
        )



class FoodSpecializationTrendTests(unittest.TestCase):
    def test_legacy_specialization_keeps_instant_threshold(self):
        from core.food_balance import needs_food_specialization

        city = SimpleNamespace(food_stock=40, max_food=100, config={})

        self.assertTrue(needs_food_specialization(city, legacy_threshold=50))

    def test_enabled_specialization_requires_a_sustained_ratio_trend(self):
        from core.food_balance import needs_food_specialization, update_food_trend

        city = SimpleNamespace(
            food_stock=80,
            max_food=100,
            config={
                "food_balance": {
                    "enabled": True,
                    "specialization_window": 3,
                    "specialization_food_ratio": 0.7,
                }
            },
        )

        update_food_trend(city)
        city.food_stock = 40
        self.assertFalse(needs_food_specialization(city, legacy_threshold=50))
        city.food_stock = 60
        update_food_trend(city)
        city.food_stock = 40
        update_food_trend(city)

        self.assertTrue(needs_food_specialization(city, legacy_threshold=50))
        self.assertEqual(city.food_ratio_history, [0.8, 0.6, 0.4])


class ObservatoryActivationTests(unittest.TestCase):
    def test_batch_summary_reports_systems_that_never_activate(self):
        from tools.observatory import run_seed_batch

        report = run_seed_batch([10, 11], 3, 1, ObservedEngineTests.engine)
        activation = report["summary"]["activation_rate"]

        self.assertEqual(activation["transactions"], 1.0)
        self.assertEqual(activation["births"], 0.0)
        self.assertEqual(activation["raids"], 0.0)
        self.assertEqual(activation["climate_events"], 0.0)
        self.assertEqual(report["summary"]["never_activated"], [
            "births",
            "raids",
            "climate_events",
        ])

if __name__ == "__main__":
    unittest.main()
