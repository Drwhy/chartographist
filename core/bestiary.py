"""Projection headless et sérialisable du bestiaire vivant."""

from copy import deepcopy

from core import bestiary_tracker
from core.religion import get_religion_templates
from core.species import get_species_templates


def bestiary_snapshot(world, config):
    """Retourne les données utiles au joueur sans exposer la configuration."""
    safe_world = world if isinstance(world, dict) else {}
    safe_config = config if isinstance(config, dict) else {}
    entities = tuple(safe_world.get("entities", ()))
    return {
        "fauna": _fauna_entries(entities, safe_config),
        "species": _species_entries(entities),
        "religions": _religion_entries(),
        "settlements": _settlement_entries(entities),
    }


def _fauna_entries(entities, config):
    from entities.species.animal.base import Animal

    live = {}
    for entity in entities:
        if isinstance(entity, Animal) and not getattr(entity, "is_expired", False):
            key = str(getattr(entity, "species", ""))
            if key:
                live[key] = live.get(key, 0) + 1

    entries = []
    for definition in config.get("fauna", ()):
        if not isinstance(definition, dict):
            continue
        key = str(definition.get("species", "")).strip()
        if not key:
            continue
        food = definition.get("food_value", (0, 0))
        if not isinstance(food, (list, tuple)) or len(food) < 2:
            food = (0, 0)
        entries.append({
            "id": key,
            "name": str(definition.get("name", key)),
            "symbol": str(definition.get("char", "?")),
            "locomotion": str(definition.get("locomotion", "land")),
            "diet": str(definition.get("diet", "unknown")),
            "weight": definition.get("weight", 0),
            "speed": definition.get("speed", 0),
            "perception": definition.get("perception_range", 0),
            "fear": definition.get("fear_sensitivity", 0),
            "food": [food[0], food[1]],
            "danger": definition.get("danger_level", 0),
            "live": live.get(key, 0),
            "killed": bestiary_tracker.get_kills(key),
            "starved": bestiary_tracker.get_starvations(key),
        })
    return entries


def _species_entries(entities):
    from entities.registry import CIV_UNITS

    populations = {}
    for entity in entities:
        if type(entity) not in CIV_UNITS or getattr(entity, "is_expired", False):
            continue
        culture = getattr(entity, "culture", None)
        name = culture.get("name") if isinstance(culture, dict) else None
        if name:
            populations[str(name)] = populations.get(str(name), 0) + 1

    entries = []
    for template in get_species_templates():
        if not isinstance(template, dict):
            continue
        culture = str(template.get("culture", ""))
        entries.append({
            "name": str(template.get("name", "?")),
            "culture": culture,
            "symbols": [str(value) for value in template.get("emojis", ())[:3]],
            "origin": str(template.get("origin", "")),
            "physiology": str(template.get("physiology", "")),
            "nature": str(template.get("nature", "")),
            "bonuses": deepcopy(template.get("bonuses", {})),
            "speed_modifier": template.get("speed_mod", 0),
            "population": populations.get(culture, 0),
        })
    return entries


def _religion_entries():
    entries = []
    for template in get_religion_templates():
        if not isinstance(template, dict):
            continue
        entries.append({
            "name": str(template.get("name", "?")),
            "god": str(template.get("god", "?")),
            "culture": str(template.get("culture", "")),
            "domain": str(template.get("domain", "")),
            "symbol": str(template.get("emoji", "🙏")),
            "bonuses": deepcopy(template.get("bonuses", {})),
            "parents": [str(value) for value in template.get("parents", ())],
        })
    return entries


def _settlement_entries(entities):
    from entities.constructs.city import City
    from entities.constructs.village import Village
    from entities.species.human.base import Human
    from entities.species.human.farmer import Farmer

    settlements = [
        entity for entity in entities
        if isinstance(entity, (City, Village))
        and not getattr(entity, "is_expired", False)
    ]
    settlements.sort(
        key=lambda item: (
            0 if isinstance(item, City) else 1,
            str(getattr(item, "name", "")),
        )
    )
    entries = []
    for settlement in settlements:
        citizens = list(getattr(settlement, "citizens", ()))
        culture = getattr(settlement, "culture", None)
        religion = getattr(settlement, "religion", None)
        entries.append({
            "id": int(getattr(settlement, "entity_id")),
            "name": str(getattr(settlement, "name", "?")),
            "symbol": str(getattr(settlement, "char", "?")),
            "kind": "city" if isinstance(settlement, City) else "village",
            "culture": str(
                culture.get("name", "?") if isinstance(culture, dict) else "?"
            ),
            "population": len(citizens),
            "civilians": sum(type(citizen) is Human for citizen in citizens),
            "farmers": sum(isinstance(citizen, Farmer) for citizen in citizens),
            "food": int(getattr(settlement, "food_stock", 0)),
            "food_capacity": int(getattr(settlement, "max_food", 0)),
            "faith": str(getattr(religion, "dominant", None) or "—"),
        })
    return entries
