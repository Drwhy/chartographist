import random
from .flyer import Flyer

class Eagle(Flyer):
    """L'Aigle : Rapide et survole les plus hauts sommets."""
    def move(self, width, height, elevation, structures):
        # L'aigle plane sur de grandes distances (pas de 3)
        for _ in range(3):
            super().move(width, height, elevation, structures)