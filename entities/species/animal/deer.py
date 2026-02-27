import math
from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService
from core.logger import GameLogger

@register_wild
class Deer(Animal):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config, species_data)
        self.type = "animal"
        self.subtype = "deer"
        self.is_flying = False
        self.is_aquatic = False
        self.fleeing = False # État de fuite
    @staticmethod
    def try_spawn(x, y, world, config):
        h = world['elev'][y][x]
        # La biche aime la plaine (élévation entre 0.05 et 0.4)
        if 0.05 < h < 0.4:
            if RandomService.random() < 0.1: # 5% de chance de spawn si le terrain est bon
                # Récupère les data du template.json
                species_data = next((f for f in config['fauna'] if f['species'] == 'deer'), None)
                return Deer(x, y, None, config, species_data)
        return None

    def update(self, world, stats):
        if self.is_expired: return

        # 1. Détection de danger (Loups, Ours, Humains)
        danger_source = self._check_for_danger(world)

        if danger_source:
            self._flee_from(world, danger_source.pos)
        else:
            self._graze_around(world)

    def _check_for_danger(self, world):
        """Cherche un prédateur ou un humain à proximité (rayon de 4)."""
        for e in world['entities']:
            if e.is_expired or e == self: continue

            # La biche a peur des loups, ours et humains (chasseurs/colons)
            if getattr(e, 'subtype', '') in ['wolf', 'bear', 'hunter', 'settler']:
                if math.dist(self.pos, e.pos) < 4:
                    return e
        return None

    def _flee_from(self, world, danger_pos):
        """Se déplace dans la direction opposée au danger."""
        dx = 1 if self._x > danger_pos[0] else -1 if self._x < danger_pos[0] else 0
        dy = 1 if self._y > danger_pos[1] else -1 if self._y < danger_pos[1] else 0

        nx, ny = self._x + dx, self._y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0: # Reste sur terre
                self._x, self._y = nx, ny
                self.pos = (self._x, self._y)

    def _graze_around(self, world):
        """Mouvement erratique lent (pâturage)."""
        if RandomService.random() < 0.3: # Ne bouge pas à chaque tour
            dx, dy = RandomService.choice([(0,1), (0,-1), (1,0), (-1,0)])
            nx, ny = self._x + dx, self._y + dy
            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                if world['elev'][ny][nx] >= 0:
                    self._x, self._y = nx, ny
                    self.pos = (self._x, self._y)