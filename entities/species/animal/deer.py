import math
from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService
from core.logger import GameLogger

@register_wild
class Deer(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        self.fleeing = False # Fleeing state

    @staticmethod
    def try_spawn(x, y, world, config):
        h = world['elev'][y][x]
        # The deer prefers plains (elevation between 0.05 and 0.4)
        if 0.05 < h < 0.4:
            if RandomService.random() < 0.1: # 10% chance to spawn if the terrain is suitable
                # Retrieve data from template.json
                species_data = next((f for f in config['fauna'] if f['species'] == 'deer'), None)
                return Deer(x, y, None, config, species_data)
        return None

    @property
    def diet(self):
        return "herbivore"

    @property
    def fear_sensitivity(self):
        return 5.0

    @property
    def danger_level(self):
        return 0.1

    @property
    def food_value(self):
        return RandomService.randint(5, 12)