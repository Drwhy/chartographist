from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Fish(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        self.perception_range = 3
        self.danger = 0.0
        self.type = 'fish'
        self.subtype = 'fish'
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
            if RandomService.random() < 0.15:
                return Fish(x, y, None, config, species_data)

        return None

    def _move_logic(self, world):
        """Déplacement aléatoire restreint à son biome aquatique."""
        # On choisit une direction au hasard (y compris l'immobilité)
        dx, dy = RandomService.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = self._x + dx, self._y + dy

        # Vérification des limites du monde
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            h_next = world['elev'][ny][nx]

            # Le poisson refuse de sortir de l'eau ou de descendre trop profond
            if -0.4 < h_next < 0:
                self._x, self._y = nx, ny
                self.pos = (self._x, self._y)

    def update(self, world, stats):
        """Le poisson ne chasse pas, il se contente de nager."""
        if self.is_expired:
            return

        self._move_logic(world)