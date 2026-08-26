"""Sites géographiques persistants, bornés et reliés à l'histoire."""

from copy import deepcopy

from core.chronicles import ChronicleBook
from core.translator import Translator


_DEFAULT_MAX_SITES = 512
_DEFAULT_MAX_HISTORY = 32
_DEFAULT_SYMBOLS = {
    "battlefield": "† ",
    "ruins": "▒▒",
    "sanctuary": "⌂ ",
    "mine": "⛏ ",
    "road": "◆ ",
}
_DEFAULT_STAGE_SYMBOLS = {
    "destroyed": "× ",
    "rebuilt": "▣ ",
    "reoccupied": "⌂ ",
    "overgrown": "░░",
}


class SiteRegistry:
    """Possède l'identité et le cycle de vie des lieux remarquables."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("sites", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.config = config if isinstance(config, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if not self.enabled:
            return
        state = world.get("sites")
        if not isinstance(state, dict):
            state = {
                "version": 1,
                "next_site_id": 1,
                "last_advanced_cycle": None,
                "entries": [],
                "position_index": {},
                "site_index": {},
                "dropped_sites": 0,
            }
            world["sites"] = state
        self._migrate_state(state)

    @property
    def state(self):
        return self.world.get("sites")

    def create(
        self,
        kind,
        position,
        *,
        founder_ids=None,
        owner_ids=None,
        resources=None,
        source_entity_id=None,
        origin_chronicle_id=None,
        status=None,
        facts=None,
    ):
        """Crée un site stable ou renvoie le site déjà attaché à cette source."""
        if not self.enabled:
            return None
        normalized_kind = str(kind).strip()
        if not normalized_kind:
            raise ValueError("site kind must be non-empty")
        normalized_position = self._position(position)
        existing = self._existing(
            normalized_kind,
            normalized_position,
            source_entity_id,
        )
        if existing is not None:
            return deepcopy(existing)
        maximum = self._positive_limit("max_sites", _DEFAULT_MAX_SITES)
        if len(self.state["entries"]) >= maximum:
            self.state["dropped_sites"] += 1
            return None

        cycle = int(self.world.get("cycle", 0))
        identifier = int(self.state["next_site_id"])
        entry = {
            "site_id": identifier,
            "kind": normalized_kind,
            "position": normalized_position,
            "status": str(status or ("ruined" if normalized_kind == "ruins" else "active")),
            "founded_cycle": cycle,
            "last_changed_cycle": cycle,
            "founder_ids": self._unique_ids(founder_ids),
            "owner_ids": self._unique_ids(owner_ids),
            "occupant_ids": [],
            "source_entity_id": (
                int(source_entity_id) if source_entity_id is not None else None
            ),
            "origin_chronicle_id": None,
            "appearance": {
                "stage": "fresh",
                "symbol": self._symbol(normalized_kind),
            },
            "resources": deepcopy(resources) if isinstance(resources, dict) else {},
            "discoveries": {},
            "history": [{
                "cycle": cycle,
                "event_type": "founded",
                "actor_ids": self._unique_ids(founder_ids),
                "facts": deepcopy(facts) if isinstance(facts, dict) else {},
            }],
        }
        self.state["next_site_id"] += 1
        self.state["entries"].append(entry)
        self._index(entry)
        chronicle = self._record_chronicle(
            entry,
            "site_founded",
            actor_ids=entry["founder_ids"],
            caused_by=[origin_chronicle_id] if origin_chronicle_id is not None else None,
            facts=facts,
        )
        if chronicle is not None:
            entry["origin_chronicle_id"] = chronicle["chronicle_id"]
        return deepcopy(entry)

    def get(self, site_id):
        """Renvoie un site par ID sans exposer le stockage mutable."""
        entry = self._stored(site_id)
        return deepcopy(entry) if entry is not None else None

    def site_at(self, position):
        """Renvoie le premier site visible d'une position."""
        if not self.enabled:
            return None
        key = self._position_key(self._position(position))
        identifiers = self.state["position_index"].get(key, ())
        for identifier in identifiers:
            entry = self._stored(identifier)
            if entry is not None:
                return deepcopy(entry)
        return None

    def query(
        self,
        *,
        kind=None,
        status=None,
        owner_id=None,
        source_entity_id=None,
        discovered_by=None,
        position=None,
        limit=None,
    ):
        """Filtre les sites dans l'ordre de fondation."""
        if not self.enabled:
            return []
        entries = self.state["entries"]
        if kind is not None:
            entries = [entry for entry in entries if entry["kind"] == kind]
        if status is not None:
            entries = [entry for entry in entries if entry["status"] == status]
        if owner_id is not None:
            entries = [entry for entry in entries if owner_id in entry["owner_ids"]]
        if source_entity_id is not None:
            entries = [
                entry
                for entry in entries
                if entry.get("source_entity_id") == source_entity_id
            ]
        if discovered_by is not None:
            key = str(int(discovered_by))
            entries = [entry for entry in entries if key in entry["discoveries"]]
        if position is not None:
            expected = self._position(position)
            entries = [entry for entry in entries if entry["position"] == expected]
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be a non-negative integer")
            entries = entries[-limit:] if limit else []
        return deepcopy(entries)

    def record_event(
        self,
        site_id,
        event_type,
        *,
        status=None,
        owner_ids=None,
        occupant_ids=None,
        resource_changes=None,
        appearance_stage=None,
        actor_ids=None,
        facts=None,
        caused_by=None,
    ):
        """Fait évoluer un site sans changer son identité."""
        entry = self._stored(site_id)
        if entry is None:
            return None
        cycle = int(self.world.get("cycle", 0))
        if status is not None:
            entry["status"] = str(status)
        if owner_ids is not None:
            entry["owner_ids"] = self._unique_ids(owner_ids)
        if occupant_ids is not None:
            entry["occupant_ids"] = self._unique_ids(occupant_ids)
        if appearance_stage is not None:
            entry["appearance"]["stage"] = str(appearance_stage)
            entry["appearance"]["symbol"] = self._appearance_symbol(
                entry["kind"], str(appearance_stage)
            )
        if isinstance(resource_changes, dict):
            for resource, delta in resource_changes.items():
                current = float(entry["resources"].get(str(resource), 0.0))
                entry["resources"][str(resource)] = round(
                    max(0.0, current + float(delta)),
                    6,
                )
        entry["last_changed_cycle"] = cycle
        event = {
            "cycle": cycle,
            "event_type": str(event_type),
            "actor_ids": self._unique_ids(actor_ids),
            "facts": deepcopy(facts) if isinstance(facts, dict) else {},
        }
        entry["history"].append(event)
        maximum = self._positive_limit(
            "max_history_per_site",
            _DEFAULT_MAX_HISTORY,
        )
        if len(entry["history"]) > maximum:
            del entry["history"][:-maximum]
        if str(event_type) in {"destroyed", "reconstructed", "reoccupied"}:
            self._record_chronicle(
                entry,
                f"site_{event_type}",
                actor_ids=event["actor_ids"],
                caused_by=caused_by,
                facts=facts,
            )
        return deepcopy(entry)

    def destroy(self, site_id, *, actor_ids=None, cause=None, caused_by=None):
        return self.record_event(
            site_id,
            "destroyed",
            status="destroyed",
            appearance_stage="destroyed",
            actor_ids=actor_ids,
            facts={"cause": str(cause)} if cause is not None else {},
            caused_by=caused_by,
        )

    def reconstruct(self, site_id, *, actor_ids=None, owner_ids=None, caused_by=None):
        return self.record_event(
            site_id,
            "reconstructed",
            status="active",
            owner_ids=owner_ids,
            appearance_stage="rebuilt",
            actor_ids=actor_ids,
            caused_by=caused_by,
        )

    def reoccupy(self, site_id, *, occupant_ids, owner_ids=None, caused_by=None):
        occupants = self._unique_ids(occupant_ids)
        return self.record_event(
            site_id,
            "reoccupied",
            status="active",
            owner_ids=owner_ids if owner_ids is not None else occupants,
            occupant_ids=occupants,
            appearance_stage="reoccupied",
            actor_ids=occupants,
            caused_by=caused_by,
        )

    def discover(self, site_id, observer_id):
        """Mémorise une première découverte sans dupliquer les visites."""
        entry = self._stored(site_id)
        if entry is None:
            return False
        key = str(int(observer_id))
        if key in entry["discoveries"]:
            return False
        cycle = int(self.world.get("cycle", 0))
        entry["discoveries"][key] = cycle
        entry["history"].append({
            "cycle": cycle,
            "event_type": "discovered",
            "actor_ids": [int(observer_id)],
            "facts": {},
        })
        maximum = self._positive_limit(
            "max_history_per_site",
            _DEFAULT_MAX_HISTORY,
        )
        if len(entry["history"]) > maximum:
            del entry["history"][:-maximum]
        return True

    def advance(self):
        """Synchronise les ruines physiques et fait vieillir l'apparence."""
        if not self.enabled:
            return False
        cycle = int(self.world.get("cycle", 0))
        interval = self._positive_limit("advance_interval", 1)
        if self.state.get("last_advanced_cycle") == cycle or cycle % interval:
            return False
        changed = False
        from entities.constructs.ruins import Ruins

        ruins_by_id = {}
        for entity in self.world.get("entities", ()):
            if not isinstance(entity, Ruins) or getattr(entity, "is_expired", False):
                continue
            ruins_by_id[int(entity.entity_id)] = entity
            existing = self.query(source_entity_id=int(entity.entity_id))
            if not existing:
                created = self.create(
                    "ruins",
                    entity.pos,
                    source_entity_id=entity.entity_id,
                    resources={"salvage": 1.0},
                    status="ruined",
                    facts={"name": getattr(entity, "name", "")},
                )
                changed = created is not None or changed

        overgrow = self._positive_limit("overgrow_cycles", 120)
        for entry in self.state["entries"]:
            age = cycle - int(entry["founded_cycle"])
            if (
                entry["status"] in {"ruined", "abandoned"}
                and age >= overgrow
                and entry["appearance"]["stage"] != "overgrown"
            ):
                entry["appearance"]["stage"] = "overgrown"
                entry["appearance"]["symbol"] = self._appearance_symbol(
                    entry["kind"], "overgrown"
                )
                entry["last_changed_cycle"] = cycle
                entry["history"].append({
                    "cycle": cycle,
                    "event_type": "overgrown",
                    "actor_ids": [],
                    "facts": {"age": age},
                })
                maximum = self._positive_limit(
                    "max_history_per_site",
                    _DEFAULT_MAX_HISTORY,
                )
                if len(entry["history"]) > maximum:
                    del entry["history"][:-maximum]
                changed = True
            if entry["kind"] == "ruins":
                physical = ruins_by_id.get(entry.get("source_entity_id"))
                if physical is not None:
                    physical.char = entry["appearance"]["symbol"]
        self.state["last_advanced_cycle"] = cycle
        return changed

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        entries = self.state["entries"]
        kinds = {}
        statuses = {}
        for entry in entries:
            kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
            statuses[entry["status"]] = statuses.get(entry["status"], 0) + 1
        return {
            "enabled": True,
            "sites": len(entries),
            "kinds": kinds,
            "statuses": statuses,
            "discoveries": sum(len(entry["discoveries"]) for entry in entries),
            "dropped_sites": int(self.state.get("dropped_sites", 0)),
        }

    def _record_chronicle(
        self,
        entry,
        event_type,
        *,
        actor_ids=None,
        caused_by=None,
        facts=None,
    ):
        history = self.config.get("history", {})
        if not isinstance(history, dict) or history.get("enabled") is not True:
            return None
        kind_key = f"sites.kind_{entry['kind']}"
        kind_name = Translator.translate(kind_key)
        if kind_name.startswith("[MISSING_TEXT:"):
            kind_name = Translator.translate("sites.kind_unknown")
        cycle = int(self.world.get("cycle", 0))
        return ChronicleBook(self.world, self.config).record(
            None,
            cycle=cycle,
            year=cycle // 12,
            month=(cycle % 12) + 1,
            category="sites",
            event_type=str(event_type),
            actors=[
                {"entity_id": identifier, "role": "site_actor"}
                for identifier in self._unique_ids(actor_ids)
            ],
            objects=[{
                "object_id": f"site:{entry['site_id']}",
                "role": entry["kind"],
            }],
            locations=[{
                "location_id": f"site:{entry['site_id']}",
                "role": "site",
                "position": list(entry["position"]),
            }],
            consequences=[{
                "kind": str(event_type),
                "status": entry["status"],
            }],
            facts={
                "site_id": entry["site_id"],
                "site_kind": entry["kind"],
                **(deepcopy(facts) if isinstance(facts, dict) else {}),
            },
            caused_by=caused_by,
            text_key=f"events.{event_type}",
            text_args={
                "kind": kind_name,
                "x": entry["position"][0],
                "y": entry["position"][1],
            },
        )

    def _existing(self, kind, position, source_entity_id):
        if source_entity_id is not None:
            expected = int(source_entity_id)
            for entry in self.state["entries"]:
                if entry.get("source_entity_id") == expected:
                    return entry
        for entry in self.state["entries"]:
            if entry["kind"] == kind and entry["position"] == position:
                return entry
        return None

    def _stored(self, site_id):
        if not self.enabled:
            return None
        try:
            identifier = int(site_id)
        except (TypeError, ValueError):
            return None
        return self.state["site_index"].get(str(identifier))

    def _migrate_state(self, state):
        state.setdefault("version", 1)
        state.setdefault("entries", [])
        state.setdefault("dropped_sites", 0)
        state.setdefault("last_advanced_cycle", None)
        state["next_site_id"] = max(
            int(state.get("next_site_id", 1)),
            max(
                (int(entry.get("site_id", 0)) for entry in state["entries"]),
                default=0,
            ) + 1,
        )
        position_index = state.get("position_index")
        site_index = state.get("site_index")
        if (
            isinstance(position_index, dict)
            and isinstance(site_index, dict)
            and len(site_index) == len(state["entries"])
        ):
            return
        state["position_index"] = {}
        state["site_index"] = {}
        for entry in state["entries"]:
            entry.setdefault("history", [])
            entry.setdefault("discoveries", {})
            entry.setdefault("resources", {})
            entry.setdefault("owner_ids", [])
            entry.setdefault("founder_ids", [])
            entry.setdefault("occupant_ids", [])
            entry.setdefault("appearance", {
                "stage": "fresh",
                "symbol": self._symbol(str(entry.get("kind", "unknown"))),
            })
            self._index(entry)

    def _index(self, entry):
        key = self._position_key(entry["position"])
        identifiers = self.state["position_index"].setdefault(key, [])
        if entry["site_id"] not in identifiers:
            identifiers.append(entry["site_id"])
        self.state["site_index"][str(int(entry["site_id"]))] = entry

    def _symbol(self, kind):
        symbols = self.settings.get("symbols", {})
        if isinstance(symbols, dict) and isinstance(symbols.get(kind), str):
            return symbols[kind]
        return _DEFAULT_SYMBOLS.get(kind, "◇ ")
    def _appearance_symbol(self, kind, stage):
        symbols = self.settings.get("stage_symbols", {})
        if isinstance(symbols, dict) and isinstance(symbols.get(stage), str):
            return symbols[stage]
        return _DEFAULT_STAGE_SYMBOLS.get(stage, self._symbol(kind))


    def _positive_limit(self, key, default):
        value = self.settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return default
        return value

    def _position(self, position):
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in position)
        ):
            raise ValueError("site position must contain two integers")
        x, y = map(int, position)
        width = int(self.world.get("width", 0))
        height = int(self.world.get("height", 0))
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError("site position is outside the world")
        return [x, y]

    @staticmethod
    def _position_key(position):
        return f"{int(position[0])},{int(position[1])}"

    @staticmethod
    def _unique_ids(values):
        result = []
        for value in values or ():
            identifier = int(value)
            if identifier not in result:
                result.append(identifier)
        return result


def visible_site_symbol(world, x, y):
    """Lit l'index spatial sans construire de service pendant le rendu."""
    state = world.get("sites")
    if not isinstance(state, dict):
        return None
    identifiers = state.get("position_index", {}).get(f"{int(x)},{int(y)}", ())
    site_index = state.get("site_index", {})
    for identifier in identifiers:
        entry = site_index.get(str(int(identifier)))
        if entry is not None:
            return entry.get("appearance", {}).get("symbol")
    return None
