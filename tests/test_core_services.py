import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from core import bestiary_tracker
from core.culture import load_config
from core.entities import Entity, EntityManager
from core.grid_service import SpatialGrid
from core.influence import InfluenceSystem
from core.logger import GameLogger
from core.naming import NameGenerator
from core.random_service import RandomService
from core.translator import Translator
from history.history_engine import connect_with_road


ROOT = Path(__file__).resolve().parents[1]


class CountingEntity(Entity):
    def __init__(self, x=0, y=0, speed=1.0):
        super().__init__(x, y, "x", 1, speed)
        self.update_count = 0

    def update(self, world, stats):
        self.update_count += 1


class CoreServicesTests(unittest.TestCase):
    def setUp(self):
        RandomService.initialize(12345)
        GameLogger.get_new_logs()
        bestiary_tracker.reset()

    def test_random_service_replays_the_same_sequence(self):
        values_a = [
            RandomService.random(),
            RandomService.randint(1, 100),
            RandomService.choice(["a", "b", "c"]),
            RandomService.uniform(-2, 2),
            RandomService.sample(range(10), 3),
        ]
        shuffled_a = list(range(6))
        self.assertIsNone(RandomService.shuffle(shuffled_a))

        RandomService.initialize(12345)
        values_b = [
            RandomService.random(),
            RandomService.randint(1, 100),
            RandomService.choice(["a", "b", "c"]),
            RandomService.uniform(-2, 2),
            RandomService.sample(range(10), 3),
        ]
        shuffled_b = list(range(6))
        RandomService.shuffle(shuffled_b)

        self.assertEqual(values_a, values_b)
        self.assertEqual(shuffled_a, shuffled_b)

    def test_logger_flushes_and_ignores_empty_messages(self):
        GameLogger.log(None)
        GameLogger.log(42)
        GameLogger.log("event")
        self.assertEqual(GameLogger.get_new_logs(), ["42", "event"])
        self.assertEqual(GameLogger.get_new_logs(), [])

    def test_bestiary_tracker_returns_copies_and_can_reset(self):
        bestiary_tracker.track_kill("wolf")
        bestiary_tracker.track_kill("wolf")
        bestiary_tracker.track_starvation("bear")
        snapshot = bestiary_tracker.all_kills()
        snapshot["wolf"] = 99

        self.assertEqual(bestiary_tracker.get_kills("wolf"), 2)
        self.assertEqual(bestiary_tracker.get_starvations("bear"), 1)
        bestiary_tracker.reset()
        self.assertEqual(bestiary_tracker.all_kills(), {})
        self.assertEqual(bestiary_tracker.all_starvations(), {})

    def test_config_loader_reads_json_and_has_missing_file_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            valid_config = {
                "world_name": "Test",
                "water": {},
                "biomes": {},
                "cultures": [{"name": "Test Culture"}],
                "fauna": [],
                "special": {},
            }
            config_path.write_text(json.dumps(valid_config), encoding="utf-8")
            self.assertEqual(load_config(config_path)["world_name"], "Test")

            fallback = load_config(Path(directory) / "missing.json")
            self.assertEqual(fallback["world_name"], "Unknown Lands")
            self.assertIn("cultures", fallback)
            self.assertIn("fauna", fallback)

    def test_config_loader_returns_empty_dict_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "invalid.json"
            config_path.write_text("{invalid", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(load_config(config_path), {})

    def test_translator_loads_formats_and_reports_missing_keys(self):
        previous = Path.cwd()
        try:
            import os
            os.chdir(ROOT)
            Translator.load("fr")
            rendered = Translator.translate("ui.seed_info", seed=123)
        finally:
            os.chdir(previous)

        self.assertIn("123", rendered)
        self.assertEqual(
            Translator.translate("path.that.does.not.exist"),
            "[MISSING_TEXT: path.that.does.not.exist]",
        )

    def test_name_generation_is_deterministic(self):
        culture = {
            "naming": {
                "prefixes": ["Al", "Bel"],
                "suffixes_person": ["dor", "ia"],
                "suffixes_place": ["heim", " polis"],
            }
        }
        RandomService.initialize(8)
        first = (
            NameGenerator.generate_person_name(culture),
            NameGenerator.generate_first_name(culture),
            NameGenerator.generate_place_name(culture),
        )
        RandomService.initialize(8)
        second = (
            NameGenerator.generate_person_name(culture),
            NameGenerator.generate_first_name(culture),
            NameGenerator.generate_place_name(culture),
        )
        self.assertEqual(first, second)

    def test_spatial_grid_indexes_candidates_and_clears(self):
        grid = SpatialGrid(30, 30, cell_size=10)
        near = CountingEntity(2, 2)
        adjacent_cell = CountingEntity(11, 2)
        far = CountingEntity(25, 25)
        for entity in (near, adjacent_cell, far):
            grid.add_entity(entity)

        candidates = grid.get_nearby(5, 5, radius=8)
        self.assertIn(near, candidates)
        self.assertIn(adjacent_cell, candidates)
        self.assertNotIn(far, candidates)
        grid.clear()
        self.assertEqual(grid.get_nearby(5, 5, radius=30), [])

    def test_influence_layers_accumulate_and_decay(self):
        influence = InfluenceSystem(5, 5, {"influence_decay": 0.5})
        influence.add_influence(2, 2, 4.0, radius=1)
        influence.add_influence(2, 2, 2.0, radius=1)
        influence.add_influence(2, 2, -3.0, radius=1)
        influence.add_influence(2, 2, -1.0, radius=1)

        self.assertEqual(influence.get_scent(2, 2), 6.0)
        self.assertEqual(influence.get_fear(2, 2), -3.0)
        self.assertEqual(influence.get_fear(-1, 2), 0.0)
        influence.update()
        self.assertEqual(influence.get_scent(2, 2), 3.0)
        self.assertEqual(influence.get_fear(2, 2), -1.5)

    def test_entity_action_meter_supports_multiple_actions(self):
        entity = CountingEntity(speed=2.5)
        entity.process_turn({}, {})
        self.assertEqual(entity.update_count, 2)
        self.assertAlmostEqual(entity.action_meter, 0.5)
        entity.process_turn({}, {})
        self.assertEqual(entity.update_count, 5)
        self.assertAlmostEqual(entity.action_meter, 0.0)
        entity.is_expired = True
        entity.process_turn({}, {})
        self.assertEqual(entity.update_count, 5)

    def test_entity_manager_add_remove_and_cleanup(self):
        manager = EntityManager()
        alive = CountingEntity()
        dead = CountingEntity()
        dead.is_expired = True
        manager.add(None)
        manager.add(alive)
        manager.add(dead)
        self.assertEqual(len(manager), 2)
        self.assertEqual(manager.remove_dead(), 1)
        self.assertEqual(list(manager), [alive])
        manager.remove(alive)
        self.assertEqual(len(manager), 0)

    def test_road_connection_reaches_target_and_stays_in_bounds(self):
        roads = [["  " for _ in range(6)] for _ in range(5)]
        connect_with_road(roads, (0, 0), (5, 3), 6, 5)
        self.assertEqual(roads[3][5], "··")
        self.assertEqual(sum(cell == "··" for row in roads for cell in row), 5)


if __name__ == "__main__":
    unittest.main()
