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
        """Cible tout ce qui est comestible et présent dans l'eau."""
        potential_targets = []

        for e in world['entities']:
            # 1. Filtres de base (Vivant, Pas moi, Pas un autre requin)
            if e.is_expired or e == self or e.species == self.species:
                continue

            # 2. Filtre de comestibilité (ignore les récifs ou débris)
            if not e.is_edible:
                continue

            # 3. Filtre de zone : La cible est-elle dans l'eau ?
            # Cela couvre les poissons ET les pêcheurs en barque
            if e.is_in_water(world):
                potential_targets.append(e)

        if potential_targets:
            # On choisit la proie la plus proche
            self.target = min(potential_targets, key=lambda t: math.dist(self.pos, t.pos))

    def _move_in_water(self, world, target_pos):
        """Se déplace vers la cible en restant impérativement dans l'eau."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] < 0: # Doit rester dans l'eau
                self.pos = (nx, ny)

    def _idle_water_move(self, world):
        """Erre dans les profondeurs."""
        dirs = [(0,1), (0,-1), (1,0), (-1,0)]
        dx, dy = RandomService.choice(dirs)
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] < -0.2:
                self.pos = (nx, ny)
    @property
    def danger_level(self):
        return 0.8  # Très effrayant
    @property
    def food_value(self):
        return RandomService.randint(20, 30)
    @property
    def is_aquatic(self):
        return True