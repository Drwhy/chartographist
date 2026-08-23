import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import events.event_manager as event_manager_module
from core.entities import Entity, EntityManager
from core.grid_service import SpatialGrid
from core.influence import InfluenceSystem
from core.random_service import RandomService
from core.translator import Translator
from core.world_factory import assemble_world
from entities.species.animal.base import Animal
from events.abduction import Abduction
from events.epidemic import Epidemic
from events.event_manager import EventManager
from events.event_registry import EVENT_CATALOG
from events.volcano import VolcanoEruption
from render.ui_header import render_header
from render.ui_map import get_char_at


ROOT = Path(__file__).resolve().parents[1]


def load_template():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


class DummyEvent:
    chance = 0.5

    def __init__(self, condition=True):
        self.condition_result = condition
        self.ticks = 0
        self.conditions = 0
        self.triggers = 0

    def tick(self, world, stats):
        self.ticks += 1

    def condition(self, world, stats):
        self.conditions += 1
        return self.condition_result

    def trigger(self, world, stats, config):
        self.triggers += 1


def animal_data():
    return {
        "species": "smoke_grazer",
        "char": "g",
        "name": "Smoke Grazer",
        "speed": 1.0,
        "locomotion": "land",
        "diet": "herbivore",
        "energy": 100,
        "max_energy": 150,
        "hunger_threshold": 60,
        "repro_threshold": 999,
        "danger": 0.1,
        "danger_level": 0.1,
        "food_value": [2, 4],
    }


class EventsRenderAndSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_template()
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)

    def setUp(self):
        RandomService.initialize(777)

    def test_event_catalog_contains_all_builtin_events_once(self):
        event_types = [type(event) for event in EVENT_CATALOG]
        self.assertEqual(event_types.count(Abduction), 1)
        self.assertEqual(event_types.count(Epidemic), 1)
        self.assertEqual(event_types.count(VolcanoEruption), 1)

    def test_event_manager_ticks_before_probability_and_triggers_when_allowed(self):
        event = DummyEvent(condition=True)
        with (
            mock.patch.object(event_manager_module, "EVENT_CATALOG", [event]),
            mock.patch.object(RandomService, "random", return_value=0.0),
        ):
            EventManager.update({}, {}, {})
        self.assertEqual((event.ticks, event.conditions, event.triggers), (1, 1, 1))

    def test_event_manager_skips_condition_when_probability_fails(self):
        event = DummyEvent(condition=True)
        with (
            mock.patch.object(event_manager_module, "EVENT_CATALOG", [event]),
            mock.patch.object(RandomService, "random", return_value=1.0),
        ):
            EventManager.update({}, {}, {})
        self.assertEqual((event.ticks, event.conditions, event.triggers), (1, 0, 0))

    def test_event_manager_respects_false_condition(self):
        event = DummyEvent(condition=False)
        with (
            mock.patch.object(event_manager_module, "EVENT_CATALOG", [event]),
            mock.patch.object(RandomService, "random", return_value=0.0),
        ):
            EventManager.update({}, {}, {})
        self.assertEqual((event.ticks, event.conditions, event.triggers), (1, 1, 0))

    def test_map_rendering_prioritizes_entity_then_road_then_river(self):
        world = {
            "width": 3,
            "height": 3,
            "cycle": 0,
            "elev": np.full((3, 3), 0.2),
            "riv": np.zeros((3, 3)),
            "road": [["  " for _ in range(3)] for _ in range(3)],
            "entities": EntityManager(),
        }
        low = Entity(1, 1, "l", 10, 1)
        high = Entity(1, 1, "H", 50, 1)
        world["entities"].add(low)
        world["entities"].add(high)
        self.assertEqual(get_char_at(1, 1, world, self.config), "H")

        high.is_expired = True
        low.is_expired = True
        world["road"][1][1] = "··"
        world["riv"][1][1] = 2
        self.assertEqual(get_char_at(1, 1, world, self.config), "··")
        world["road"][1][1] = "  "
        self.assertEqual(get_char_at(1, 1, world, self.config), self.config["water"]["river"])

    def test_header_accepts_runtime_stats_contract(self):
        world = {"entities": EntityManager()}
        stats = {"year": 2, "month": 4, "seed": 99}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            render_header(4, world, stats, self.config)
        rendered = output.getvalue()
        self.assertIn("99", rendered)
        self.assertNotIn("MISSING_TEXT", rendered)

    def test_small_simulation_pipeline_runs_multiple_cycles(self):
        config = dict(self.config)
        config["max_fauna"] = 0
        RandomService.initialize(909)
        world, stats = assemble_world(12, 8, config, 909)
        world["grid"] = SpatialGrid(12, 8, cell_size=4)
        land_positions = np.argwhere(world["elev"] >= 0)
        self.assertGreater(len(land_positions), 0)
        y, x = map(int, land_positions[0])
        grazer = Animal(x, y, config, animal_data())
        world["entities"].add(grazer)

        for cycle in range(1, 26):
            world["cycle"] = cycle
            world["grid"].clear()
            for entity in world["entities"]:
                if not entity.is_expired:
                    world["grid"].add_entity(entity)
            if cycle % 10 == 0:
                world["influence"].update()
            for entity in list(world["entities"]):
                entity.process_turn(world, stats)
                if cycle % 10 == 0:
                    entity.update_influence(world)
                    if hasattr(entity, "check_vital_signs"):
                        entity.check_vital_signs(world)
            with mock.patch.object(event_manager_module, "EVENT_CATALOG", []):
                EventManager.update(world, stats, config)
            world["entities"].remove_dead()

        self.assertEqual(world["cycle"], 25)
        self.assertGreaterEqual(len(world["entities"]), 0)
        self.assertEqual(world["elev"].shape, (8, 12))


if __name__ == "__main__":
    unittest.main()
