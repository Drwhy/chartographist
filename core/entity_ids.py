"""Attribution déterministe d'identifiants persistants aux entités."""


class EntityIdService:
    """Séquence monotone réinitialisable et sérialisable d'identifiants entiers."""

    _next_id = 1

    @classmethod
    def next_id(cls):
        entity_id = cls._next_id
        cls._next_id += 1
        return entity_id

    @classmethod
    def reset(cls):
        cls._next_id = 1

    @classmethod
    def get_state(cls):
        return cls._next_id

    @classmethod
    def set_state(cls, next_id):
        if not isinstance(next_id, int) or isinstance(next_id, bool) or next_id < 1:
            raise ValueError("invalid:next_entity_id")
        cls._next_id = next_id
