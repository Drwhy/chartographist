import ast
import importlib
import json
import pkgutil
import string
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALE_PATHS = {
    language: ROOT / "locales" / f"textes.{language}.json"
    for language in ("fr", "en", "es")
}


def flatten_leaves(value, prefix=""):
    leaves = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            leaves.update(flatten_leaves(child, path))
        else:
            leaves[path] = child
    return leaves


def format_fields(value):
    if not isinstance(value, str):
        return set()
    return {
        field_name.split(".")[0].split("[")[0]
        for _, field_name, _, _ in string.Formatter().parse(value)
        if field_name
    }


class I18nAndArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.locales = {
            language: json.loads(path.read_text(encoding="utf-8"))
            for language, path in LOCALE_PATHS.items()
        }
        cls.flat_locales = {
            language: flatten_leaves(data)
            for language, data in cls.locales.items()
        }

    def test_all_locale_files_have_identical_leaf_keys(self):
        reference = set(self.flat_locales["fr"])
        self.assertGreater(len(reference), 0)
        for language in ("en", "es"):
            self.assertEqual(reference, set(self.flat_locales[language]))

    def test_placeholders_match_between_translations(self):
        for key, french_value in self.flat_locales["fr"].items():
            expected = format_fields(french_value)
            for language in ("en", "es"):
                self.assertEqual(
                    expected,
                    format_fields(self.flat_locales[language][key]),
                    f"Placeholders incompatibles pour {key} ({language})",
                )

    def test_literal_translation_keys_used_by_python_exist(self):
        known_keys = set(self.flat_locales["fr"])
        missing = []
        source_roots = [ROOT / name for name in ("core", "entities", "events", "render")]
        python_files = [ROOT / "main.py"]
        for source_root in source_roots:
            python_files.extend(source_root.rglob("*.py"))

        for path in python_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                function = node.func
                if (
                    isinstance(function, ast.Attribute)
                    and function.attr == "translate"
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    key = node.args[0].value
                    if key not in known_keys:
                        missing.append(f"{path.relative_to(ROOT)}:{node.lineno}:{key}")

        self.assertEqual([], missing)

    def test_direct_random_imports_are_confined_to_seed_services(self):
        allowed = {Path("core/random_service.py"), Path("core/system.py")}
        violations = []
        for path in ROOT.rglob("*.py"):
            relative = path.relative_to(ROOT)
            if (
                "tests" in relative.parts
                or any(part.startswith(".") for part in relative.parts)
            ):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imports_random = (
                    isinstance(node, ast.Import)
                    and any(alias.name == "random" for alias in node.names)
                ) or (isinstance(node, ast.ImportFrom) and node.module == "random")
                if imports_random and relative not in allowed:
                    violations.append(f"{relative}:{node.lineno}")
        self.assertEqual([], violations)

    def test_template_has_required_runtime_sections(self):
        config = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
        required = {
            "world_name", "water", "biomes", "cultures", "fauna", "special",
            "influence_decay", "species", "fauna_archetypes", "domains",
        }
        self.assertTrue(required.issubset(config))
        self.assertTrue(config["cultures"])
        for culture in config["cultures"]:
            self.assertTrue({"name", "city", "village", "road", "naming"}.issubset(culture))
            naming = culture["naming"]
            self.assertTrue(naming["prefixes"])
            self.assertTrue(naming["suffixes_person"])
            self.assertTrue(naming["suffixes_place"])

        for archetype in config["fauna_archetypes"].values():
            self.assertTrue(archetype.get("emoji_pool"))
            self.assertIn("naming", archetype)
            self.assertIn("count", archetype)

    def test_all_application_modules_import(self):
        imported = []
        for package_name in ("core", "entities", "events", "history", "render"):
            package = importlib.import_module(package_name)
            imported.append(package_name)
            if hasattr(package, "__path__"):
                for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                    importlib.import_module(module.name)
                    imported.append(module.name)
        self.assertGreater(len(imported), 20)


if __name__ == "__main__":
    unittest.main()
