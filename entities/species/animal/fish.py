from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Fish(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        self.perception_range = 3
        self.danger = 0.0

    @staticmethod
    def try_spawn(x, y, world, config):
        """
        Checks if conditions are met to spawn a fish.
        Habitat: Shallow water only (between the shore and the abyss).
        """
        h = world['elev'][y][x]
        species_data = next((f for f in config['fauna'] if f['species'] == 'fish'), None)

        # Water threshold: h < 0
        # Abyss threshold: h > -0.5 (to stay near the coasts)
        if -0.6 < h < 0:
            # Success probability to prevent water over-saturation
            if RandomService.random() < 0.40:
                return Fish(x, y, None, config, species_data)

        return None

    @property
    def food_value(self):
        return RandomService.randint(5, 10)

    @property
    def is_aquatic(self):
        """Restricts movement to water tiles."""
        return True

    @property
    def diet(self):
        return "herbivore"

    @property
    def fear_sensitivity(self):
        return 5.0