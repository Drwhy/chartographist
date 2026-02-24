import random
from fauna.animal import Animal

class Aquatic(Animal):
    def move(self, width, height, elevation, structures):
        dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < width and 0 <= ny < height:
            # Ne se déplace que dans l'eau
            if elevation[ny][nx] < 0:
                self.x, self.y = nx, ny