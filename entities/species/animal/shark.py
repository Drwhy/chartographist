import math
from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService
from core.logger import GameLogger

@register_wild
class Shark(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # C'est cette ligne qui crée self.target en appelant Animal.__init__
        super().__init__(x, y, culture, config, species_data)
        # Tu peux ensuite ajouter des spécificités au loup
        self.perception_range = 3
        self.danger = 0.7
        self.type = 'animal'
        self.subtype = 'shark'
        self.is_aquatic = True

    @staticmethod
    def try_spawn(x, y, world, config):
        """Le requin apparaît dans les eaux plus profondes que le poisson."""
        species_data = next((f for f in config['fauna'] if f['species'] == 'shark'), None)
        h = world['elev'][y][x]
        # Il préfère l'océan (-0.6) au rivage (0)
        if -0.8 < h < -0.3:
            if RandomService.random() < 0.05: # Rare
                return Shark(x, y, None, config, species_data)
        return None

    def update(self, world, stats):
        if self.is_expired: return

        # 1. Recherche de proie : Poisson ou Pêcheur en barque
        if not self.target or self.target.is_expired:
            self._find_aquatic_target(world)

        # 2. Déplacement et Attaque
        if self.target:
            if self.pos == self.target.pos:
                self._attack_target(world)
            else:
                self._move_in_water(world, self.target.pos)
        else:
            self._idle_water_move(world)

    def _find_aquatic_target(self, world):
        """Cible les poissons et les pêcheurs qui sont sur l'eau."""
        potential_targets = []
        for e in world['entities']:
            if e.is_expired or e == self: continue

            # Cible les poissons
            if getattr(e, 'subtype', '') == 'fish':
                potential_targets.append(e)

            # Cible les pêcheurs UNIQUEMENT s'ils sont en barque (h < 0)
            elif getattr(e, 'subtype', '') == 'fisherman':
                if world['elev'][e.y][e.x] < 0:
                    potential_targets.append(e)

        if potential_targets:
            self.target = min(potential_targets, key=lambda t: math.dist(self.pos, t.pos))

    def _move_in_water(self, world, target_pos):
        """Se déplace vers la cible en restant impérativement dans l'eau."""
        tx, ty = target_pos
        dx = 1 if tx > self._x else -1 if tx < self._x else 0
        dy = 1 if ty > self._y else -1 if ty < self._y else 0

        nx, ny = self._x + dx, self._y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] < 0: # Doit rester dans l'eau
                self._x, self._y = nx, ny
                self.pos = (self._x, self._y)

    def _idle_water_move(self, world):
        """Erre dans les profondeurs."""
        dirs = [(0,1), (0,-1), (1,0), (-1,0)]
        dx, dy = RandomService.choice(dirs)
        nx, ny = self._x + dx, self._y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] < -0.2:
                self._x, self._y = nx, ny
                self.pos = (self._x, self._y)