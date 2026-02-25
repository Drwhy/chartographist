import random
from fauna.species.animal import Animal


class Flyer(Animal):
    """Classe de base pour les animaux volants avec contrainte côtière."""
    def move(self, width, height, elevation, structures):
        # Les flyers sont agiles : ils choisissent une direction parmi 8
        moves = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1), (0, 0)]
        dx, dy = random.choice(moves)

        # Un flyer peut faire des bonds de 2 cases
        nx, ny = self.x + (dx * 2), self.y + (dy * 2)

        if 0 <= nx < width and 0 <= ny < height:
            h_target = elevation[ny][nx]

            # --- CONTRAINTE CÔTIÈRE ---
            # h > -0.15 correspond généralement à la terre + les eaux peu profondes (shore)
            # On autorise le survol tant qu'on n'est pas en "Deep Ocean"
            if h_target > -0.15:
                self.x, self.y = nx, ny
            else:
                # Si c'est trop profond, l'oiseau essaie de rester sur place
                # ou de trouver une autre direction au prochain tour
                pass