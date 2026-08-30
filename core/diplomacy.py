"""Relations diplomatiques persistantes entre etablissements.

Le stockage reste compose de types Python simples afin d'etre sauvegardable avec
le checkpoint courant et inspectable sans reference aux objets en memoire.
"""

from copy import deepcopy


DEFAULT_STATUS = "neutral"
STATUSES = frozenset({"neutral", "trade_pact", "alliance", "hostile", "war", "truce"})


class DiplomacyTransitionError(ValueError):
    """Signale une transition diplomatique interdite."""


def canonical_relation_key(first_id, second_id):
    """Construit la cle symetrique de deux identifiants d'entite stables."""
    first_id = int(first_id)
    second_id = int(second_id)
    if first_id == second_id:
        raise ValueError("a diplomatic relation requires two distinct entities")
    low, high = sorted((first_id, second_id))
    return f"{low}:{high}"


class DiplomacyRegistry:
    """Accede aux relations diplomatiques structurees conservees dans world."""

    def __init__(self, world):
        self.world = world
        if not isinstance(world.get("diplomacy"), dict):
            world["diplomacy"] = {}
        next_id = world.get("next_relation_id", 1)
        world["next_relation_id"] = next_id if isinstance(next_id, int) and next_id > 0 else 1

    def get_or_create(self, first_id, second_id):
        key = canonical_relation_key(first_id, second_id)
        relation = self.world["diplomacy"].get(key)
        if relation is None:
            low, high = sorted((int(first_id), int(second_id)))
            relation = {
                "relation_id": self.world["next_relation_id"],
                "first_id": low,
                "second_id": high,
                "status": DEFAULT_STATUS,
                "trust": 0.0,
                "tension": 0.0,
                "interdependence": 0.0,
                "last_change_cycle": int(self.world.get("cycle", 0)),
                "truce_until": None,
                "war_started_cycle": None,
                "reasons": [],
            }
            self.world["diplomacy"][key] = relation
            self.world["next_relation_id"] += 1
        return deepcopy(relation)

    def get(self, first_id, second_id):
        relation = self.world["diplomacy"].get(
            canonical_relation_key(first_id, second_id)
        )
        return deepcopy(relation) if relation is not None else None

    def query(self, *, entity_id=None, status=None):
        relations = []
        for relation in self.world["diplomacy"].values():
            if entity_id is not None and int(entity_id) not in (
                relation["first_id"],
                relation["second_id"],
            ):
                continue
            if status is not None and relation["status"] != status:
                continue
            relations.append(deepcopy(relation))
        return sorted(relations, key=lambda relation: relation["relation_id"])

    def adjust(
        self,
        first_id,
        second_id,
        *,
        trust=0,
        tension=0,
        interdependence=0,
        reason=None,
    ):
        relation = self._stored_relation(first_id, second_id)
        relation["trust"] = _clamp(relation["trust"] + float(trust), -100.0, 100.0)
        relation["tension"] = _clamp(relation["tension"] + float(tension), 0.0, 100.0)
        relation["interdependence"] = _clamp(
            relation["interdependence"] + float(interdependence),
            0.0,
            100.0,
        )
        relation["last_change_cycle"] = int(self.world.get("cycle", 0))
        if reason:
            relation["reasons"].append(
                {
                    "cycle": relation["last_change_cycle"],
                    "kind": str(reason),
                }
            )
        return deepcopy(relation)

    def transition(
        self,
        first_id,
        second_id,
        status,
        *,
        reason,
        truce_duration=None,
    ):
        if status not in STATUSES:
            raise DiplomacyTransitionError(f"unknown diplomatic status: {status}")

        relation = self._stored_relation(first_id, second_id)
        current = relation["status"]
        cycle = int(self.world.get("cycle", 0))
        if current == status:
            return deepcopy(relation)
        if status == "war" and current == "alliance":
            raise DiplomacyTransitionError("an alliance must be dissolved before war")
        if status == "war" and current == "truce":
            truce_until = relation.get("truce_until")
            if truce_until is None or cycle < truce_until:
                raise DiplomacyTransitionError("an active truce prevents war")
        if current == "war" and status != "truce":
            raise DiplomacyTransitionError("war can only transition to truce")
        if status == "truce" and current != "war":
            raise DiplomacyTransitionError("a truce can only end a war")
        if status == "truce" and (truce_duration is None or truce_duration <= 0):
            raise DiplomacyTransitionError("a truce requires a positive duration")

        relation["status"] = status
        relation["last_change_cycle"] = cycle
        relation["war_started_cycle"] = cycle if status == "war" else None
        relation["truce_until"] = (
            cycle + int(truce_duration) if status == "truce" else None
        )
        relation["reasons"].append(
            {
                "cycle": cycle,
                "kind": str(reason),
                "from_status": current,
                "to_status": status,
            }
        )
        return deepcopy(relation)

    def expire_truces(self):
        cycle = int(self.world.get("cycle", 0))
        expired = []
        for relation in self.world["diplomacy"].values():
            if relation["status"] != "truce":
                continue
            truce_until = relation.get("truce_until")
            if truce_until is None or cycle < truce_until:
                continue
            previous = relation["status"]
            relation["status"] = "neutral"
            relation["truce_until"] = None
            relation["last_change_cycle"] = cycle
            relation["reasons"].append(
                {
                    "cycle": cycle,
                    "kind": "truce_expired",
                    "from_status": previous,
                    "to_status": "neutral",
                }
            )
            expired.append(deepcopy(relation))
        return expired

    def _stored_relation(self, first_id, second_id):
        key = canonical_relation_key(first_id, second_id)
        self.get_or_create(first_id, second_id)
        return self.world["diplomacy"][key]


def diplomacy_settings(entity):
    section = getattr(entity, "config", {}).get("diplomacy", {})
    return section if isinstance(section, dict) else {}


def diplomacy_enabled(entity):
    return diplomacy_settings(entity).get("enabled") is True


def trade_allowed(world, first, second):
    if not diplomacy_enabled(first):
        return True
    relation = DiplomacyRegistry(world).get(first.entity_id, second.entity_id)
    return relation is None or relation["status"] != "war"


def trade_capacity_multiplier(world, first, second):
    if not diplomacy_enabled(first):
        return 1.0
    relation = DiplomacyRegistry(world).get(first.entity_id, second.entity_id)
    if relation is None or relation["status"] not in {"trade_pact", "alliance"}:
        return 1.0
    return max(
        1.0,
        float(diplomacy_settings(first).get("trade_pact_capacity_multiplier", 1.5)),
    )


def record_trade(world, first, second):
    if not diplomacy_enabled(first):
        return None

    settings = diplomacy_settings(first)
    registry = DiplomacyRegistry(world)
    relation = registry.adjust(
        first.entity_id,
        second.entity_id,
        trust=float(settings.get("trade_trust_gain", 2)),
        tension=-float(settings.get("trade_tension_relief", 1)),
        interdependence=float(settings.get("trade_interdependence_gain", 2)),
        reason="trade",
    )
    pact_threshold = float(settings.get("trade_pact_threshold", 20))
    alliance_threshold = float(settings.get("alliance_threshold", 60))
    if relation["status"] in {"neutral", "hostile"} and relation["trust"] >= pact_threshold:
        relation = registry.transition(
            first.entity_id,
            second.entity_id,
            "trade_pact",
            reason="trade_pact_threshold",
        )
    if (
        relation["status"] == "trade_pact"
        and relation["trust"] >= alliance_threshold
        and relation["interdependence"] >= pact_threshold
    ):
        relation = registry.transition(
            first.entity_id,
            second.entity_id,
            "alliance",
            reason="alliance_threshold",
        )
    return relation


def war_probability_multiplier(world, first_id, second_id):
    relation = DiplomacyRegistry(world).get(first_id, second_id)
    if relation is None:
        return 1.0
    if relation["status"] in {"alliance", "truce"}:
        return 0.0
    multiplier = 1.0 + (relation["tension"] / 100.0)
    if relation["status"] == "hostile":
        multiplier *= 1.5
    return multiplier


def is_at_war(world, first_id, second_id):
    relation = DiplomacyRegistry(world).get(first_id, second_id)
    return relation is not None and relation["status"] == "war"


def world_diplomatic_summary(world):
    relations = DiplomacyRegistry(world).query()
    statuses = {}
    for relation in relations:
        status = relation["status"]
        statuses[status] = statuses.get(status, 0) + 1
    count = len(relations)
    return {
        "relations": count,
        "statuses": statuses,
        "average_trust": (
            sum(relation["trust"] for relation in relations) / count if count else 0.0
        ),
        "average_tension": (
            sum(relation["tension"] for relation in relations) / count if count else 0.0
        ),
        "average_interdependence": (
            sum(relation["interdependence"] for relation in relations) / count
            if count
            else 0.0
        ),
        "peace": {
            "treaties": len(world.get("peace", {}).get("treaties", ())),
            "last_treaty": deepcopy(world.get("peace", {}).get("treaties", ())[-1]) if world.get("peace", {}).get("treaties") else None,
        },
    }


def advance_diplomacy(world, config):
    section = config.get("diplomacy", {}) if isinstance(config, dict) else {}
    registry = DiplomacyRegistry(world)
    events = []
    migrate_legacy_wars(world)

    for relation in registry.expire_truces():
        event = {"kind": "truce_expired", "relation": relation}
        events.append(event)
        _log_diplomatic_event(world, event)

    if not isinstance(section, dict) or section.get("enabled") is not True:
        return events

    cycle = int(world.get("cycle", 0))
    if cycle % 12 != 0:
        synchronize_legacy_enemies(world)
        return events

    minimum_duration = max(1, int(section.get("war_min_duration", 60)))
    truce_duration = max(1, int(section.get("truce_duration", 60)))
    exhaustion = max(0.0, float(section.get("war_exhaustion_rate", 1)))
    for relation in list(registry.query(status="war")):
        started = relation.get("war_started_cycle")
        elapsed = cycle - (started if started is not None else cycle)
        if elapsed >= minimum_duration:
            changed = registry.transition(
                relation["first_id"],
                relation["second_id"],
                "truce",
                reason="war_exhaustion",
                truce_duration=truce_duration,
            )
            event = {"kind": "truce_started", "relation": changed}
            events.append(event)
            _log_diplomatic_event(world, event)
        elif exhaustion:
            registry.adjust(
                relation["first_id"],
                relation["second_id"],
                tension=-exhaustion,
                reason="war_exhaustion",
            )

    aid_quantity = max(0, int(section.get("alliance_aid_food", 10)))
    reserve = max(0, int(section.get("alliance_aid_reserve", 50)))
    if aid_quantity:
        entities = _entities_by_id(world)
        for relation in registry.query(status="alliance"):
            first = entities.get(relation["first_id"])
            second = entities.get(relation["second_id"])
            event = _transfer_alliance_aid(first, second, aid_quantity, reserve)
            if event is not None:
                event["relation"] = relation
                events.append(event)
                _log_diplomatic_event(world, event)

    synchronize_legacy_enemies(world)
    return events


def migrate_legacy_wars(world):
    registry = DiplomacyRegistry(world)
    entities = _entities_by_id(world)
    migrated = []
    seen = set()
    for entity in entities.values():
        for enemy in getattr(entity, "enemies", ()):
            enemy_id = getattr(enemy, "entity_id", None)
            if enemy_id not in entities or enemy_id == entity.entity_id:
                continue
            key = canonical_relation_key(entity.entity_id, enemy_id)
            if key in seen or registry.get(entity.entity_id, enemy_id) is not None:
                continue
            seen.add(key)
            migrated.append(
                registry.transition(
                    entity.entity_id,
                    enemy_id,
                    "war",
                    reason="legacy_enemy_migration",
                )
            )
    return migrated


def synchronize_legacy_enemies(world):
    entities = _entities_by_id(world)
    active_wars = {
        canonical_relation_key(relation["first_id"], relation["second_id"])
        for relation in DiplomacyRegistry(world).query(status="war")
    }
    for entity in entities.values():
        if not hasattr(entity, "enemies"):
            continue
        entity.enemies = [
            enemy
            for enemy in entity.enemies
            if getattr(enemy, "entity_id", None) in entities
            and canonical_relation_key(entity.entity_id, enemy.entity_id) in active_wars
        ]


def _entities_by_id(world):
    return {
        entity.entity_id: entity
        for entity in world.get("entities", [])
        if hasattr(entity, "entity_id") and not getattr(entity, "is_expired", False)
    }


def _transfer_alliance_aid(first, second, capacity, reserve):
    if first is None or second is None:
        return None
    if not all(hasattr(entity, "food_stock") for entity in (first, second)):
        return None

    first_ratio = first.food_stock / max(getattr(first, "max_food", 1), 1)
    second_ratio = second.food_stock / max(getattr(second, "max_food", 1), 1)
    donor, recipient = (first, second) if first_ratio > second_ratio else (second, first)
    if first_ratio == second_ratio:
        return None

    available = max(0, int(donor.food_stock - reserve))
    room = max(0, int(getattr(recipient, "max_food", 0) - recipient.food_stock))
    quantity = min(capacity, available, room)
    if quantity <= 0:
        return None

    donor.food_stock -= quantity
    recipient.food_stock += quantity
    return {
        "kind": "alliance_aid",
        "quantity": quantity,
        "donor_id": donor.entity_id,
        "recipient_id": recipient.entity_id,
    }


def _log_diplomatic_event(world, event):
    from core.logger import GameLogger
    from core.translator import Translator

    relation = event["relation"]
    entities = _entities_by_id(world)
    first = entities.get(relation["first_id"])
    second = entities.get(relation["second_id"])
    first_name = getattr(first, "name", relation["first_id"])
    second_name = getattr(second, "name", relation["second_id"])
    if event["kind"] == "alliance_aid":
        donor = entities.get(event["donor_id"])
        recipient = entities.get(event["recipient_id"])
        message = Translator.translate(
            "events.alliance_aid",
            donor=getattr(donor, "name", event["donor_id"]),
            recipient=getattr(recipient, "name", event["recipient_id"]),
            quantity=event["quantity"],
        )
    else:
        message = Translator.translate(
            f"events.{event['kind']}",
            first=first_name,
            second=second_name,
        )
    GameLogger.log(
        message,
        category="diplomacy",
        entity_ids=[relation["first_id"], relation["second_id"]],
        position=getattr(first, "pos", None),
    )


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))