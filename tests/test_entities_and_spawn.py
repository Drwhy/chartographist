import json
import os
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from core import bestiary_tracker
from core.entities import EntityManager, Z_ANIMAL, Z_HUMAN
from core.grid_service import SpatialGrid
from core.influence import InfluenceSystem
from core.logger import GameLogger
from core.random_service import RandomService
from core.religion import init_religion_data
from core.species import init_species_data
from core.translator import Translator
from entities.constructs.city import City
from entities.constructs.ruins import Ruins
from entities.constructs.village import Village
from entities.registry import CIV_UNITS, STRUCTURE_TYPES
from entities.spawn_system import _spawn_fauna
from entities.species.animal.base import Animal
from entities.species.human.base import Human
from entities.species.human.fisherman import Fisherman
from entities.species.human.hunter import Hunter
from entities.species.human.settler import Settler
from entities.species.human.soldier import Soldier
from entities.species.human.trader import Trader


ROOT = Path(__file__).resolve().parents[1]


def load_template():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


def animal_data(**overrides):
    data = {
        "species": "test_beast",
        "char": "🐾",
        "name": "Test Beast",
        "speed": 1.0,
        "locomotion": "land",
        "diet": "herbivore",
        "weight": 10,
        "perception_range": 5,
        "danger": 0.6,
        "danger_level": 0.6,
        "fear_sensitivity": 2.0,
        "food_value": [5, 10],
        "energy": 100,
        "max_energy": 150,
        "hunger_threshold": 60,
        "repro_threshold": 120,
        "spawn": {"elevation_min": 0.0, "elevation_max": 0.5, "chance": 1.0},
    }
    data.update(overrides)
    return data


def make_world(width=5, height=5, elevation=0.2):
    return {
        "width": width,
        "height": height,
        "cycle": 0,
        "elev": np.full((height, width), elevation, dtype=float),
        "riv": np.zeros((height, width), dtype=float),
        "road": [["  " for _ in range(width)] for _ in range(height)],
        "entities": EntityManager(),
        "influence": InfluenceSystem(width, height, {}),
        "grid": SpatialGrid(width, height, cell_size=2),
    }


class EntityAndSpawnTests(unittest.TestCase):
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
        RandomService.initialize(123)
        init_religion_data(self.config)
        init_species_data(self.config)
        GameLogger.get_new_logs()
        bestiary_tracker.reset()

    def test_active_registry_contains_expected_concrete_types(self):
        self.assertTrue({City, Village, Ruins}.issubset(set(STRUCTURE_TYPES)))
        self.assertTrue({Hunter, Fisherman, Settler, Soldier, Trader}.issubset(set(CIV_UNITS)))

    def test_animal_properties_are_data_driven(self):
        animal = Animal(1, 2, self.config, animal_data(locomotion="aquatic"))
        self.assertEqual(animal.pos, (1, 2))
        self.assertEqual(animal.z_index, Z_ANIMAL)
        self.assertTrue(animal.is_edible)
        self.assertTrue(animal.is_aquatic)
        self.assertFalse(animal.is_flying)
        self.assertEqual(animal.diet, "herbivore")
        self.assertEqual(animal.danger_level, 0.6)

    def test_animal_spawn_uses_strict_elevation_bounds_and_probability(self):
        world = make_world(elevation=0.2)
        species = animal_data()
        with mock.patch.object(RandomService, "random", return_value=0.0):
            spawned = Animal.try_spawn(2, 2, world, self.config, species)
        self.assertIsInstance(spawned, Animal)

        world["elev"][2][2] = species["spawn"]["elevation_min"]
        with mock.patch.object(RandomService, "random", return_value=0.0):
            self.assertIsNone(Animal.try_spawn(2, 2, world, self.config, species))

    def test_animal_starvation_expires_tracks_and_logs(self):
        world = make_world()
        animal = Animal(2, 2, self.config, animal_data(energy=4))
        animal.check_vital_signs(world)

        self.assertTrue(animal.is_expired)
        self.assertEqual(bestiary_tracker.get_starvations("test_beast"), 1)
        logs = GameLogger.get_new_logs()
        self.assertEqual(len(logs), 1)
        self.assertNotIn("MISSING_TEXT", logs[0])

    def test_animal_reproduction_adds_offspring_and_halves_energy(self):
        world = make_world()
        animal = Animal(2, 2, self.config, animal_data(energy=140))
        world["entities"].add(animal)
        animal.process_long_term_logic(world)

        self.assertEqual(len(world["entities"]), 2)
        offspring = [entity for entity in world["entities"] if entity is not animal][0]
        self.assertIsInstance(offspring, Animal)
        self.assertEqual(offspring.species, animal.species)
        self.assertEqual(animal.energy, 70)

    def test_spawn_system_respects_capacity_and_adds_at_most_one_animal(self):
        world = make_world()
        species = animal_data()
        config = {"fauna": [species], "max_fauna": 1}
        with (
            mock.patch.object(RandomService, "choice", return_value=species),
            mock.patch.object(RandomService, "randint", side_effect=[2, 2]),
            mock.patch.object(RandomService, "random", return_value=0.0),
        ):
            _spawn_fauna(world, config, 5, 5)
        self.assertEqual(len(world["entities"]), 1)

        _spawn_fauna(world, config, 5, 5)
        self.assertEqual(len(world["entities"]), 1)

    def test_human_family_fertility_monthly_update_and_traits(self):
        culture = self.config["cultures"][0]
        parent = Human(1, 1, culture, self.config, 1, name="Ada Lineage")
        child = Human(1, 1, culture, self.config, 1, name="Nova", parents=(parent, None))
        child.age = 20
        child.hunger = 10

        self.assertEqual(child.z_index, Z_HUMAN)
        self.assertEqual(child.family_name, "Lineage")
        self.assertTrue(child.is_fertile)
        self.assertTrue(child.is_single)
        self.assertEqual(child.faith_bonus("growth", 7), 7)
        self.assertEqual(child.species_trait("speed", 3), 3)
        child.process_monthly_update()
        self.assertAlmostEqual(child.age, 20 + 1 / 12)
        self.assertEqual(child.hunger, 15)

    def test_village_initializes_inhabitants_and_runtime_contract(self):
        culture = self.config["cultures"][0]
        village = Village(2, 2, culture, self.config)
        self.assertGreaterEqual(village.population, 5)
        self.assertLessEqual(village.population, 12)
        self.assertEqual(village.char, culture["village"])
        self.assertTrue(all(isinstance(citizen, Human) for citizen in village.citizens))
        self.assertTrue(all(citizen.species_data is not None for citizen in village.citizens))
        self.assertIsNotNone(village.religion)


if __name__ == "__main__":
    unittest.main()
