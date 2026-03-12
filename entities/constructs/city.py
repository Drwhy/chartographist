from .base import Construct
from entities.registry import register_structure, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.constructs.ruins import Ruins
import math

@register_structure
class City(Construct):
    """
    The primary civilization hub.
    Handles population growth, economic activity (traders),
    and territorial expansion (settlers).
    """
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)

        # Identity and Visuals
        self.char = culture.get("city", "🏛️ ")

        # Economy and Population
        self.population = RandomService.randint(500, 1000)
        self.growth_rate = config.get("city_growth", 1.005)

        # Expansion Mechanics
        self.settler_threshold = 5000  # Population required to dispatch settlers
        self.settler_cost = 1500       # Population "consumed" by sending a group
        self.settler_cooldown = 0
        self.cooldown_duration = 100

        # Status Effects
        self.infected_count = 0
        self.is_infected = False
        self.active_trader = None

    def update(self, world, stats):
        """
        Processes population growth and triggers expansion/trade events.
        Uses a logistic growth model to simulate resource saturation.
        """
        # Theoretical carrying capacity for a single tile
        max_pop = 10000

        # Saturation Factor: Growth slows down as population approaches max_pop
        saturation = max(0, (max_pop - self.population) / max_pop)

        # Environmental Bonus: Settlements near rivers grow faster
        near_water = world['riv'][self.y][self.x] > 0
        base_growth = 0.01 if near_water else 0.005

        # Update population with logistic damping
        self.population += int(self.population * base_growth * saturation)

        # Manage expansion cooldown
        if self.settler_cooldown > 0:
            self.settler_cooldown -= 1

        # --- EXPANSION LOGIC ---
        if self.population >= self.settler_threshold and self.settler_cooldown == 0:
            # Check if the world has enough room for a new settlement
            if self._can_world_support_new_settler(world):
                if self._spawn_settler(world):
                    # Success: Deduct population cost and trigger cooldown
                    self.population -= self.settler_cost
                    self.settler_cooldown = self.cooldown_duration
            else:
                # World is saturated; put expansion logic on "peace cooldown"
                self.settler_cooldown = 100

        # --- TRADE SPAWN LOGIC ---
        # Condition: Sufficient population and 1% chance per tick
        if self.active_trader is None or self.active_trader.is_expired:
            if self.population > 1000 and RandomService.random() < 0.01:
                # Find other valid, non-ruined settlements for trade
                other_cities = [
                    e for e in world['entities']
                    if type(e) in STRUCTURE_TYPES and e != self
                    and not e.is_expired and not isinstance(e, Ruins)
                ]

                if len(other_cities) > 0:
                    self._spawn_trader(world)

        # Process cultural drift and stability (Inherited from Construct)
        self._check_cultural_drift(world)

    def _spawn_settler(self, world):
        """Creates a settler unit to found a new village linked back to this city."""
        from entities.species.human.settler import Settler

        new_settler = Settler(self.x, self.y, self.culture, self.config, home_city=self)
        world['entities'].add(new_settler)

        GameLogger.log(Translator.translate("entities.settler_spawn", name=self.name))
        return True

    def take_damage(self, amount):
        """Reduces population. If it hits zero, the city collapses into ruins."""
        self.population -= amount
        if self.population <= 0:
            self.is_expired = True
            GameLogger.log(Translator.translate("entities.ruins_desc", name=self.name))

    def _spawn_trader(self, world):
        """Generates a unique merchant for this city if one isn't already active."""
        from entities.species.human.trader import Trader

        # Verify no active traders belong to this specific city
        active_my_traders = [
            e for e in world['entities']
            if isinstance(e, Trader)
            and getattr(e, 'home_city', None) == self
            and not e.is_expired
        ]

        if len(active_my_traders) >= 1:
            return False

        new_trader = Trader(self.x, self.y, self.culture, self.config, self)
        world['entities'].add(new_trader)
        self.active_trader = new_trader

        GameLogger.log(
            Translator.translate("events.trader_spawn", city_name=self.name)
        )
        return True

    def _can_world_support_new_settler(self, world):
        """
        Global check to prevent world saturation and over-expansion.
        Ensures entities don't choke the engine or empty the map.
        """
        from entities.registry import STRUCTURE_TYPES
        from entities.species.human.settler import Settler

        living_structures = [
            e for e in world['entities']
            if type(e) in STRUCTURE_TYPES and not e.is_expired
        ]

        # Calculate Carrying Capacity: Approx. 1 city per 15x15 block
        total_area = world['width'] * world['height']
        max_cities = total_area // 225

        # Halt expansion if world is at 90% capacity
        if len(living_structures) >= max_cities * 0.9:
            return False

        # Global limit: Only 3 settlers active simultaneously to preserve performance
        active_settlers = [e for e in world['entities'] if isinstance(e, Settler) and not e.is_expired]
        if len(active_settlers) > 3:
            return False

        return True