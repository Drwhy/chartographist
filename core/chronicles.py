"""Historique causal, interrogeable et sérialisable d'une simulation."""

from collections import deque
from copy import deepcopy

from core.translator import Translator


_CHRONICLE_VERSION = 2
_DEFAULT_MAX_FACTS = 16
_DEFAULT_MAX_LINKS = 8


class ChronicleBook:
    """Façade rétrocompatible autour des données de chroniques du monde."""

    def __init__(self, world, settings=None):
        self.world = world
        supplied = settings if isinstance(settings, dict) else {}
        history = supplied.get("history", supplied)
        self.settings = history if isinstance(history, dict) else {}
        entries = world.setdefault("chronicles", [])
        for entry in entries:
            if isinstance(entry, dict):
                self._migrate_entry(entry)
        if "next_chronicle_id" not in world:
            world["next_chronicle_id"] = max(
                (
                    int(entry.get("chronicle_id", 0))
                    for entry in entries
                    if isinstance(entry, dict)
                ),
                default=0,
            ) + 1

    def record(
        self,
        message,
        *,
        cycle,
        year,
        month,
        category="event",
        entity_ids=None,
        position=None,
        event_type=None,
        actors=None,
        objects=None,
        locations=None,
        causes=None,
        consequences=None,
        facts=None,
        caused_by=None,
        text_key=None,
        text_args=None,
    ):
        """Ajoute une entrée causale et renvoie une copie indépendante."""
        rendered = message
        if not rendered and text_key:
            rendered = Translator.translate(str(text_key), **deepcopy(text_args or {}))
        if not rendered:
            return None

        related_ids = self._unique_scalars(entity_ids)
        normalized_actors = self._normalize_refs(actors, "entity_id")
        for actor in normalized_actors:
            entity_id = actor["entity_id"]
            if entity_id not in related_ids:
                related_ids.append(entity_id)

        maximum_facts = self._positive_limit("max_facts", _DEFAULT_MAX_FACTS)
        entry = {
            "chronicle_version": _CHRONICLE_VERSION,
            "chronicle_id": self.world["next_chronicle_id"],
            "cycle": int(cycle),
            "year": int(year),
            "month": int(month),
            "category": str(category),
            "event_type": str(event_type or category),
            "message": str(rendered),
            "text_key": str(text_key) if text_key else None,
            "text_args": deepcopy(text_args or {}),
            "entity_ids": related_ids,
            "position": list(position) if position is not None else None,
            "actors": normalized_actors[:maximum_facts],
            "objects": self._normalize_refs(objects, "object_id")[:maximum_facts],
            "locations": self._normalize_refs(locations, "location_id")[:maximum_facts],
            "causes": self._normalize_facts(causes)[:maximum_facts],
            "consequences": self._normalize_facts(consequences)[:maximum_facts],
            "facts": (
                dict(list(deepcopy(facts).items())[:maximum_facts])
                if isinstance(facts, dict)
                else {}
            ),
            "caused_by": [],
            "resulted_in": [],
        }
        self.world["chronicles"].append(entry)
        self.world["next_chronicle_id"] += 1
        for cause_id in self._unique_scalars(caused_by):
            self.link(cause_id, entry["chronicle_id"])
        return deepcopy(entry)

    def record_many(self, messages, *, cycle, year, month, category="event", metadata=None):
        """Enregistre un lot de journaux et leurs contextes optionnels."""
        contexts = list(metadata or ())
        entries = []
        structured_keys = (
            "event_type",
            "actors",
            "objects",
            "locations",
            "causes",
            "consequences",
            "facts",
            "caused_by",
            "text_key",
            "text_args",
        )
        for index, message in enumerate(messages):
            context = contexts[index] if index < len(contexts) else {}
            keyword = {
                key: context.get(key)
                for key in structured_keys
                if context.get(key) is not None
            }
            entry = self.record(
                message,
                cycle=cycle,
                year=year,
                month=month,
                category=context.get("category", category),
                entity_ids=context.get("entity_ids"),
                position=context.get("position"),
                **keyword,
            )
            if entry is not None:
                entries.append(entry)
        return entries

    def get(self, chronicle_id):
        """Renvoie une entrée par identifiant stable."""
        entry = self._stored_entry(chronicle_id)
        return deepcopy(entry) if entry is not None else None

    def link(self, cause_id, result_id):
        """Crée un lien causal bidirectionnel borné et idempotent."""
        cause = self._stored_entry(cause_id)
        result = self._stored_entry(result_id)
        if cause is None or result is None or cause is result:
            return False
        cause_id = int(cause["chronicle_id"])
        result_id = int(result["chronicle_id"])
        if (
            result_id in cause["resulted_in"]
            or cause_id in result["caused_by"]
        ):
            return False
        maximum = self._positive_limit("max_links", _DEFAULT_MAX_LINKS)
        if len(cause["resulted_in"]) >= maximum or len(result["caused_by"]) >= maximum:
            return False
        cause["resulted_in"].append(result_id)
        result["caused_by"].append(cause_id)
        return True

    def causal_chain(self, chronicle_id, *, direction="causes", max_depth=32):
        """Parcourt le graphe causal sans boucle, depuis l'événement demandé."""
        if direction not in {"causes", "results"}:
            raise ValueError("direction must be causes or results")
        if (
            isinstance(max_depth, bool)
            or not isinstance(max_depth, int)
            or max_depth < 0
        ):
            raise ValueError("max_depth must be a non-negative integer")
        start = self._stored_entry(chronicle_id)
        if start is None:
            return []
        link_key = "caused_by" if direction == "causes" else "resulted_in"
        queue = deque([(int(start["chronicle_id"]), 0)])
        visited = set()
        ordered = []
        while queue:
            current_id, depth = queue.popleft()
            if current_id in visited:
                continue
            current = self._stored_entry(current_id)
            if current is None:
                continue
            visited.add(current_id)
            ordered.append(deepcopy(current))
            if depth >= max_depth:
                continue
            for linked_id in current.get(link_key, ()):
                if int(linked_id) not in visited:
                    queue.append((int(linked_id), depth + 1))
        return ordered

    def query(
        self,
        *,
        category=None,
        entity_id=None,
        event_type=None,
        actor_id=None,
        object_id=None,
        location_id=None,
        caused_by=None,
        since_cycle=None,
        until_cycle=None,
        limit=None,
    ):
        """Filtre l'historique et renvoie des copies, dans l'ordre chronologique."""
        entries = self.world["chronicles"]
        if category is not None:
            entries = [entry for entry in entries if entry.get("category") == category]
        if entity_id is not None:
            entries = [entry for entry in entries if entity_id in entry.get("entity_ids", [])]
        if event_type is not None:
            entries = [entry for entry in entries if entry.get("event_type") == event_type]
        if actor_id is not None:
            entries = [
                entry
                for entry in entries
                if any(actor.get("entity_id") == actor_id for actor in entry.get("actors", ()))
            ]
        if object_id is not None:
            entries = [
                entry
                for entry in entries
                if any(item.get("object_id") == object_id for item in entry.get("objects", ()))
            ]
        if location_id is not None:
            entries = [
                entry
                for entry in entries
                if any(place.get("location_id") == location_id for place in entry.get("locations", ()))
            ]
        if caused_by is not None:
            entries = [entry for entry in entries if caused_by in entry.get("caused_by", ())]
        if since_cycle is not None:
            entries = [entry for entry in entries if entry.get("cycle", 0) >= since_cycle]
        if until_cycle is not None:
            entries = [entry for entry in entries if entry.get("cycle", 0) <= until_cycle]
        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be non-negative")
            entries = entries[-limit:] if limit else []
        return deepcopy(entries)

    def _migrate_entry(self, entry):
        entry["chronicle_version"] = _CHRONICLE_VERSION
        entry.setdefault("event_type", str(entry.get("category", "event")))
        entry.setdefault("text_key", None)
        entry.setdefault("text_args", {})
        entry.setdefault("actors", [])
        entry.setdefault("objects", [])
        entry.setdefault("locations", [])
        entry.setdefault("causes", [])
        entry.setdefault("consequences", [])
        entry.setdefault("facts", {})
        entry.setdefault("caused_by", [])
        entry.setdefault("resulted_in", [])
        entry.setdefault("entity_ids", [])
        entry.setdefault("position", None)
        return entry

    def _stored_entry(self, chronicle_id):
        try:
            identifier = int(chronicle_id)
        except (TypeError, ValueError):
            return None
        return next(
            (
                entry
                for entry in self.world["chronicles"]
                if isinstance(entry, dict)
                and int(entry.get("chronicle_id", -1)) == identifier
            ),
            None,
        )

    def _positive_limit(self, key, default):
        value = self.settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return default
        return value

    @staticmethod
    def _unique_scalars(values):
        unique = []
        for value in values or ():
            if value not in unique:
                unique.append(value)
        return unique

    @staticmethod
    def _normalize_refs(values, identifier_key):
        normalized = []
        seen = set()
        for value in values or ():
            if not isinstance(value, dict) or value.get(identifier_key) is None:
                continue
            item = deepcopy(value)
            identity = (item.get(identifier_key), str(item.get("role", "")))
            if identity in seen:
                continue
            seen.add(identity)
            normalized.append(item)
        return normalized

    @staticmethod
    def _normalize_facts(values):
        return [deepcopy(value) for value in values or () if isinstance(value, dict)]
