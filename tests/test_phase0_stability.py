import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from core.config_validator import ConfigValidationError, validate_config
from core.culture import load_config
from core.geo import generate_geology
from core.random_service import RandomService
from core.religion import SyncreticReligion, init_religion_data
from core.species import init_species_data
from core.system import load_arguments, stable_seed
from core.translator import Translator
from entities.constructs.ruins import Ruins
from entities.species.human.base import Human
from events import discover_event_modules


ROOT = Path(__file__).resolve().parents[1]


def load_template():
    return json.loads((ROOT / "template.json").read_text(encoding="utf-8"))


class PhaseZeroStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_template()

    def setUp(self):
        RandomService.initialize(2026)
        init_religion_data(self.config)
        init_species_data(self.config)
        self.previous_cwd = Path.cwd()
        os.chdir(ROOT)
        Translator.load("fr")

    def tearDown(self):
        os.chdir(self.previous_cwd)

    def test_text_seed_uses_a_stable_sha256_mapping(self):
        expected = int.from_bytes(hashlib.sha256(b"atlas").digest()[:8], "big")
        self.assertEqual(stable_seed("atlas"), expected)
        self.assertEqual(stable_seed("42"), 42)
        self.assertEqual(stable_seed("-5"), -5)

    def test_mobile_human_ages_once_per_world_cycle(self):
        human = Human(1, 1, self.config["cultures"][0], self.config, speed=2.0)
        human.age = 20
        world = {"cycle": 1}

        human.update(world, {})
        human.update(world, {})
        self.assertAlmostEqual(human.age, 20 + 1 / 12)

        world["cycle"] = 2
        human.update(world, {})
        self.assertAlmostEqual(human.age, 20 + 2 / 12)

    def test_ruins_name_is_localized_in_all_supported_languages(self):
        expected = {
            "fr": "Ruines de Lutèce",
            "en": "Ruins of Lutetia",
            "es": "Ruinas de Lutecia",
        }
        original_names = {"fr": "Lutèce", "en": "Lutetia", "es": "Lutecia"}
        culture = self.config["cultures"][0]
        for language in ("fr", "en", "es"):
            Translator.load(language)
            ruins = Ruins(1, 1, culture, self.config, original_names[language])
            self.assertEqual(ruins.name, expected[language])

    def test_syncretic_religion_name_is_localized(self):
        religion_a = {
            "name": "A",
            "god": "Sol",
            "domain": "life",
            "bonuses": {},
            "naming": {"prefixes": ["Sol"]},
        }
        religion_b = {
            "name": "B",
            "god": "Luna",
            "domain": "life",
            "bonuses": {},
            "naming": {"suffixes": ["una"]},
        }
        expected = {
            "fr": "Soluna le Double",
            "en": "Soluna the Twofold",
            "es": "Soluna el Doble",
        }
        for language, name in expected.items():
            Translator.load(language)
            self.assertEqual(SyncreticReligion.create(religion_a, religion_b)["name"], name)

    def test_cli_help_uses_requested_language(self):
        with mock.patch("sys.argv", ["chartographist", "--help", "--lang", "en"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                load_arguments()
        self.assertIn("Procedural world simulation", output.getvalue())
        self.assertIn("World seed", output.getvalue())

    def test_missing_locale_falls_back_to_english_with_i18n_message(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            Translator.load("does-not-exist")
        self.assertIn("does-not-exist", output.getvalue())
        self.assertNotIn("MISSING_TEXT", output.getvalue())
        self.assertNotIn("MISSING_TEXT", Translator.translate("system.user_interrupt"))

    def test_event_discovery_ignores_infrastructure_modules(self):
        modules = discover_event_modules()
        self.assertTrue({"abduction", "epidemic", "volcano"}.issubset(modules))
        self.assertTrue(
            {"__init__", "base_event", "event_registry", "event_manager"}.isdisjoint(modules)
        )

    def test_flat_noise_map_is_finite_and_neutral(self):
        with mock.patch("core.geo.noise.pnoise2", return_value=0.25):
            elevation, plates = generate_geology(5, 4)
        self.assertTrue(np.all(np.isfinite(elevation)))
        np.testing.assert_array_equal(elevation, np.zeros((4, 5)))
        self.assertEqual(len(plates), 8)

    def test_config_validator_accepts_template_and_rejects_missing_sections(self):
        self.assertIs(validate_config(self.config), self.config)
        invalid = dict(self.config)
        invalid.pop("cultures")
        with self.assertRaises(ConfigValidationError) as error:
            validate_config(invalid)
        self.assertIn("missing:cultures", error.exception.errors)

    def test_config_loader_rejects_structurally_invalid_json_with_i18n_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-structure.json"
            path.write_text(json.dumps({"world_name": "Broken"}), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = load_config(path)
        self.assertEqual(result, {})
        self.assertNotIn("MISSING_TEXT", output.getvalue())
        self.assertIn("missing:cultures", output.getvalue())


if __name__ == "__main__":
    unittest.main()
