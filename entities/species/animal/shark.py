from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Shark(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        # Specific configuration if not present in the JSON
        self.perception_range = species_data.get('perception_range', 8)

    @staticmethod
    def try_spawn(x, y, world, config):
        """The shark appears in deeper waters than the fish."""
        species_data = next((f for f in config['fauna'] if f['species'] == 'shark'), None)
        h = world['elev'][y][x]
        # It prefers the ocean (-0.6) over the shore (0)
        if -0.8 < h < -0.3:
            if RandomService.random() < 0.2: # Rare spawn chance
                return Shark(x, y, None, config, species_data)
        return None

    # --- Environmental Properties ---
    @property
    def is_aquatic(self):
        """Restricts movement strictly to deep water tiles."""
        return True

    @property
    def is_flying(self):
        return False

    @property
    def danger_level(self):
        """Causes strong repulsion on the Heatmap (fear factor)."""
        return 0.8

    @property
    def food_value(self):
        return RandomService.randint(20, 30)