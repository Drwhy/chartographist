import random

class Animal:
    def __init__(self, x, y, char):
        self.x = x
        self.y = y
        self.char = char

    @property
    def pos(self):
        return (self.x, self.y)

    def move(self, width, height, elevation, structures):
        dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < width and 0 <= ny < height:
            if 0 < elevation[ny][nx] < 0.8 and (nx, ny) not in structures:
                self.x, self.y = nx, ny
