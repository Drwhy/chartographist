import math
from entities.actor import Actor
from core.logger import GameLogger
from entities.constructs.village import Village
from history.history_engine import connect_with_road
from entities.registry import register_civ
from core.random_service import RandomService

@register_civ
class Settler(Actor):
    def __init__(self, x, y, culture, config, home_city=None):
        # Respect de l'ordre strict des paramètres de Actor
        super().__init__(x, y, culture, config)

        self.type = "actor"
        self.subtype = "settler"
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
            GameLogger.log(f"💀 Un groupe de colons s'est perdu dans les terres sauvages.")

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

        new_x, new_y = self.x + dx, self.y + dy

        # Collision simple : on évite l'eau profonde (h < 0)
        if 0 <= new_x < world['width'] and 0 <= new_y < world['height']:
            if world['elev'][new_y][new_x] >= 0:
                # Utilisation des membres privés pour éviter le bug de "Property no setter"
                self._x, self._y = new_x, new_y
                self.pos = (self._x, self._y)
            else:
                # Si on touche l'eau, on change de direction
                self.target_pos = self._choose_exploration_direction()

    def _is_ideal_spot(self, world):
        """
        Détermine si la case actuelle est valide pour un village.
        Tolérance maximale : Tout sauf Eau, Peaks (>0.85) et Volcans (>0.90).
        """
        h = world['elev'][self.y][self.x]

        # REGLÈS D'EXCLUSION STRICTES
        if h < 0: return False      # Eau
        if h > 0.85: return False   # Peaks et Volcans (selon tes seuils de rendu)

        # Vérification si une entité occupe déjà la place
        for e in world['entities']:
            if e.pos == self.pos and e != self:
                return False
            if getattr(e, 'type', '') == 'construct':
                    dist = math.dist(self.pos, e.pos)
                    if dist < 8: return False

        # PROBABILITÉ DE FONDATION
        # Bonus si près d'une rivière, sinon chance standard
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
            GameLogger.log(f"🏘️  Nouveau village fondé ! Une route le relie à en ({self.x}, {self.y}).")
        else:
            GameLogger.log(f"🏘️  Un village indépendant a été fondé en ({self.x}, {self.y}).")

        self.is_expired = True