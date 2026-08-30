"""Scénarios et composition de mods JSON, sans exécution de code externe."""

from copy import deepcopy
import json
from pathlib import Path

from core.logger import GameLogger
from core.translator import Translator


ALLOWED_METRICS = frozenset({"cycle", "population", "settlements", "fauna", "treasury"})
ALLOWED_OPERATORS = frozenset({">=", "<=", ">", "<"})
DATA_IDENTIFIERS = {
    "fauna": "species",
    "cultures": "name",
    "materials.resources": "id",
    "materials.items": "id",
    "materials.recipes": "id",
    "materials.infrastructures": "id",
}


class ScenarioValidationError(ValueError):
    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def compose_config(base, *, scenario=None, mods=()):
    """Compose des couches déclaratives dans un nouveau dictionnaire."""
    result = deepcopy(base)
    seen_mods = set()
    active_mods = []
    for layer in mods or ():
        metadata = layer.get("mod", {}) if isinstance(layer, dict) else {}
        mod_id = metadata.get("id") if isinstance(metadata, dict) else None
        if not isinstance(mod_id, str) or not mod_id:
            raise ScenarioValidationError("missing_mod_id")
        if mod_id in seen_mods:
            raise ScenarioValidationError(f"duplicate_mod_id:{mod_id}")
        seen_mods.add(mod_id)
        active_mods.append(mod_id)
        _apply_layer(result, layer)
    if scenario is not None:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("scenario"), dict):
            raise ScenarioValidationError("missing_scenario")
        _apply_layer(result, scenario)
        result["scenario"] = deepcopy(scenario["scenario"])
    if active_mods:
        result["active_mods"] = active_mods
    return result


def load_config_layers(base_path, *, scenario_path=None, mod_paths=()):
    """Charge uniquement des documents JSON puis les compose."""
    base = _load_json(base_path)
    mods = [_load_json(path) for path in mod_paths or ()]
    scenario = _load_json(scenario_path) if scenario_path is not None else None
    return compose_config(base, scenario=scenario, mods=mods)


def _load_json(path):
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ScenarioValidationError(f"invalid_json:{path}") from error
    if not isinstance(data, dict):
        raise ScenarioValidationError(f"type:layer:{path}:dict")
    return data


def _apply_layer(result, layer):
    if not isinstance(layer, dict):
        raise ScenarioValidationError("type:layer:dict")
    patch = layer.get("patch", {})
    additions = layer.get("append", {})
    if not isinstance(patch, dict):
        raise ScenarioValidationError("type:patch:dict")
    if not isinstance(additions, dict):
        raise ScenarioValidationError("type:append:dict")
    _deep_merge(result, patch)
    for key, values in additions.items():
        if not isinstance(values, list):
            raise ScenarioValidationError(f"type:append.{key}:list")
        target = _nested_append_target(result, key)
        identifier_key = DATA_IDENTIFIERS.get(key)
        if identifier_key:
            existing = {item.get(identifier_key) for item in target if isinstance(item, dict)}
            for value in values:
                identifier = value.get(identifier_key) if isinstance(value, dict) else None
                if identifier in existing and identifier is not None:
                    raise ScenarioValidationError(f"duplicate_data_id:{key}:{identifier}")
                existing.add(identifier)
        target.extend(deepcopy(values))


def _nested_append_target(result, dotted_key):
    parts = str(dotted_key).split(".")
    container = result
    for index, part in enumerate(parts[:-1]):
        child = container.setdefault(part, {})
        if not isinstance(child, dict):
            path = ".".join(parts[:index + 1])
            raise ScenarioValidationError(f"type:target.{path}:dict")
        container = child
    target = container.setdefault(parts[-1], [])
    if not isinstance(target, list):
        raise ScenarioValidationError(f"type:target.{dotted_key}:list")
    return target


def _deep_merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)


class ScenarioService:
    """Évalue l'état persistant d'un scénario à partir de métriques autorisées."""

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        definition = self.config.get("scenario", {})
        self.definition = definition if isinstance(definition, dict) else {}
        scenario_id = self.definition.get("id", "sandbox")
        state = world.get("scenario")
        if not isinstance(state, dict):
            state = {}
            world["scenario"] = state
        state.setdefault("id", scenario_id)
        state.setdefault("status", "active")
        state.setdefault("last_evaluation_cycle", None)
        state.setdefault("objectives", [])
        self.state = state
        self._sync_objectives()
        self._apply_initial_state_once()

    def _apply_initial_state_once(self):
        if self.state.get("initial_state_applied"):
            return
        initial = self.definition.get("initial", {})
        if isinstance(initial, dict):
            climate_values = initial.get("climate", {})
            if isinstance(climate_values, dict):
                climate = self.world.setdefault("climate", {})
                for key, value in climate_values.items():
                    climate[key] = deepcopy(value)
        self.state["initial_state_applied"] = True
    @property
    def enabled(self):
        return bool(self.definition)

    def summary(self):
        return deepcopy(self.state)

    def advance(self):
        if not self.enabled or self.state["status"] != "active":
            return self.summary()
        cycle = int(self.world.get("cycle", 0))
        if self.state.get("last_evaluation_cycle") == cycle:
            return self.summary()
        self.state["last_evaluation_cycle"] = cycle

        losses = self._evaluate(self.definition.get("defeat_conditions", []))
        objectives = self._evaluate(self.definition.get("objectives", []), store=True)
        if losses and any(item["complete"] for item in losses):
            self._finish("lost", "scenario_lost")
        elif objectives and all(item["complete"] for item in objectives):
            self._finish("won", "scenario_won")
        return self.summary()

    def _sync_objectives(self):
        known = {item.get("id"): item for item in self.state["objectives"]}
        synchronized = []
        for definition in self.definition.get("objectives", []):
            objective = known.get(definition.get("id"), {})
            objective.update({
                "id": definition.get("id"),
                "metric": definition.get("metric"),
                "operator": definition.get("operator"),
                "target": definition.get("target"),
            })
            objective.setdefault("value", 0)
            objective.setdefault("complete", False)
            synchronized.append(objective)
        self.state["objectives"] = synchronized

    def _evaluate(self, definitions, store=False):
        evaluated = []
        for definition in definitions or ():
            value = self._metric(definition["metric"])
            complete = _compare(value, definition["operator"], definition["target"])
            item = {"id": definition["id"], "metric": definition["metric"], "operator": definition["operator"], "target": definition["target"], "value": value, "complete": complete}
            evaluated.append(item)
        if store:
            self.state["objectives"] = evaluated
        return evaluated

    def _metric(self, metric):
        active = [entity for entity in self.world.get("entities", ()) if not getattr(entity, "is_expired", False)]
        if metric == "cycle":
            return int(self.world.get("cycle", 0))
        if metric == "population":
            return sum(max(0, int(getattr(entity, "population", 0))) for entity in active)
        if metric == "settlements":
            return sum(1 for entity in active if hasattr(entity, "population"))
        if metric == "fauna":
            return sum(1 for entity in active if getattr(entity, "species", None) != "human" and not hasattr(entity, "population"))
        if metric == "treasury":
            return sum(float(getattr(entity, "economy", {}).get("treasury", 0.0)) for entity in active)
        raise ScenarioValidationError(f"unknown_metric:{metric}")

    def _finish(self, status, translation_key):
        self.state["status"] = status
        self.state["finished_cycle"] = int(self.world.get("cycle", 0))
        GameLogger.log(Translator.translate(f"events.{translation_key}", scenario_id=self.state["id"]), category="scenario")


def _compare(value, operator, target):
    if operator == ">=": return value >= target
    if operator == "<=": return value <= target
    if operator == ">": return value > target
    if operator == "<": return value < target
    raise ScenarioValidationError(f"unknown_operator:{operator}")