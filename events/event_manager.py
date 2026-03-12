from .event_registry import EVENT_CATALOG
from core.random_service import RandomService

class EventManager:
    """
    Orchestrates the lifecycle of global simulation events.
    Responsible for checking probabilities and conditions before triggering disasters or changes.
    """
    @staticmethod
    def update(world, stats, config):
        """
        Processes all registered events for the current simulation tick.
        """
        for event in EVENT_CATALOG:
            # 1. Update internal event state (e.g., flame dissipation, plague spread)
            event.tick(world, stats)

            # 2. Probability check based on the event's specific chance
            if RandomService.random() < event.chance:

                # 3. Check for specific environmental requirements (e.g., mountains for volcanoes)
                if event.condition(world, stats):

                    # 4. Trigger the actual event effect
                    event.trigger(world, stats, config)