from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Wolf(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # This line creates self.target by calling Animal.__init__
        super().__init__(x, y, culture, config, species_data)

        # Specific traits for the wolf
        self.perception_range = 6 # A wolf has a better scent than the base animal
        self.danger = 0.3

    @staticmethod
    def try_spawn(x, y, world, config):
        h = world['elev'][y][x]
        # The wolf prefers plains (elevation between 0.05 and 0.4)
        if 0.05 < h < 0.4:
            if RandomService.random() < 0.05: # 5% spawn chance if the terrain is suitable
                # Retrieve data from template.json
                species_data = next((f for f in config['fauna'] if f['species'] == 'wolf'), None)
                return Wolf(x, y, None, config, species_data)
        return None

    @property
    def danger_level(self):
        return 0.6  # Very frightening

    @property
    def food_value(self):
        return RandomService.randint(15, 20)