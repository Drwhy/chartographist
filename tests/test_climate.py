import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core.entities import EntityManager
from entities.species.animal.base import Animal
from entities.species.human.farmer import Farmer


ROOT = Path(__file__).resolve().parents[1]


def climate_config(**overrides):
    climate = {
        "enabled": True,
        "seasonal_amplitude": 0.2,
        "altitude_lapse_rate": 0.6,
        "base_humidity": 0.4,
        "river_humidity_bonus": 0.3,
        "temperature_anomaly_decay": 0.9,
        "precipitation_anomaly_decay": 0.9,
    }
    climate.update(overrides)
    return {
        "climate": climate,
        "biomes": {
            "volcano": "volcano",
            "peak": "peak",
            "high_mountain": "high_mountain",
            "mountain": "mountain",
            "sand": "sand",
            "glaciated": "glaciated",
            "boreal_forest": "boreal",
            "temperate_forest": "temperate",
            "autumn_forest": "autumn",
            "tropical_forest": "tropical",
            "grassland": "grassland",
            "tundra": "tundra",
            "desert": "desert",
            "cactus": "cactus",
        },
        "water": {"ocean": "ocean", "shore": "shore", "river": "river"},
    }


def make_world(cycle=0, width=6, height=6):
    elevation = np.full((height, width), 0.2, dtype=float)
    rivers = np.zeros((height, width), dtype=float)
    return {
        "width": width,
        "height": height,
        "cycle": cycle,
        "elev": elevation,
        "riv": rivers,
    }


class ClimateModelTests(unittest.TestCase):
    def test_old_world_is_initialized_lazily_with_serializable_defaults(self):
        from core.climate import ClimateSystem

        world = make_world(cycle=7)
        climate = ClimateSystem(world, {})
        snapshot = climate.snapshot()
        snapshot["temperature_anomaly"] = 99

        self.assertEqual(
            world["climate"],
            {
                "season": "summer",
                "season_index": 2,
                "temperature_anomaly": 0.0,
                "precipitation_anomaly": 0.0,
                "drought_severity": 0.0,
                "flood_severity": 0.0,
                "last_update_cycle": 7,
            },
        )
        self.assertEqual(climate.snapshot()["temperature_anomaly"], 0.0)

    def test_seasons_follow_a_replayable_twelve_month_cycle(self):
        from core.climate import ClimateSystem

        expected = {
            0: ("winter", 0),
            3: ("spring", 1),
            6: ("summer", 2),
            9: ("autumn", 3),
            12: ("winter", 0),
        }
        world = make_world()
        climate = ClimateSystem(world, climate_config())

        for cycle, season in expected.items():
            world["cycle"] = cycle
            climate.advance()
            self.assertEqual(
                (world["climate"]["season"], world["climate"]["season_index"]),
                season,
            )

    def test_temperature_uses_latitude_altitude_and_opposite_hemisphere_seasons(self):
        from core.climate import ClimateSystem

        world = make_world(width=5, height=8)
        config = climate_config()
        climate = ClimateSystem(world, config)

        world["cycle"] = 0
        climate.advance()
        northern_winter = climate.temperature_at(2, 1)
        southern_summer = climate.temperature_at(2, 6)
        equator_low = climate.temperature_at(2, 4)
        world["elev"][4][2] = 0.8
        equator_high = climate.temperature_at(2, 4)

        world["cycle"] = 6
        climate.advance()
        northern_summer = climate.temperature_at(2, 1)

        self.assertLess(northern_winter, northern_summer)
        self.assertGreater(southern_summer, northern_winter)
        self.assertGreater(equator_low, equator_high)

    def test_moisture_is_bounded_and_rivers_humidify_nearby_tiles(self):
        from core.climate import ClimateSystem

        world = make_world()
        world["riv"][2][2] = 1
        climate = ClimateSystem(world, climate_config(base_humidity=0.4))

        dry = climate.moisture_at(4, 4)
        river = climate.moisture_at(2, 2)
        world["climate"]["precipitation_anomaly"] = 10
        saturated = climate.moisture_at(2, 2)

        self.assertGreater(river, dry)
        self.assertGreaterEqual(dry, 0.0)
        self.assertLessEqual(saturated, 1.0)

    def test_legacy_biomes_preserve_the_render_formula_without_climate_section(self):
        from core.climate import biome_at

        config = climate_config()
        config.pop("climate")
        world = make_world(width=6, height=6)

        self.assertEqual(biome_at(3, 3, 0.2, world, config), "tropical")
        self.assertEqual(biome_at(3, 0, 0.2, world, config), "glaciated")
        self.assertEqual(biome_at(3, 3, -0.2, world, config), "ocean")
        self.assertEqual(biome_at(3, 3, 0.7, world, config), "high_mountain")


class ClimateEngineAndRenderTests(unittest.TestCase):
    def test_world_factory_initializes_climate_storage_explicitly(self):
        from unittest import mock
        from core.world_factory import assemble_world

        with (
            mock.patch("core.world_factory.generate_geology", return_value=([[0]], [])),
            mock.patch("core.world_factory.simulate_hydrology", return_value=[[0]]),
            mock.patch("core.world_factory.InfluenceSystem"),
        ):
            world, _ = assemble_world(1, 1, {}, 9)

        self.assertEqual(world["climate"]["season"], "winter")
        self.assertEqual(world["climate"]["temperature_anomaly"], 0.0)

    def test_engine_advances_climate_and_exposes_defensive_headless_views(self):
        from unittest import mock
        from core.entities import EntityManager
        from core.simulation_engine import SimulationEngine

        config = climate_config()
        world = make_world(cycle=2)
        world.update(
            {
                "entities": EntityManager(),
                "grid": mock.Mock(),
                "influence": mock.Mock(),
            }
        )
        stats = {"year": 0, "seed": 4, "logs": []}
        engine = SimulationEngine(world, stats, config)

        with (
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            engine.step()

        snapshot = engine.get_climate_snapshot()
        tile = engine.get_tile_climate(2, 2)
        snapshot["season"] = "corrupted"

        self.assertEqual(world["climate"]["season"], "spring")
        self.assertEqual(engine.get_climate_snapshot()["season"], "spring")
        self.assertEqual(tile["position"], [2, 2])
        self.assertIn("temperature", tile)
        self.assertIn("moisture", tile)
        self.assertIn("biome", tile)

    def test_render_terrain_delegates_to_shared_headless_biome_service(self):
        from unittest import mock
        from core.entities import EntityManager
        from render.ui_map import get_char_at

        world = make_world(width=3, height=3)
        world.update(
            {
                "entities": EntityManager(),
                "road": [["  "] * 3 for _ in range(3)],
            }
        )
        config = climate_config()

        with mock.patch("core.presentation.biome_key_at", return_value="grassland"), \
                mock.patch("core.presentation.biome_glyph", return_value="shared") as shared:
            rendered = get_char_at(1, 1, world, config)

        self.assertEqual(rendered, "shared")
        shared.assert_called_once_with("grassland", config)

class ClimateEcologyTests(unittest.TestCase):
    def _farmer(self, config):
        from entities.species.human.farmer import Farmer

        farmer = Farmer.__new__(Farmer)
        farmer.is_dead = False
        farmer.experience = 0
        farmer.config = config
        farmer.species_trait = lambda key: 0
        return farmer

    def test_legacy_farmer_yield_is_unchanged_without_climate_configuration(self):
        from types import SimpleNamespace
        from unittest import mock

        config = climate_config()
        config.pop("climate")
        farmer = self._farmer(config)
        city = SimpleNamespace(x=2, y=2, food_stock=0, max_food=100)
        world = make_world()

        with mock.patch("entities.species.human.farmer.RandomService.random", return_value=1.0):
            farmer.work(city, world)

        self.assertEqual(city.food_stock, 8)

    def test_drought_reduces_farm_yield_only_when_climate_is_enabled(self):
        from types import SimpleNamespace
        from unittest import mock

        config = climate_config(seasonal_amplitude=0.0, base_humidity=0.65)
        wet_world = make_world()
        dry_world = copy.deepcopy(wet_world)
        dry_world["climate"] = {"drought_severity": 0.65}
        wet_city = SimpleNamespace(x=2, y=2, food_stock=0, max_food=100)
        dry_city = SimpleNamespace(x=2, y=2, food_stock=0, max_food=100)

        with mock.patch("entities.species.human.farmer.RandomService.random", return_value=1.0):
            self._farmer(config).work(wet_city, wet_world)
            self._farmer(config).work(dry_city, dry_world)

        self.assertGreater(wet_city.food_stock, dry_city.food_stock)
        self.assertGreaterEqual(dry_city.food_stock, 1)

    def test_animal_habitat_preferences_are_optional_and_climate_aware(self):
        from unittest import mock
        from entities.species.animal.base import Animal

        config = climate_config(seasonal_amplitude=0.0)
        world = make_world()
        species = {
            "species": "cold_test_beast",
            "char": "x",
            "name": "Cold Test Beast",
            "spawn": {"elevation_min": 0.0, "elevation_max": 0.5, "chance": 1.0},
        }
        climate_species = copy.deepcopy(species)
        climate_species["habitat"] = {"temperature_max": 0.4}

        with mock.patch("entities.species.animal.base.RandomService.random", return_value=0.0):
            self.assertIsInstance(Animal.try_spawn(2, 2, world, config, species), Animal)
            self.assertIsNone(Animal.try_spawn(2, 2, world, config, climate_species))

    def test_herbivore_grazing_tracks_local_ecosystem_productivity(self):
        from entities.species.animal.base import Animal

        config = climate_config(seasonal_amplitude=0.0, base_humidity=0.65)
        species = {
            "species": "grazer",
            "char": "g",
            "name": "Grazer",
            "diet": "herbivore",
            "energy": 50,
            "max_energy": 100,
        }
        lush_world = make_world()
        dry_world = copy.deepcopy(lush_world)
        dry_world["climate"] = {"drought_severity": 0.65}
        lush = Animal(2, 2, config, species)
        dry = Animal(2, 2, config, species)

        lush._graze(lush_world)
        dry._graze(dry_world)

        self.assertGreater(lush.energy, dry.energy)

    def test_legacy_grazing_gain_remains_exact_without_climate_configuration(self):
        from entities.species.animal.base import Animal

        config = climate_config()
        config.pop("climate")
        world = make_world()
        animal = Animal(2, 2, config, {
            "species": "legacy_grazer",
            "char": "g",
            "name": "Legacy Grazer",
            "diet": "herbivore",
            "energy": 50,
            "max_energy": 100,
        })

        animal._graze(world)

        self.assertEqual(animal.energy, 52)
class ClimateAnomalyConfigPersistenceTests(unittest.TestCase):
    def setUp(self):
        from core.logger import GameLogger
        from core.random_service import RandomService

        RandomService.initialize(2468)
        GameLogger.get_new_logs()
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            from core.translator import Translator
            Translator.load("fr")
        finally:
            os.chdir(previous)

    def test_deterministic_anomaly_updates_state_and_structured_log(self):
        from unittest import mock
        from core.climate import ClimateSystem
        from core.logger import GameLogger
        from core.random_service import RandomService

        world = make_world(cycle=0)
        config = climate_config(anomaly_chance=1.0, anomaly_min_severity=0.4, anomaly_max_severity=0.4)
        climate = ClimateSystem(world, config)
        world["cycle"] = 1

        with (
            mock.patch.object(RandomService, "random", return_value=0.0),
            mock.patch.object(RandomService, "choice", return_value="drought"),
            mock.patch.object(RandomService, "uniform", return_value=0.4),
        ):
            climate.advance()

        self.assertEqual(world["climate"]["last_anomaly"], "drought")
        self.assertAlmostEqual(world["climate"]["drought_severity"], 0.4)
        logs = GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(len(logs))
        self.assertEqual(len(logs), 1)
        self.assertNotIn("MISSING_TEXT", logs[0])
        self.assertEqual(metadata[0]["category"], "climate")

    def test_flood_anomaly_damages_configured_infrastructure(self):
        from unittest import mock
        from core.climate import ClimateSystem
        from core.random_service import RandomService

        world = make_world(cycle=0)
        config = climate_config(
            anomaly_chance=1.0,
            anomaly_min_severity=0.4,
            anomaly_max_severity=0.4,
        )
        climate = ClimateSystem(world, config)
        world["cycle"] = 1

        with (
            mock.patch.object(RandomService, "random", return_value=0.0),
            mock.patch.object(RandomService, "choice", return_value="flood"),
            mock.patch.object(RandomService, "uniform", return_value=0.4),
            mock.patch("core.infrastructure.damage_world_infrastructure") as damage,
        ):
            climate.advance()

        damage.assert_called_once_with(world, config, "flood", severity=0.4)

    def test_engine_records_triggered_anomaly_as_climate_chronicle(self):
        from unittest import mock
        from core.entities import EntityManager
        from core.grid_service import SpatialGrid
        from core.influence import InfluenceSystem
        from core.random_service import RandomService
        from core.simulation_engine import SimulationEngine

        config = climate_config(anomaly_chance=1.0, anomaly_min_severity=0.3, anomaly_max_severity=0.3)
        world = make_world()
        world.update({
            "entities": EntityManager(),
            "grid": SpatialGrid(world["width"], world["height"], cell_size=2),
            "influence": InfluenceSystem(world["width"], world["height"], {}),
        })
        engine = SimulationEngine(world, {"year": 0, "month": 1, "seed": 2468, "logs": []}, config)

        with (
            mock.patch.object(RandomService, "random", return_value=0.0),
            mock.patch.object(RandomService, "choice", return_value="flood"),
            mock.patch.object(RandomService, "uniform", return_value=0.3),
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            engine.step()

        chronicles = engine.get_chronicles(category="climate")
        self.assertEqual(len(chronicles), 1)
        self.assertEqual(chronicles[0]["cycle"], 1)
        self.assertNotIn("MISSING_TEXT", chronicles[0]["message"])
    def test_hazards_decay_and_zero_chance_consumes_no_random_draw(self):
        from unittest import mock
        from core.climate import ClimateSystem
        from core.random_service import RandomService

        world = make_world(cycle=1)
        world["climate"] = {"drought_severity": 0.8, "last_update_cycle": 0}
        config = climate_config(anomaly_chance=0.0, hazard_decay=0.5)

        with mock.patch.object(RandomService, "random") as random_draw:
            ClimateSystem(world, config).advance()

        random_draw.assert_not_called()
        self.assertAlmostEqual(world["climate"]["drought_severity"], 0.4)

    def test_climate_configuration_validates_types_probabilities_and_severity_bounds(self):
        from core.config_validator import ConfigValidationError, validate_config

        template = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        template["climate"] = {"enabled": True, "anomaly_chance": 0.02, "hazard_decay": 0.9}
        self.assertIs(validate_config(template), template)

        for climate in (
            {"enabled": "yes"},
            {"anomaly_chance": 1.1},
            {"anomaly_min_severity": 0.8, "anomaly_max_severity": 0.2},
        ):
            invalid = copy.deepcopy(template)
            invalid["climate"] = climate
            with self.subTest(climate=climate), self.assertRaises(ConfigValidationError):
                validate_config(invalid)

    def test_checkpoint_preserves_climate_and_migrates_world_without_it(self):
        from core.entities import EntityManager
        from core.grid_service import SpatialGrid
        from core.influence import InfluenceSystem
        from core.simulation_engine import SimulationEngine

        config = climate_config()
        world = make_world()
        world.update({
            "entities": EntityManager(),
            "grid": SpatialGrid(world["width"], world["height"], cell_size=2),
            "influence": InfluenceSystem(world["width"], world["height"], {}),
            "chronicles": [],
            "next_chronicle_id": 1,
            "diplomacy": {},
        })
        engine = SimulationEngine(world, {"year": 0, "month": 1, "seed": 2468, "logs": []}, config)
        engine.world["climate"]["temperature_anomaly"] = 0.35

        with tempfile.TemporaryDirectory() as directory:
            current_path = Path(directory) / "current.chart"
            old_path = Path(directory) / "old.chart"
            engine.save(current_path)
            restored = SimulationEngine.load(current_path)
            self.assertAlmostEqual(restored.world["climate"]["temperature_anomaly"], 0.35)

            engine.world.pop("climate")
            engine.save(old_path)
            migrated = SimulationEngine.load(old_path)

        self.assertEqual(migrated.world["climate"]["temperature_anomaly"], 0.0)

    def test_header_displays_localized_season_only_when_climate_is_enabled(self):
        from core.entities import EntityManager
        from core.translator import Translator
        from render.ui_header import render_header

        world = make_world(cycle=6)
        world["entities"] = EntityManager()
        stats = {"year": 0, "month": 7, "seed": 1}
        config = climate_config()
        config["world_name"] = "Test"

        for language, expected in (("fr", "Été"), ("en", "Summer"), ("es", "Verano")):
            previous = Path.cwd()
            try:
                os.chdir(ROOT)
                Translator.load(language)
            finally:
                os.chdir(previous)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                render_header(6, world, stats, config)
            self.assertIn(expected, output.getvalue())
            self.assertNotIn("MISSING_TEXT", output.getvalue())
if __name__ == "__main__":
    unittest.main()
