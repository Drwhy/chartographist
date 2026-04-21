# entities/constructs/village.py
from .base import Construct
from entities.registry import register_structure, STRUCTURE_TYPES
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.species.human.base import Human
from entities.species.human.farmer import Farmer
from core.religion import create_faith_from_demographics, SyncreticReligion, _find_template
import math

@register_structure
class Village(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)

        initial_count = RandomService.randint(5, 12)
        self.citizens = []
        for _ in range(initial_count):
            c = Human(self.x, self.y, self.culture, self.config, 1)
            c.age = RandomService.randint(15, 45)
            c.species_data = self._personal_species
            self.citizens.append(c)

        # Resources
        self.food_stock = 40
        self.max_food = 500

        # Evolution
        self.city_threshold = 40
        self.char = culture.get("village", "🏡")
        self.known_cities = set()

        # Reference to the specialized external worker (Hunter/Fisherman entity)
        self.active_worker_entity = None

    @property
    def population(self):
        return len(self.citizens)

    def update(self, world, stats):
        if self.is_expired: return

        # 1. Monthly biological update (Hunger, Age)
        self._update_citizens(world)

        # 2. Reproduction — religion bonus modulates growth
        religion_growth = self.religion.bonus("growth", 0) if self.religion else 0
        growth_mult = 1.0 + (religion_growth * 0.01)
        self._handle_reproduction(chance_multiplier=growth_mult)

        # 3. Workforce & Evolution (Slow Tick - Every 12 months)
        if world['cycle'] % 12 == 0:
            self._manage_specialization(world)

            if self.population >= self.city_threshold:
                self._evolve_to_city(world)

        # 4. Syncretism check (slow tick)
        if world['cycle'] % 100 == 0:
            self._check_syncretism()

        # 5. Cleanup
        self.citizens = [c for c in self.citizens if not c.is_dead]
        if self.population <= 0:
            self.is_expired = True

    def _update_citizens(self, world):
        """Standard feeding and aging logic."""
        for person in self.citizens:
            person.process_monthly_update()

            # Feeding from village stores
            if self.food_stock >= 1:
                self.food_stock -= 1
                person.hunger = max(0, person.hunger - 10)
            else:
                person.hunger += 10
                if person.hunger >= 100: person.is_dead = True

            # Basic work (Gathering/Small farming)
            person.work(self, world)

    def _manage_specialization(self, world):
        """Village logic: promote to Farmer OR spawn an external Hunter/Fisherman."""
        # A. Check internal Farmers
        # In a village, we only want a few farmers, the rest gather or hunt
        farmers_count = sum(1 for p in self.citizens if isinstance(p, Farmer))
        if farmers_count < (self.population * 0.3) and self.food_stock < 50:
            self._promote_to_farmer()

        # B. Check External Worker (The Unit on the map)
        if self.active_worker_entity and self.active_worker_entity.is_expired:
            self.active_worker_entity = None

        if self.active_worker_entity is None and self.population > 10:
            if self._is_coastal(world):
                self._spawn_fisherman(world)
            else:
                self._spawn_hunter(world)

    def _assign_faith(self, agent):
        """Assign a personal faith to an agent based on village demographics."""
        if self.religion:
            agent.faith = create_faith_from_demographics(self.religion)

    def _promote_to_farmer(self):
        """Turns one basic Citizen into a Farmer, preserving family bonds."""
        for i, p in enumerate(self.citizens):
            if type(p) is Human:
                new_farmer = Farmer(self.x, self.y, self.culture, self.config, name=p.name, age=p.age)
                new_farmer.faith = p.faith
                new_farmer.species_data = p.species_data
                new_farmer.partner = p.partner
                new_farmer.children = p.children
                new_farmer.sex = p.sex
                new_farmer.love_interest = p.love_interest
                new_farmer.love_score = p.love_score
                new_farmer.birth_city = p.birth_city
                if p.partner and p.partner.partner is p:
                    p.partner.partner = new_farmer
                self.citizens[i] = new_farmer
                return

    def _is_coastal(self, world):
        """Checks if water is nearby for fishing."""
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = self.y + dy, self.x + dx
            if 0 <= ny < world['height'] and 0 <= nx < world['width']:
                if world['elev'][ny][nx] < 0: return True
        return False

    def _spawn_hunter(self, world):
        from entities.species.human.hunter import Hunter
        self.active_worker_entity = Hunter(self.x, self.y, self.culture, self.config, self.pos, self)
        self._assign_faith(self.active_worker_entity)
        self._assign_species(self.active_worker_entity)
        world['entities'].add(self.active_worker_entity)

    def _spawn_fisherman(self, world):
        from entities.species.human.fisherman import Fisherman
        self.active_worker_entity = Fisherman(self.x, self.y, self.culture, self.config, self.pos, self)
        self._assign_faith(self.active_worker_entity)
        self._assign_species(self.active_worker_entity)
        world['entities'].add(self.active_worker_entity)

    def _evolve_to_city(self, world):
        """Village becomes a City. Citizens and religion are transferred."""
        from entities.constructs.city import City
        GameLogger.log(Translator.translate("entities.village_promoted", name=self.name, x=self.x, y=self.y))

        new_city = City(self.x, self.y, self.culture, self.config)
        # CRITICAL: Transfer the actual list of agents (preserving age/XP/faith)
        new_city.citizens = self.citizens
        new_city.food_stock = self.food_stock
        # Transfer religion demographics from village to city
        if self.religion:
            new_city.religion = self.religion

        world['entities'].add(new_city)
        self.is_expired = True

    # _check_syncretism is inherited from Construct with _syncretism_chance = 0.01