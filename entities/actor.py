from core.entities import Entity
from core.naming import NameGenerator

class Actor(Entity):
    """
    Base class for all autonomous agents in the simulation.
    Extends the basic Entity with cultural identity, naming logic, and life cycles.
    """
    def __init__(self, x, y, char, z_index, speed, culture, config):
        # Initialize the base physical entity
        # Speed and Z-Index are now passed up to the Entity parent
        super().__init__(x, y, char, z_index, speed)

        self.culture = culture  # Cultural dictionary (e.g., Empire, Nomad)
        self.config = config    # The complete global configuration template
        self.age = 0
        self.energy = 100
        self.is_dead = False

        # Procedural naming based on cultural linguistic data
        if culture is not None:
            self.name = NameGenerator.generate_person_name(culture)
        else:
            self.name = "Unknown"

    def update(self, world, stats):
        """
        Universal life loop for an agent.
        Increments age and triggers the perception-decision-action cycle.
        """
        if self.is_dead or self.is_expired:
            return

        self.age += 1

        # 1. PERCEPTION/ANALYSIS: Handled within think()
        # 2. DECISION: AI logic based on environmental signals
        self.think(world)

        # 3. ACTION: Physical movement or world interaction
        self.perform_action(world)

    def think(self, world):
        """Logic to be defined in child classes (e.g., Hunter, Wolf, Trader)."""
        pass

    def perform_action(self, world):
        """Action implementation to be defined in child classes."""
        pass