"""Vues de lecture stables pour inspecter les entités d'un monde."""

from copy import deepcopy

from core.chronicles import ChronicleBook
from core.economy import economy_snapshot


_SNAPSHOT_FIELDS = (
    "name",
    "char",
    "speed",
    "age",
    "sex",
    "health",
    "energy",
    "species",
    "food_stock",
    "max_food",
)


def inspect_entity(world, entity_id):
    """Renvoie un instantané d'entité et ses chroniques, ou ``None``."""
    entity = next(
        (
            candidate
            for candidate in world.get("entities", ())
            if getattr(candidate, "entity_id", None) == entity_id
        ),
        None,
    )
    if entity is None:
        return None

    snapshot = {
        "entity_id": entity.entity_id,
        "type": type(entity).__name__,
        "position": list(entity.pos),
        "is_expired": bool(getattr(entity, "is_expired", False)),
    }
    for field in _SNAPSHOT_FIELDS:
        if hasattr(entity, field):
            snapshot[field] = deepcopy(getattr(entity, field))

    culture = getattr(entity, "culture", None)
    if isinstance(culture, dict):
        snapshot["culture"] = culture.get("name")
    citizens = getattr(entity, "citizens", None)
    if citizens is not None:
        snapshot["population"] = len(citizens)
    if hasattr(entity, "food_stock") and hasattr(entity, "max_food"):
        snapshot["economy"] = economy_snapshot(entity)

    from core.diplomacy import DiplomacyRegistry

    return {
        "entity": snapshot,
        "chronicles": ChronicleBook(world).query(entity_id=entity_id),
        "relationships": DiplomacyRegistry(world).query(entity_id=entity_id),
    }