from .base import Construct
from entities.registry import register_structure
from core.logger import GameLogger
from entities.species.human.hunter import Hunter
from entities.species.human.fisherman import Fisherman
from core.random_service import RandomService

@register_structure
class Village(Construct):
    """
    A small settlement that serves as the foundation for expansion.
    Villages can spawn specialized workers (Hunters/Fishermen) and
    evolve into Cities once a population threshold is met.
    """
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.population = RandomService.randint(50, 150)
        self.city_threshold = 1000  # Population required to promote to City
        self.char = culture.get("village", "🏡")
        self.active_worker = None

        # Worker management logic
        self.check_interval = 20    # Tick frequency for workforce validation
        self.timer = 0

    def update(self, world, stats):
        """Cyclic village update loop."""
        # 1. Demographic growth (Fixed 1% per tick)
        self.population = int(self.population * 1.01)

        # 2. Workforce management (Unique specialized unit)
        self.timer += 1
        if self.timer >= self.check_interval:
            self._manage_workforce(world)
            self.timer = 0

        # 3. EVOLUTION TO CITY
        if self.population >= self.city_threshold:
            self._evolve_to_city(world)

        # Inherited cultural check
        self._check_cultural_drift(world)

    def _manage_workforce(self, world):
        """Validates the state of the specialized worker and spawns a new one if necessary."""

        # If the reference exists but the entity is marked as expired (dead/removed)
        if self.active_worker and self.active_worker.is_expired:
            self.active_worker = None

        # If no active worker exists and population is sufficient
        if self.active_worker is None and self.population > 60:
            if self._is_coastal(world):
                self._spawn_fisherman(world)
            else:
                self._spawn_hunter(world)

    def _is_coastal(self, world):
        """Checks cardinal neighbors for water (negative elevation)."""
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = self.y + dy, self.x + dx
            if 0 <= ny < world['height'] and 0 <= nx < world['width']:
                if world['elev'][ny][nx] < 0:
                    return True
        return False

    def _spawn_hunter(self, world):
        """Spawns a Hunter and stores a direct reference."""
        self.active_worker = Hunter(self.x, self.y, self.culture, self.config, self.pos, self)
        world['entities'].add(self.active_worker)

    def _spawn_fisherman(self, world):
        """Spawns a Fisherman and stores a direct reference."""
        self.active_worker = Fisherman(self.x, self.y, self.culture, self.config, self.pos, self)
        world['entities'].add(self.active_worker)

    def _evolve_to_city(self, world):
        """Promotes the Village to a City, clearing workers and current instance."""
        from entities.constructs.city import City

        # Expire current specialized worker upon promotion
        if self.active_worker:
            self.active_worker.is_expired = True

        new_city = City(self.x, self.y, self.culture, self.config)
        new_city.population = self.population
        world['entities'].add(new_city)

        # Mark this village for removal from the entity manager
        self.is_expired = True