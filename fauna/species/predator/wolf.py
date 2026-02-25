from fauna.species.predator.predator import Predator


class Wolf(Predator):
    """Le Loup : Endurance extrême (3 pas)."""

    def __init__(self, x, y, char="🐺"):
        self.x = x
        self.y = y
        self.char = char
        self.power = 0.25  # Puissance du loup 25% de chance de tuer le chasseur

    def move(self, width, height, elevation, structures):
        for _ in range(3):
            super().move(width, height, elevation, structures)
