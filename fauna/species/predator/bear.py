import random
from .predator import Predator


class Bear(Predator):
    """
    L'Ours : Un prédateur puissant mais plus lent que le loup.
    Sa force réside dans sa capacité à grimper là où les autres ne vont pas.
    """

    def move(self, width, height, elevation, structures):
        """
        Déplacement unique : l'ours peut s'aventurer sur des reliefs
        très élevés (hautes montagnes).
        """
        # L'ours ne fait qu'un pas, contrairement au prédateur de base (2 pas)
        # ou au loup (3 pas), pour simuler sa lourdeur.
        dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = self.x + dx, self.y + dy

        if 0 <= nx < width and 0 <= ny < height:
            # L'ours peut atteindre une élévation de 0.95 (pics enneigés)
            # alors que la plupart des animaux s'arrêtent à 0.8.
            if 0 < elevation[ny][nx] < 0.95 and (nx, ny) not in structures:
                self.x, self.y = nx, ny
