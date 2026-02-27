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
        self.type = "animal"
        self.subtype = "eagle"
        self._x, self._y = x, y
        self.is_flying = True

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
            self._find_fish(world)

        # 2. Logique de mouvement et action
        if self.target:
            if self.pos == self.target.pos:
                self._fish_strike(world)
            else:
                self._fly_logic(world, self.target.pos)
        else:
            self._soar_around(world)

    def _find_fish(self, world):
        """L'aigle cherche le poisson le plus proche."""
        fishes = [e for e in world['entities'] if getattr(e, 'subtype', '') == 'fish']
        if fishes:
            self.target = min(fishes, key=lambda f: math.dist(self.pos, f.pos))

    def _fly_logic(self, world, target_pos):
        """Déplacement aérien avec interdiction de survol de l'océan profond."""
        tx, ty = target_pos
        dx = 1 if tx > self._x else -1 if tx < self._x else 0
        dy = 1 if ty > self._y else -1 if ty < self._y else 0

        nx, ny = self._x + dx, self._y + dy

        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            h_target = world['elev'][ny][nx]
            # Interdiction : L'aigle refuse de voler au-dessus de l'océan profond (ex: h < -0.6)
            if h_target > -0.6:
                self._x, self._y = nx, ny
                self.pos = (self._x, self._y)
            else:
                # Si c'est l'océan profond, il perd sa cible (trop loin/dangereux)
                self.target = None

    def _fish_strike(self, world):
        """Capture du poisson en piqué."""
        if self.target and not self.target.is_expired:
            self.target.is_expired = True
            self.target = None
            # Log discret car c'est un événement naturel fréquent
            GameLogger.log("🦅 Un aigle a plongé pour capturer un poisson.")

    def _soar_around(self, world):
        """Errance au-dessus des terres et des côtes uniquement."""
        dx, dy = RandomService.choice([(0,1), (0,-1), (1,0), (-1,0)])
        nx, ny = self._x + dx, self._y + dy

        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] > -0.6: # Reste hors du grand large
                self._x, self._y = nx, ny
                self.pos = (self._x, self._y)