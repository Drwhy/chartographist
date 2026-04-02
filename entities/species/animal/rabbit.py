from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Rabbit(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        
        # Rabbits are small and move quickly
        self.perception_range = 4
        self.danger = 0.0  # Completely harmless
        
        # --- Rabbit Specific Stats ---
        self.energy = 80
        self.max_energy = 120
        self.hunger_threshold = 40
        self.repro_threshold = 100  # Very low threshold = rapid population growth

    @staticmethod
    def try_spawn(x, y, world, config):
        """Rabbits spawn in plains and meadows."""
        h = world['elev'][y][x]
        # Preference for low-altitude green plains
        if 0.1 < h < 0.5:
            if RandomService.random() < 0.1: # High spawn rate for the initial population
                species_data = next((f for f in config['fauna'] if f['species'] == 'rabbit'), None)
                if species_data:
                    return Rabbit(x, y, None, config, species_data)
        return None

    @property
    def diet(self):
        return "herbivore"

    @property
    def fear_sensitivity(self):
        return 8.0  # Extremely skittish

    @property
    def food_value(self):
        """Small meal for predators."""
        return RandomService.randint(4, 8)