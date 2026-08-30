"""Read-only inventory of simulation systems and their observable effects."""

from copy import deepcopy

from core.simulation_metrics import SimulationMetrics


_SYSTEM_ORDER = (
    "climate",
    "resources",
    "ecology",
    "food",
    "economy",
    "diplomacy",
    "characters",
    "materials",
    "artifacts",
    "legends",
    "knowledge",
    "politics",
    "pathfinding",
    "territory",
    "sites",
    "migration",
    "warfare",
    "peace",
    "history",
    "influence",
    "events",
    "scenario",
)


def _enabled(config, section):
    settings = config.get(section, {}) if isinstance(config, dict) else {}
    return isinstance(settings, dict) and settings.get("enabled") is True


def _settlements(world):
    return [
        entity
        for entity in world.get("entities", ())
        if not getattr(entity, "is_expired", False)
        and hasattr(entity, "citizens")
        and hasattr(entity, "food_stock")
    ]


def _knowledge_state(settlements):
    owners = 0
    facts = 0
    tiles = 0
    for settlement in settlements:
        state = getattr(settlement, "knowledge", None)
        if not isinstance(state, dict):
            continue
        owners += 1
        facts += len(state.get("facts", ()))
        tiles += sum(fact.get("kind") == "tile" for fact in state.get("facts", ()) if isinstance(fact, dict))
    return {"owners": owners, "facts": facts, "mapped_tiles": tiles}


def _infrastructure_levels(settlements):
    total = 0
    for settlement in settlements:
        state = getattr(settlement, "infrastructure", None)
        levels = state.get("levels", {}) if isinstance(state, dict) else {}
        if isinstance(levels, dict):
            total += sum(max(0, int(level)) for level in levels.values())
    return total



def _influence_state(world):
    influence = world.get("influence")
    fear_grid = getattr(influence, "fear_grid", ())
    scent_grid = getattr(influence, "scent_grid", ())
    fear_values = [float(value) for row in fear_grid for value in row]
    scent_values = [float(value) for row in scent_grid for value in row]
    return {
        "fear_cells": sum(value < 0 for value in fear_values),
        "scent_cells": sum(value > 0 for value in scent_values),
        "strongest_fear": round(min(fear_values, default=0.0), 3),
        "strongest_scent": round(max(scent_values, default=0.0), 3),
    }


def _event_state(world):
    from events.event_registry import EVENT_CATALOG

    chronicles = world.get("chronicles", ())
    entries = chronicles if isinstance(chronicles, list) else ()
    triggered = sum(
        isinstance(entry, dict) and entry.get("category") == "event"
        for entry in entries
    )
    return {
        "registered": len(EVENT_CATALOG),
        "triggered": triggered,
    }
def _history_state(world):
    entries = world.get("chronicles", ())
    entries = entries if isinstance(entries, list) else ()
    return {
        "entries": sum(isinstance(entry, dict) for entry in entries),
        "structured": sum(
            isinstance(entry, dict) and int(entry.get("chronicle_version", 1)) >= 2
            for entry in entries
        ),
        "causal_links": sum(
            len(entry.get("caused_by", ()))
            for entry in entries
            if isinstance(entry, dict)
        ),
        "event_types": len({
            entry.get("event_type")
            for entry in entries
            if isinstance(entry, dict) and entry.get("event_type")
        }),
    }




def systems_snapshot(world, config):
    """Return a deterministic JSON snapshot of every influential system."""
    metrics = SimulationMetrics(world).snapshot()
    state = metrics["state"]
    flows = metrics["flows"]
    settlements = _settlements(world)

    from core.climate import ClimateSystem
    from core.diplomacy import world_diplomatic_summary
    from core.resources import ResourceSystem
    from core.scenarios import ScenarioService
    from core.politics import world_political_summary
    from core.pathfinding import PathfindingService
    from core.territory import TerritorySystem
    from core.migration import MigrationSystem
    from core.warfare import WarfareSystem
    from core.peace import PeaceSystem
    from core.sites import SiteRegistry
    from core.artifacts import ArtifactRegistry
    from core.legends import LegendRegistry

    climate = ClimateSystem(world, config).snapshot()
    resources = ResourceSystem(world, config).summary()
    diplomacy = world_diplomatic_summary(world)
    politics = world_political_summary(world, config)
    pathfinding = PathfindingService(world, config).summary()
    territory = TerritorySystem(world, config).summary()
    migration = MigrationSystem(world, config).summary()
    warfare = WarfareSystem(world, config).summary()
    peace = PeaceSystem(world, config).summary()
    sites = SiteRegistry(world, config).summary()
    artifacts = ArtifactRegistry(world, config).summary()
    legends = LegendRegistry(world, config).summary()
    scenario = ScenarioService(world, config)
    scenario_state = scenario.summary()
    scenario_state["configured"] = scenario.enabled
    material_flows = flows["materials"]
    stockpile_units = round(sum(state["stockpile_goods"].values()), 3)

    entries = {
        "climate": {
            "enabled": _enabled(config, "climate"),
            "state": climate,
            "effects": {"events": flows["climate"]["events"]},
        },
        "resources": {
            "enabled": _enabled(config, "resources"),
            "state": {
                "biomass_ratio": state["biomass_ratio"],
                "fish_ratio": state["fish_ratio"],
                "soil_ratio": state["soil_fertility_ratio"],
                "forest_ratio": state["forest_ratio"],
            },
            "effects": deepcopy(flows["resources"]),
        },
        "ecology": {
            "enabled": bool(config.get("ecology", {}).get("population_limits", {}).get("enabled") is True),
            "state": {"fauna": state["fauna"], "resource_state": resources.get("enabled", False)},
            "effects": deepcopy(flows["fauna"]),
        },
        "food": {
            "enabled": _enabled(config, "food_balance"),
            "state": {
                "stock": state["food_stock"],
                "capacity": state["food_capacity"],
                "saturation": state["food_saturation"],
            },
            "effects": deepcopy(flows["food"]),
        },
        "economy": {
            "enabled": _enabled(config, "economy"),
            "state": {
                "treasury": state["treasury"],
                "average_food_price": state["average_food_price"],
                "transactions": state["transactions"],
            },
            "effects": deepcopy(flows["economy"]),
        },
        "diplomacy": {
            "enabled": _enabled(config, "diplomacy"),
            "state": diplomacy,
            "effects": {"relations": sum(state["diplomacy"].values())},
        },
        "characters": {
            "enabled": _enabled(config, "characters"),
            "state": {
                "notables": state["notables"],
                "archived": state["archived_notables"],
            },
            "effects": deepcopy(flows["characters"]),
        },
        "materials": {
            "enabled": _enabled(config, "materials"),
            "state": {
                "goods_kinds": len(state["stockpile_goods"]),
                "goods_units": stockpile_units,
                "weight": state["stockpile_weight"],
                "capacity": state["stockpile_capacity"],
                "orders": state["active_production_orders"],
                "infrastructure": _infrastructure_levels(settlements),
            },
            "effects": deepcopy(material_flows),
        },
        "artifacts": {
            "enabled": _enabled(config, "artifacts"),
            "state": artifacts,
            "effects": {
                "transfers": max(
                    0,
                    artifacts.get("provenance_events", 0)
                    - artifacts.get("artifacts", 0),
                ),
                "dropped": artifacts.get("dropped_artifacts", 0),
            },
        },
        "legends": {
            "enabled": _enabled(config, "legends"),
            "state": legends,
            "effects": {
                "propagations": legends.get("propagations", 0),
                "motivations": sum(
                    int(value)
                    for value in legends.get("motivations", {}).values()
                ),
            },
        },
        "knowledge": {
            "enabled": _enabled(config, "knowledge"),
            "state": _knowledge_state(settlements),
            "effects": {
                "decisions": sum(
                    isinstance(getattr(settlement, "knowledge_decision", None), dict)
                    for settlement in settlements
                )
            },
        },
        "politics": {
            "enabled": _enabled(config, "politics"),
            "state": politics,
            "effects": deepcopy(flows["politics"]),
        },
        "pathfinding": {
            "enabled": _enabled(config, "pathfinding"),
            "state": pathfinding,
            "effects": {
                "queries": pathfinding.get("queries", 0),
                "cache_hits": pathfinding.get("cache_hits", 0),
                "expanded_nodes": pathfinding.get("expanded_nodes", 0),
            },
        },
        "territory": {
            "enabled": _enabled(config, "territory"),
            "state": territory,
            "effects": {
                "contested_tiles": territory.get("contested_tiles", 0),
                "borders": len(territory.get("borders", ())),
            },
        },
        "sites": {
            "enabled": _enabled(config, "sites"),
            "state": sites,
            "effects": {
                "discoveries": sites.get("discoveries", 0),
                "dropped": sites.get("dropped_sites", 0),
            },
        },
        "migration": {
            "enabled": _enabled(config, "migration"),
            "state": migration,
            "effects": {
                "migrants": migration.get("total_migrants", 0),
                "diasporas": migration.get("active_diasporas", 0),
                "returnees": migration.get("returnees", 0),
            },
        },
        "warfare": {
            "enabled": _enabled(config, "warfare"),
            "state": warfare,
            "effects": {
                "casualties": warfare.get("total_casualties", 0),
                "prisoners": warfare.get("total_prisoners", 0),
                "supply": warfare.get("total_supply_consumed", 0.0),
            },
        },
        "peace": {
            "enabled": _enabled(config, "peace"),
            "state": peace,
            "effects": {
                "treaties": peace.get("treaties", 0),
                "refugees": peace.get("refugees", 0),
                "ruins": peace.get("ruins", 0),
                "debts": len(peace.get("debts", ())),
            },
        },
        "history": {
            "enabled": _enabled(config, "history"),
            "state": _history_state(world),
            "effects": _history_state(world),
        },

        "influence": {
            "enabled": world.get("influence") is not None,
            "state": _influence_state(world),
            "effects": {"decay": float(config.get("influence_decay", 0.9))},
        },
        "events": {
            "enabled": True,
            "state": _event_state(world),
            "effects": {"chronicles": _event_state(world)["triggered"]},
        },
        "scenario": {
            "enabled": scenario.enabled,
            "state": scenario_state,
            "effects": {
                "completed_objectives": sum(
                    bool(item.get("complete"))
                    for item in scenario_state.get("objectives", ())
                )
            },
        },
    }
    return [
        {"id": identifier, **deepcopy(entries[identifier])}
        for identifier in _SYSTEM_ORDER
    ]
