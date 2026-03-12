from core.entities import Entity, Z_HUMAN
from core.naming import NameGenerator

class Human(Entity):
    def __init__(self, x, y, culture, config, speed):
        # Initialize the base entity
        super().__init__(x, y, "?", Z_HUMAN, speed)
        self.culture = culture # Cultural dictionary (e.g., Empire)
        self.config = config   # Full template.json
        self.age = 0
        self.energy = 100
        self.is_dead = False
        self.species = 'human'

        if culture is not None:
            self.name = NameGenerator.generate_person_name(culture)

        self.is_infected = False
        self.infection_turns = 0

    def update(self, world, stats):
        """Universal agent life loop."""
        if self.is_dead or self.is_expired:
            return

        self.age += 1
        # 1. ANALYSIS (Perception)
        # 2. DECISION (AI) -> self.think(world)
        # 3. ACTION (Movement/Interaction) -> self.perform_action(world)

        self.think(world)
        self.perform_action(world)

    def think(self, world):
        """To be defined in child classes (Hunter, etc.)"""
        pass

    def perform_action(self, world):
        """To be defined in child classes"""
        pass

    @property
    def is_edible(self):
        return True

    @property
    def danger_level(self):
        return 0.2  # Not very frightening

    def _get_accessible_neighbors(self, world):
        """Returns adjacent walkable tiles (no water)."""
        neighbors = []
        for dx, dy in [(0,0), (0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                if world['elev'][ny][nx] >= 0: # Terrestrial biome check
                    neighbors.append((nx, ny))
        return neighbors