from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Shark(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        # Configuration spécifique si non présente dans le JSON
        self.perception_range = species_data.get('perception_range', 8)

    @staticmethod
    def try_spawn(x, y, world, config):
        """Le requin apparaît dans les eaux plus profondes que le poisson."""
        species_data = next((f for f in config['fauna'] if f['species'] == 'shark'), None)
        h = world['elev'][y][x]
        # Il préfère l'océan (-0.6) au rivage (0)
        if -0.8 < h < -0.3:
            if RandomService.random() < 0.2: # Rare
                return Shark(x, y, None, config, species_data)
        return None

    # --- Propriétés de milieu ---
    @property
    def is_aquatic(self):
        return True

    @property
    def is_flying(self):
        return False

    @property
    def danger_level(self):
        return 0.8  # Provoque une forte répulsion sur la Heatmap

    @property
    def food_value(self):
        return RandomService.randint(20, 30)