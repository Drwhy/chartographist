import json
import unittest
from pathlib import Path

import numpy as np

from core.entities import EntityManager
from core.fauna_gen import generate_fauna
from core.geo import generate_geology, simulate_hydrology
from core.random_service import RandomService
from core.religion import (
    PersonalFaith,
    ReligionDemographics,
    get_religion_templates,
    init_religion_data,
)
from core.species import PersonalSpecies, get_species_templates, init_species_data
from core.world_factory import assemble_world


ROOT = Path(__file__).resolve().parents[1]


def load_template():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.config = load_template()
        RandomService.initialize(2468)

    def test_geology_is_seeded_normalized_and_has_expected_shape(self):
        elevation_a, plates_a = generate_geology(18, 10)
        RandomService.initialize(2468)
        elevation_b, plates_b = generate_geology(18, 10)

        np.testing.assert_array_equal(elevation_a, elevation_b)
        self.assertEqual(plates_a, plates_b)
        self.assertEqual(elevation_a.shape, (10, 18))
        self.assertAlmostEqual(float(elevation_a.min()), -1.0)
        self.assertAlmostEqual(float(elevation_a.max()), 1.0)
        self.assertEqual(len(plates_a), 8)

    def test_hydrology_is_seeded_non_negative_and_shape_preserving(self):
        elevation, _ = generate_geology(16, 9)
        RandomService.initialize(99)
        rivers_a = simulate_hydrology(16, 9, elevation)
        RandomService.initialize(99)
        rivers_b = simulate_hydrology(16, 9, elevation)

        np.testing.assert_array_equal(rivers_a, rivers_b)
        self.assertEqual(rivers_a.shape, elevation.shape)
        self.assertTrue(np.all(rivers_a >= 0))

    def test_fauna_generation_is_deterministic_and_schema_compatible(self):
        expected_count = sum(
            archetype.get("count", 2)
            for archetype in self.config["fauna_archetypes"].values()
        )
        RandomService.initialize(111)
        fauna_a = generate_fauna(self.config)
        RandomService.initialize(111)
        fauna_b = generate_fauna(self.config)

        self.assertEqual(fauna_a, fauna_b)
        self.assertEqual(len(fauna_a), expected_count)
        required = {
            "species", "char", "name", "speed", "locomotion", "diet",
            "weight", "perception_range", "danger", "danger_level",
            "fear_sensitivity", "food_value", "energy", "max_energy",
            "hunger_threshold", "repro_threshold", "spawn",
        }
        for species in fauna_a:
            self.assertTrue(required.issubset(species))
            self.assertLessEqual(species["danger_level"], 1.0)
            self.assertLess(species["spawn"]["elevation_min"], species["spawn"]["elevation_max"])

    def test_species_generation_is_deterministic_and_one_per_culture(self):
        RandomService.initialize(222)
        init_species_data(self.config)
        species_a = get_species_templates()
        RandomService.initialize(222)
        init_species_data(self.config)
        species_b = get_species_templates()

        self.assertEqual(species_a, species_b)
        self.assertEqual(len(species_a), len(self.config["cultures"]))
        self.assertEqual(
            {item["culture"] for item in species_a},
            {culture["name"] for culture in self.config["cultures"]},
        )
        personal = PersonalSpecies(species_a[0])
        self.assertEqual(personal.name, species_a[0]["name"])
        self.assertEqual(personal.emoji_str, " ".join(species_a[0]["emojis"]))

    def test_religion_generation_and_demographics_contract(self):
        RandomService.initialize(333)
        init_religion_data(self.config)
        religions_a = get_religion_templates()
        RandomService.initialize(333)
        init_religion_data(self.config)
        religions_b = get_religion_templates()

        self.assertEqual(religions_a, religions_b)
        self.assertEqual(len(religions_a), len(self.config["cultures"]))
        demographics = ReligionDemographics({religions_a[0]["name"]: 3, religions_a[1]["name"]: 1})
        self.assertAlmostEqual(sum(demographics.fractions.values()), 1.0)
        self.assertEqual(demographics.dominant, religions_a[0]["name"])
        faith = PersonalFaith(religions_a[0])
        self.assertEqual(faith.religion_name, religions_a[0]["name"])
        self.assertEqual(faith.domain, religions_a[0]["domain"])

    def test_world_factory_builds_a_replayable_world_contract(self):
        RandomService.initialize(444)
        world_a, stats_a = assemble_world(14, 8, self.config, 444)
        RandomService.initialize(444)
        world_b, stats_b = assemble_world(14, 8, self.config, 444)

        required_world = {
            "width", "height", "seed", "cycle", "elev", "riv", "plates",
            "road", "entities", "influence",
        }
        self.assertTrue(required_world.issubset(world_a))
        self.assertEqual((world_a["width"], world_a["height"]), (14, 8))
        self.assertIsInstance(world_a["entities"], EntityManager)
        self.assertEqual(len(world_a["road"]), 8)
        self.assertTrue(all(len(row) == 14 for row in world_a["road"]))
        np.testing.assert_array_equal(world_a["elev"], world_b["elev"])
        np.testing.assert_array_equal(world_a["riv"], world_b["riv"])
        self.assertEqual(world_a["plates"], world_b["plates"])
        self.assertEqual(stats_a, stats_b)
        self.assertTrue({"year", "seed", "logs"}.issubset(stats_a))


if __name__ == "__main__":
    unittest.main()
