"""Faits historiques, récits publics et motivations légendaires."""

from copy import deepcopy

from core.chronicles import ChronicleBook
from core.translator import Translator


_DEFAULT_MAX_LEGENDS = 256
_DEFAULT_MAX_VERSIONS = 12
_DEFAULT_MAX_HISTORY = 48


class LegendRegistry:
    """Sépare le fait source de ses versions culturelles propagées."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("legends", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.config = config if isinstance(config, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if not self.enabled:
            return
        state = world.get("legends")
        if not isinstance(state, dict):
            state = {
                "version": 1,
                "next_legend_id": 1,
                "entries": [],
                "legend_index": {},
                "origin_index": {},
                "dropped_legends": 0,
                "total_propagations": 0,
            }
            world["legends"] = state
        self._migrate(state)

    @property
    def state(self):
        return self.world.get("legends")

    def promote_chronicle(
        self,
        chronicle_id,
        *,
        importance,
        subject_kind=None,
        subject_id=None,
    ):
        if not self.enabled:
            return None
        origin_id = int(chronicle_id)
        existing = self.state["origin_index"].get(str(origin_id))
        if existing is not None:
            return self.get(existing)
        event = ChronicleBook(self.world, self.config).get(origin_id)
        if event is None:
            return None
        if len(self.state["entries"]) >= self._positive_int(
            "max_legends", _DEFAULT_MAX_LEGENDS
        ):
            self.state["dropped_legends"] += 1
            return None
        identifier = int(self.state["next_legend_id"])
        self.state["next_legend_id"] += 1
        resolved_kind, resolved_id = self._subject(
            event, subject_kind, subject_id
        )
        value = max(0.0, float(importance))
        cycle = int(self.world.get("cycle", event.get("cycle", 0)))
        entry = {
            "legend_id": identifier,
            "origin_chronicle_id": origin_id,
            "subject_kind": resolved_kind,
            "subject_id": resolved_id,
            "fact": {
                "chronicle_id": origin_id,
                "cycle": int(event.get("cycle", 0)),
                "event_type": event.get("event_type"),
                "category": event.get("category"),
                "message": event.get("message"),
                "actors": deepcopy(event.get("actors", [])),
                "objects": deepcopy(event.get("objects", [])),
                "locations": deepcopy(event.get("locations", [])),
                "causes": deepcopy(event.get("causes", [])),
                "consequences": deepcopy(event.get("consequences", [])),
                "facts": deepcopy(event.get("facts", {})),
            },
            "importance": round(value, 6),
            "renown": round(value, 6),
            "versions": [],
            "created_cycle": cycle,
            "last_changed_cycle": cycle,
            "history": [{
                "cycle": cycle,
                "event_type": "legend_born",
                "culture_id": None,
                "faction_id": None,
                "reliability": 1.0,
                "audience_id": None,
            }],
        }
        self.state["entries"].append(entry)
        self._index(entry)
        self._record_chronicle(entry)
        return deepcopy(entry)

    def promote_artifact(self, artifact):
        if not self.enabled or not isinstance(artifact, dict):
            return None
        artifact_id = int(artifact["artifact_id"])
        existing = self.query(
            subject_kind="artifact",
            subject_id=artifact_id,
        )
        if existing:
            return existing[0]
        chronicles = ChronicleBook(self.world, self.config).query(
            object_id=f"artifact:{artifact_id}"
        )
        if not chronicles:
            return None
        return self.promote_chronicle(
            chronicles[-1]["chronicle_id"],
            importance=float(artifact.get("renown", 0.0)),
            subject_kind="artifact",
            subject_id=artifact_id,
        )

    def get(self, legend_id):
        entry = self._stored(legend_id)
        return None if entry is None else deepcopy(entry)

    def query(
        self,
        *,
        subject_kind=None,
        subject_id=None,
        culture_id=None,
        faction_id=None,
        min_renown=None,
    ):
        if not self.enabled:
            return []
        selected = []
        for entry in self.state["entries"]:
            if subject_kind is not None and entry["subject_kind"] != str(subject_kind):
                continue
            if subject_id is not None and entry["subject_id"] != self._normalize_subject_id(subject_id):
                continue
            if min_renown is not None and entry["renown"] < float(min_renown):
                continue
            if culture_id is not None and not any(
                version["culture_id"] == str(culture_id)
                for version in entry["versions"]
            ):
                continue
            if faction_id is not None and not any(
                version["faction_id"] == str(faction_id)
                for version in entry["versions"]
            ):
                continue
            selected.append(deepcopy(entry))
        return selected

    def propagate(
        self,
        legend_id,
        *,
        culture_id=None,
        faction_id=None,
        reliability=1.0,
        audience_id=None,
    ):
        entry = self._stored(legend_id)
        if entry is None:
            return None
        bounded_reliability = round(
            min(1.0, max(0.0, float(reliability))), 6
        )
        culture = None if culture_id is None else str(culture_id)
        faction = None if faction_id is None else str(faction_id)
        emphasis = self._emphasis(culture, faction)
        version = next(
            (
                value for value in entry["versions"]
                if value["culture_id"] == culture
                and value["faction_id"] == faction
            ),
            None,
        )
        cycle = int(self.world.get("cycle", 0))
        if version is None:
            version = {
                "culture_id": culture,
                "faction_id": faction,
                "emphasis": emphasis,
                "narrative": Translator.translate(
                    "legends.public_version",
                    event=entry["fact"].get("message", ""),
                    emphasis=emphasis,
                ),
                "claims": self._claims(entry, emphasis),
                "reliability": bounded_reliability,
                "audience_count": 0,
                "last_propagated_cycle": cycle,
            }
            entry["versions"].append(version)
        else:
            version["reliability"] = round(
                (float(version["reliability"]) + bounded_reliability) / 2.0,
                6,
            )
            version["last_propagated_cycle"] = cycle
        version["audience_count"] += 1
        entry["renown"] = round(
            float(entry["renown"])
            + float(entry["importance"]) * bounded_reliability,
            6,
        )
        entry["last_changed_cycle"] = cycle
        self.state["total_propagations"] += 1
        self._append_history(
            entry,
            culture,
            faction,
            bounded_reliability,
            audience_id,
        )
        maximum = self._positive_int(
            "max_versions_per_legend", _DEFAULT_MAX_VERSIONS
        )
        if len(entry["versions"]) > maximum:
            del entry["versions"][:-maximum]
        if audience_id is not None:
            self._teach_audience(entry, version, audience_id)
        return deepcopy(entry)

    def motivations(self, *, kind=None):
        if not self.enabled:
            return []
        thresholds = {
            "exploration": self._number("exploration_threshold", 10.0),
            "war": self._number("war_threshold", 25.0),
            "cult": self._number("cult_threshold", 50.0),
        }
        motives = []
        for entry in self.state["entries"]:
            for motive_kind, threshold in thresholds.items():
                if kind is not None and motive_kind != str(kind):
                    continue
                if float(entry["renown"]) < threshold:
                    continue
                motives.append({
                    "kind": motive_kind,
                    "legend_id": entry["legend_id"],
                    "subject_kind": entry["subject_kind"],
                    "subject_id": entry["subject_id"],
                    "renown": entry["renown"],
                    "target_locations": deepcopy(
                        entry["fact"].get("locations", [])
                    ),
                    "cause": (
                        entry["fact"].get("causes", [{}])[0].get("kind")
                        if entry["fact"].get("causes")
                        else entry["fact"].get("event_type")
                    ),
                })
        return motives

    def advance(self):
        if not self.enabled:
            return False
        cycle = int(self.world.get("cycle", 0))
        interval = self._positive_int("advance_interval", 1)
        last_cycle = self.state.get("last_advanced_cycle")
        if last_cycle is not None and cycle - int(last_cycle) < interval:
            return False
        self.state["last_advanced_cycle"] = cycle
        maximum = self._positive_int("max_propagations_per_cycle", 8)
        reliability = min(
            1.0, self._number("default_reliability", 0.75)
        )
        candidates = sorted(
            (
                entry for entry in self.state["entries"]
                if not entry["versions"]
            ),
            key=lambda entry: int(entry["legend_id"]),
        )
        changed = False
        for entry in candidates[:maximum]:
            self.propagate(
                entry["legend_id"],
                culture_id=self._culture_for(entry),
                reliability=reliability,
            )
            changed = True
        return changed

    def _culture_for(self, entry):
        entity = None
        if entry["subject_kind"] == "entity":
            entity = self._entity(entry["subject_id"])
        elif entry["subject_kind"] == "artifact":
            from core.artifacts import ArtifactRegistry
            artifact = ArtifactRegistry(self.world, self.config).get(
                entry["subject_id"]
            )
            if artifact is not None and artifact["holder"]["id"] is not None:
                entity = self._entity(artifact["holder"]["id"])
        culture = getattr(entity, "culture", None)
        if isinstance(culture, dict):
            value = culture.get("name") or culture.get("id")
        else:
            value = culture
        return "world" if value in (None, "") else str(value)

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        entries = self.state["entries"]
        return {
            "enabled": True,
            "legends": len(entries),
            "versions": sum(len(entry["versions"]) for entry in entries),
            "total_renown": round(
                sum(float(entry["renown"]) for entry in entries), 6
            ),
            "propagations": int(self.state.get("total_propagations", 0)),
            "motivations": {
                key: len(self.motivations(kind=key))
                for key in ("exploration", "war", "cult")
            },
            "dropped_legends": int(self.state.get("dropped_legends", 0)),
        }

    def _teach_audience(self, entry, version, audience_id):
        owner = self._entity(audience_id)
        if owner is None:
            return
        from core.knowledge import KnowledgeService
        KnowledgeService(owner, self.config).learn(
            kind="legend",
            subject_id=entry["legend_id"],
            claim="public_version",
            value=deepcopy(version),
            cycle=int(self.world.get("cycle", 0)),
            source_id=int(audience_id),
            source_type="legend",
            reliability=float(version["reliability"]),
            position=self._first_position(entry),
        )

    def _record_chronicle(self, entry):
        history = self.config.get("history", {})
        if not isinstance(history, dict) or history.get("enabled") is not True:
            return None
        cycle = int(self.world.get("cycle", 0))
        return ChronicleBook(self.world, self.config).record(
            None,
            cycle=cycle,
            year=cycle // 12,
            month=(cycle % 12) + 1,
            category="legends",
            event_type="legend_born",
            objects=[{
                "object_id": f"legend:{entry['legend_id']}",
                "role": "legend",
            }],
            locations=deepcopy(entry["fact"].get("locations", [])),
            facts={
                "legend_id": entry["legend_id"],
                "origin_chronicle_id": entry["origin_chronicle_id"],
                "subject_kind": entry["subject_kind"],
                "subject_id": entry["subject_id"],
                "importance": entry["importance"],
            },
            caused_by=[entry["origin_chronicle_id"]],
            text_key="events.legend_born",
            text_args={"event": entry["fact"].get("message", "")},
        )

    def _append_history(
        self, entry, culture, faction, reliability, audience_id
    ):
        entry["history"].append({
            "cycle": int(self.world.get("cycle", 0)),
            "event_type": "propagated",
            "culture_id": culture,
            "faction_id": faction,
            "reliability": reliability,
            "audience_id": None if audience_id is None else int(audience_id),
        })
        maximum = self._positive_int(
            "max_history_per_legend", _DEFAULT_MAX_HISTORY
        )
        if len(entry["history"]) > maximum:
            del entry["history"][:-maximum]

    def _subject(self, event, kind, identifier):
        if kind is not None:
            return str(kind), self._normalize_subject_id(identifier)
        objects = event.get("objects", [])
        if objects:
            object_id = str(objects[0].get("object_id", "event"))
            if ":" in object_id:
                object_kind, object_value = object_id.split(":", 1)
                return object_kind, self._normalize_subject_id(object_value)
            return "object", object_id
        actors = event.get("actors", [])
        if actors:
            return "entity", int(actors[0]["entity_id"])
        return "event", int(event["chronicle_id"])

    def _emphasis(self, culture, faction):
        configured = self.settings.get("culture_emphases", {})
        if isinstance(configured, dict) and culture in configured:
            return str(configured[culture])
        if faction is not None:
            return f"faction:{faction}"
        return "memory"

    @staticmethod
    def _claims(entry, emphasis):
        fact = entry["fact"]
        return {
            "event_type": fact.get("event_type"),
            "cause": (
                fact.get("causes", [{}])[0].get("kind")
                if fact.get("causes") else None
            ),
            "emphasis": emphasis,
        }

    def _migrate(self, state):
        state.setdefault("version", 1)
        state.setdefault("entries", [])
        state.setdefault("dropped_legends", 0)
        state.setdefault("total_propagations", 0)
        state.setdefault("last_advanced_cycle", None)
        state["next_legend_id"] = max(
            int(state.get("next_legend_id", 1)),
            max(
                (int(entry.get("legend_id", 0)) for entry in state["entries"]),
                default=0,
            ) + 1,
        )
        state["legend_index"] = {}
        state["origin_index"] = {}
        for entry in state["entries"]:
            entry.setdefault("versions", [])
            entry.setdefault("history", [])
            entry.setdefault("renown", entry.get("importance", 0.0))
            self._index(entry)

    def _index(self, entry):
        identifier = int(entry["legend_id"])
        self.state["legend_index"][str(identifier)] = entry
        self.state["origin_index"][
            str(int(entry["origin_chronicle_id"]))
        ] = identifier

    def _stored(self, legend_id):
        if not self.enabled:
            return None
        try:
            identifier = int(legend_id)
        except (TypeError, ValueError):
            return None
        return self.state["legend_index"].get(str(identifier))

    def _entity(self, entity_id):
        identifier = int(entity_id)
        for entity in self.world.get("entities", ()):
            if int(getattr(entity, "entity_id", -1)) == identifier:
                return entity
            for citizen in getattr(entity, "citizens", ()):
                if int(getattr(citizen, "entity_id", -1)) == identifier:
                    return citizen
        return None

    @staticmethod
    def _first_position(entry):
        for location in entry["fact"].get("locations", ()):
            location_id = str(location.get("location_id", ""))
            if location_id.startswith("tile:"):
                values = location_id.split(":", 1)[1].split(",")
                if len(values) == 2:
                    return [int(values[0]), int(values[1])]
        return None

    @staticmethod
    def _normalize_subject_id(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value)

    def _positive_int(self, key, default):
        value = self.settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return default
        return value

    def _number(self, key, default):
        value = self.settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return float(default)
        return max(0.0, float(value))
