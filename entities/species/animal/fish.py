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
        Vérifie si les conditions sont réunies pour faire apparaître un poisson.
        Habitat : Eau peu profonde uniquement (entre le rivage et les abysses).
        """
        h = world['elev'][y][x]
        species_data = next((f for f in config['fauna'] if f['species'] == 'fish'), None)
        # Seuil de l'eau : h < 0
        # Seuil des abysses : h > -0.4 (pour rester près des côtes)
        if -0.4 < h < 0:
            # On peut ajouter une probabilité de réussite pour ne pas saturer l'eau
            if RandomService.random() < 0.30:
                return Fish(x, y, None, config, species_data)

        return None

    @property
    def food_value(self):
        return RandomService.randint(5, 10)
    @property
    def is_aquatic(self):
        return True
    @property
    def diet(self):
        return "herbivore"
    @property
    def fear_sensitivity(self):
        return 5.0