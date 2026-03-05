import math
from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService
from core.logger import GameLogger

@register_wild
class Eagle(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # C'est cette ligne qui crée self.target en appelant Animal.__init__
        super().__init__(x, y, culture, config, species_data)

    @staticmethod
    def try_spawn(x, y, world, config):
        """L'aigle apparaît sur les hauts sommets."""
        h = world['elev'][y][x]
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
        return True