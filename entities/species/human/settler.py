import math
from .base import Human
from core.logger import GameLogger
from entities.constructs.village import Village
from history.history_engine import connect_with_road
from entities.registry import register_civ
from core.random_service import RandomService
from entities.registry import STRUCTURE_TYPES
from core.translator import Translator

@register_civ
class Settler(Human):
    def __init__(self, x, y, culture, config, home_city=None):
        # Respect de l'ordre strict des paramètres de Actor
        super().__init__(x, y, culture, config)
        self.char = culture.get("settler_emoji", "🚶")
        self.home_city = home_city # La ville d'origine pour la route
        # Logique de mouvement
        self.target_pos = self._choose_exploration_direction()
        self.distance_traveled = 0
        self.min_distance_from_home = 20 # Distance mini pour fonder un village
        self.max_travel_time = 100       # Un peu plus de temps pour trouver un spot

    def update(self, world, stats):
        """Logique de déplacement et de fondation."""
        if self.is_expired:
            return

        # 1. On avance vers la terre promise
        self._move_towards_target(world)
        self.distance_traveled += 1

        # 2. On vérifie si le terrain est propice à la fondation
        if self.distance_traveled > self.min_distance_from_home:
            if self._is_ideal_spot(world):
                self._found_village(world)
                return

        # 3. Si trop vieux ou perdu, le colon disparaît
        if self.distance_traveled > self.max_travel_time:
            self.is_expired = True
            GameLogger.log(Translator.translate("events.settler_lost", settler_city_name=self.home_city.name))

    def _choose_exploration_direction(self):
        """Choisit un point lointain au hasard pour migrer."""
        angle = RandomService.uniform(0, 2 * math.pi)
        dist = RandomService.randint(15, 30)
        tx = int(self.x + math.cos(angle) * dist)
        ty = int(self.y + math.sin(angle) * dist)
        return (tx, ty)

    def _move_towards_target(self, world):
        """Marche simple vers la destination."""
        tx, ty = self.target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy
        # Collision simple : on évite l'eau profonde (h < 0)
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0:
                # Utilisation des membres privés pour éviter le bug de "Property no setter"
                self.pos = (nx, ny)
            else:
                # Si on touche l'eau, on change de direction
                self.target_pos = self._choose_exploration_direction()

    def _is_ideal_spot(self, world):
        """
        Détermine si la case est valide pour fonder un village.
        Critères : Pas d'eau, pas de sommets, pas de voisinage urbain trop proche.
        """
        h = world['elev'][self.y][self.x]

        # 1. RÈGLES GÉOGRAPHIQUES (0 = Plage, 0.85 = Haute montagne)
        if not (0 <= h <= 0.85):
            return False

        # 2. VÉRIFICATION DU VOISINAGE (Registry & Proximité)
        for e in world['entities']:
            if e.is_expired: continue

            # Empêche de spawner deux entités exactement au même endroit
            if e.pos == self.pos and e != self:
                return False

            # RÈGLE DE DISTANCE : Pas d'autre structure dans un rayon de 8
            if type(e) in STRUCTURE_TYPES:
                if math.dist(self.pos, e.pos) < 8:
                    return False

        # 3. PROBABILITÉ DE FONDATION
        # Une rivière (riv > 0) rend le terrain beaucoup plus attractif
        is_near_river = world['riv'][self.y][self.x] > 0
        chance = 0.25 if is_near_river else 0.08

        return RandomService.random() < chance

    def _found_village(self, world):
        """Crée le village et trace la route vers la cité mère."""
        new_village = Village(self.x, self.y, self.culture, self.config)
        world['entities'].add(new_village)

        if self.home_city:
            connect_with_road(
                world['road'],
                self.home_city.pos,
                self.pos,
                world['width'],
                world['height']
            )
            GameLogger.log(Translator.translate("events.settler_found_village", new_village_char=new_village.char, new_village_name=new_village.name, home_city_name=self.home_city.name))
        else:
            GameLogger.log(Translator.translate("events.settler_found_village_independant", new_village_char=new_village.char, new_village_name=new_village.name))

        self.is_expired = True