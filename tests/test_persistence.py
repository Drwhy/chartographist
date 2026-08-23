import json
import tempfile
import unittest

import numpy as np
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core import bestiary_tracker
from core.entities import Entity
from core.entity_ids import EntityIdService
from core.logger import GameLogger
from core.persistence import SaveFormatError
from core.religion import get_religion_templates, init_religion_data
from core.species import get_species_templates, init_species_data
from core.random_service import RandomService
from core.simulation_engine import SimulationEngine
from core import bestiary_tracker
from core.entities import EntityManager
from entities.constructs.base import Construct
from entities.constructs.city import City
from entities.constructs.village import Village
from entities.species.human.base import Human
from entities.species.human.farmer import Farmer
from entities.species.human.trader import Trader
from events.event_registry import EVENT_CATALOG
from events.volcano import VolcanoEruption
from entities.constructs.ruins import Ruins

ROOT = Path(__file__).resolve().parents[1]


class StableEntityIdTests(unittest.TestCase):
    def setUp(self):
        EntityIdService.reset()

    def test_entities_receive_monotonic_stable_ids(self):
        first = Entity(0, 0, "a", 1, 1.0)
        second = Entity(1, 1, "b", 1, 1.0)

        self.assertEqual(first.entity_id, 1)
        self.assertEqual(second.entity_id, 2)
        self.assertNotEqual(first.entity_id, second.entity_id)

    def test_id_sequence_can_be_snapshotted_and_restored(self):
        Entity(0, 0, "a", 1, 1.0)
        saved_state = EntityIdService.get_state()
        Entity(1, 1, "b", 1, 1.0)

        EntityIdService.set_state(saved_state)
        resumed = Entity(2, 2, "c", 1, 1.0)

        self.assertEqual(resumed.entity_id, 2)

    def test_identity_can_be_transferred_during_entity_evolution(self):
        village = Entity(0, 0, "v", 1, 1.0)
        city = Entity(0, 0, "c", 1, 1.0)

        city.preserve_identity_from(village)

        self.assertEqual(city.entity_id, village.entity_id)

    def test_new_engine_resets_ids_before_world_assembly(self):
        for _ in range(5):
            Entity(0, 0, "x", 1, 1.0)
        captured = {}

        def assemble(width, height, config, seed):
            captured["entity"] = Entity(0, 0, "x", 1, 1.0)
            return {"cycle": 0, "entities": mock.Mock()}, {"year": 0, "seed": seed, "logs": []}

        with (
            mock.patch("core.simulation_engine.RandomService.initialize"),
            mock.patch("core.simulation_engine.init_religion_data"),
            mock.patch("core.simulation_engine.init_species_data"),
            mock.patch("core.simulation_engine.generate_fauna", return_value=[]),
            mock.patch("core.simulation_engine.assemble_world", side_effect=assemble),
            mock.patch("core.simulation_engine.SpatialGrid"),
            mock.patch("core.simulation_engine.entities_spawn.seed_initial_cities"),
        ):
            SimulationEngine.create({"fauna": []}, 42, 8, 6)

        self.assertEqual(captured["entity"].entity_id, 1)

    def test_trader_connections_store_stable_city_ids(self):
        RandomService.initialize(7)
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        culture = config["cultures"][0]
        home = SimpleNamespace(
            entity_id=101,
            name="Home",
            pos=(0, 0),
            known_cities=set(),
            is_expired=False,
        )
        target = SimpleNamespace(
            entity_id=202,
            name="Target",
            pos=(2, 2),
            known_cities=set(),
            is_expired=False,
        )
        trader = Trader(0, 0, culture, config, home)
        trader.target_city = target
        world = {"road": [["  "] * 3 for _ in range(3)], "width": 3, "height": 3}

        with mock.patch("entities.species.human.trader.connect_with_road"):
            trader._establish_connection(world)

        self.assertEqual(home.known_cities, {target.entity_id})
        self.assertEqual(target.known_cities, {home.entity_id})

    def test_genealogy_compares_stable_parent_ids(self):
        shared_parent_a = SimpleNamespace(entity_id=77)
        shared_parent_reloaded = SimpleNamespace(entity_id=77)
        first = SimpleNamespace(entity_id=1, parents=(shared_parent_a,))
        second = SimpleNamespace(entity_id=2, parents=(shared_parent_reloaded,))
        construct = Construct.__new__(Construct)

        self.assertTrue(construct._are_related(first, second))

    def test_farmer_promotion_preserves_citizen_identity(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        culture = config["cultures"][0]
        RandomService.initialize(8)
        citizen = Human(1, 1, culture, config, speed=1.0, name="Ada Stable")
        settlement = Construct.__new__(Construct)
        settlement._pos = [1, 1]
        settlement.culture = culture
        settlement.config = config
        settlement.citizens = [citizen]

        from entities.constructs.village import Village
        Village._promote_to_farmer(settlement)

        self.assertIsInstance(settlement.citizens[0], Farmer)
        self.assertEqual(settlement.citizens[0].entity_id, citizen.entity_id)
    def test_city_specialization_preserves_citizen_identity(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        culture = config["cultures"][0]
        RandomService.initialize(9)
        citizen = Human(1, 1, culture, config, speed=1.0, name="Lin Stable")
        settlement = Construct.__new__(Construct)
        settlement._pos = [1, 1]
        settlement.culture = culture
        settlement.config = config
        settlement.citizens = [citizen]
        settlement.food_stock = 0

        City._manage_specialization(settlement)

        self.assertIsInstance(settlement.citizens[0], Farmer)
        self.assertEqual(settlement.citizens[0].entity_id, citizen.entity_id)

    def test_village_evolution_preserves_settlement_identity(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        culture = config["cultures"][0]
        RandomService.initialize(10)
        settlement = Construct.__new__(Construct)
        settlement.entity_id = 404
        settlement._pos = [1, 1]
        settlement.culture = culture
        settlement.config = config
        settlement.name = "Continuum"
        settlement.citizens = []
        settlement.food_stock = 20
        settlement.religion = None
        settlement.is_expired = False
        world = {"entities": EntityManager()}

        Village._evolve_to_city(settlement, world)
        evolved = next(iter(world["entities"]))

        self.assertEqual(evolved.entity_id, settlement.entity_id)
        self.assertTrue(settlement.is_expired)
    def test_destroyed_settlement_transfers_identity_to_ruins(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        culture = config["cultures"][0]
        RandomService.initialize(11)
        settlement = Entity(1, 1, "C", 20, 0)
        settlement.population = 10
        settlement.culture = culture
        settlement.config = config
        settlement.name = "Pompeii"
        world = {
            "width": 3,
            "height": 3,
            "elev": np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]),
            "road": [["  "] * 3 for _ in range(3)],
            "entities": EntityManager(),
            "influence": mock.Mock(),
        }
        world["entities"].add(settlement)
        event = VolcanoEruption()

        event.trigger(world, {}, config)

        ruin = next(entity for entity in world["entities"] if isinstance(entity, Ruins))
        self.assertEqual(ruin.entity_id, settlement.entity_id)
        self.assertTrue(settlement.is_expired)
    def test_reset_makes_new_world_ids_deterministic(self):
        first_world_ids = [Entity(0, 0, "x", 1, 1.0).entity_id for _ in range(3)]
        EntityIdService.reset()
        second_world_ids = [Entity(0, 0, "x", 1, 1.0).entity_id for _ in range(3)]

        self.assertEqual(first_world_ids, second_world_ids)


class SaveGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.translator import Translator
        Translator.load("fr")

    def make_engine(self, seed=8080):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config["max_fauna"] = 10
        return SimulationEngine.create(config, seed, width=24, height=12)

    def snapshot(self, engine):
        entities = sorted(
            (
                entity.entity_id,
                type(entity).__name__,
                getattr(entity, "name", ""),
                entity.pos,
                getattr(entity, "population", None),
                round(getattr(entity, "energy", 0), 6),
                tuple(sorted(getattr(entity, "economy", {}).items())),
            )
            for entity in engine.world["entities"]
        )
        return {
            "cycle": engine.world["cycle"],
            "year": engine.stats["year"],
            "month": engine.stats["month"],
            "entities": entities,
            "random": RandomService.get_state(),
            "next_id": EntityIdService.get_state(),
        }

    def test_save_round_trip_preserves_engine_and_next_identity(self):
        engine = self.make_engine()
        with mock.patch("core.simulation_engine.EventManager.update"):
            engine.run(4)
        expected_cycle = engine.world["cycle"]
        expected_ids = sorted(entity.entity_id for entity in engine.world["entities"])
        expected_next_id = EntityIdService.get_state()

        with tempfile.TemporaryDirectory() as directory:
            save_path = Path(directory) / "world.chart"
            engine.save(save_path)
            engine.world["cycle"] = 999
            EntityIdService.reset()
            restored = SimulationEngine.load(save_path)

        self.assertEqual(restored.world["cycle"], expected_cycle)
        self.assertEqual(
            sorted(entity.entity_id for entity in restored.world["entities"]),
            expected_ids,
        )
        self.assertEqual(EntityIdService.get_state(), expected_next_id)
        self.assertEqual(Entity(0, 0, "x", 1, 1.0).entity_id, expected_next_id)

    def test_resumed_run_matches_uninterrupted_run(self):
        uninterrupted = self.make_engine(seed=9090)
        with mock.patch("core.simulation_engine.EventManager.update"):
            uninterrupted.run(12)
        expected = self.snapshot(uninterrupted)

        staged = self.make_engine(seed=9090)
        with tempfile.TemporaryDirectory() as directory:
            save_path = Path(directory) / "resume.chart"
            with mock.patch("core.simulation_engine.EventManager.update"):
                staged.run(6)
            staged.save(save_path)

            RandomService.initialize(1)
            EntityIdService.reset()
            restored = SimulationEngine.load(save_path)
            with mock.patch("core.simulation_engine.EventManager.update"):
                restored.run(6)

        self.assertEqual(self.snapshot(restored), expected)

    def test_load_restores_runtime_module_state(self):
        engine = self.make_engine(seed=6060)
        religion_names = [item["name"] for item in get_religion_templates()]
        species_names = [item["name"] for item in get_species_templates()]
        volcano = next(event for event in EVENT_CATALOG if isinstance(event, VolcanoEruption))
        previous_lava = set(volcano._lava_tiles)
        GameLogger.get_new_logs()
        bestiary_tracker.reset()
        volcano._lava_tiles = {(3, 4)}
        GameLogger.log("pending checkpoint log")
        bestiary_tracker.track_kill("checkpoint_species")

        try:
            with tempfile.TemporaryDirectory() as directory:
                save_path = Path(directory) / "runtime.chart"
                engine.save(save_path)
                volcano._lava_tiles.clear()
                GameLogger.get_new_logs()
                bestiary_tracker.reset()
                init_religion_data({})
                init_species_data({})

                SimulationEngine.load(save_path)

            restored_volcano = next(
                event for event in EVENT_CATALOG if isinstance(event, VolcanoEruption)
            )
            self.assertEqual(restored_volcano._lava_tiles, {(3, 4)})
            self.assertEqual(GameLogger.get_new_logs(), ["pending checkpoint log"])
            self.assertEqual(bestiary_tracker.get_kills("checkpoint_species"), 1)
            self.assertEqual(
                [item["name"] for item in get_religion_templates()],
                religion_names,
            )
            self.assertEqual(
                [item["name"] for item in get_species_templates()],
                species_names,
            )
        finally:
            current_volcano = next(
                event for event in EVENT_CATALOG if isinstance(event, VolcanoEruption)
            )
            current_volcano._lava_tiles = previous_lava
            GameLogger.get_new_logs()
            bestiary_tracker.reset()
    def test_launch_options_expose_load_and_save_paths(self):
        from core.system import load_launch_options

        with mock.patch(
            "sys.argv",
            [
                "chartographist",
                "--seed",
                "42",
                "--load",
                "existing.chart",
                "--save",
                "next.chart",
            ],
        ):
            options = load_launch_options()

        self.assertEqual(options.seed, 42)
        self.assertEqual(options.load_path, "existing.chart")
        self.assertEqual(options.save_path, "next.chart")
        self.assertEqual(options.config, {})

    def test_main_loads_checkpoint_and_saves_on_exit(self):
        import main as application

        world = {"cycle": 0, "entities": EntityManager()}
        stats = {"year": 0, "seed": 321, "logs": []}
        engine = mock.Mock()
        engine.world = world
        engine.stats = stats
        engine.config = {"world_name": "Restored", "fauna": []}
        options = SimpleNamespace(
            config={},
            seed=999,
            load_path="existing.chart",
            save_path="next.chart",
        )
        renderer = mock.Mock()

        with (
            mock.patch.object(application.core, "init_terminal"),
            mock.patch.object(application.core, "restore_terminal"),
            mock.patch.object(application.core, "load_launch_options", return_value=options),
            mock.patch.object(application.SimulationEngine, "load", return_value=engine) as load,
            mock.patch.object(application.SimulationEngine, "create") as create,
            mock.patch.object(application, "RenderEngine", return_value=renderer),
            mock.patch.object(application, "print_bestiary_summary"),
            mock.patch.object(application, "MAX_CYCLES", 0),
            mock.patch("builtins.print") as output,
        ):
            application.main()

        load.assert_called_once_with("existing.chart")
        create.assert_not_called()
        engine.save.assert_called_once_with("next.chart")
        engine.record_chronicle.assert_called_once()
        self.assertIn("existing.chart", engine.record_chronicle.call_args.args[0])
        self.assertEqual(engine.record_chronicle.call_args.kwargs["category"], "system")
        self.assertTrue(
            any("next.chart" in str(call) for call in output.call_args_list)
        )

    def test_main_reports_invalid_checkpoint_without_starting_renderer(self):
        import main as application

        options = SimpleNamespace(
            config={},
            seed=999,
            load_path="broken.chart",
            save_path=None,
        )
        renderer = mock.Mock()

        with (
            mock.patch.object(application.core, "init_terminal"),
            mock.patch.object(application.core, "restore_terminal") as restore,
            mock.patch.object(application.core, "load_launch_options", return_value=options),
            mock.patch.object(
                application.SimulationEngine,
                "load",
                side_effect=SaveFormatError("invalid_header"),
            ),
            mock.patch.object(application, "RenderEngine", renderer),
            mock.patch("builtins.print") as output,
        ):
            application.main()

        renderer.assert_not_called()
        restore.assert_called()
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertIn("broken.chart", rendered)
        self.assertNotIn("MISSING_TEXT", rendered)
    def test_load_rejects_file_without_save_header(self):
        with tempfile.TemporaryDirectory() as directory:
            save_path = Path(directory) / "invalid.chart"
            save_path.write_bytes(b"not-a-chartographist-save")

            with self.assertRaises(SaveFormatError) as error:
                SimulationEngine.load(save_path)

        self.assertEqual(error.exception.code, "invalid_header")
if __name__ == "__main__":
    unittest.main()
