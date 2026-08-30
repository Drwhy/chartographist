import json
import unittest
from pathlib import Path

from core.random_service import RandomService
from core.simulation_engine import SimulationEngine
from core.translator import Translator


ROOT = Path(__file__).resolve().parents[1]


def visible_config():
    config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
    for section in (
        "characters",
        "climate",
        "diplomacy",
        "economy",
        "pathfinding",
        "migration",
        "warfare",
        "peace",
        "history",
        "sites",
        "territory",
        "food_balance",
        "knowledge",
        "materials",
        "artifacts",
        "legends",
        "politics",
        "resources",
    ):
        config[section]["enabled"] = True
    return config


class SystemVisibilityTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")
        self.engine = SimulationEngine.create(visible_config(), 731, 12, 8)
        self.engine.step()

    def test_engine_exposes_all_influential_systems_without_random_draws(self):
        before = RandomService.get_state()
        self.engine.record_chronicle("Événement visible", category="event")

        snapshot = self.engine.get_systems_snapshot()

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(
            [entry["id"] for entry in snapshot],
            [
                "climate", "resources", "ecology", "food", "economy",
                "diplomacy", "characters", "materials", "artifacts", "legends", "knowledge",
                "politics", "pathfinding", "territory", "sites", "migration", "warfare", "peace", "history", "influence", "events", "scenario",
            ],
        )
        self.assertTrue(all(
            {"id", "enabled", "state", "effects"} <= set(entry)
            for entry in snapshot
        ))
        self.assertTrue(next(
            entry for entry in snapshot if entry["id"] == "knowledge"
        )["enabled"])
        json.dumps(snapshot)
        history = next(entry for entry in snapshot if entry["id"] == "history")
        events = next(entry for entry in snapshot if entry["id"] == "events")
        self.assertGreaterEqual(history["state"]["entries"], 1)
        self.assertGreaterEqual(history["state"]["causal_links"], 0)
        self.assertGreaterEqual(events["state"]["triggered"], 1)



    def test_snapshot_and_system_tab_are_defensive_and_translated(self):
        from render.ui_bestiary import SYSTEMS_TAB, _build_system_entries
        from main import handle_bestiary_input

        snapshot = self.engine.get_systems_snapshot()
        snapshot[0]["state"]["corrupted"] = True
        self.assertNotIn("corrupted", self.engine.get_systems_snapshot()[0]["state"])

        entries = _build_system_entries(self.engine.world, self.engine.config)
        rendered = "\n".join(line for entry in entries for line in entry)
        self.assertEqual(len(entries), 22)
        self.assertIn("territoires", rendered)
        self.assertIn("chemins", rendered)
        self.assertIn("Migrations", rendered)
        self.assertIn("Guerres", rendered)
        self.assertIn("Paix", rendered)
        self.assertIn("Historique causal", rendered)
        self.assertIn("Sites persistants", rendered)
        self.assertIn("Objets et artefacts", rendered)
        self.assertIn("Réputation et légendes", rendered)
