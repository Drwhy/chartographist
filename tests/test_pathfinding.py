import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.pathfinding import PathfindingService
from core.random_service import RandomService


def path_config(**overrides):
    settings = {
        "enabled": True,
        "allow_diagonal": False,
        "base_cost": 1.0,
        "elevation_weight": 10.0,
        "road_multiplier": 0.5,
        "weather_weight": 2.0,
        "danger_weight": 1.0,
        "unknown_multiplier": 2.0,
        "max_cache_entries": 8,
        "max_expanded_nodes": 500,
    }
    settings.update(overrides)
    return {"pathfinding": settings}


def path_world(width=5, height=3):
    return {
        "width": width,
        "height": height,
        "cycle": 1,
        "elev": [[0.0 for _ in range(width)] for _ in range(height)],
        "riv": [[0 for _ in range(width)] for _ in range(height)],
        "road": [["  " for _ in range(width)] for _ in range(height)],
        "climate": {
            "last_update_cycle": 1,
            "drought_severity": 0.0,
            "flood_severity": 0.0,
        },
        "influence": SimpleNamespace(
            fear_grid=[[0.0 for _ in range(width)] for _ in range(height)],
            get_fear=lambda x, y: 0.0,
        ),
    }


class PathfindingServiceTests(unittest.TestCase):
    def test_disabled_service_does_not_mutate_legacy_world(self):
        world = path_world()
        service = PathfindingService(world, {"pathfinding": {"enabled": False}})

        result = service.find_path((0, 1), (4, 1))

        self.assertFalse(service.enabled)
        self.assertEqual(result["path"], [[0, 1], [1, 1], [2, 1], [3, 1], [4, 1]])
        self.assertNotIn("pathfinding", world)

    def test_astar_prefers_a_longer_road_over_steep_terrain(self):
        world = path_world()
        world["elev"][1][2] = 1.0
        for x in range(5):
            world["road"][0][x] = "=="
        service = PathfindingService(world, path_config())

        result = service.find_path((0, 1), (4, 1))

        self.assertTrue(result["reachable"])
        self.assertIn([2, 0], result["path"])
        self.assertNotIn([2, 1], result["path"])
        self.assertEqual(result["cost"], service.measure_path(result["path"]))
        self.assertGreater(result["expanded_nodes"], 0)

    def test_cost_combines_weather_danger_and_unknown_knowledge(self):
        world = path_world(width=2, height=1)
        world["riv"][0][1] = 1
        world["climate"]["flood_severity"] = 0.5
        world["influence"].fear_grid[0][1] = -3.0
        service = PathfindingService(world, path_config(elevation_weight=0.0))

        known = service.find_path((0, 0), (1, 0), known_tiles={(0, 0), (1, 0)})
        unknown = service.find_path((0, 0), (1, 0), known_tiles={(0, 0)})

        self.assertEqual(known["cost"], 5.0)
        self.assertEqual(unknown["cost"], 10.0)
        self.assertEqual(unknown["cost_breakdown"]["weather"], 1.0)
        self.assertEqual(unknown["cost_breakdown"]["danger"], 3.0)
        self.assertEqual(unknown["cost_breakdown"]["knowledge_multiplier"], 2.0)

    def test_cache_is_bounded_and_invalidates_when_roads_change(self):
        world = path_world()
        service = PathfindingService(world, path_config(max_cache_entries=1))

        first = service.find_path((0, 1), (4, 1))
        cached = service.find_path((0, 1), (4, 1))
        world["road"][1][2] = "=="
        changed = service.find_path((0, 1), (4, 1))

        self.assertFalse(first["cache_hit"])
        self.assertTrue(cached["cache_hit"])
        self.assertFalse(changed["cache_hit"])
        self.assertEqual(service.summary()["cache_entries"], 1)
        self.assertGreaterEqual(service.summary()["invalidations"], 1)

    def test_queries_do_not_draw_randomness_and_snapshots_are_defensive(self):
        world = path_world()
        RandomService.initialize(1421)
        before = RandomService.get_state()
        service = PathfindingService(world, path_config())
        result = service.find_path((0, 0), (4, 2))
        snapshot = copy.deepcopy(service.summary())
        snapshot["queries"] = -1

        self.assertEqual(RandomService.get_state(), before)
        self.assertTrue(result["reachable"])
        self.assertNotEqual(service.summary()["queries"], -1)


ROOT = Path(__file__).resolve().parents[1]


class PathfindingIntegrationTests(unittest.TestCase):
    def test_template_is_opt_in_and_validator_checks_limits(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["pathfinding"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["pathfinding"]["road_multiplier"] = 0
        invalid["pathfinding"]["max_cache_entries"] = -1
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:pathfinding.road_multiplier:positive", caught.exception.errors)
        self.assertIn("range:pathfinding.max_cache_entries:positive", caught.exception.errors)

    def test_engine_exposes_and_persists_measured_paths(self):
        from core.simulation_engine import SimulationEngine

        legacy = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        legacy_engine = SimulationEngine.create(legacy, 1431, 8, 6)
        self.assertNotIn("pathfinding", legacy_engine.world)

        config = copy.deepcopy(legacy)
        config["pathfinding"]["enabled"] = True
        engine = SimulationEngine.create(config, 1433, 8, 6)
        result = engine.find_path((0, 0), (7, 5))
        summary = engine.get_pathfinding_summary()
        system = next(
            item for item in engine.get_systems_snapshot()
            if item["id"] == "pathfinding"
        )

        self.assertTrue(result["reachable"])
        self.assertEqual(summary["queries"], 1)
        self.assertTrue(system["enabled"])
        self.assertEqual(system["state"], summary)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pathfinding.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.get_pathfinding_summary(), summary)
        self.assertTrue(resumed.find_path((0, 0), (7, 5))["cache_hit"])


    def test_traders_follow_the_configured_measured_path(self):
        from entities.species.human.trader import Trader

        world = path_world(width=5, height=3)
        world["elev"][1][2] = 1.0
        for x in range(5):
            world["road"][0][x] = "=="
        trader = Trader.__new__(Trader)
        trader.pos = [0, 1]
        trader.target_city = SimpleNamespace(pos=[4, 1])
        trader.config = path_config()
        trader.fear_sensitivity = 1.0
        trader._get_accessible_neighbors = lambda unused: [(1, 1), (0, 0), (0, 2)]

        Trader._move_smart(trader, world)

        self.assertEqual(trader.pos, (0, 0))
        self.assertEqual(trader.pathfinding_decision["next_tile"], [0, 0])
        self.assertGreater(trader.pathfinding_decision["cost"], 0)

    def test_soldiers_use_pathfinding_only_when_opted_in(self):
        from entities.species.human.soldier import Soldier

        world = path_world(width=5, height=3)
        for x in range(5):
            world["road"][0][x] = "=="
        soldier = Soldier.__new__(Soldier)
        soldier.pos = [0, 1]
        soldier.config = path_config()
        soldier.fear_sensitivity = 0.1
        soldier._get_accessible_neighbors = lambda unused: [(1, 1), (0, 0), (0, 2)]

        Soldier._move_towards(soldier, [4, 1], world)
        self.assertEqual(soldier.pos, (0, 0))

        legacy = Soldier.__new__(Soldier)
        legacy.pos = [0, 1]
        legacy.config = {"pathfinding": {"enabled": False}}
        legacy.fear_sensitivity = 0.1
        legacy._get_accessible_neighbors = lambda unused: [(1, 1), (0, 0), (0, 2)]
        Soldier._move_towards(legacy, [4, 1], path_world(width=5, height=3))
        self.assertEqual(legacy.pos, (1, 1))


if __name__ == "__main__":
    unittest.main()

