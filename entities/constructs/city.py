# entities/constructs/city.py
from .base import Construct
from entities.registry import register_structure, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.constructs.ruins import Ruins
from entities.species.human.base import Human
from entities.species.human.farmer import Farmer
from core.naming import NameGenerator
from core.religion import create_faith_from_demographics, SyncreticReligion, _find_template
import math

@register_structure
class City(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.char = culture.get("city", "🏛️ ")

        # --- New Agent-Based Population ---
        # We start with a pool of individual citizens
        initial_pop_count = RandomService.randint(100, 500)
        self.citizens = [Human(self.x, self.y, self.culture, self.config, 1) for i in range(initial_pop_count)]

        # Resource Management
        self.food_stock = 100
        self.max_food = 2000

        # Expansion settings
        self.settler_threshold = 500 # Citizens
        self.settler_cooldown = 0
        self.settler_cost = 150

        # Active agent references
        self.active_trader = None

        # Discovery: set of city ids this city knows about (via trade)
        self.known_cities = set()
    @property
    def population(self):
        """Dynamic population count based on the citizen list."""
        return len(self.citizens)

    def update(self, world, stats):
        if self.is_expired: return

        # 1. INDIVIDUAL UPDATES & FEEDING
        self._update_citizens(world)

        # 2. REPRODUCTION — religion bonus modulates growth
        religion_growth = self.religion.bonus("growth", 0) if self.religion else 0
        growth_mult = 1.0 + (religion_growth * 0.01)
        self._handle_reproduction(chance_multiplier=growth_mult)

        # 3. EXPANSION & TRADE (Macro Logic)
        self._manage_expansion(world)
        self._manage_trade(world)
        self._manage_specialization()

        # 4. Syncretism check (slow tick)
        if world['cycle'] % 100 == 0:
            self._check_syncretism()

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
    def _manage_trade(self, world):
        """Spawns a trader if pop > 15 and luck strikes."""
        # Check if active trader is still alive
        if self.active_trader and self.active_trader.is_expired:
            self.active_trader = None

        if self.population > 15 and RandomService.random() < 0.01:
            if self.active_trader is None:
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
        # Assign faith from city demographics
        if self.religion:
            new_settler.faith = create_faith_from_demographics(self.religion)
        world['entities'].add(new_settler)
        GameLogger.log(Translator.translate("entities.settler_spawn", name=self.name))

    def _spawn_trader(self, world):
        from entities.species.human.trader import Trader
        new_trader = Trader(self.x, self.y, self.culture, self.config, self)
        # Assign faith from city demographics
        if self.religion:
            new_trader.faith = create_faith_from_demographics(self.religion)
        world['entities'].add(new_trader)
        self.active_trader = new_trader
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
            if type(person) is Human and self.food_stock < (len(self.citizens) * 10):
                # We replace the object in the list with a Farmer version
                new_farmer = Farmer(self.x, self.y, self.culture, self.config, person.name, person.age)
                new_farmer.faith = person.faith  # Preserve faith
                self.citizens[i] = new_farmer

    def _check_syncretism(self):
        """
        Check if conditions are met for religion fusion.
        If no single religion dominates (>70%), there's a small chance
        of a syncretic religion emerging from the two largest faiths.
        """
        if not self.religion or not self.religion.fractions:
            return

        dominant_frac = self.religion.dominant_fraction
        # Syncretism only when no overwhelming majority
        if dominant_frac < 0.7 and len(self.religion.fractions) >= 2:
            if RandomService.random() < 0.02:  # 2% chance per slow tick
                sorted_religions = sorted(self.religion.fractions.items(), key=lambda x: -x[1])
                name_a, _ = sorted_religions[0]
                name_b, _ = sorted_religions[1]

                tmpl_a = _find_template(name_a)
                tmpl_b = _find_template(name_b)

                if tmpl_a and tmpl_b:
                    syncretic = SyncreticReligion.create(tmpl_a, tmpl_b)
                    # The new syncretic religion takes a portion of both parents
                    old_a = self.religion.fractions.get(name_a, 0)
                    old_b = self.religion.fractions.get(name_b, 0)
                    self.religion.fractions[syncretic["name"]] = (old_a + old_b) * 0.3
                    self.religion.fractions[name_a] *= 0.7
                    self.religion.fractions[name_b] *= 0.7
                    self.religion._normalize()

                    GameLogger.log(Translator.translate(
                        "events.religion_syncretism_emerges",
                        religion=syncretic["name"], name=self.name
                    ))