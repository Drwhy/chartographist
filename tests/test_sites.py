import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

import numpy as np

from core.entities import Entity, EntityManager
from core.sites import SiteRegistry
from core.translator import Translator
from entities.constructs.ruins import Ruins


ROOT = Path(__file__).resolve().parents[1]


def sites_config(**overrides):
    settings = {
        "enabled": True,
        "advance_interval": 1,
        "max_sites": 8,
        "max_history_per_site": 3,
        "overgrow_cycles": 12,
        "symbols": {
            "battlefield": "† ",
            "ruins": "▒▒",
            "sanctuary": "⌂ ",
            "mine": "⛏ ",
            "road": "◆ ",
        },
    }
    settings.update(overrides)
    return {
        "sites": settings,
        "history": {"enabled": True, "max_facts": 16, "max_links": 8},
    }


def site_world():
    return {
        "width": 8,
        "height": 4,
        "cycle": 1,
        "entities": EntityManager(),
        "chronicles": [],
        "next_chronicle_id": 1,
    }


class SiteRegistryTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_disabled_registry_does_not_mutate_legacy_world(self):
        world = site_world()
        registry = SiteRegistry(world, {"sites": {"enabled": False}})

        self.assertIsNone(registry.create("mine", [2, 1]))
        self.assertEqual(registry.summary(), {"enabled": False})
        self.assertNotIn("sites", world)

    def test_create_is_stable_idempotent_queryable_and_defensive(self):
        world = site_world()
        registry = SiteRegistry(world, sites_config())

        created = registry.create(
            "sanctuary",
            [2, 1],
            founder_ids=[7, 7],
            owner_ids=[9],
            resources={"offerings": 3.0},
            source_entity_id=41,
        )
        duplicate = registry.create(
            "sanctuary",
            [2, 1],
            founder_ids=[7],
            source_entity_id=41,
        )

        self.assertEqual(created["site_id"], duplicate["site_id"])
        self.assertEqual(created["founder_ids"], [7])
        self.assertEqual(created["owner_ids"], [9])
        self.assertEqual(created["appearance"]["symbol"], "⌂ ")
        self.assertEqual(registry.query(kind="sanctuary", owner_id=9), [created])
        created["resources"]["offerings"] = 99
        self.assertEqual(registry.get(1)["resources"]["offerings"], 3.0)

    def test_lifecycle_keeps_identity_and_bounded_history(self):
        world = site_world()
        registry = SiteRegistry(world, sites_config(max_history_per_site=3))
        site = registry.create("mine", [3, 2], owner_ids=[1])

        registry.destroy(site["site_id"], actor_ids=[2], cause="collapse")
        registry.reconstruct(site["site_id"], actor_ids=[3], owner_ids=[3])
        registry.reoccupy(site["site_id"], occupant_ids=[4], owner_ids=[4])

        current = registry.get(site["site_id"])
        self.assertEqual(current["site_id"], site["site_id"])
        self.assertEqual(current["status"], "active")
        self.assertEqual(current["owner_ids"], [4])
        self.assertEqual(current["occupant_ids"], [4])
        self.assertEqual(current["appearance"]["stage"], "reoccupied")
        self.assertEqual(current["appearance"]["symbol"], "⌂ ")
        self.assertEqual(
            [event["event_type"] for event in current["history"]],
            ["destroyed", "reconstructed", "reoccupied"],
        )

    def test_capacity_is_bounded_without_reusing_monotonic_ids(self):
        world = site_world()
        registry = SiteRegistry(world, sites_config(max_sites=2))

        first = registry.create("mine", [0, 0])
        second = registry.create("road", [1, 0])
        dropped = registry.create("sanctuary", [2, 0])

        self.assertEqual((first["site_id"], second["site_id"]), (1, 2))
        self.assertIsNone(dropped)
        self.assertEqual(registry.summary()["dropped_sites"], 1)
        self.assertEqual(world["sites"]["next_site_id"], 3)

    def test_ruin_entities_become_sites_and_age_visibly(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(sites_config(overgrow_cycles=2))
        world = site_world()
        ruin = Ruins(4, 2, config["cultures"][0], config, "Orée")
        ruin.entity_id = 77
        world["entities"].add(ruin)
        registry = SiteRegistry(world, config)

        self.assertTrue(registry.advance())
        site = registry.query(kind="ruins")[0]
        self.assertEqual(site["source_entity_id"], 77)
        self.assertEqual(site["status"], "ruined")
        world["cycle"] = 4
        registry.advance()

        aged = registry.get(site["site_id"])
        self.assertEqual(aged["appearance"]["stage"], "overgrown")
        self.assertEqual(ruin.char, "░░")
        self.assertEqual(aged["appearance"]["symbol"], "░░")
        self.assertEqual(len(registry.query(source_entity_id=77)), 1)

    def test_discovery_and_reoccupation_are_explicit_and_filterable(self):
        registry = SiteRegistry(site_world(), sites_config())
        site = registry.create("ruins", [5, 2], status="ruined")

        self.assertTrue(registry.discover(site["site_id"], 31))
        self.assertFalse(registry.discover(site["site_id"], 31))
        registry.reoccupy(site["site_id"], occupant_ids=[31], owner_ids=[31])

        selected = registry.query(discovered_by=31, status="active")
        self.assertEqual([item["site_id"] for item in selected], [site["site_id"]])
        self.assertEqual(selected[0]["discoveries"]["31"], 1)

    def test_site_creation_emits_a_structured_chronicle(self):
        world = site_world()
        registry = SiteRegistry(world, sites_config())
        cause = registry.create("road", [1, 1], founder_ids=[5])

        chronicle = world["chronicles"][0]
        self.assertEqual(chronicle["event_type"], "site_founded")
        self.assertEqual(chronicle["objects"][0]["object_id"], "site:1")
        self.assertEqual(chronicle["locations"][0]["location_id"], "site:1")
        self.assertEqual(cause["origin_chronicle_id"], chronicle["chronicle_id"])
        self.assertNotIn("MISSING_TEXT", chronicle["message"])


class SiteIntegrationTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_battle_creates_one_persistent_battlefield(self):
        from core.warfare import WarfareSystem
        from tests.test_warfare import settlement, war_world, warfare_config

        first, second = settlement(1, 0, population=30), settlement(2, 5, population=10)
        world = war_world(first, second)
        config = warfare_config(casualty_rate=0.5)
        config.update(sites_config())
        system = WarfareSystem(world, config)
        system.declare_war(1, 2, cause="revenge", objective="secure_frontier")

        system.advance()
        campaign = system.summary()["active_campaigns"][0]
        battlefield = SiteRegistry(world, config).query(kind="battlefield")[0]

        self.assertEqual(campaign["engagements"][0]["site_id"], battlefield["site_id"])
        self.assertEqual(set(battlefield["founder_ids"]), {1, 2})
        self.assertGreater(battlefield["resources"]["relics"], 0)
        self.assertEqual(
            SiteRegistry(world, config).site_at(battlefield["position"])["site_id"],
            battlefield["site_id"],
        )

    def test_engine_api_checkpoint_visibility_and_map_rendering(self):
        from core.simulation_engine import SimulationEngine
        from render.ui_map import get_char_at

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(sites_config())
        engine = SimulationEngine.create(config, 1523, 8, 6)
        site = engine.create_site(
            "mine",
            [2, 2],
            owner_ids=[11],
            resources={"ore": 8},
        )
        snapshot = next(
            item for item in engine.get_systems_snapshot() if item["id"] == "sites"
        )
        visible = get_char_at(2, 2, engine.world, config, entity_map={})

        self.assertEqual(engine.get_site(site["site_id"]), site)
        self.assertEqual(engine.get_sites(kind="mine"), [site])
        self.assertTrue(snapshot["enabled"])
        self.assertEqual(snapshot["state"]["sites"], 1)
        self.assertEqual(visible, "⛏ ")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sites.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.get_site(site["site_id"]), site)

    def test_entity_layer_remains_above_site_and_site_above_road(self):
        from render.ui_map import get_char_at

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(sites_config())
        world = site_world()
        world.update({
            "elev": np.full((4, 8), 0.2),
            "riv": np.zeros((4, 8)),
            "road": [["  " for _ in range(8)] for _ in range(4)],
        })
        SiteRegistry(world, config).create("battlefield", [2, 2])
        world["road"][2][2] = "··"

        class NoIteration(list):
            def __iter__(self):
                raise AssertionError("map rendering scanned every site")

        world["sites"]["entries"] = NoIteration(world["sites"]["entries"])

        self.assertEqual(get_char_at(2, 2, world, config, entity_map={}), "† ")
        entity = Entity(2, 2, "H", 50, 1)
        self.assertEqual(
            get_char_at(2, 2, world, config, entity_map={(2, 2): entity}),
            "H",
        )

    def test_settler_can_refound_a_registered_ruin(self):
        from core.random_service import RandomService
        from entities.constructs.village import Village
        from entities.species.human.settler import Settler

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(sites_config())
        culture = config["cultures"][0]
        world = site_world()
        world.update({
            "elev": np.full((4, 8), 0.2),
            "riv": np.zeros((4, 8)),
            "road": [["  " for _ in range(8)] for _ in range(4)],
        })
        ruin = Ruins(4, 2, culture, config, "Orée")
        ruin.entity_id = 88
        world["entities"].add(ruin)
        world["grid"] = SimpleNamespace(get_nearby=lambda *_: [ruin])
        registry = SiteRegistry(world, config)
        site = registry.create(
            "ruins",
            [4, 2],
            source_entity_id=ruin.entity_id,
            status="ruined",
        )
        home = SimpleNamespace(settler_cost=3, pos=[0, 0], name="Source")
        RandomService.initialize(1531)
        settler = Settler(4, 2, culture, config, home_city=home)

        with mock.patch.object(RandomService, "random", return_value=0.0):
            self.assertTrue(settler._is_ideal_spot(world))
        settler._found_village(world)

        village = next(entity for entity in world["entities"] if isinstance(entity, Village))
        reoccupied = SiteRegistry(world, config).get(site["site_id"])
        self.assertTrue(ruin.is_expired)
        self.assertEqual(reoccupied["status"], "active")
        self.assertEqual(reoccupied["occupant_ids"], [village.entity_id])
        self.assertEqual(reoccupied["appearance"]["stage"], "reoccupied")

    def test_template_and_validator_cover_site_bounds_and_symbols(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["sites"]["enabled"])
        self.assertIs(validate_config(config), config)

        invalid = copy.deepcopy(config)
        invalid["sites"]["max_sites"] = 0
        invalid["sites"]["overgrow_cycles"] = True
        invalid["sites"]["symbols"] = ["ruins"]
        invalid["sites"]["stage_symbols"] = {"overgrown": ""}
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)

        self.assertIn("range:sites.max_sites:positive", caught.exception.errors)
        self.assertIn("type:sites.overgrow_cycles:int", caught.exception.errors)
        self.assertIn("type:sites.symbols:dict", caught.exception.errors)
        self.assertIn("type:sites.stage_symbols:str_to_str", caught.exception.errors)


if __name__ == "__main__":
    unittest.main()
