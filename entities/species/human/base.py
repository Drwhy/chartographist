from core.entities import Entity, Z_HUMAN
from core.naming import NameGenerator
from core.random_service import RandomService
from core.religion import PersonalFaith

class Human(Entity):
    def __init__(self, x, y, culture, config, speed, name=None, parents=None):
        # Initialize the base entity
        super().__init__(x, y, "?", Z_HUMAN, speed)
        self.culture = culture # Cultural dictionary (e.g., Empire)
        self.config = config   # Full template.json
        self.age = 0
        self.energy = 100
        self.hunger = 0
        self.experience = 0
        self.is_dead = False
        self.species = 'human'
        # --- Genealogy & Family ---
        self.parents = parents      # tuple (p1, p2) or None for founders
        self.partner = None         # current spouse/partner, or None if single
        self.children = []          # list of Human children born to this person
        self.name = name if name else NameGenerator.generate_person_name(culture)
        self.family_name = self._derive_family_name()
        self.birth_city = None      # name of the city where this person was born
        # --- Biological sex (used for reproduction) ---
        self.sex = RandomService.choice(['M', 'F'])
        # --- Love & Attraction ---
        self.love_interest = None   # Human this person is attracted to
        self.love_score = 0.0       # attraction level toward love_interest (0.0–1.0)
        self.faith = None
        self.species_data = None  # PersonalSpecies, assigned by the spawning settlement
        self.is_infected = False
        self.infection_turns = 0

    @property
    def is_edible(self):
        return True

    @property
    def danger_level(self):
        return 0.2  # Not very frightening

    @property
    def is_fertile(self):
        return 18 <= self.age <= 45 and self.hunger < 50

    @property
    def is_single(self):
        return self.partner is None or self.partner.is_dead

    def update(self, world, stats):
        """Universal agent life loop."""
        if self.is_dead or self.is_expired:
            return

        self.age += 1
        # 1. ANALYSIS (Perception)
        # 2. DECISION (AI) -> self.think(world)
        # 3. ACTION (Movement/Interaction) -> self.perform_action(world)

        self.think(world)
        self.perform_action(world)

    def think(self, world):
        """To be defined in child classes (Hunter, etc.)"""
        pass

    def perform_action(self, world):
        """To be defined in child classes"""
        pass

    def _get_accessible_neighbors(self, world):
        """Returns adjacent walkable tiles (no water)."""
        neighbors = []
        for dx, dy in [(0,0), (0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                if world['elev'][ny][nx] >= 0: # Terrestrial biome check
                    neighbors.append((nx, ny))
        return neighbors

    def _derive_family_name(self):
        if self.parents and isinstance(self.parents, (list, tuple)):
            parent = self.parents[0]
            if hasattr(parent, 'family_name') and parent.family_name:
                return parent.family_name
            if isinstance(parent, str) and " " in parent:
                return parent.split(" ")[-1]
        if isinstance(self.name, str) and " " in self.name:
            return self.name.split(" ")[-1]
        return str(self.name)

    def process_monthly_update(self):
        """Common biological logic for everyone."""
        self.age += (1/12)
        self.hunger += 5

        # Natural death risk
        if self.age > 50:
            if RandomService.random() < (self.age - 50) * 0.01:
                self.is_dead = True

    def faith_bonus(self, key, default=0):
        """Returns the additive bonus from personal faith for the given key."""
        if self.faith is None:
            return default
        return self.faith.bonus(key, default)

    def species_trait(self, key, default=0):
        """Returns the additive trait value from personal species for the given key."""
        if self.species_data is None:
            return default
        return self.species_data.trait(key, default)

    def work(self, city, world):
        """Base citizens provide basic labor (slow food gain)."""
        city.food_stock = min(city.max_food, city.food_stock + 1)