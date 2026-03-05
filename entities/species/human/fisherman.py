import math
from .base import Human
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

@register_civ
class Fisherman(Human):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        # Initialisation via Actor (gère culture et config)
        super().__init__(x, y, culture, config, 1)
        # Attributs d'identité
        self.home_pos = home_pos
        self.home_city = home_city
        # Visuels (Emojis)
        self.land_char = culture.get("fisherman_emoji", "🎣")
        self.boat_char = culture.get("boat_emoji", "🛶")
        self.char = self.land_char
        # Logique métier
        self.target = None
        self.fishing_cooldown = 0

    def update(self, world, stats):
            if self.is_expired:
                return

            # 1. Gestion du repos après pêche
            if self.fishing_cooldown > 0:
                self.fishing_cooldown -= 1
                return

            # 2. Mise à jour de l'apparence selon le terrain
            self._update_status(world)

            # 3. Intelligence de recherche
            if not self.target or self.target.is_expired:
                self._find_prey_in_water(world)

            # 4. Action ou Déplacement
            if self.target:
                # --- MODIFICATION ICI : Portée de pêche augmentée à 2 cases ---
                dist_to_fish = math.dist(self.pos, self.target.pos)

                if dist_to_fish <= 2.1: # 2.1 pour couvrir les diagonales de 2 cases
                    self._fish_action(world)
                else:
                    self._move_logic(world, self.target.pos)
            else:
                self._idle_movement(world)

    def _fish_action(self, world):
        """Capture le poisson à distance et déclenche le cooldown."""
        if self.target and not self.target.is_expired:
            self.target.is_expired = True
            self.fishing_cooldown = 10
            self.target = None

            # --- MODIFICATION DU LOG ---
            GameLogger.log(
                Translator.translate(
                    "events.fishing_success",
                    fisherman_char=self.char,
                    fisherman_name=self.name,
                    fisherman_city=self.home_city.name
                )
            )
            # Optionnel : Bonus de population pour le village d'origine
            # On cherche l'entité à la position home_pos
            for e in world['entities']:
                if e.pos == self.home_pos:
                    if hasattr(e, 'population'):
                        e.population += RandomService.randint(5, 12)
                    break

    def _update_status(self, world):
        """Détermine si le pêcheur est à pied ou en barque."""
        h = world['elev'][self.y][self.x]
        if h < 0:
            self.char = self.boat_char
        else:
            self.char = self.land_char

    def _find_prey_in_water(self, world):
        """L'aigle cible n'importe quelle entité comestible aquatique."""

        # On cherche les entités qui sont :
        # 1. Comestibles
        # 2. Aquatiques
        # 3. Non expirées
        aquatic_preys = [
            e for e in world['entities']
            if getattr(e, 'is_edible', False)
            and e.is_aquatic
            and not e.is_expired
        ]

        if aquatic_preys:
            # L'aigle a une vue perçante, il prend la plus proche
            self.target = min(aquatic_preys, key=lambda p: math.dist(self.pos, p.pos))
        else:
            self.target = None

    def _move_logic(self, world, target_pos):
        """Avance vers la cible (Terre ou Eau peu profonde)."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            h = world['elev'][ny][nx]
            # ACCÈS : Terre ferme OU Eau peu profonde (>-0.4)
            if h > -0.4:
                self.pos = (nx, ny)
            # Si c'est des abysses (<-0.4), il ne bouge pas (sécurité)

    def _idle_movement(self, world):
        """Flânerie côtière en attendant que le poisson morde."""
        dx, dy = RandomService.choice([(0,1), (0,-1), (1,0), (-1,0), (0,0)])
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] > -0.4:
                self.pos = (nx, ny)

    @property
    def danger_level(self):
        return 0.3  # Très effrayant