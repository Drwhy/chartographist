import random
from .base import Animal
from entities.registry import register_wild

@register_wild
class Bear(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # C'est cette ligne qui crée self.target en appelant Animal.__init__
        super().__init__(x, y, culture, config, species_data)

        # Tu peux ensuite ajouter des spécificités au loup
        self.perception_range = 3 # Un loup a un meilleur flair que l'animal de base
    @staticmethod
    def try_spawn(x, y, world, config):
        """L'ours apparaît en haute altitude."""
        h = world['elev'][y][x]
        if 0.5 < h < 0.85 and random.random() < 0.05:
            species_data = next((f for f in config['fauna'] if f['species'] == 'bear'), None)
            if species_data:
                return Bear(x, y, None, config, species_data)
        return None

    def think(self, world):
        # Si la cible est morte ou partie, on en cherche une nouvelle
        if self.target and self.target.is_expired:
            self.target = None

        if not self.target:
            self._find_target(world)

    def perform_action(self, world):
        if self.target:
            self._approach_target(world)
        else:
            # S'il n'y a rien à manger, on erre
            self._wander(world, valid_elev_range=(0.05, 0.5))