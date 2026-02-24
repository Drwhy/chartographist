from fauna.species.predator.predator import Predator


class Wolf(Predator):
    """Le Loup : Endurance extrême (3 pas)."""

    def move(self, width, height, elevation, structures):
        for _ in range(3):
            super().move(width, height, elevation, structures)
