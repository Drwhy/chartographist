class BaseEvent:
    """
    Abstract base class for all global simulation events.
    Defines the standard interface for triggers, conditions, and maintenance ticks.
    """
    name = "Base Event"
    chance = 0.001  # Probability of triggering per simulation tick

    @staticmethod
    def condition(world, stats):
        """
        Validates if the environmental conditions allow this event to occur.
        Returns:
            bool: True if the event can trigger, False otherwise.
        """
        return True

    @staticmethod
    def trigger(world, stats, config):
        """
        Executes the main logic of the event (e.g., spawning fires, starting plagues).
        """
        pass

    def tick(self, world, stats):
        """
        Optional: Logic executed every turn regardless of whether the event triggers.
        Useful for lingering effects like heat dissipation or disease progression.
        """
        pass