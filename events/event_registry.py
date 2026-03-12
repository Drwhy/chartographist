"""
Global registry for simulation events.
Any class decorated with @register_event will be automatically added
to the catalog and processed by the game engine.
"""

EVENT_CATALOG = []

def register_event(cls):
    """
    Decorator used to register an event class into the global catalog.
    Instantiates the event and adds it to the list for engine processing.
    """
    EVENT_CATALOG.append(cls())
    return cls