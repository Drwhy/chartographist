"""Objets uniques persistants, provenance et transferts déterministes."""

from copy import deepcopy

from core.chronicles import ChronicleBook
from core.translator import Translator


_ALLOWED_TRANSFERS = {
    "inheritance",
    "trade",
    "loot",
    "gift",
    "lost",
    "recovered",
}
_DEFAULT_MAX_ARTIFACTS = 256
_DEFAULT_MAX_HISTORY = 48


class ArtifactRegistry:
    """Possède l'identité, la provenance et le détenteur des artefacts."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("artifacts", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.config = config if isinstance(config, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if not self.enabled:
            return
        state = world.get("artifacts")
        if not isinstance(state, dict):
            state = {
                "version": 1,
                "next_artifact_id": 1,
                "entries": [],
                "artifact_index": {},
                "source_index": {},
                "dropped_artifacts": 0,
            }
            world["artifacts"] = state
        self._migrate(state)

    @property
    def state(self):
        return self.world.get("artifacts")

    def create(
        self,
        item_id,
        *,
        quality,
        creator_id=None,
        material_ids=None,
        inscription=None,
        holder_kind=None,
        holder_id=None,
        location=None,
        source_key=None,
        caused_by=None,
    ):
        if not self.enabled:
            return None
        source = None if source_key is None else str(source_key)
        if source is not None:
            existing = self.state["source_index"].get(source)
            if existing is not None:
                return self.get(existing)
        if len(self.state["entries"]) >= self._positive_int(
            "max_artifacts", _DEFAULT_MAX_ARTIFACTS
        ):
            self.state["dropped_artifacts"] += 1
            return None
        cycle = int(self.world.get("cycle", 0))
        identifier = int(self.state["next_artifact_id"])
        self.state["next_artifact_id"] += 1
        numeric_quality = max(0.0, float(quality))
        materials = []
        for value in material_ids or ():
            material = str(value)
            if material and material not in materials:
                materials.append(material)
        entry = {
            "artifact_id": identifier,
            "item_id": str(item_id),
            "name": Translator.translate(
                "artifacts.generated_name",
                item=str(item_id),
                artifact_id=identifier,
            ),
            "quality": round(numeric_quality, 6),
            "creator_id": self._optional_id(creator_id),
            "material_ids": materials,
            "inscription": None if inscription is None else str(inscription),
            "holder": {
                "kind": None if holder_kind is None else str(holder_kind),
                "id": self._optional_id(holder_id),
            },
            "location": self._location(location),
            "status": "active",
            "renown": round(min(self._max_renown(), numeric_quality), 6),
            "source_key": source,
            "created_cycle": cycle,
            "last_changed_cycle": cycle,
            "origin_chronicle_id": None,
            "provenance": [{
                "cycle": cycle,
                "event_type": "created",
                "actor_ids": [] if creator_id is None else [int(creator_id)],
                "holder": {
                    "kind": None if holder_kind is None else str(holder_kind),
                    "id": self._optional_id(holder_id),
                },
                "location": self._location(location),
                "facts": {"quality": round(numeric_quality, 6)},
            }],
        }
        self.state["entries"].append(entry)
        self._index(entry)
        chronicle = self._chronicle(
            entry,
            "artifact_created",
            actors=[] if creator_id is None else [int(creator_id)],
            reason="created",
            caused_by=caused_by,
        )
        if chronicle is not None:
            entry["origin_chronicle_id"] = chronicle["chronicle_id"]
        self._promote_legend_if_ready(entry)
        return deepcopy(entry)

    def get(self, artifact_id):
        entry = self._stored(artifact_id)
        return None if entry is None else deepcopy(entry)

    def query(
        self,
        *,
        item_id=None,
        holder_id=None,
        creator_id=None,
        status=None,
        material_id=None,
        source_key=None,
    ):
        if not self.enabled:
            return []
        selected = []
        for entry in self.state["entries"]:
            if item_id is not None and entry["item_id"] != str(item_id):
                continue
            if holder_id is not None and entry["holder"]["id"] != int(holder_id):
                continue
            if creator_id is not None and entry["creator_id"] != int(creator_id):
                continue
            if status is not None and entry["status"] != str(status):
                continue
            if material_id is not None and str(material_id) not in entry["material_ids"]:
                continue
            if source_key is not None and entry["source_key"] != str(source_key):
                continue
            selected.append(deepcopy(entry))
        return selected

    def transfer(
        self,
        artifact_id,
        reason,
        holder_kind,
        holder_id,
        *,
        location=None,
        actor_ids=None,
        facts=None,
        caused_by=None,
    ):
        entry = self._stored(artifact_id)
        if entry is None:
            return None
        event_type = str(reason)
        if event_type not in _ALLOWED_TRANSFERS:
            raise ValueError("unsupported artifact transfer reason")
        previous_holder = deepcopy(entry["holder"])
        if event_type == "lost":
            holder = {"kind": None, "id": None}
            entry["status"] = "lost"
        else:
            if holder_kind is None or holder_id is None:
                raise ValueError("artifact transfer requires a holder")
            holder = {"kind": str(holder_kind), "id": int(holder_id)}
            entry["status"] = "active"
        entry["holder"] = holder
        if location is not None:
            entry["location"] = self._location(location)
        entry["last_changed_cycle"] = int(self.world.get("cycle", 0))
        event_facts = dict(facts or {})
        event_facts["previous_holder"] = previous_holder
        self._append_event(
            entry,
            event_type,
            actor_ids=actor_ids,
            facts=event_facts,
        )
        self._increase_renown(entry, 1.0)
        self._chronicle(
            entry,
            "artifact_transferred",
            actors=list(actor_ids or ()),
            reason=event_type,
            caused_by=caused_by,
        )
        return deepcopy(entry)

    def record_event(
        self,
        artifact_id,
        event_type,
        *,
        actor_ids=None,
        location=None,
        importance=1.0,
        facts=None,
        caused_by=None,
    ):
        entry = self._stored(artifact_id)
        if entry is None:
            return None
        if location is not None:
            entry["location"] = self._location(location)
        entry["last_changed_cycle"] = int(self.world.get("cycle", 0))
        self._append_event(
            entry,
            str(event_type),
            actor_ids=actor_ids,
            facts=facts,
        )
        self._increase_renown(entry, importance)
        self._chronicle(
            entry,
            "artifact_event",
            actors=list(actor_ids or ()),
            reason=str(event_type),
            caused_by=caused_by,
        )
        return deepcopy(entry)

    def prestige_bonus(self, holder_id):
        if not self.enabled:
            return 0.0
        identifier = int(holder_id)
        renown = sum(
            float(entry["renown"])
            for entry in self.state["entries"]
            if entry["status"] == "active"
            and entry["holder"]["id"] == identifier
        )
        multiplier = self.settings.get("prestige_per_renown", 0.0)
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
            multiplier = 0.0
        return round(renown * max(0.0, float(multiplier)), 6)

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        entries = self.state["entries"]
        holders = {
            (entry["holder"]["kind"], entry["holder"]["id"])
            for entry in entries
            if entry["holder"]["id"] is not None
        }
        return {
            "enabled": True,
            "artifacts": len(entries),
            "active": sum(entry["status"] == "active" for entry in entries),
            "lost": sum(entry["status"] == "lost" for entry in entries),
            "holders": len(holders),
            "total_renown": round(sum(float(entry["renown"]) for entry in entries), 6),
            "provenance_events": sum(len(entry["provenance"]) for entry in entries),
            "dropped_artifacts": int(self.state.get("dropped_artifacts", 0)),
        }

    def _append_event(self, entry, event_type, *, actor_ids, facts):
        event = {
            "cycle": int(self.world.get("cycle", 0)),
            "event_type": str(event_type),
            "actor_ids": self._unique_ids(actor_ids),
            "holder": deepcopy(entry["holder"]),
            "location": deepcopy(entry["location"]),
            "facts": deepcopy(dict(facts or {})),
        }
        entry["provenance"].append(event)
        maximum = self._positive_int(
            "max_history_per_artifact", _DEFAULT_MAX_HISTORY
        )
        if len(entry["provenance"]) > maximum:
            del entry["provenance"][:-maximum]

    def _increase_renown(self, entry, importance):
        weight = self.settings.get("renown_per_event", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            weight = 1.0
        amount = max(0.0, float(importance)) * max(0.0, float(weight))
        entry["renown"] = round(
            min(self._max_renown(), float(entry["renown"]) + amount),
            6,
        )
        self._promote_legend_if_ready(entry)

    def _promote_legend_if_ready(self, entry):
        """Promote a renowned artifact once its origin chronicle is known."""
        legends = self.config.get("legends", {})
        threshold = (
            legends.get("artifact_renown_threshold", float("inf"))
            if isinstance(legends, dict) and legends.get("enabled") is True
            else float("inf")
        )
        if (
            not isinstance(threshold, bool)
            and isinstance(threshold, (int, float))
            and float(entry["renown"]) >= max(0.0, float(threshold))
        ):
            from core.legends import LegendRegistry
            LegendRegistry(self.world, self.config).promote_artifact(entry)

    def _chronicle(self, entry, event_type, *, actors, reason, caused_by):
        history = self.config.get("history", {})
        if not isinstance(history, dict) or history.get("enabled") is not True:
            return None
        cycle = int(self.world.get("cycle", 0))
        actor_values = [
            {"entity_id": identifier, "role": "participant"}
            for identifier in self._unique_ids(actors)
        ]
        if entry["creator_id"] is not None and event_type == "artifact_created":
            actor_values = [{"entity_id": entry["creator_id"], "role": "creator"}]
        locations = []
        if entry["location"] is not None:
            locations.append({
                "location_id": f"tile:{entry['location'][0]},{entry['location'][1]}",
                "role": "current_location",
            })
        return ChronicleBook(self.world, self.config).record(
            None,
            cycle=cycle,
            year=cycle // 12,
            month=(cycle % 12) + 1,
            category="artifacts",
            event_type=event_type,
            actors=actor_values,
            objects=[{
                "object_id": f"artifact:{entry['artifact_id']}",
                "role": "artifact",
            }],
            locations=locations,
            facts={
                "artifact_id": entry["artifact_id"],
                "item_id": entry["item_id"],
                "quality": entry["quality"],
                "reason": str(reason),
                "holder": deepcopy(entry["holder"]),
                "renown": entry["renown"],
            },
            caused_by=caused_by,
            text_key=f"events.{event_type}",
            text_args={"artifact": entry["name"], "reason": str(reason)},
        )

    def _migrate(self, state):
        state.setdefault("version", 1)
        state.setdefault("entries", [])
        state.setdefault("dropped_artifacts", 0)
        state["next_artifact_id"] = max(
            int(state.get("next_artifact_id", 1)),
            max(
                (int(entry.get("artifact_id", 0)) for entry in state["entries"]),
                default=0,
            ) + 1,
        )
        state["artifact_index"] = {}
        state["source_index"] = {}
        for entry in state["entries"]:
            entry.setdefault("provenance", [])
            entry.setdefault("renown", 0.0)
            entry.setdefault("status", "active")
            entry.setdefault("holder", {"kind": None, "id": None})
            entry.setdefault("location", None)
            self._index(entry)

    def _index(self, entry):
        identifier = int(entry["artifact_id"])
        self.state["artifact_index"][str(identifier)] = entry
        if entry.get("source_key") is not None:
            self.state["source_index"][str(entry["source_key"])] = identifier

    def _stored(self, artifact_id):
        if not self.enabled:
            return None
        try:
            identifier = int(artifact_id)
        except (TypeError, ValueError):
            return None
        return self.state["artifact_index"].get(str(identifier))

    def _max_renown(self):
        value = self.settings.get("max_renown", 100.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 100.0
        return max(0.0, float(value))

    def _positive_int(self, key, default):
        value = self.settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return default
        return value

    @staticmethod
    def _optional_id(value):
        return None if value is None else int(value)

    @staticmethod
    def _location(value):
        if value is None:
            return None
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
        ):
            raise ValueError("artifact location must contain two integers")
        return [int(value[0]), int(value[1])]

    @staticmethod
    def _unique_ids(values):
        result = []
        for value in values or ():
            identifier = int(value)
            if identifier not in result:
                result.append(identifier)
        return result


def promote_completed_order(world, settlement, order, recipe, config):
    """Promote at most a configured number of conserved output units."""
    registry = ArtifactRegistry(world, config)
    if not registry.enabled or not isinstance(order, dict):
        return []
    quality = float(order.get("output_quality", 0.0))
    threshold = registry.settings.get("promotion_quality", 1.5)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        return []
    if quality < float(threshold):
        return []
    eligible = registry.settings.get("eligible_items", [])
    if not isinstance(eligible, list):
        return []
    eligible_ids = {str(value) for value in eligible if isinstance(value, str)}
    maximum = registry._positive_int("max_promotions_per_order", 1)
    from core.stockpiles import StockpileService

    stockpile = StockpileService(settlement, config)
    promoted = []
    for item_id, quantity in sorted(recipe.get("outputs", {}).items()):
        if item_id not in eligible_ids:
            continue
        count = min(maximum - len(promoted), int(float(quantity)))
        for index in range(max(0, count)):
            if stockpile.quantity(item_id) < 1.0:
                break
            source_key = (
                f"production:{int(settlement.entity_id)}:"
                f"{int(order['order_id'])}:{item_id}:{index}"
            )
            existing = registry.query(source_key=source_key)
            if existing:
                promoted.append(existing[0]["artifact_id"])
                continue
            artifact = registry.create(
                item_id,
                quality=quality,
                creator_id=order.get("worker_id"),
                material_ids=sorted(recipe.get("inputs", {})),
                holder_kind="settlement",
                holder_id=int(settlement.entity_id),
                location=list(settlement.pos),
                source_key=source_key,
            )
            if artifact is None:
                continue
            removed = stockpile.withdraw(item_id, 1.0)
            if removed != 1.0:
                raise RuntimeError("artifact promotion conservation failure")
            promoted.append(artifact["artifact_id"])
        if len(promoted) >= maximum:
            break
    return promoted
