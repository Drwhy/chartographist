import math
from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService
from core.logger import GameLogger

@register_wild
class Eagle(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # This line creates self.target by calling Animal.__init__
        super().__init__(x, y, culture, config, species_data)

    @staticmethod
    def try_spawn(x, y, world, config):
        """The eagle appears on high mountain peaks."""
        h = world['elev'][y][x]
        # Spawns only at high elevation (h > 0.6)
        if h > 0.6:
            if RandomService.random() < 0.1:
                species_data = next((f for f in config['fauna'] if f['species'] == 'eagle'), None)
                return Eagle(x, y, None, config, species_data)
        return None

    @property
    def danger_level(self):
        return 0.2

    @property
    def is_flying(self):
        """Allows the entity to ignore terrain elevation and target specific prey."""
        return True