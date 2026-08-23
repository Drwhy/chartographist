import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.entities import Entity, EntityManager
from core.grid_service import SpatialGrid
from core.logger import GameLogger
from core.simulation_engine import SimulationEngine
from core.translator import Translator


ROOT = Path(__file__).resolve().parents[1]


class ChronicleAndInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            Translator.load("fr")
        finally:
            os.chdir(previous)

    def setUp(self):
        GameLogger.get_new_logs()

    def test_chronicle_records_structured_entries_and_filters_them(self):
        from core.chronicles import ChronicleBook

        world = {}
        book = ChronicleBook(world)
        first = book.record(
            "Fondation",
            cycle=12,
            year=1,
            month=1,
            category="settlement",
            entity_ids=[9, 9, 3],
            position=(4, 5),
        )
        second = book.record("Éruption", cycle=18, year=1, month=7, category="disaster")

        self.assertEqual(first["chronicle_id"], 1)
        self.assertEqual(first["entity_ids"], [9, 3])
        self.assertEqual(first["position"], [4, 5])
        self.assertEqual(second["chronicle_id"], 2)
        self.assertEqual(
            book.query(category="settlement", entity_id=9, since_cycle=10, until_cycle=15),
            [first],
        )
        self.assertEqual(book.query(limit=1), [second])

    def test_chronicle_ignores_empty_messages_and_returns_copies(self):
        from core.chronicles import ChronicleBook

        book = ChronicleBook({})
        self.assertIsNone(book.record(None, cycle=0, year=0, month=1))
        entry = book.record("Événement", cycle=1, year=0, month=2)
        result = book.query()
        result[0]["message"] = "altéré"
        self.assertEqual(entry["message"], "Événement")
        self.assertEqual(book.query()[0]["message"], "Événement")

    def test_engine_records_pending_logs_without_changing_legacy_log_contract(self):
        world = {
            "width": 2,
            "height": 2,
            "cycle": 0,
            "entities": EntityManager(),
            "grid": SpatialGrid(2, 2, cell_size=1),
            "influence": mock.Mock(),
        }
        stats = {"year": 0, "month": 1, "seed": 7, "logs": []}
        engine = SimulationEngine(world, stats, {"max_fauna": 0})
        self.assertEqual(world["chronicles"], [])
        self.assertEqual(world["next_chronicle_id"], 1)
        GameLogger.log("Une cité est fondée")

        with (
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            engine.step()

        self.assertEqual(stats["logs"], ["Une cité est fondée"])
        self.assertEqual(world["chronicles"][0]["message"], "Une cité est fondée")
        self.assertEqual(world["chronicles"][0]["cycle"], 1)

    def test_inspector_finds_entity_by_stable_id_and_related_chronicles(self):
        from core.chronicles import ChronicleBook
        from core.inspection import inspect_entity

        entity = Entity(4, 5, "@", 40, 1.25)
        entity.name = "Ada"
        world = {"entities": EntityManager()}
        world["entities"].add(entity)
        ChronicleBook(world).record(
            "Ada voyage",
            cycle=3,
            year=0,
            month=4,
            entity_ids=[entity.entity_id],
        )

        inspection = inspect_entity(world, entity.entity_id)

        self.assertEqual(inspection["entity"]["entity_id"], entity.entity_id)
        self.assertEqual(inspection["entity"]["type"], "Entity")
        self.assertEqual(inspection["entity"]["name"], "Ada")
        self.assertEqual(inspection["entity"]["position"], [4, 5])
        self.assertEqual(inspection["chronicles"][0]["message"], "Ada voyage")
        self.assertIsNone(inspect_entity(world, 999999))

    def test_chronicles_survive_checkpoint_round_trip(self):
        from core.chronicles import ChronicleBook

        world = {
            "width": 2,
            "height": 2,
            "cycle": 4,
            "entities": EntityManager(),
            "grid": SpatialGrid(2, 2, cell_size=1),
        }
        stats = {"year": 0, "month": 5, "seed": 11, "logs": []}
        engine = SimulationEngine(world, stats, {})
        ChronicleBook(world).record("Trace durable", cycle=4, year=0, month=5)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chronicles.chart"
            engine.save(path)
            restored = SimulationEngine.load(path)

        self.assertEqual(restored.get_chronicles()[0]["message"], "Trace durable")
        self.assertEqual(restored.world["next_chronicle_id"], 2)

    def test_terminal_chronicle_entries_are_localized(self):
        from core.chronicles import ChronicleBook
        from render.ui_bestiary import _build_chronicle_entries

        world = {}
        ChronicleBook(world).record("Une trace", cycle=14, year=1, month=3, category="event")
        ChronicleBook(world).record("Trace récente", cycle=15, year=1, month=4, category="event")
        rendered = "\n".join(_build_chronicle_entries(world)[0])

        self.assertIn("Trace récente", rendered)
        self.assertIn("15", rendered)
        self.assertIn("Événement", rendered)
        self.assertNotIn("MISSING_TEXT", rendered)

    def test_logger_metadata_links_runtime_chronicle_to_an_entity(self):
        entity = Entity(1, 1, "@", 40, 1.0)
        world = {
            "width": 2,
            "height": 2,
            "cycle": 0,
            "entities": EntityManager(),
            "grid": SpatialGrid(2, 2, cell_size=1),
            "influence": mock.Mock(),
        }
        world["entities"].add(entity)
        stats = {"year": 0, "month": 1, "seed": 7, "logs": []}
        engine = SimulationEngine(world, stats, {"max_fauna": 0})
        GameLogger.log(
            "Départ",
            category="journey",
            entity_ids=[entity.entity_id],
            position=entity.pos,
        )

        with (
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            engine.step()

        entry = engine.get_chronicles(entity_id=entity.entity_id)[0]
        self.assertEqual(entry["category"], "journey")
        self.assertEqual(entry["position"], [1, 1])
        self.assertEqual(stats["logs"], ["Départ"])

    def test_pending_log_metadata_survives_checkpoint(self):
        world = {
            "width": 2,
            "height": 2,
            "cycle": 0,
            "entities": EntityManager(),
            "grid": SpatialGrid(2, 2, cell_size=1),
        }
        stats = {"year": 0, "month": 1, "seed": 13, "logs": []}
        engine = SimulationEngine(world, stats, {"max_fauna": 0})
        GameLogger.log("Trace liée", category="settlement", entity_ids=[77], position=(1, 0))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pending.chart"
            engine.save(path)
            GameLogger.get_new_logs()
            restored = SimulationEngine.load(path)

        with (
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            restored.step()

        entry = restored.get_chronicles(entity_id=77)[0]
        self.assertEqual(entry["category"], "settlement")
        self.assertEqual(entry["position"], [1, 0])
    def test_chronicle_tab_can_be_selected_and_rendered(self):
        from main import handle_bestiary_input
        from render.ui_bestiary import CHRONICLES_TAB, render_bestiary

        world = {"entities": EntityManager()}
        from core.chronicles import ChronicleBook
        ChronicleBook(world).record("Mémoire du monde", cycle=2, year=0, month=3)
        state = {"active": True, "tab": "fauna", "page": 4}

        handle_bestiary_input("h", state)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            render_bestiary(60, 5, world, {}, state)

        self.assertEqual(state["tab"], CHRONICLES_TAB)
        self.assertEqual(state["page"], 0)
        self.assertIn("Mémoire du monde", output.getvalue())
        self.assertNotIn("MISSING_TEXT", output.getvalue())
    def test_village_promotion_emits_entity_linked_chronicle_metadata(self):
        from entities.constructs.base import Construct
        from entities.constructs.village import Village

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        settlement = Construct.__new__(Construct)
        settlement.entity_id = 404
        settlement._pos = [1, 1]
        settlement.culture = config["cultures"][0]
        settlement.config = config
        settlement.name = "Continuum"
        settlement.citizens = []
        settlement.food_stock = 20
        settlement.religion = None
        settlement.is_expired = False
        world = {"entities": EntityManager()}

        Village._evolve_to_city(settlement, world)
        GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(1)[0]

        self.assertEqual(metadata["category"], "settlement")
        self.assertEqual(metadata["entity_ids"], [404])
        self.assertEqual(metadata["position"], [1, 1])

    def test_city_collapse_preserves_identity_and_emits_linked_metadata(self):
        from entities.constructs.base import Construct
        from entities.constructs.city import City
        from entities.constructs.ruins import Ruins

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        settlement = Construct.__new__(Construct)
        settlement.entity_id = 505
        settlement._pos = [2, 3]
        settlement.culture = config["cultures"][0]
        settlement.config = config
        settlement.name = "Mémoire"
        settlement.is_expired = False
        world = {"entities": EntityManager()}

        City._collapse_into_ruins(settlement, world)
        ruin = next(entity for entity in world["entities"] if isinstance(entity, Ruins))
        GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(1)[0]

        self.assertEqual(ruin.entity_id, 505)
        self.assertEqual(metadata["category"], "settlement")
        self.assertEqual(metadata["entity_ids"], [505])
        self.assertEqual(metadata["position"], [2, 3])
    def test_runtime_code_does_not_use_memory_addresses_as_entity_identity(self):
        offenders = []
        for source_root in (ROOT / "core", ROOT / "entities", ROOT / "events", ROOT / "render"):
            for path in source_root.rglob("*.py"):
                if re.search(r"(?<![_\w])id\(", path.read_text(encoding="utf-8")):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()