import random
from fauna.species.animal import Animal

class Aquatic(Animal):
    """Classe de base pour les animaux marins."""
    def move(self, width, height, elevation, structures):
        # Mouvement fluide dans l'eau
        dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = self.x + dx, self.y + dy

        if 0 <= nx < width and 0 <= ny < height:
            # Ne peut se déplacer QUE dans l'eau (h < 0)
            if elevation[ny][nx] < 0:
                self.x, self.y = nx, ny