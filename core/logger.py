class GameLogger:
    """Tampon global rétrocompatible pour les événements de simulation."""

    _logs = []
    _metadata = []
    _last_metadata = []

    @classmethod
    def log(
        cls,
        message,
        *,
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
        """Ajoute un message et, facultativement, son contexte structuré."""
        if message:
            cls._logs.append(str(message))
            metadata = {
                "category": str(category),
                "entity_ids": list(entity_ids or ()),
                "position": list(position) if position is not None else None,
            }
            optional = {
                "event_type": event_type,
                "actors": actors,
                "objects": objects,
                "locations": locations,
                "causes": causes,
                "consequences": consequences,
                "facts": facts,
                "caused_by": caused_by,
                "text_key": text_key,
                "text_args": text_args,
            }
            for key, value in optional.items():
                if value is not None:
                    if isinstance(value, dict):
                        metadata[key] = dict(value)
                    elif isinstance(value, (list, tuple)):
                        metadata[key] = [
                            dict(item) if isinstance(item, dict) else item
                            for item in value
                        ]
                    else:
                        metadata[key] = value
            cls._metadata.append(metadata)

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