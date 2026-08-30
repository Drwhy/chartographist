import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.chronicles import ChronicleBook
from core.entities import EntityManager
from core.grid_service import SpatialGrid
from core.logger import GameLogger
from core.simulation_engine import SimulationEngine
from core.translator import Translator


ROOT = Path(__file__).resolve().parents[1]


class CausalChronicleTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")
        GameLogger.get_new_logs()

    def test_legacy_entries_are_migrated_without_losing_the_message(self):
        world = {
            "chronicles": [
                {
                    "chronicle_version": 1,
                    "chronicle_id": 4,
                    "cycle": 2,
                    "year": 0,
                    "month": 3,
                    "category": "event",
                    "message": "Ancienne trace",
                    "entity_ids": [9],
                    "position": [1, 2],
                }
            ]
        }

        entry = ChronicleBook(world).query()[0]

        self.assertEqual(entry["message"], "Ancienne trace")
        self.assertEqual(entry["chronicle_version"], 2)
        self.assertEqual(entry["event_type"], "event")
        self.assertEqual(entry["actors"], [])
        self.assertEqual(entry["objects"], [])
        self.assertEqual(entry["locations"], [])
        self.assertEqual(entry["causes"], [])
        self.assertEqual(entry["consequences"], [])
        self.assertEqual(entry["caused_by"], [])
        self.assertEqual(entry["resulted_in"], [])
        self.assertEqual(world["next_chronicle_id"], 5)

    def test_record_accepts_structured_facts_and_keeps_legacy_entity_links(self):
        world = {}
        book = ChronicleBook(world, {"max_facts": 2, "max_links": 4})
        entry = book.record(
            "La bataille commence",
            cycle=3,
            year=0,
            month=4,
            category="warfare",
            event_type="battle_started",
            entity_ids=[1],
            actors=[
                {"entity_id": 1, "role": "attacker"},
                {"entity_id": 2, "role": "defender"},
                {"entity_id": 2, "role": "defender"},
            ],
            objects=[
                {"object_id": "banner:1", "role": "standard"},
                {"object_id": "sword:2", "role": "weapon"},
                {"object_id": "shield:3", "role": "armor"},
            ],
            locations=[{"location_id": "tile:3,4", "role": "battlefield"}],
            causes=[{"kind": "territorial_dispute"}, {"kind": "revenge"}, {"kind": "ignored"}],
            consequences=[{"kind": "casualties", "count": 3}],
            facts={"winner_id": None, "front": "north", "ignored": True},
        )

        self.assertEqual(entry["event_type"], "battle_started")
        self.assertEqual(entry["entity_ids"], [1, 2])
        self.assertEqual(len(entry["actors"]), 2)
        self.assertEqual(len(entry["objects"]), 2)
        self.assertEqual(entry["locations"][0]["location_id"], "tile:3,4")
        self.assertEqual(len(entry["facts"]), 2)
        self.assertEqual(len(entry["causes"]), 2)
        self.assertEqual(entry["facts"]["front"], "north")
        self.assertEqual(world["chronicles"][0], entry)

    def test_causal_links_are_bidirectional_idempotent_and_bounded(self):
        book = ChronicleBook({}, {"max_links": 2})
        root = book.record("Famine", cycle=1, year=0, month=2, event_type="famine")
        first = book.record(
            "Exode",
            cycle=2,
            year=0,
            month=3,
            event_type="migration",
            caused_by=[root["chronicle_id"]],
        )
        second = book.record(
            "Ville affaiblie",
            cycle=3,
            year=0,
            month=4,
            event_type="decline",
            caused_by=[root["chronicle_id"], root["chronicle_id"]],
        )
        overflow = book.record(
            "Dernière rumeur",
            cycle=4,
            year=0,
            month=5,
            event_type="rumor",
            caused_by=[root["chronicle_id"]],
        )

        self.assertEqual(
            book.get(root["chronicle_id"])["resulted_in"],
            [first["chronicle_id"], second["chronicle_id"]],
        )
        self.assertEqual(overflow["caused_by"], [])
        self.assertFalse(book.link(root["chronicle_id"], first["chronicle_id"]))
        self.assertFalse(book.link(999, first["chronicle_id"]))

    def test_causal_chain_traverses_causes_and_results_without_cycles(self):
        book = ChronicleBook({})
        root = book.record("Sécheresse", cycle=1, year=0, month=2)
        middle = book.record(
            "Famine", cycle=2, year=0, month=3, caused_by=[root["chronicle_id"]]
        )
        leaf = book.record(
            "Migration", cycle=3, year=0, month=4, caused_by=[middle["chronicle_id"]]
        )

        causes = book.causal_chain(leaf["chronicle_id"], direction="causes")
        results = book.causal_chain(root["chronicle_id"], direction="results")

        self.assertEqual([entry["chronicle_id"] for entry in causes], [leaf["chronicle_id"], middle["chronicle_id"], root["chronicle_id"]])
        self.assertEqual([entry["chronicle_id"] for entry in results], [root["chronicle_id"], middle["chronicle_id"], leaf["chronicle_id"]])
        with self.assertRaises(ValueError):
            book.causal_chain(root["chronicle_id"], direction="sideways")

    def test_text_can_be_generated_from_i18n_facts_without_explicit_message(self):
        for language, expected in (("fr", "migrent"), ("en", "migrate"), ("es", "migran")):
            Translator.load(language)
            entry = ChronicleBook({}).record(
                None,
                cycle=5,
                year=0,
                month=6,
                event_type="migration_cohort",
                text_key="events.migration_cohort",
                text_args={
                    "count": 3,
                    "origin": "A",
                    "destination": "B",
                    "cause": "test",
                },
            )
            self.assertIn(expected, entry["message"])
            self.assertEqual(entry["text_key"], "events.migration_cohort")
            self.assertNotIn("MISSING_TEXT", entry["message"])

    def test_query_filters_event_actors_objects_locations_and_causes(self):
        book = ChronicleBook({})
        cause = book.record("Cause", cycle=1, year=0, month=2)
        selected = book.record(
            "Effet",
            cycle=2,
            year=0,
            month=3,
            event_type="battle",
            actors=[{"entity_id": 7, "role": "leader"}],
            objects=[{"object_id": "artifact:2", "role": "weapon"}],
            locations=[{"location_id": "site:9", "role": "field"}],
            caused_by=[cause["chronicle_id"]],
        )
        book.record("Autre", cycle=3, year=0, month=4)

        self.assertEqual(book.query(event_type="battle"), [selected])
        self.assertEqual(book.query(actor_id=7), [selected])
        self.assertEqual(book.query(object_id="artifact:2"), [selected])
        self.assertEqual(book.query(location_id="site:9"), [selected])
        self.assertEqual(book.query(caused_by=cause["chronicle_id"]), [selected])

    def test_logger_metadata_flows_into_a_causal_chronicle(self):
        world = {
            "width": 2,
            "height": 2,
            "cycle": 0,
            "entities": EntityManager(),
            "grid": SpatialGrid(2, 2, cell_size=1),
            "influence": mock.Mock(),
        }
        stats = {"year": 0, "month": 1, "seed": 9, "logs": []}
        engine = SimulationEngine(world, stats, {"max_fauna": 0})
        root = engine.record_chronicle(
            "Tension",
            category="diplomacy",
            event_type="tension_risen",
            actors=[{"entity_id": 1, "role": "claimant"}],
        )
        GameLogger.log(
            "Guerre",
            category="warfare",
            entity_ids=[1, 2],
            event_type="war_declared",
            actors=[
                {"entity_id": 1, "role": "attacker"},
                {"entity_id": 2, "role": "defender"},
            ],
            caused_by=[root["chronicle_id"]],
            consequences=[{"kind": "mobilization"}],
        )

        with (
            mock.patch("core.simulation_engine.entities_spawn.spawn_system"),
            mock.patch("core.simulation_engine.EventManager.update"),
        ):
            engine.step()

        event = engine.get_chronicles(event_type="war_declared")[0]
        self.assertEqual(event["caused_by"], [root["chronicle_id"]])
        self.assertEqual(event["actors"][0]["role"], "attacker")
        self.assertEqual(
            engine.get_chronicle_chain(event["chronicle_id"], direction="causes")[-1]["event_type"],
            "tension_risen",
        )

    def test_history_template_is_opt_in_and_limits_are_validated(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["history"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["history"]["enabled"] = "yes"
        invalid["history"]["max_facts"] = 0
        invalid["history"]["max_links"] = True
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("type:history.enabled:bool", caught.exception.errors)
        self.assertIn("range:history.max_facts:positive", caught.exception.errors)
        self.assertIn("type:history.max_links:int", caught.exception.errors)

    def test_war_and_peace_form_a_real_cross_system_causal_chain(self):
        from core.warfare import WarfareSystem
        from tests.test_warfare import settlement, war_world, warfare_config

        first, second = settlement(1, 0), settlement(2, 5)
        world = war_world(first, second)
        config = warfare_config(
            max_supply_cost=1.0,
            unsupplied_morale_loss=100.0,
            retreat_morale=50.0,
        )
        config["history"] = {"enabled": True, "max_facts": 16, "max_links": 8}
        config["peace"] = {
            "enabled": True,
            "transfer_territory": False,
            "tribute_food_ratio": 0.0,
            "tribute_base": 0.0,
            "commercial_rights": 0.0,
            "postwar_tension": 0.0,
            "refugee_rate": 0.25,
            "max_treaties": 8,
        }
        system = WarfareSystem(world, config)

        declared = system.declare_war(
            1,
            2,
            cause="territorial_dispute",
            objective="secure_frontier",
            evidence=["contested_tile:3,0"],
        )
        stored = system._campaign_for(1, 2)
        system._end_campaign(stored, 1, "military_defeat")
        treaty = world["peace"]["treaties"][0]

        self.assertIsNotNone(declared["chronicle_id"])
        self.assertIsNotNone(stored["end_chronicle_id"])
        self.assertIsNotNone(treaty["chronicle_id"])
        chain = ChronicleBook(world, config).causal_chain(
            treaty["chronicle_id"], direction="causes"
        )
        self.assertEqual(
            [entry["event_type"] for entry in chain],
            ["peace_treaty", "war_ended", "war_declared"],
        )

    def test_causal_graph_survives_checkpoint_and_snapshots_are_defensive(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        engine = SimulationEngine.create(config, 1507, 8, 6)
        root = engine.record_chronicle("Cause", event_type="cause")
        effect = engine.record_chronicle(
            "Effet",
            event_type="effect",
            caused_by=[root["chronicle_id"]],
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "causal.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)

        chain = resumed.get_chronicle_chain(effect["chronicle_id"], direction="causes")
        chain[0]["message"] = "corrompu"
        self.assertEqual(
            resumed.get_chronicle(effect["chronicle_id"])["message"],
            "Effet",
        )

    def test_terminal_chronicle_view_exposes_causal_links(self):
        from render.ui_bestiary import _build_chronicle_entries

        world = {}
        book = ChronicleBook(world)
        cause = book.record("Cause", cycle=1, year=0, month=2, category="warfare")
        book.record(
            "Conséquence",
            cycle=2,
            year=0,
            month=3,
            caused_by=[cause["chronicle_id"]],
        )

        rendered = "\n".join(_build_chronicle_entries(world)[0])
        self.assertIn("1 cause", rendered)
        self.assertNotIn("MISSING_TEXT", rendered)

        all_rendered = "\n".join(
            line for item in _build_chronicle_entries(world) for line in item
        )
        self.assertIn("Guerre", all_rendered)

if __name__ == "__main__":
    unittest.main()

