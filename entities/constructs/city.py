# entities/constructs/city.py
from .base import Construct
from entities.registry import register_structure, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.constructs.ruins import Ruins
from entities.species.human.citizen import Citizen
from entities.species.human.farmer import Farmer
from core.naming import NameGenerator
import math

@register_structure
class City(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.char = culture.get("city", "🏛️ ")

        # --- New Agent-Based Population ---
        # We start with a pool of individual citizens
        initial_pop_count = RandomService.randint(100, 500)
        self.citizens = [Citizen(f"Gen0_{i}", age=RandomService.randint(15, 40)) for i in range(initial_pop_count)]

        # Resource Management
        self.food_stock = 100
        self.max_food = 2000

        # Expansion settings
        self.settler_threshold = 500 # Citizens
        self.settler_cooldown = 0
        self.settler_cost = 150
    @property
    def population(self):
        """Dynamic population count based on the citizen list."""
        return len(self.citizens)

    def update(self, world, stats):
        if self.is_expired: return

        # 1. INDIVIDUAL UPDATES & FEEDING
        self._update_citizens(world)

        # 2. REPRODUCTION (Monthly check)
        self._handle_reproduction()

        # 3. EXPANSION & TRADE (Macro Logic)
        self._manage_expansion(world)
        self._manage_trade(world)
        self._manage_specialization()
        # Cleanup dead bodies
        self.citizens = [c for c in self.citizens if not c.is_dead]

        if self.population <= 0:
            self._collapse_into_ruins(world)

    def _update_citizens(self, world):
        """Each month, citizens consume food and age."""
        for citizen in self.citizens:
            citizen.process_monthly_update()

            # Food consumption
            if self.food_stock > 0:
                self.food_stock -= 1
                citizen.hunger = max(0, citizen.hunger - 10)
            else:
                # Starvation
                citizen.hunger += 10
                if citizen.hunger >= 100:
                    citizen.is_dead = True
            # 3. Economic update (Work)
            # This calls Farmer.work() or Citizen.work() automatically!
            citizen.work(self, world)

    def _handle_reproduction(self):
        """Birth logic based on food abundance and population capacity."""
        # Simple birth model: if food is plentiful, new citizens are born
        if self.food_stock > (self.population * 5) and self.population > 2:
            birth_chance = 0.2 # 5% chance per month
            if RandomService.random() < birth_chance:
                new_baby = Citizen(NameGenerator.generate_person_name(self.culture), age=0)
                self.citizens.append(new_baby)

    def _manage_expansion(self, world):
        """Sends settlers if population is high enough."""
        if self.settler_cooldown > 0:
            self.settler_cooldown -= 1

        if self.population >= self.settler_threshold and self.settler_cooldown == 0:
            if self._can_world_support_new_settler(world):
                # Remove 10 citizens to form the new colony
                self.citizens = self.citizens[:-10]
                self._spawn_settler(world)
                self.settler_cooldown = 100
    def _manage_expansion(self, world):
        """Sends settlers if population is high enough, consuming a part of the population."""
        if self.settler_cooldown > 0:
            self.settler_cooldown -= 1

        # Check if we reached the threshold (e.g. 50 citizens)
        if self.population >= self.settler_threshold and self.settler_cooldown == 0:
            if self._can_world_support_new_settler(world):

                # SAFETY: Ensure we don't try to remove more citizens than we have
                actual_cost = min(len(self.citizens), self.settler_cost)

                if actual_cost > 0:
                    # The 'settler_cost' citizens leave the city list
                    # We take the most 'experienced' or the youngest?
                    # Usually, we take them from the end of the list (newest)
                    self.citizens = self.citizens[:-actual_cost]

                    # Spawn the settler entity on the map
                    self._spawn_settler(world)

                    # Trigger the cooldown to prevent rapid-fire expansion
                    self.settler_cooldown = 100

                    GameLogger.log(
                        f"🚀 {self.name} sent {actual_cost} pioneers to found a new land."
                    )
    def _manage_trade(self, world):
        """Spawns a trader if pop > 15 and luck strikes."""
        if self.population > 15 and RandomService.random() < 0.01:
            from entities.species.human.trader import Trader
            # Check if we already have an active trader
            my_traders = [e for e in world['entities'] if isinstance(e, Trader) and getattr(e, 'home_city', None) == self]
            if not my_traders:
                self._spawn_trader(world)

    def take_damage(self, amount):
        """Damage now kills random citizens."""
        kill_count = min(len(self.citizens), int(amount / 10))
        for _ in range(kill_count):
            if self.citizens:
                target = RandomService.choice(self.citizens)
                target.is_dead = True

    def _collapse_into_ruins(self, world):
        self.is_expired = True
        ruins = Ruins(self.x, self.y, self.culture, self.config, self.name)
        world['entities'].add(ruins)
        GameLogger.log(Translator.translate("entities.ruins_desc", name=self.name))

    # --- RE-USING YOUR REFACTORED HELPERS ---
    def _spawn_settler(self, world):
        from entities.species.human.settler import Settler
        new_settler = Settler(self.x, self.y, self.culture, self.config, home_city=self)
        world['entities'].add(new_settler)
        GameLogger.log(Translator.translate("entities.settler_spawn", name=self.name))

    def _spawn_trader(self, world):
        from entities.species.human.trader import Trader
        new_trader = Trader(self.x, self.y, self.culture, self.config, self)
        world['entities'].add(new_trader)
        return True

    def _can_world_support_new_settler(self, world):
        total_area = world['width'] * world['height']
        max_cities = total_area // 225
        living_structures = [e for e in world['entities'] if type(e) in STRUCTURE_TYPES and not e.is_expired]
        if len(living_structures) >= max_cities * 0.9: return False
        return True
    def _manage_specialization(self):
        """
        Logic to 'promote' a Citizen into a Farmer
        if the city needs more food.
        """
        for i, person in enumerate(self.citizens):
            # If we need farmers and this is just a basic Citizen
            if type(person) is Citizen and self.food_stock < (len(self.citizens) * 10):
                # We replace the object in the list with a Farmer version
                self.citizens[i] = Farmer(person.name, person.age)
                # We can even transfer experience if needed
                self.citizens[i].experience = person.experience