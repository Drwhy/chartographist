import unittest
from types import SimpleNamespace
from unittest import mock

from core import bestiary_tracker
from core.entities import EntityManager
from core.simulation_engine import SimulationEngine
from entities.species.animal.base import Animal


class BestiarySnapshotTests(unittest.TestCase):
    def setUp(self):
        bestiary_tracker.reset()

    def tearDown(self):
        bestiary_tracker.reset()

    def test_snapshot_exposes_living_fauna_without_raw_configuration(self):
        animal = object.__new__(Animal)
        animal.species = "wolf"
        animal.is_expired = False
        entities = EntityManager()
        entities.add(animal)
        config = {
            "fauna": [{
                "species": "wolf",
                "name": "Loup",
                "char": "🐺",
                "locomotion": "land",
                "diet": "carnivore",
                "weight": 45,
                "speed": 1.1,
                "perception_range": 5,
                "fear_sensitivity": 2.0,
                "food_value": [8, 14],
                "danger_level": 0.7,
                "internal_debug": {"spawn_weight": 99},
            }],
        }
        bestiary_tracker.track_kill("wolf")

        with (
            mock.patch(
                "core.bestiary.get_species_templates",
                return_value=[{
                    "name": "Sylvain",
                    "culture": "Empire",
                    "origin": "forest",
                    "physiology": "slender",
                    "nature": "patient",
                    "emojis": ["🌲", "🧬", "🌀"],
                    "bonuses": {"strength": 2},
                    "speed_mod": 0.1,
                    "naming": {"private": True},
                }],
            ),
            mock.patch(
                "core.bestiary.get_religion_templates",
                return_value=[{
                    "name": "Foi des Sources",
                    "god": "Aqua",
                    "culture": "Empire",
                    "domain": "water",
                    "emoji": "💧",
                    "bonuses": {"growth": 1},
                    "naming": {"private": True},
                }],
            ),
        ):
            from core.bestiary import bestiary_snapshot
            snapshot = bestiary_snapshot({"entities": entities}, config)

        self.assertEqual(set(snapshot), {"fauna", "species", "religions", "settlements"})
        self.assertEqual(snapshot["fauna"][0]["live"], 1)
        self.assertEqual(snapshot["fauna"][0]["killed"], 1)
        self.assertEqual(snapshot["fauna"][0]["name"], "Loup")
        self.assertEqual(snapshot["species"][0]["name"], "Sylvain")
        self.assertEqual(snapshot["religions"][0]["god"], "Aqua")
        self.assertNotIn("internal_debug", snapshot["fauna"][0])
        self.assertNotIn("naming", snapshot["species"][0])
        self.assertNotIn("naming", snapshot["religions"][0])

    def test_engine_exposes_the_headless_bestiary_contract(self):
        engine = SimpleNamespace(world={"entities": EntityManager()}, config={"fauna": []})

        snapshot = SimulationEngine.get_bestiary_snapshot(engine)

        self.assertEqual(snapshot["fauna"], [])
        self.assertEqual(snapshot["settlements"], [])

    def test_terminal_b_key_still_opens_and_closes_the_bestiary(self):
        from main import handle_bestiary_input

        state = {"active": False, "tab": "fauna", "page": 3}
        handle_bestiary_input("B", state)
        self.assertTrue(state["active"])
        self.assertEqual(state["page"], 0)
        handle_bestiary_input("b", state)
        self.assertFalse(state["active"])


if __name__ == "__main__":
    unittest.main()
