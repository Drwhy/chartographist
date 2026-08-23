class GameLogger:
    """Tampon global rétrocompatible pour les événements de simulation."""

    _logs = []
    _metadata = []
    _last_metadata = []

    @classmethod
    def log(cls, message, *, category="event", entity_ids=None, position=None):
        """Ajoute un message et, facultativement, son contexte structuré."""
        if message:
            cls._logs.append(str(message))
            cls._metadata.append({
                "category": str(category),
                "entity_ids": list(entity_ids or ()),
                "position": list(position) if position is not None else None,
            })

    @classmethod
    def get_new_logs(cls):
        """Renvoie les chaînes accumulées et vide le tampon historique."""
        current_batch = list(cls._logs)
        cls._last_metadata = list(cls._metadata)
        cls._logs.clear()
        cls._metadata.clear()
        return current_batch

    @classmethod
    def get_last_metadata(cls, expected_count=None):
        """Consomme les contextes associés au dernier lot de chaînes extrait."""
        metadata = list(cls._last_metadata)
        cls._last_metadata.clear()
        if expected_count is not None and len(metadata) != expected_count:
            return [{} for _ in range(expected_count)]
        return metadata