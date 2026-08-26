import json
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace

import numpy as np

from core.climate import biome_at, biome_key_at
from core.config_validator import ConfigValidationError, validate_config
from core.simulation_engine import SimulationEngine
from core.entities import Entity, EntityManager
from core.presentation import (
    PresentationProjector,
    VisualCellResolver,
    snapshot_delta,
    _json_value,
)
from core.random_service import RandomService
from core.simulation_host import SimulationHost
from render.ui_map import get_char_at

ROOT = Path(__file__).resolve().parents[1]



def visual_config():
    return {
        "world_name": "Test",
        "water": {"ocean": "OO", "shore": "SS", "river": "RR"},
        "biomes": {
            "volcano": "VV",
            "peak": "PP",
            "high_mountain": "HH",
            "mountain": "MM",
            "sand": "SA",
            "glaciated": "GL",
            "tundra": "TU",
            "desert": "DE",
            "cactus": "CA",
            "tropical_forest": "TF",
            "boreal_forest": "BF",
            "temperate_forest": "WF",
            "grassland": "GG",
        },
        "sites": {
            "enabled": True,
            "symbols": {"ruins": "RU"},
            "stage_symbols": {"overgrown": "OV"},
        },
        "history": {"enabled": True},
        "legends": {"enabled": True},
        "explanations": {"enabled": True, "max_results": 16},
    }


def visual_world():
    world = {
        "width": 3,
        "height": 2,
        "seed": 7,
        "cycle": 0,
        "elev": np.array([[0.2, 0.2, 0.2], [-0.2, 0.2, 0.2]]),
        "riv": np.array([[0, 2, 0], [0, 0, 0]]),
        "road": [["  ", "  ", "=="], ["  ", "  ", "  "]],
        "entities": EntityManager(),
        "chronicles": [],
        "next_chronicle_id": 1,
        "sites": {
            "version": 1,
            "next_site_id": 2,
            "last_advanced_cycle": None,
            "entries": [{
                "site_id": 1,
                "kind": "ruins",
                "position": [1, 1],
                "status": "ruined",
                "appearance": {"stage": "overgrown", "symbol": "OV"},
                "history": [],
                "discoveries": {},
                "founder_ids": [],
                "owner_ids": [],
                "occupant_ids": [],
                "resources": {},
                "source_entity_id": None,
                "origin_chronicle_id": None,
                "founded_cycle": 0,
                "last_changed_cycle": 0,
            }],
            "position_index": {"1,1": [1]},
            "site_index": {},
            "dropped_sites": 0,
        },
    }
    world["sites"]["site_index"]["1"] = world["sites"]["entries"][0]
    return world


class PresentationFoundationTests(unittest.TestCase):
    def setUp(self):
        RandomService.initialize(404)
        self.config = visual_config()
        self.world = visual_world()

    def test_biome_key_is_semantic_while_legacy_glyph_is_preserved(self):
        key = biome_key_at(0, 1, -0.2, self.world, self.config)
        self.assertEqual(key, "ocean")
        self.assertEqual(
            biome_at(0, 1, -0.2, self.world, self.config),
            self.config["water"][key],
        )

    def test_visual_resolver_owns_layer_priority_and_semantic_keys(self):
        entity = Entity(1, 1, "EN", 40, 1)
        self.world["entities"].add(entity)
        resolver = VisualCellResolver(self.world, self.config)

        entity_cell = resolver.resolve(1, 1)
        self.assertEqual(entity_cell["visible_key"], "entity.core.entity")
        self.assertEqual(entity_cell["glyph"], "EN")
        entity.is_expired = True

        site_cell = VisualCellResolver(self.world, self.config).resolve(1, 1)
        self.assertEqual(site_cell["visible_key"], "site.ruins.overgrown")
        self.assertEqual(site_cell["glyph"], "OV")
        self.assertEqual(
            resolver.resolve(2, 0)["visible_key"],
            "infrastructure.road",
        )
        self.assertEqual(
            resolver.resolve(1, 0)["visible_key"],
            "hydrology.river",
        )
        self.assertEqual(
            resolver.resolve(0, 0)["visible_key"],
            "terrain.glaciated",
        )


    def test_terminal_glyphs_match_the_semantic_resolver(self):
        resolver = VisualCellResolver(self.world, self.config)
        for y in range(self.world["height"]):
            for x in range(self.world["width"]):
                self.assertEqual(
                    get_char_at(x, y, self.world, self.config),
                    resolver.resolve(x, y)["glyph"],
                )
    def test_snapshot_is_json_safe_defensive_and_does_not_draw_randomness(self):
        entity = Entity(2, 1, "EN", 40, 1)
        entity.name = "Visible"
        self.world["entities"].add(entity)
        engine = SimpleNamespace(
            world=self.world,
            stats={"year": 0, "month": 1, "seed": 7, "logs": ["ready"]},
            config=self.config,
            get_systems_snapshot=lambda: [{"id": "history"}],
            get_chronicles=lambda **filters: [{"chronicle_id": 1}],
            get_diplomatic_summary=lambda: {"relations": 2},
            get_sites_summary=lambda: {"sites": 1},
            get_explanations_overview=lambda: {"events": 1},
        )
        before = RandomService.get_state()
        snapshot = PresentationProjector(engine).snapshot(revision=3)

        json.dumps(snapshot)
        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["revision"], 3)
        self.assertEqual(len(snapshot["cells"]), 6)
        self.assertEqual(snapshot["panels"]["systems"], [{"id": "history"}])
        self.assertEqual(snapshot["panels"]["diplomacy"]["relations"], 2)
        self.assertEqual(snapshot["panels"]["sites"]["sites"], 1)
        self.assertEqual(snapshot["panels"]["why"]["events"], 1)
        self.assertNotIn("config", snapshot)
        snapshot["cells"][0]["visible_key"] = "tampered"
        self.assertNotEqual(
            PresentationProjector(engine).snapshot()["cells"][0]["visible_key"],
            "tampered",
        )

    def test_snapshot_delta_is_versioned_bounded_and_resynchronizable(self):

        engine = SimpleNamespace(
            world=self.world,
            stats={"year": 0, "month": 1, "seed": 7, "logs": []},
            config=self.config,
            get_systems_snapshot=lambda: [],
            get_chronicles=lambda **filters: [],
        )
        first = PresentationProjector(engine).snapshot(revision=1)
        self.world["road"][0][0] = "=="
        second = PresentationProjector(engine).snapshot(revision=2)
        delta = snapshot_delta(first, second, max_changes=8)
        self.assertEqual(delta["from_revision"], 1)
        self.assertEqual(delta["to_revision"], 2)
        self.assertFalse(delta["resync"])
        self.assertEqual(len(delta["cells"]), 1)
        self.assertEqual(delta["cells"][0]["visible_key"], "infrastructure.road")
        self.assertTrue(snapshot_delta(first, second, max_changes=0)["resync"])
    def test_projection_rejects_unknown_python_objects(self):
        engine = SimpleNamespace(
            world=self.world,
            stats={"year": 0, "month": 1, "seed": 7, "logs": []},
            config=self.config,
            get_systems_snapshot=lambda: [object()],
            get_chronicles=lambda **filters: [],
        )
        with self.assertRaises(TypeError):
            PresentationProjector(engine).snapshot()

    def test_json_projection_orders_sets_deterministically(self):
        self.assertEqual(
            _json_value({"zeta", "alpha", "middle"}),
            ["alpha", "middle", "zeta"],
        )

    def test_explicit_render_key_is_stable_and_independent_from_glyph(self):
        entity = Entity(0, 0, "old", 40, 1)
        entity.render_key = "entity.human.cartographer"
        self.world["entities"].add(entity)
        engine = SimpleNamespace(
            world=self.world,
            stats={"year": 0, "month": 1, "seed": 7, "logs": []},
            config=self.config,
            get_systems_snapshot=lambda: [],
            get_chronicles=lambda **filters: [],
        )
        cell = PresentationProjector(engine).snapshot()["cells"][0]
        self.assertEqual(cell["entity"]["render_key"], entity.render_key)
        self.assertEqual(cell["visible_key"], entity.render_key)

        self.assertEqual(cell["glyph"], "old")
    def test_engine_exposes_the_versioned_presentation_contract(self):
        engine = SimpleNamespace(
            world=self.world,
            stats={"year": 0, "month": 1, "seed": 7, "logs": []},
            config=self.config,
            get_systems_snapshot=lambda: [],
            get_chronicles=lambda **filters: [],
        )
        snapshot = SimulationEngine.get_presentation_snapshot(
            engine, revision=9
        )
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["revision"], 9)

    def test_templates_and_validator_bound_presentation_buffers(self):
        for filename in ("template.json", "template-all.json"):
            config = json.loads(
                (ROOT / filename).read_text(encoding="utf-8")
            )
            section = config["presentation"]
            self.assertGreater(section["max_logs"], 0)
            self.assertGreater(section["max_delta_cells"], 0)
            self.assertGreater(section["max_commands"], 0)
            self.assertIs(validate_config(config), config)

        invalid = visual_config()
        invalid["presentation"] = {
            "max_logs": 0,
            "max_delta_cells": True,
            "max_commands": -1,
        }
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)
        self.assertIn("range:presentation.max_logs:positive", caught.exception.errors)
        self.assertIn("type:presentation.max_delta_cells:int", caught.exception.errors)
        self.assertIn("range:presentation.max_commands:positive", caught.exception.errors)

    def test_engine_exposes_structured_explanation_overview(self):
        engine = SimpleNamespace(
            world={},
            config={"explanations": {"enabled": False}},
        )
        self.assertEqual(
            SimulationEngine.get_explanations_overview(engine),
            [],
        )


class FakeEngine:
    def __init__(self):
        self.world = {"cycle": 0}
        self.stats = {}
        self.config = {}
        self.saved = []

    def step(self):
        self.world["cycle"] += 1
        return self.world["cycle"]

    def save(self, path):
        self.saved.append(path)


class SimulationHostTests(unittest.TestCase):
    def make_host(self, **kwargs):
        return SimulationHost(
            FakeEngine(),
            snapshot_factory=lambda engine, revision: {
                "revision": revision,
                "cycle": engine.world["cycle"],
            },
            **kwargs,
        )

    def test_host_runs_pauses_steps_and_bounds_speed(self):
        host = self.make_host(tick_interval=0.15)
        self.assertEqual(host.tick()["cycle"], 1)
        self.assertTrue(host.submit_command("pause"))
        self.assertEqual(host.tick()["cycle"], 1)
        self.assertTrue(host.submit_command("step"))
        self.assertEqual(host.tick()["cycle"], 2)
        self.assertTrue(host.submit_command("speed", 0.05))
        host.tick()
        self.assertEqual(host.tick_interval, 0.05)
        self.assertFalse(host.submit_command("speed", 0))
        self.assertFalse(host.submit_command("unknown"))


    def test_command_queue_is_bounded_and_save_path_is_server_owned(self):
        host = self.make_host(max_commands=1, save_path="trusted.chart")
        self.assertTrue(host.submit_command("pause"))
        self.assertFalse(host.submit_command("resume"))
        host.tick()
        self.assertTrue(host.submit_command("save"))
        host.tick()
        self.assertEqual(host.engine.saved, ["trusted.chart"])
        without_path = self.make_host()
        self.assertFalse(without_path.submit_command("save"))

    def test_only_owner_thread_can_advance_engine(self):
        host = self.make_host()
        errors = []

        def advance_from_worker():
            try:
                host.tick()
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=advance_from_worker)
        worker.start()
        worker.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual(host.engine.world["cycle"], 0)


if __name__ == "__main__":
    unittest.main()
