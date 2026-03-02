from .base import Construct
from entities.registry import register_structure
from core.logger import GameLogger
from entities.species.human.hunter import Hunter
from entities.species.human.fisherman import Fisherman
from core.random_service import RandomService

@register_structure
class Village(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.population = RandomService.randint(50, 150)
        self.city_threshold = 1000 # Population requise pour devenir une ville
        self.char = culture.get("village", "🏛️ ")
        self.active_worker = None
        # Logique de gestion du chasseur
        self.check_interval = 20   # Fréquence de vérification du chasseur
        self.timer = 0

    def update(self, world, stats):
        """Mise à jour cyclique du village."""
        # 1. Croissance démographique (1% par tour)
        self.population = int(self.population * 1.01)

        # 2. Gestion du chasseur unique
        self.timer += 1
        if self.timer >= self.check_interval:
            self._manage_workforce(world)
            self.timer = 0

        # 3. TRANSFORMATION EN CITÉ
        if self.population >= self.city_threshold:
            self._evolve_to_city(world)

    def _manage_workforce(self, world):
            """Vérifie l'état du travailleur via la référence interne."""

            # Si on a une référence mais que l'entité est expirée (morte/supprimée)
            if self.active_worker and self.active_worker.is_expired:
                self.active_worker = None

            # Si pas de travailleur actif, on en crée un
            if self.active_worker is None and self.population > 60:
                if self._is_coastal(world):
                    self._spawn_fisherman(world)
                else:
                    self._spawn_hunter(world)

    def _is_coastal(self, world):
        for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
            ny, nx = self.y + dy, self.x + dx
            if 0 <= ny < world['height'] and 0 <= nx < world['width']:
                if world['elev'][ny][nx] < 0:
                    return True
        return False

    def _spawn_hunter(self, world):
        # On stocke l'instance directement dans self.active_worker
        self.active_worker = Hunter(self.x, self.y, self.culture, self.config, self.pos, self)
        world['entities'].add(self.active_worker)

    def _spawn_fisherman(self, world):
        self.active_worker = Fisherman(self.x, self.y, self.culture, self.config, self.pos, self)
        world['entities'].add(self.active_worker)

    def _evolve_to_city(self, world):
        from entities.constructs.city import City
        # Nettoyage immédiat via la référence
        if self.active_worker:
            self.active_worker.is_expired = True

        new_city = City(self.x, self.y, self.culture, self.config)
        new_city.population = self.population
        world['entities'].add(new_city)
        self.is_expired = True