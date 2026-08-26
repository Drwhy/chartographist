"""Projection visuelle sémantique, défensive et indépendante des rendus."""

from copy import deepcopy
import json

from core.climate import biome_glyph, biome_key_at


PRESENTATION_SCHEMA_VERSION = 1
_DEFAULT_LOG_LIMIT = 100


class VisualCellResolver:
    """Résout une cellule une seule fois selon la priorité visuelle historique."""

    def __init__(self, world, config, entity_map=None):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.entity_map = {}
        if entity_map is not None:
            self.entity_map.update(entity_map)
            return
        for entity in world.get("entities", ()):
            if getattr(entity, "is_expired", False):
                continue
            position = tuple(getattr(entity, "pos", ()))
            if len(position) != 2:
                continue
            current = self.entity_map.get(position)
            if (
                current is None
                or int(getattr(entity, "z_index", 0))
                > int(getattr(current, "z_index", 0))
            ):
                self.entity_map[position] = entity

    def resolve(self, x, y):
        x, y = int(x), int(y)
        elevation = float(self.world["elev"][y][x])
        terrain_key = biome_key_at(
            x, y, elevation, self.world, self.config
        )
        terrain_glyph = biome_glyph(terrain_key, self.config)
        cell = {
            "x": x,
            "y": y,
            "terrain_key": terrain_key,
            "infrastructure_key": None,
            "hydrology_key": None,
            "site_key": None,
            "entity": None,
            "visible_key": f"terrain.{terrain_key}",
            "glyph": terrain_glyph,
        }

        river = self.world["riv"][y][x]
        if river > 0 and elevation >= 0:
            cell["hydrology_key"] = "river"
            cell["visible_key"] = "hydrology.river"
            cell["glyph"] = self.config.get("water", {}).get("river", "~~")

        road = self.world["road"][y][x]
        if road and road != "  " and elevation >= 0:
            cell["infrastructure_key"] = "road"
            cell["visible_key"] = "infrastructure.road"
            cell["glyph"] = str(road)

        site = _site_at(self.world, x, y)
        if site is not None:
            kind = _safe_key(site.get("kind"), "unknown")
            appearance = site.get("appearance", {})
            stage = _safe_key(
                appearance.get("stage") if isinstance(appearance, dict) else None,
                "fresh",
            )
            cell["site_key"] = f"{kind}.{stage}"
            cell["visible_key"] = f"site.{kind}.{stage}"
            cell["glyph"] = str(
                appearance.get("symbol", "◇ ")
                if isinstance(appearance, dict) else "◇ "
            )

        entity = self.entity_map.get((x, y))
        if entity is not None:
            render_key = entity_render_key(entity)
            cell["entity"] = {
                "entity_id": int(getattr(entity, "entity_id")),
                "render_key": render_key,
                "z_index": int(getattr(entity, "z_index", 0)),
                "category": render_key.split(".", 2)[1],
                "name": _public_text(getattr(entity, "name", None)),
            }
            cell["visible_key"] = render_key
            cell["glyph"] = str(getattr(entity, "char", "?"))
        return cell


class PresentationProjector:
    """Construit une liste blanche JSON sans exposer le graphe Python."""

    def __init__(self, engine, *, log_limit=None):
        self.engine = engine
        if log_limit is None:
            section = engine.config.get("presentation", {})
            log_limit = (
                section.get("max_logs", _DEFAULT_LOG_LIMIT)
                if isinstance(section, dict) else _DEFAULT_LOG_LIMIT
            )
        self.log_limit = max(1, int(log_limit))

    def snapshot(self, revision=0):
        world = self.engine.world
        stats = self.engine.stats
        resolver = VisualCellResolver(world, self.engine.config)
        width = int(world["width"])
        height = int(world["height"])
        cells = [
            resolver.resolve(x, y)
            for y in range(height)
            for x in range(width)
        ]
        logs = list(stats.get("logs", ()))
        panels = {
            "metrics": self._call("get_metrics_snapshot", {}),
            "systems": self._call("get_systems_snapshot", []),
            "chronicles": self._call("get_chronicles", [])[-self.log_limit:],
            "sites": self._call("get_sites_summary", {}),
            "artifacts": self._call("get_artifacts_summary", {}),
            "legends": self._call("get_legends_summary", {}),
            "economy": self._call("get_economic_summary", {}),
            "scenario": self._call("get_scenario_summary", {}),
            "resources": self._call("get_resource_summary", {}),
            "climate": self._call("get_climate_snapshot", {}),
            "diplomacy": self._call("get_diplomatic_summary", {}),
            "politics": self._call("get_political_summary", {}),
            "pathfinding": self._call("get_pathfinding_summary", {}),
            "territory": self._call("get_territory_summary", {}),
            "migration": self._call("get_migration_summary", {}),
            "warfare": self._call("get_warfare_summary", {}),
            "peace": self._call("get_peace_summary", {}),
            "why": self._call("get_explanations_overview", []),
        }
        return _json_value({
            "schema_version": PRESENTATION_SCHEMA_VERSION,
            "revision": int(revision),
            "cycle": int(world.get("cycle", 0)),
            "clock": {
                "year": int(stats.get("year", 0)),
                "month": int(stats.get("month", 1)),
            },
            "world": {
                "width": width,
                "height": height,
                "seed": stats.get("seed", world.get("seed")),
                "name": _public_text(
                    self.engine.config.get("world_name", "WORLD")
                ),
            },
            "cells": cells,
            "logs": [_public_text(value) for value in logs[-self.log_limit:]],
            "panels": panels,
        })

    def _call(self, name, default):
        function = getattr(self.engine, name, None)
        if not callable(function):
            return deepcopy(default)
        return function()


def entity_render_key(entity):
    """Retourne une identité visuelle stable indépendante du glyphe."""
    explicit = getattr(entity, "render_key", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    module = type(entity).__module__.lower()
    class_name = _snake_case(type(entity).__name__)
    if ".constructs." in module:
        category = "structure"
    elif ".species.animal." in module:
        category = "animal"
        species = getattr(entity, "species", None)
        if isinstance(species, str) and species.strip():
            class_name = _safe_key(species, class_name)
    elif ".species.human." in module:
        category = "human"
    elif ".special." in module:
        category = "special"
    else:
        category = module.split(".", 1)[0] or "generic"
    return f"entity.{category}.{class_name}"


def snapshot_delta(previous, current, *, max_changes=2048):
    """Calcule un delta borné ou demande une resynchronisation complète."""
    limit = int(max_changes)
    base = {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "from_revision": int(previous.get("revision", 0)),
        "to_revision": int(current.get("revision", 0)),
        "cycle": int(current.get("cycle", 0)),
    }
    if limit <= 0:
        return {**base, "resync": True, "cells": []}
    previous_cells = {
        (cell["x"], cell["y"]): cell
        for cell in previous.get("cells", ())
    }
    changed = [
        cell for cell in current.get("cells", ())
        if previous_cells.get((cell["x"], cell["y"])) != cell
    ]
    if len(changed) > limit:
        return {**base, "resync": True, "cells": []}
    return {
        **base,
        "resync": False,
        "cells": deepcopy(changed),
        "clock": deepcopy(current.get("clock", {})),
        "logs": deepcopy(current.get("logs", [])),
        "panels": deepcopy(current.get("panels", {})),
    }


def _site_at(world, x, y):
    state = world.get("sites")
    if not isinstance(state, dict):
        return None
    identifiers = state.get("position_index", {}).get(f"{x},{y}", ())
    if isinstance(identifiers, (int, str)):
        identifiers = (identifiers,)
    entries = state.get("entries", ())
    site_index = state.get("site_index", {})
    for identifier in identifiers:
        entry = site_index.get(str(int(identifier)))
        if isinstance(entry, int) and 0 <= entry < len(entries):
            entry = entries[entry]
        if isinstance(entry, dict):
            return entry
    return None



def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item") and callable(value.item):
        return _json_value(value.item())
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, set):
        projected = [_json_value(item) for item in value]
        return sorted(
            projected,
            key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        )
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"unsupported presentation value: {type(value).__name__}")


def _snake_case(value):
    result = []
    for index, character in enumerate(str(value)):
        if character.isupper() and index:
            result.append("_")
        result.append(character.lower())
    return _safe_key("".join(result), "unknown")


def _safe_key(value, default):
    text = str(value or "").strip().lower()
    cleaned = "".join(
        character if character.isalnum() or character in "_-" else "_"
        for character in text
    ).strip("_")
    return cleaned or default


def _public_text(value):
    return None if value is None else str(value)
