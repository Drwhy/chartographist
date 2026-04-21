# entities/constructs/city.py
from .base import Construct
from entities.registry import register_structure, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.constructs.ruins import Ruins
from entities.species.human.base import Human
from entities.species.human.farmer import Farmer
from core.religion import create_faith_from_demographics
import math

@register_structure
class City(Construct):
    _syncretism_chance = 0.02  # Cities fuse religions faster than villages
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.char = culture.get("city", "🏛️ ")

        initial_pop_count = RandomService.randint(100, 500)
        self.citizens = []
        for _ in range(initial_pop_count):
            c = Human(self.x, self.y, self.culture, self.config, 1)
            c.age = RandomService.randint(15, 45)
            c.species_data = self._personal_species
            self.citizens.append(c)

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

        # War state
        self.enemies = []         # List of city objects we are at war with
        self.war_cooldown = 0     # Ticks before we can declare another war
        self.soldier_cooldown = 0 # Ticks between soldier spawns
        self.soldier_cost = 20    # Citizens consumed per soldier
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

        # 4. WAR (evaluated every 12 cycles)
        if world['cycle'] % 12 == 0:
            self._manage_war(world)

        # 5. Syncretism check (slow tick)
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
        if self.religion:
            new_settler.faith = create_faith_from_demographics(self.religion)
        self._assign_species(new_settler)
        world['entities'].add(new_settler)
        GameLogger.log(Translator.translate("entities.settler_spawn", name=self.name))

    def _spawn_trader(self, world):
        from entities.species.human.trader import Trader
        new_trader = Trader(self.x, self.y, self.culture, self.config, self)
        if self.religion:
            new_trader.faith = create_faith_from_demographics(self.religion)
        self._assign_species(new_trader)
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
        """Promote one basic Citizen to Farmer per tick when food is scarce."""
        if self.food_stock >= len(self.citizens) * 10:
            return
        for i, person in enumerate(self.citizens):
            if type(person) is Human:
                new_farmer = Farmer(self.x, self.y, self.culture, self.config, name=person.name, age=person.age)
                new_farmer.faith = person.faith
                new_farmer.species_data = person.species_data
                new_farmer.partner = person.partner
                new_farmer.children = person.children
                new_farmer.sex = person.sex
                new_farmer.love_interest = person.love_interest
                new_farmer.love_score = person.love_score
                new_farmer.birth_city = person.birth_city
                if person.partner and person.partner.partner is person:
                    person.partner.partner = new_farmer
                self.citizens[i] = new_farmer
                break  # one promotion per tick

    # ── WAR SYSTEM ──────────────────────────────
    def _manage_war(self, world):
        """Handles war declaration, soldier spawning, and peace resolution."""
        # Tick down cooldowns
        if self.war_cooldown > 0:
            self.war_cooldown -= 1
        if self.soldier_cooldown > 0:
            self.soldier_cooldown -= 1

        # Clean up ended wars (enemy dead or expired)
        self.enemies = [e for e in self.enemies if not e.is_expired and getattr(e, 'population', 0) > 0]

        # Consider declaring war if we know other cities
        if not self.enemies and self.war_cooldown == 0 and self.population >= 200:
            self._consider_war(world)

        # Spawn soldiers if at war
        if self.enemies and self.soldier_cooldown == 0 and self.population > self.soldier_cost * 2:
            self._spawn_soldier(world)

    def _consider_war(self, world):
        """
        Evaluate whether to declare war on a known city.
        Wars happen between cities of different cultures.
        Probability increases with population advantage and proximity.
        """
        from core.discovery_service import DiscoveryService

        known_settlements = DiscoveryService.get_known_settlements(world)
        foreign_cities = [
            c for c in known_settlements
            if c != self
            and not c.is_expired
            and c.culture.get('name') != self.culture.get('name')
            and getattr(c, 'population', 0) > 0
        ]

        if not foreign_cities:
            return

        # Pick the closest foreign city
        target = min(foreign_cities, key=lambda c: math.dist(self.pos, c.pos))
        dist = math.dist(self.pos, target.pos)

        # War probability: higher with pop advantage, lower with distance
        pop_ratio = self.population / max(target.population, 1)
        proximity_factor = max(0, 1.0 - (dist / 40))  # Closer = more likely

        war_chance = 0.03 * pop_ratio * proximity_factor

        if RandomService.random() < war_chance:
            self._declare_war(target)

    def _declare_war(self, target):
        """Formally declare war on another city."""
        self.enemies.append(target)
        self.war_cooldown = 200  # Can't declare another war for 200 ticks

        # Mutual war: the target retaliates
        if hasattr(target, 'enemies'):
            if self not in target.enemies:
                target.enemies.append(self)

        GameLogger.log(Translator.translate(
            "events.war_declared",
            attacker=self.name, defender=target.name
        ))

    def _spawn_soldier(self, world):
        """Consume citizens to create a soldier unit targeting the enemy."""
        from entities.species.human.soldier import Soldier

        if not self.enemies:
            return

        target = self.enemies[0]  # Focus on primary enemy
        actual_cost = min(len(self.citizens), self.soldier_cost)
        if actual_cost <= 0:
            return

        # Consume citizens
        self.citizens = self.citizens[:-actual_cost]

        new_soldier = Soldier(self.x, self.y, self.culture, self.config, self, target)
        if self.religion:
            new_soldier.faith = create_faith_from_demographics(self.religion)
            new_soldier.strength += new_soldier.faith_bonus("defense") * 0.15
        self._assign_species(new_soldier)
        new_soldier.strength += new_soldier.species_trait("strength") * 0.1

        world['entities'].add(new_soldier)
        self.soldier_cooldown = 24  # One soldier per 2 years

        GameLogger.log(Translator.translate(
            "events.soldier_spawned",
            city=self.name, target=target.name
        ))