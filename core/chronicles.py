"""Historique structuré, interrogeable et sérialisable d'une simulation."""

from copy import deepcopy


class ChronicleBook:
    """Façade rétrocompatible autour des données de chroniques du monde."""

    def __init__(self, world):
        self.world = world
        entries = world.setdefault("chronicles", [])
        if "next_chronicle_id" not in world:
            world["next_chronicle_id"] = max(
                (entry.get("chronicle_id", 0) for entry in entries),
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
    ):
        """Ajoute une entrée structurée et renvoie une copie indépendante."""
        if not message:
            return None

        related_ids = []
        for entity_id in entity_ids or ():
            if entity_id not in related_ids:
                related_ids.append(entity_id)

        entry = {
            "chronicle_id": self.world["next_chronicle_id"],
            "cycle": int(cycle),
            "year": int(year),
            "month": int(month),
            "category": str(category),
            "message": str(message),
            "entity_ids": related_ids,
            "position": list(position) if position is not None else None,
        }
        self.world["chronicles"].append(entry)
        self.world["next_chronicle_id"] += 1
        return deepcopy(entry)

    def record_many(self, messages, *, cycle, year, month, category="event", metadata=None):
        """Enregistre un lot de journaux et leurs contextes optionnels."""
        contexts = list(metadata or ())
        entries = []
        for index, message in enumerate(messages):
            context = contexts[index] if index < len(contexts) else {}
            entry = self.record(
                message,
                cycle=cycle,
                year=year,
                month=month,
                category=context.get("category", category),
                entity_ids=context.get("entity_ids"),
                position=context.get("position"),
            )
            if entry is not None:
                entries.append(entry)
        return entries

    def query(
        self,
        *,
        category=None,
        entity_id=None,
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
        if since_cycle is not None:
            entries = [entry for entry in entries if entry.get("cycle", 0) >= since_cycle]
        if until_cycle is not None:
            entries = [entry for entry in entries if entry.get("cycle", 0) <= until_cycle]
        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be non-negative")
            entries = entries[-limit:] if limit else []
        return deepcopy(entries)