import random
from .aquatic import Aquatic

class Shark(Aquatic):
    """Le Requin : Rapide et préfère le grand large."""
    def move(self, width, height, elevation, structures):
        # Le requin est une torpille : 2 pas par tour
        for _ in range(2):
            dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
            nx, ny = self.x + dx, self.y + dy

            if 0 <= nx < width and 0 <= ny < height:
                # Le requin évite les côtes (eaux trop peu profondes)
                # Il préfère h < -0.15
                if elevation[ny][nx] < -0.15:
                    self.x, self.y = nx, ny