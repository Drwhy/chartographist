import copy
import json
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from core.entities import EntityManager
from core.random_service import RandomService


RESOURCE_NAMES = {
    "biomass",
    "soil_fertility",
    "surface_water",
    "fish_stock",
    "forest_cover",
}


def resource_config(**overrides):
    settings = {
        "enabled": True,
        "regeneration_interval": 1,
        "biomass_regeneration_rate": 0.08,
        "soil_regeneration_rate": 0.02,
        "water_regeneration_rate": 0.1,
        "fish_regeneration_rate": 0.06,
        "forest_regeneration_rate": 0.01,
        "winter_mortality_rate": 0.05,
        "drought_pressure": 0.8,
        "flood_recovery": 0.2,
        "agriculture_soil_cost": 0.02,
        "agriculture_min_support": 0.85,
        "biomass_capacity_scale": 5000.0,
        "fish_capacity_scale": 1000.0,
    }
    settings.update(overrides)
    return {
        "resources": settings,
        "climate": {
            "enabled": True,
            "seasonal_amplitude": 0.0,
            "base_humidity": 0.5,
            "river_humidity_bonus": 0.25,
        },
        "biomes": {"grassland": "grass", "temperate_forest": "forest"},
        "water": {"ocean": "ocean", "shore": "shore"},
    }


def resource_world(width=3, height=2):
    return {
        "width": width,
        "height": height,
        "cycle": 0,
        "elev": [
            [0.2 + (x * 0.03) for x in range(width)]
            for _ in range(height)
        ],
        "riv": [
            [1 if x == 0 else 0 for x in range(width)]
            for _ in range(height)
        ],
        "entities": EntityManager(),
        "diplomacy": {},
        "climate": {
            "season": "spring",
            "season_index": 1,
            "temperature_anomaly": 0.0,
            "precipitation_anomaly": 0.0,
            "drought_severity": 0.0,
            "flood_severity": 0.0,
            "last_update_cycle": 0,
        },
    }


class ResourceModelTests(unittest.TestCase):
    def test_generation_is_bounded_deterministic_serializable_and_uses_no_randomness(self):
        from core.resources import ResourceSystem

        config = resource_config()
        RandomService.initialize(912)
        before = RandomService.get_state()

        first_world = resource_world()
        first = ResourceSystem(first_world, config).snapshot()
        second_world = resource_world()
        second = ResourceSystem(second_world, config).snapshot()

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(first, second)
        self.assertEqual(set(first["grids"]), RESOURCE_NAMES)
        self.assertEqual(first["version"], 1)
        json.dumps(first_world["resources"])

        for resource in first["grids"].values():
            for key in ("stock", "capacity", "regeneration_rate"):
                self.assertEqual(len(resource[key]), 2)
                self.assertTrue(all(len(row) == 3 for row in resource[key]))
            for y in range(2):
                for x in range(3):
                    stock = resource["stock"][y][x]
                    capacity = resource["capacity"][y][x]
                    rate = resource["regeneration_rate"][y][x]
                    self.assertTrue(math.isfinite(stock))
                    self.assertTrue(math.isfinite(capacity))
                    self.assertTrue(math.isfinite(rate))
                    self.assertGreaterEqual(stock, 0)
                    self.assertLessEqual(stock, capacity)
                    self.assertGreaterEqual(rate, 0)

    def test_disabled_or_old_world_is_initialized_lazily_without_resources(self):
        from core.resources import ResourceSystem

        world = resource_world()
        service = ResourceSystem(world, {})

        self.assertFalse(service.enabled)
        self.assertEqual(service.snapshot()["grids"], {})
        self.assertEqual(service.summary()["enabled"], False)

    def test_partial_old_storage_is_migrated_without_losing_existing_stock(self):
        from core.resources import ResourceSystem

        world = resource_world()
        world["resources"] = {
            "version": 1,
            "enabled": True,
            "grids": {
                "biomass": {
                    "stock": [[3.0, 3.0, 3.0], [3.0, 3.0, 3.0]],
                    "capacity": [[5.0, 5.0, 5.0], [5.0, 5.0, 5.0]],
                    "regeneration_rate": [[0.1, 0.1, 0.1], [0.1, 0.1, 0.1]],
                }
            },
        }

        snapshot = ResourceSystem(world, resource_config()).snapshot()

        self.assertEqual(snapshot["grids"]["biomass"]["stock"][0][0], 3.0)
        self.assertEqual(set(snapshot["grids"]), RESOURCE_NAMES)
        self.assertIn("disturbances", snapshot)

    def test_tile_and_world_views_are_defensive_and_reject_out_of_bounds(self):
        from core.resources import ResourceSystem

        service = ResourceSystem(resource_world(), resource_config())

        tile = service.tile_snapshot(0, 0)
        summary = service.summary()
        tile["biomass"]["stock"] = -1
        summary["resources"]["biomass"]["stock"] = -1

        self.assertGreater(service.tile_snapshot(0, 0)["biomass"]["stock"], 0)
        self.assertGreater(service.summary()["resources"]["biomass"]["stock"], 0)
        with self.assertRaises(IndexError):
            service.tile_snapshot(-1, 0)
        with self.assertRaises(IndexError):
            service.tile_snapshot(3, 0)


    def test_repeated_service_construction_reuses_complete_grid_storage(self):
        from unittest import mock
        from core.resources import ResourceSystem

        world = resource_world()
        first = ResourceSystem(world, resource_config())
        grids = first.state["grids"]

        with mock.patch.object(
            ResourceSystem,
            "_generate_state",
            side_effect=AssertionError("complete grids must be reused"),
        ):
            second = ResourceSystem(world, resource_config())

        self.assertIs(second.state["grids"], grids)


class ResourceRegenerationTests(unittest.TestCase):
    def test_regeneration_is_bounded_and_runs_only_at_configured_cadence(self):
        from core.resources import ResourceSystem

        config = resource_config(regeneration_interval=2)
        world = resource_world()
        service = ResourceSystem(world, config)
        biomass = service.state["grids"]["biomass"]
        biomass["stock"][0][0] = 0.0
        capacity = biomass["capacity"][0][0]

        world["cycle"] = 1
        service.advance()
        self.assertEqual(biomass["stock"][0][0], 0.0)

        world["cycle"] = 2
        service.advance()
        self.assertGreater(biomass["stock"][0][0], 0.0)
        self.assertLessEqual(biomass["stock"][0][0], capacity)
        self.assertEqual(service.state["last_update_cycle"], 2)

    def test_drought_reduces_recovery_and_winter_can_reduce_biomass(self):
        from core.resources import ResourceSystem

        wet_world = resource_world()
        dry_world = copy.deepcopy(wet_world)
        wet = ResourceSystem(wet_world, resource_config())
        dry = ResourceSystem(dry_world, resource_config())
        for service in (wet, dry):
            service.state["grids"]["biomass"]["stock"][0][0] = 1.0

        dry_world["climate"]["drought_severity"] = 0.8
        wet_world["cycle"] = dry_world["cycle"] = 1
        wet.advance()
        dry.advance()

        self.assertGreater(
            wet.state["grids"]["biomass"]["stock"][0][0],
            dry.state["grids"]["biomass"]["stock"][0][0],
        )

        wet_world["climate"]["season"] = "winter"
        wet_world["cycle"] = 2
        before = wet.state["grids"]["biomass"]["stock"][0][0]
        wet.advance()
        self.assertLess(
            wet.state["grids"]["biomass"]["stock"][0][0],
            min(
                wet.state["grids"]["biomass"]["capacity"][0][0],
                before + wet.state["grids"]["biomass"]["capacity"][0][0],
            ),
        )

    def test_extraction_is_conservative_and_never_negative(self):
        from core.resources import ResourceSystem

        service = ResourceSystem(resource_world(), resource_config())
        grid = service.state["grids"]["biomass"]["stock"]
        grid[0][0] = 4.5

        first = service.extract("biomass", 0, 0, 3)
        second = service.extract("biomass", 0, 0, 9)

        self.assertEqual(first, 3.0)
        self.assertEqual(second, 1.5)
        self.assertEqual(grid[0][0], 0.0)
        with self.assertRaises(KeyError):
            service.extract("ore", 0, 0, 1)

    def test_fire_and_flood_leave_persistent_bounded_disturbances(self):
        from core.resources import ResourceSystem

        service = ResourceSystem(resource_world(), resource_config())
        before_forest = service.tile_snapshot(0, 0)["forest_cover"]["stock"]
        before_soil = service.tile_snapshot(0, 0)["soil_fertility"]["stock"]

        fire = service.apply_disturbance("fire", [(0, 0)], severity=0.5, duration=3)
        service.apply_disturbance("flood", [(0, 0)], severity=0.4, duration=2)

        tile = service.tile_snapshot(0, 0)
        self.assertLess(tile["forest_cover"]["stock"], before_forest)
        self.assertGreaterEqual(tile["soil_fertility"]["stock"], before_soil)
        self.assertEqual(fire["remaining_cycles"], 3)
        self.assertEqual(len(service.snapshot()["disturbances"]), 2)

        service.world["cycle"] = 1
        service.advance()
        self.assertEqual(service.snapshot()["disturbances"][0]["remaining_cycles"], 2)




    def test_river_and_dry_tiles_follow_different_recovery_trajectories(self):
        from core.resources import ResourceSystem

        world = resource_world(width=2, height=1)
        service = ResourceSystem(world, resource_config())
        biomass = service.state["grids"]["biomass"]
        biomass["stock"][0] = [0.0, 0.0]
        world["cycle"] = 1

        service.advance()

        self.assertGreater(biomass["stock"][0][0], biomass["stock"][0][1])


class ResourceIntegrationTests(unittest.TestCase):
    def test_world_factory_initializes_resource_storage_explicitly(self):
        from unittest import mock
        from core.world_factory import assemble_world

        config = resource_config()
        with (
            mock.patch("core.world_factory.generate_geology", return_value=([[0.2]], [[0]])),
            mock.patch("core.world_factory.simulate_hydrology", return_value=[[1]]),
        ):
            world, _ = assemble_world(1, 1, config, 44)

        self.assertTrue(world["resources"]["enabled"])
        self.assertEqual(set(world["resources"]["grids"]), RESOURCE_NAMES)

    def test_engine_exposes_defensive_tile_and_world_resource_views(self):
        from core.simulation_engine import SimulationEngine

        world = resource_world()
        engine = SimulationEngine(world, {"year": 0, "logs": []}, resource_config())

        tile = engine.get_tile_resources(0, 0)
        summary = engine.get_resource_summary()
        tile["biomass"]["stock"] = -1
        summary["resources"]["biomass"]["stock"] = -1

        self.assertGreater(engine.get_tile_resources(0, 0)["biomass"]["stock"], 0)
        self.assertGreater(engine.get_resource_summary()["resources"]["biomass"]["stock"], 0)

    def test_checkpoint_preserves_resources_and_regenerates_missing_storage(self):
        import tempfile
        from pathlib import Path
        from core.resources import ResourceSystem
        from core.simulation_engine import SimulationEngine

        config = resource_config()
        world = resource_world()
        world.update({"chronicles": [], "next_chronicle_id": 1, "next_relation_id": 1})
        RandomService.initialize(123)
        engine = SimulationEngine(world, {"year": 0, "logs": []}, config)
        ResourceSystem(world, config).extract("biomass", 0, 0, 7)
        expected = engine.get_tile_resources(0, 0)["biomass"]["stock"]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.save"
            engine.save(path)
            restored = SimulationEngine.load(path)
            self.assertEqual(
                restored.get_tile_resources(0, 0)["biomass"]["stock"],
                expected,
            )
            for cycle in range(1, 5):
                engine.world["cycle"] = cycle
                restored.world["cycle"] = cycle
                ResourceSystem(engine.world, config).advance()
                ResourceSystem(restored.world, restored.config).advance()
            self.assertEqual(
                engine.get_resource_summary(),
                restored.get_resource_summary(),
            )

            engine.world.pop("resources")
            engine.save(path)
            migrated = SimulationEngine.load(path)

        self.assertTrue(migrated.get_resource_summary()["enabled"])
        self.assertGreater(migrated.get_tile_resources(0, 0)["biomass"]["stock"], 0)

    def test_climate_anomaly_creates_persistent_spatial_disturbance(self):
        from unittest import mock
        from core.climate import ClimateSystem
        from core.resources import ResourceSystem

        config = resource_config()
        config["climate"].update({
            "anomaly_chance": 1.0,
            "anomaly_min_severity": 0.4,
            "anomaly_max_severity": 0.4,
        })
        world = resource_world()
        ResourceSystem(world, config)
        world["cycle"] = 1

        with (
            mock.patch.object(RandomService, "random", return_value=0.0),
            mock.patch.object(RandomService, "choice", return_value="drought"),
            mock.patch.object(RandomService, "uniform", return_value=0.4),
        ):
            ClimateSystem(world, config).advance()

        disturbances = world["resources"]["disturbances"]
        self.assertEqual(len(disturbances), 1)
        self.assertEqual(disturbances[0]["kind"], "drought")
        self.assertEqual(disturbances[0]["remaining_cycles"], 12)


class ResourceConfigurationTests(unittest.TestCase):
    @staticmethod
    def base_config():
        from pathlib import Path

        return json.loads(Path("template.json").read_text(encoding="utf-8"))

    def test_validator_accepts_resources_and_rejects_invalid_values(self):
        from core.config_validator import ConfigValidationError, validate_config

        valid = self.base_config()
        valid["resources"] = resource_config()["resources"]
        validate_config(valid)

        invalid = self.base_config()
        invalid["resources"] = {
            "enabled": "yes",
            "regeneration_interval": 0,
            "biomass_regeneration_rate": -0.1,
            "winter_mortality_rate": 1.2,
            "biomass_capacity_scale": 0,
            "agriculture_min_support": 1.2,
        }
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:resources.enabled:bool", caught.exception.errors)
        self.assertIn("range:resources.regeneration_interval:positive", caught.exception.errors)
        self.assertIn("range:resources.biomass_regeneration_rate:0_1", caught.exception.errors)
        self.assertIn("range:resources.winter_mortality_rate:0_1", caught.exception.errors)
        self.assertIn("range:resources.biomass_capacity_scale:positive", caught.exception.errors)
        self.assertIn("range:resources.agriculture_min_support:0_1", caught.exception.errors)



    def test_validator_rejects_negative_minimum_birth_resource(self):
        from core.config_validator import ConfigValidationError, validate_config

        invalid = self.base_config()
        invalid["resources"] = resource_config()["resources"]
        invalid["resources"]["minimum_birth_resource"] = -1

        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn(
            "range:resources.minimum_birth_resource:nonnegative",
            caught.exception.errors,
        )


    def test_template_keeps_calibrated_spatial_resources_opt_in(self):
        from core.config_validator import validate_config

        config = self.base_config()
        validate_config(config)

        self.assertFalse(config["resources"]["enabled"])
        self.assertEqual(config["resources"]["biomass_capacity_scale"], 5000.0)
        self.assertEqual(config["resources"]["fish_capacity_scale"], 1000.0)


class ResourceConsumerTests(unittest.TestCase):
    def test_agriculture_is_limited_by_biomass_and_depletes_soil(self):
        from unittest import mock
        from core.resources import ResourceSystem
        from entities.species.human.farmer import Farmer

        config = resource_config()
        world = resource_world()
        service = ResourceSystem(world, config)
        service.state["grids"]["biomass"]["stock"][0][0] = 3.0
        soil_before = service.available("soil_fertility", 0, 0)
        farmer = Farmer.__new__(Farmer)
        farmer.is_dead = False
        farmer.experience = 0
        farmer.config = config
        farmer.species_trait = lambda key: 0
        city = SimpleNamespace(x=0, y=0, food_stock=0, max_food=100)

        with mock.patch("entities.species.human.farmer.RandomService.random", return_value=1.0):
            farmer.work(city, world)

        self.assertEqual(city.food_stock, 3)
        self.assertEqual(service.available("biomass", 0, 0), 0.0)
        self.assertLess(service.available("soil_fertility", 0, 0), soil_before)

    def test_full_granary_does_not_waste_local_biomass(self):
        from unittest import mock
        from core.resources import ResourceSystem
        from entities.species.human.farmer import Farmer

        config = resource_config()
        world = resource_world()
        service = ResourceSystem(world, config)
        before = service.available("biomass", 0, 0)
        farmer = Farmer.__new__(Farmer)
        farmer.is_dead = False
        farmer.experience = 0
        farmer.config = config
        farmer.species_trait = lambda key: 0
        city = SimpleNamespace(x=0, y=0, food_stock=100, max_food=100)

        with mock.patch("entities.species.human.farmer.RandomService.random", return_value=1.0):
            farmer.work(city, world)

        self.assertEqual(service.available("biomass", 0, 0), before)
        self.assertEqual(
            world["metrics"]["flows"]["resources"]["biomass_harvested"],
            0,
        )


    def test_herbivore_energy_gain_cannot_exceed_removed_biomass(self):
        from core.resources import ResourceSystem
        from entities.species.animal.base import Animal

        config = resource_config()
        species = {
            "species": "grazer",
            "name": "Grazer",
            "char": "g",
            "diet": "herbivore",
            "energy": 10,
            "max_energy": 100,
        }
        world = resource_world()
        service = ResourceSystem(world, config)
        animal = Animal(0, 0, config, species)
        service.state["grids"]["biomass"]["stock"][0][0] = 1.5
        before_energy = animal.energy
        before_biomass = service.available("biomass", 0, 0)

        animal._graze(world)

        removed = before_biomass - service.available("biomass", 0, 0)
        gained = animal.energy - before_energy
        self.assertGreater(removed, 0)
        self.assertLessEqual(gained, removed)

        animal.energy = 10
        service.state["grids"]["biomass"]["stock"][0][0] = 0.0
        animal._graze(world)
        self.assertEqual(animal.energy, 10)

    def test_fishing_gain_is_limited_by_local_fish_stock(self):
        from unittest import mock
        from core.resources import ResourceSystem
        from entities.species.human.fisherman import Fisherman

        config = resource_config()
        world = resource_world()
        service = ResourceSystem(world, config)
        service.state["grids"]["fish_stock"]["stock"][0][0] = 2.0
        target = SimpleNamespace(is_expired=False)
        home = SimpleNamespace(food_stock=0, max_food=100, name="Harbor")
        fisher = Fisherman.__new__(Fisherman)
        fisher._pos = [0, 0]
        fisher.target = target
        fisher.home_city = home
        fisher.config = config
        fisher.faith_bonus = lambda key: 0
        fisher.char = "f"
        fisher.name = "Fish"
        fisher.fishing_cooldown = 0

        with mock.patch("entities.species.human.fisherman.RandomService.randint", return_value=10):
            fisher._fish_action(world)

        self.assertEqual(home.food_stock, 2)
        self.assertEqual(service.available("fish_stock", 0, 0), 0.0)
        self.assertTrue(target.is_expired)

    def test_herbivore_wandering_prefers_richer_neighbor_in_resource_mode(self):
        from unittest import mock
        from core.resources import ResourceSystem
        from entities.species.animal.base import Animal

        config = resource_config()
        world = resource_world(width=3, height=1)
        world["influence"] = SimpleNamespace(
            get_fear=lambda x, y: 0.0,
            get_scent=lambda x, y: 0.0,
        )
        service = ResourceSystem(world, config)
        for x in range(3):
            service.state["grids"]["biomass"]["stock"][0][x] = float(x * 10)
        animal = Animal(
            1,
            0,
            config,
            {
                "species": "grazer",
                "name": "Grazer",
                "char": "g",
                "diet": "herbivore",
                "energy": 10,
                "max_energy": 100,
            },
        )

        with mock.patch("entities.species.animal.base.RandomService.random", return_value=0.0):
            animal._wander(world)

        self.assertEqual(animal.pos, (2, 0))

    def test_resource_fauna_randomness_is_isolated_from_legacy_stream(self):
        from core.resources import ResourceSystem
        from entities.species.animal.base import Animal

        config = resource_config()
        world = resource_world(width=3, height=1)
        world["influence"] = SimpleNamespace(
            get_fear=lambda x, y: 0.0,
            get_scent=lambda x, y: 0.0,
        )
        ResourceSystem(world, config)
        animal = Animal(
            1,
            0,
            config,
            {
                "species": "grazer",
                "name": "Grazer",
                "char": "g",
                "diet": "herbivore",
            },
        )
        RandomService.initialize(1357)
        default_before = RandomService.get_state()

        animal._wander(world)

        self.assertEqual(RandomService.get_state(), default_before)
        self.assertIn("ecology", RandomService.get_stream_states())

    def test_resource_fauna_lifecycle_uses_only_the_ecology_stream(self):
        from entities.spawn_system import _spawn_fauna
        from entities.species.animal.base import Animal

        species = {
            "species": "grazer",
            "name": "Grazer",
            "char": "g",
            "diet": "herbivore",
            "food_value": [5, 10],
            "energy": 140,
            "max_energy": 150,
            "repro_threshold": 120,
            "spawn": {
                "elevation_min": 0.0,
                "elevation_max": 1.0,
                "chance": 1.0,
            },
        }
        config = resource_config()
        config.update({"fauna": [species], "max_fauna": 20})
        world = resource_world()
        RandomService.initialize(2468)
        default_before = RandomService.get_state()

        spawned = Animal.try_spawn(0, 0, world, config, species)
        self.assertIsInstance(spawned, Animal)
        world["entities"].add(spawned)
        spawned._reproduce(world)
        _ = spawned.food_value

        prey = Animal(0, 0, config, {
            **species,
            "species": "prey",
            "name": "Prey",
            "energy": 10,
        })
        prey.get_defense_power = lambda: 0.1
        spawned.target = prey
        spawned._attack_target(world)

        _spawn_fauna(world, config, world["width"], world["height"])

        self.assertEqual(RandomService.get_state(), default_before)
        self.assertIn("ecology", RandomService.get_stream_states())

    def test_legacy_fauna_lifecycle_keeps_using_the_default_stream(self):
        from entities.species.animal.base import Animal

        config = {}
        species = {
            "species": "legacy_grazer",
            "name": "Legacy Grazer",
            "char": "g",
            "diet": "herbivore",
            "spawn": {
                "elevation_min": 0.0,
                "elevation_max": 1.0,
                "chance": 1.0,
            },
        }
        world = resource_world()
        RandomService.initialize(9753)
        default_before = RandomService.get_state()

        self.assertIsInstance(Animal.try_spawn(0, 0, world, config, species), Animal)

        self.assertNotEqual(RandomService.get_state(), default_before)
        self.assertNotIn("ecology", RandomService.get_stream_states())

    def test_local_resource_shortage_blocks_enabled_herbivore_reproduction(self):
        from core.ecology_limits import can_add_fauna
        from core.resources import ResourceSystem
        from entities.species.animal.base import Animal

        config = resource_config()
        config["ecology"] = {
            "population_limits": {"enabled": True, "global": 10}
        }
        species = {
            "species": "grazer",
            "name": "Grazer",
            "char": "g",
            "diet": "herbivore",
        }
        world = resource_world()
        ResourceSystem(world, config).state["grids"]["biomass"]["stock"][0][0] = 0.0
        parent = Animal(0, 0, config, species)
        world["entities"].add(parent)

        self.assertFalse(can_add_fauna(world, config, species, 0, 0))

    def test_overgrazing_causes_energy_decline_and_local_starvation(self):
        from core.resources import ResourceSystem
        from entities.species.animal.base import Animal

        config = resource_config()
        world = resource_world(width=1, height=1)
        service = ResourceSystem(world, config)
        service.state["grids"]["biomass"]["stock"][0][0] = 1.0
        animal = Animal(
            0,
            0,
            config,
            {
                "species": "grazer",
                "name": "Grazer",
                "char": "g",
                "diet": "herbivore",
                "energy": 10,
                "max_energy": 20,
                "danger": 0.0,
            },
        )
        world["entities"].add(animal)

        for _ in range(3):
            animal._graze(world)
            animal.check_vital_signs(world)

        self.assertEqual(service.available("biomass", 0, 0), 0.0)
        self.assertTrue(animal.is_expired)


class ResourceObservabilityAndDisturbanceTests(unittest.TestCase):
    def test_resource_flows_and_snapshot_ratios_are_observable_without_randomness(self):
        from core.resources import ResourceSystem
        from core.simulation_metrics import SimulationMetrics

        world = resource_world()
        service = ResourceSystem(world, resource_config())
        RandomService.initialize(811)
        before_random = RandomService.get_state()

        service.harvest_agriculture(0, 0, 4)
        service.harvest_fish(0, 0, 3)
        service.apply_disturbance("fire", [(0, 0)], severity=0.2, duration=2)
        snapshot = SimulationMetrics(world).snapshot()

        self.assertEqual(RandomService.get_state(), before_random)
        self.assertEqual(snapshot["flows"]["resources"]["biomass_harvested"], 4)
        self.assertEqual(snapshot["flows"]["resources"]["fish_harvested"], 3)
        self.assertGreater(snapshot["flows"]["resources"]["soil_depleted"], 0)
        self.assertEqual(snapshot["flows"]["resources"]["disturbances"], 1)
        self.assertLess(snapshot["state"]["biomass_ratio"], 1.0)
        self.assertLess(snapshot["state"]["fish_ratio"], 1.0)

    def test_fire_spreads_only_through_sufficiently_vegetated_tiles(self):
        from core.resources import ResourceSystem

        world = resource_world(width=3, height=1)
        service = ResourceSystem(world, resource_config())
        forest = service.state["grids"]["forest_cover"]
        forest["stock"][0] = [80.0, 80.0, 0.0]
        forest["capacity"][0] = [100.0, 100.0, 100.0]

        disturbance = service.spread_fire(
            (0, 0), severity=0.5, duration=4, max_tiles=3
        )

        self.assertEqual(disturbance["positions"], [[0, 0], [1, 0]])
        self.assertLess(forest["stock"][0][1], 80.0)
        self.assertEqual(forest["stock"][0][2], 0.0)

    def test_volcano_event_updates_spatial_resources_on_impacted_tiles(self):
        from unittest import mock
        from core.resources import ResourceSystem
        from events.volcano import VolcanoEruption

        world = resource_world(width=1, height=1)
        world["elev"] = [[0.95]]
        world["road"] = [["  "]]
        world["influence"] = SimpleNamespace(add_influence=lambda *args, **kwargs: None)
        config = resource_config()
        service = ResourceSystem(world, config)
        forest_before = service.available("forest_cover", 0, 0)
        soil_before = service.available("soil_fertility", 0, 0)

        with mock.patch("events.volcano.RandomService.choice", return_value=(0, 0)):
            VolcanoEruption().trigger(world, {}, config)

        self.assertLess(service.available("forest_cover", 0, 0), forest_before)
        self.assertGreaterEqual(service.available("soil_fertility", 0, 0), soil_before)
        self.assertEqual(world["resources"]["disturbances"][0]["kind"], "volcano")


if __name__ == "__main__":
    unittest.main()
