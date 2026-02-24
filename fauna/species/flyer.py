import random
from fauna.animal import Animal

class Flyer(Animal):
    def move(self, width, height, elevation, structures):
        # L'oiseau ignore les obstacles et vole plus loin
        dx, dy = random.randint(-2, 2), random.randint(-2, 2)
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < width and 0 <= ny < height:
            self.x, self.y = nx, ny