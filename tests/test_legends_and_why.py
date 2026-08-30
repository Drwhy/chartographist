import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.chronicles import ChronicleBook
from core.entities import Entity, EntityManager
from core.legends import LegendRegistry
from core.translator import Translator
from core.why import ExplanationService


ROOT = Path(__file__).resolve().parents[1]


def phase15_config(**legend_overrides):
    legends = {
        "enabled": True,
        "max_legends": 16,
        "max_versions_per_legend": 3,
        "max_history_per_legend": 4,
        "artifact_renown_threshold": 6.0,
        "exploration_threshold": 5.0,
        "war_threshold": 9.0,
        "cult_threshold": 12.0,
        "culture_emphases": {
            "north": "valor",
            "south": "sacred",
        },
    }
    legends.update(legend_overrides)
    return {
        "history": {"enabled": True, "max_facts": 16, "max_links": 8},
        "knowledge": {
            "enabled": True,
            "max_facts": 32,
            "minimum_reliability": 0.05,
        },
        "legends": legends,
        "explanations": {
            "enabled": True,
            "max_results": 32,
            "hunger_ratio": 0.25,
        },
    }


def phase15_world():
    return {
        "width": 8,
        "height": 4,
        "cycle": 12,
        "entities": EntityManager(),
        "chronicles": [],
        "next_chronicle_id": 1,
    }


def factual_event(world, config):
    return ChronicleBook(world, config).record(
        "Victoire ancienne",
        cycle=12,
        year=1,
        month=1,
        category="warfare",
        event_type="battle_won",
        actors=[{"entity_id": 7, "role": "victor"}],
        objects=[{"object_id": "artifact:1", "role": "weapon"}],
        locations=[{"location_id": "tile:2,1", "role": "battlefield"}],
        causes=[{"kind": "revenge"}],
        facts={"family": "Orée", "importance": 5},
    )


class LegendRegistryTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_disabled_registry_preserves_legacy_world(self):
        world = phase15_world()
        registry = LegendRegistry(world, {"legends": {"enabled": False}})
        self.assertIsNone(registry.promote_chronicle(1, importance=3))
        self.assertEqual(registry.summary(), {"enabled": False})
        self.assertNotIn("legends", world)

    def test_facts_and_public_versions_remain_distinct_and_defensive(self):
        world, config = phase15_world(), phase15_config()
        event = factual_event(world, config)
        registry = LegendRegistry(world, config)
        legend = registry.promote_chronicle(event["chronicle_id"], importance=5)
        registry.propagate(
            legend["legend_id"], culture_id="north",
            faction_id="wolves", reliability=0.8,
        )
        registry.propagate(
            legend["legend_id"], culture_id="south",
            faction_id="doves", reliability=0.8,
        )
        current = registry.get(legend["legend_id"])
        self.assertEqual(current["fact"]["chronicle_id"], event["chronicle_id"])
        self.assertEqual(
            {version["emphasis"] for version in current["versions"]},
            {"valor", "sacred"},
        )
        self.assertTrue(all("claims" in version for version in current["versions"]))
        current["fact"]["facts"]["corrupt"] = True
        self.assertNotIn("corrupt", registry.get(legend["legend_id"])["fact"]["facts"])

    def test_propagation_builds_bounded_renown_and_private_knowledge(self):
        world, config = phase15_world(), phase15_config(max_versions_per_legend=2)
        owner = Entity(1, 1, "P ", 10, 0)
        owner.config = config
        world["entities"].add(owner)
        event = factual_event(world, config)
        registry = LegendRegistry(world, config)
        legend = registry.promote_chronicle(event["chronicle_id"], importance=5)

        registry.propagate(
            legend["legend_id"], culture_id="north",
            reliability=0.8, audience_id=owner.entity_id,
        )
        registry.propagate(legend["legend_id"], culture_id="south", reliability=0.5)
        registry.propagate(legend["legend_id"], culture_id="east", reliability=0.5)

        current = registry.get(legend["legend_id"])
        self.assertEqual(current["renown"], 14.0)
        self.assertEqual(len(current["versions"]), 2)
        self.assertTrue(any(
            fact["kind"] == "legend"
            for fact in owner.knowledge["facts"]
        ))

    def test_thresholds_create_actionable_exploration_war_and_cult_motives(self):
        world, config = phase15_world(), phase15_config()
        legend = LegendRegistry(world, config).promote_chronicle(
            factual_event(world, config)["chronicle_id"], importance=5
        )
        registry = LegendRegistry(world, config)
        registry.propagate(legend["legend_id"], culture_id="north", reliability=1.0)
        registry.propagate(legend["legend_id"], culture_id="south", reliability=1.0)

        motives = registry.motivations()
        self.assertEqual(
            {motive["kind"] for motive in motives},
            {"exploration", "war", "cult"},
        )
        self.assertTrue(all(motive["legend_id"] == legend["legend_id"] for motive in motives))


    def test_advance_propagates_new_legends_without_random_draws(self):
        from core.random_service import RandomService

        world, config = phase15_world(), phase15_config()
        legend = LegendRegistry(world, config).promote_chronicle(
            factual_event(world, config)["chronicle_id"], importance=5
        )
        before = RandomService.get_state()
        self.assertTrue(LegendRegistry(world, config).advance())
        self.assertEqual(RandomService.get_state(), before)
        current = LegendRegistry(world, config).get(legend["legend_id"])
        self.assertEqual(current["versions"][0]["culture_id"], "world")
        self.assertFalse(LegendRegistry(world, config).advance())

class Phase15IntegrationTests(unittest.TestCase):
    def setUp(self):
        Translator.load("fr")

    def test_renowned_artifact_becomes_a_legend(self):
        from core.artifacts import ArtifactRegistry
        from tests.test_artifacts import artifacts_config

        world = phase15_world()
        config = phase15_config(artifact_renown_threshold=6.0)
        config.update(artifacts_config(renown_per_event=2.0))
        config["legends"] = phase15_config()["legends"]
        artifact = ArtifactRegistry(world, config).create(
            "stone_tool", quality=2.0,
            creator_id=3, holder_kind="entity", holder_id=3,
        )
        ArtifactRegistry(world, config).record_event(
            artifact["artifact_id"], "battle_used",
            actor_ids=[3], importance=3,
        )

        legends = LegendRegistry(world, config).query(subject_kind="artifact")
        self.assertEqual(len(legends), 1)
        self.assertEqual(legends[0]["subject_id"], artifact["artifact_id"])

    def test_engine_checkpoint_visibility_and_legend_api(self):
        from core.simulation_engine import SimulationEngine

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        config.update(phase15_config())
        engine = SimulationEngine.create(config, 1701, 8, 6)
        event = engine.record_chronicle(
            "Fondation mémorable",
            event_type="memorable_founding",
            actors=[{"entity_id": 8, "role": "founder"}],
            locations=[{"location_id": "tile:1,1", "role": "origin"}],
            facts={"family": "Aube"},
        )
        legend = engine.create_legend(event["chronicle_id"], importance=5)
        engine.propagate_legend(legend["legend_id"], culture_id="north")

        snapshot = next(
            item for item in engine.get_systems_snapshot() if item["id"] == "legends"
        )
        self.assertEqual(engine.get_legend(legend["legend_id"])["legend_id"], 1)
        self.assertEqual(len(engine.get_legends(culture_id="north")), 1)
        self.assertEqual(snapshot["state"]["legends"], 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legends.chart"
            engine.save(path)
            resumed = SimulationEngine.load(path)
        self.assertEqual(resumed.get_legend(1), engine.get_legend(1))

    def test_explanation_queries_every_dimension_and_builds_views(self):
        world, config = phase15_world(), phase15_config()
        event = factual_event(world, config)
        legend = LegendRegistry(world, config).promote_chronicle(
            event["chronicle_id"], importance=5
        )
        service = ExplanationService(world, config)

        selected = service.query(
            entity_id=7,
            location_id="tile:2,1",
            object_id="artifact:1",
            family="Orée",
            event_type="battle_won",
        )
        self.assertEqual([item["chronicle_id"] for item in selected["chronicles"]], [1])
        self.assertEqual(selected["legends"][0]["legend_id"], legend["legend_id"])
        self.assertEqual(service.timeline(event_type="battle_won")[0]["cycle"], 12)
        causal = service.causal_view(event["chronicle_id"])
        self.assertEqual(causal["event"]["chronicle_id"], event["chronicle_id"])
        self.assertEqual(causal["causes"], [])
        self.assertEqual(
            causal["consequences"][0]["event_type"], "legend_born"
        )

    def test_why_explains_hunger_war_and_artifact_provenance_and_exports(self):
        from core.artifacts import ArtifactRegistry
        from tests.test_artifacts import artifacts_config

        world, config = phase15_world(), phase15_config()
        config.update(artifacts_config())
        config["legends"] = phase15_config()["legends"]
        city = Entity(1, 1, "C ", 20, 0)
        city.config = config
        city.food_stock = 10.0
        city.max_food = 100.0
        city.citizens = []
        world["entities"].add(city)
        world["warfare"] = {
            "campaigns": [{
                "campaign_id": 4, "attacker_id": city.entity_id,
                "defender_id": 99, "cause": "revenge",
                "objective": "secure_frontier", "evidence": ["raid"],
                "status": "active",
            }]
        }
        artifact = ArtifactRegistry(world, config).create(
            "stone_tool", quality=2.0,
            holder_kind="entity", holder_id=city.entity_id,
        )
        ArtifactRegistry(world, config).transfer(
            artifact["artifact_id"], "lost", None, None,
        )
        service = ExplanationService(world, config)

        hunger = service.why("entity", city.entity_id, question="hunger")
        war = service.why("war", 4)
        provenance = service.why("artifact", artifact["artifact_id"])
        self.assertEqual(hunger["status"], "explained")
        self.assertIn("low_food_stock", [cause["kind"] for cause in hunger["causes"]])
        self.assertEqual(war["causes"][0]["kind"], "revenge")
        self.assertEqual(provenance["timeline"][-1]["event_type"], "lost")
        exported = json.loads(service.export_json())
        self.assertIn("timeline", exported)
        self.assertIn("legends", exported)

    def test_terminal_why_tab_filters_and_translates(self):
        from main import handle_bestiary_input
        from render.ui_bestiary import WHY_TAB, _build_why_entries

        world, config = phase15_world(), phase15_config()
        factual_event(world, config)
        state = {"active": True, "tab": "fauna", "page": 3}
        handle_bestiary_input("w", state)
        self.assertEqual(state["tab"], WHY_TAB)
        self.assertEqual(state["page"], 0)
        handle_bestiary_input("2", state)
        self.assertEqual(state["why_filter"], "warfare")
        rendered = "\n".join(
            line for entry in _build_why_entries(world, config, state) for line in entry
        )
        self.assertIn("Pourquoi", rendered)
        self.assertIn("Victoire ancienne", rendered)

    def test_templates_and_validator_cover_remaining_phase_15_options(self):
        from core.config_validator import ConfigValidationError, validate_config

        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        self.assertFalse(config["legends"]["enabled"])
        self.assertFalse(config["explanations"]["enabled"])
        self.assertIs(validate_config(config), config)
        invalid = copy.deepcopy(config)
        invalid["legends"]["max_legends"] = 0
        invalid["legends"]["culture_emphases"] = []
        all_config = json.loads(
            (ROOT / "template-all.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all_config["legends"]["enabled"])
        self.assertTrue(all_config["explanations"]["enabled"])
        self.assertLessEqual(
            all_config["legends"]["artifact_renown_threshold"], 1.0
        )
        invalid["explanations"]["max_results"] = True
        with self.assertRaises(ConfigValidationError) as caught:
            validate_config(invalid)
        self.assertIn("range:legends.max_legends:positive", caught.exception.errors)
        self.assertIn("type:legends.culture_emphases:dict", caught.exception.errors)
        self.assertIn("type:explanations.max_results:int", caught.exception.errors)


if __name__ == "__main__":
    unittest.main()
