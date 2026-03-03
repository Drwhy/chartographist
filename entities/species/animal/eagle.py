import math
from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService
from core.logger import GameLogger

@register_wild
class Eagle(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # C'est cette ligne qui crée self.target en appelant Animal.__init__
        super().__init__(x, y, culture, config, species_data)

    @staticmethod
    def try_spawn(x, y, world, config):
        """L'aigle apparaît sur les hauts sommets."""
        h = world['elev'][y][x]
        if h > 0.6:
            if RandomService.random() < 0.1:
                species_data = next((f for f in config['fauna'] if f['species'] == 'eagle'), None)
                return Eagle(x, y, None, config, species_data)
        return None

    def update(self, world, stats):
        if self.is_expired: return

        # 1. Recherche de cibles : Uniquement les poissons désormais
        if not self.target or self.target.is_expired:
            self._find_prey_in_water(world)

        # 2. Logique de mouvement et action
        if self.target:
            if self.pos == self.target.pos:
                self._fish_strike(world)
            else:
                self._fly_logic(world, self.target.pos)
        else:
            self._soar_around(world)

    def _find_prey_in_water(self, world):
        """L'aigle cible des proies aquatiques, mais évite les prédateurs dangereux."""

        potential_targets = []
        for e in world['entities']:
            if e.is_expired or e == self:
                continue

            # 1. Filtre de niche : Comestible et Aquatique
            if not (getattr(e, 'is_edible', False) and e.is_aquatic):
                continue

            # 2. SÉCURITÉ : L'aigle ne s'attaque pas à quelque chose de trop dangereux
            # Un poisson a un danger_level de 0, un requin a 0.8.
            # L'aigle (danger_level 0.5) n'attaquera que ce qui est < 0.5.
            if e.danger_level <= self.danger_level:
                continue

            potential_targets.append(e)

        if potential_targets:
            self.target = min(potential_targets, key=lambda p: math.dist(self.pos, p.pos))

    def _fly_logic(self, world, target_pos):
        """Déplacement aérien avec interdiction de survol de l'océan profond."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            h_target = world['elev'][ny][nx]
            # Interdiction : L'aigle refuse de voler au-dessus de l'océan profond (ex: h < -0.6)
            if h_target > -0.6:
                self.pos = (nx, ny)
            else:
                # Si c'est l'océan profond, il perd sa cible (trop loin/dangereux)
                self.target = None

    def _fish_strike(self, world):
        """Capture du poisson en piqué."""
        if self.target and not self.target.is_expired:
            self.target.is_expired = True
            self.target = None

    def _soar_around(self, world):
        """Errance au-dessus des terres et des côtes uniquement."""
        dx, dy = RandomService.choice([(0,1), (0,-1), (1,0), (-1,0)])
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] > -0.6: # Reste hors du grand large
                self.pos = (self.x + dx, self.y + dy)
    @property
    def danger_level(self):
        return 0.2
    @property
    def is_flying(self):
        return True