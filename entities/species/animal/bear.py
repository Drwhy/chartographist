from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Bear(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # This line creates self.target by calling Animal.__init__
        super().__init__(x, y, culture, config, species_data)

        # Specific traits for the bear
        self.perception_range = 3  # A bear has better scent tracking than the base animal
        self.danger = 0.8

    @staticmethod
    def try_spawn(x, y, world, config):
        """The bear appears at high altitudes."""
        h = world['elev'][y][x]
        # Check for mountain/highland elevation and spawn chance
        if 0.5 < h < 0.85 and RandomService.random() < 0.05:
            species_data = next((f for f in config['fauna'] if f['species'] == 'bear'), None)
            if species_data:
                return Bear(x, y, None, config, species_data)
        return None

    @property
    def danger_level(self):
        return 0.8  # Very frightening

    @property
    def food_value(self):
        return RandomService.randint(15, 30)