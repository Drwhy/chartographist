EVENT_CATALOG = []

def register_event(cls):
    """Décorateur pour ajouter un événement au catalogue."""
    EVENT_CATALOG.append(cls())
    return cls