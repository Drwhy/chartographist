import math
from core.naming import NameGenerator
from core.random_service import RandomService
from entities.species.human.base import Human
from core.entities import Entity, Z_CONSTRUCT
from core.logger import GameLogger
from core.translator import Translator
from core.religion import generate_demographics

class Construct(Entity):
    """
    Base class for all static structures built on the map.
    Handles naming, cultural stability, and the 'Cultural Drift' mechanic.
    """
    def __init__(self, x, y, culture, config):
        # Initialize the physical entity at Z_CONSTRUCT layer with speed 1
        super().__init__(x, y, "?", Z_CONSTRUCT, 1.0)

        self.culture = culture
        self.original_culture = culture
        self.ticks_since_founded = 0
        self.stability = 1.0
        self.config = config
        self.species = "construct"

        # Generates a procedural place name based on cultural linguistics
        self.name = NameGenerator.generate_place_name(culture)

        # Religion demographics for this settlement
        self.religion = generate_demographics(culture)

    def update(self, world, stats):
        """Standard update loop to be overridden by child classes (City, Village, etc.)."""
        pass

    def _check_cultural_drift(self, world):
        """
        Calculates the likelihood of a settlement shifting its cultural identity.
        Driven by distance from the mother city and the passage of time.
        """
        from entities.constructs.ruins import Ruins

        if self.is_expired or isinstance(self, Ruins):
            return

        self.ticks_since_founded += 1

        # 1. Distance to Capital Calculation
        # Cultural influence weakens the further a settlement is from its origin
        dist_to_origin = 0
        if hasattr(self, 'home_city') and self.home_city:
            dist_to_origin = math.dist(self.pos, self.home_city.pos)

        # 2. Drift Factors: Time (Aging) + Distance (Isolation)
        # Probabilities scale based on 5000-tick intervals and 500-unit distances
        drift_chance = (self.ticks_since_founded / 5000) + (dist_to_origin / 500)

        # 3. Mutation Event Trigger
        if RandomService.random() < drift_chance * 0.01:
            self._mutate_culture(world)

    def _mutate_culture(self, world):
        """
        Forces a cultural shift, changing the settlement's values and visual style.
        """
        from entities.constructs.city import City
        from entities.constructs.village import Village

        all_cultures = self.config['cultures']

        # Filter to ensure we select a new, different culture
        available_cultures = [c for c in all_cultures if c['name'] != self.culture['name']]
        if not available_cultures:
            return

        old_culture_name = self.culture['name']
        self.culture = RandomService.choice(available_cultures)

        # --- VISUAL UPDATE BY TYPE ---
        # Refresh the display character based on the new culture's theme
        if isinstance(self, City):
            self.char = self.culture.get('city', '🏙️')
        elif isinstance(self, Village):
            self.char = self.culture.get('village', '🏡')

        GameLogger.log(
            Translator.translate(
                "events.cultural_mutation",
                name=self.name,
                old_culture=old_culture_name,
                new_culture=self.culture['name']
            )
        )
    def _update_population_logic(self, world):
        """Shared biological and economic logic for all settlements."""
        if not self.citizens:
            return

        # 1. Monthly Status (Aging, Hunger, Working)
        for person in self.citizens:
            person.process_monthly_status()

            # Feeding Logic
            if self.food_stock >= 1:
                self.food_stock -= 1
                person.hunger = max(0, person.hunger - 10)
            else:
                person.hunger += 10 # Starvation
                if person.hunger >= 100: person.is_dead = True

            # Production (Polymorphism: Farmer.work or Citizen.work)
            person.work(self, world)

        # 2. Cleanup dead
        self.citizens = [c for c in self.citizens if not c.is_dead]

    def _handle_reproduction(self, chance_multiplier=1.0):
        """Shared genealogy and birth system."""
        if self.food_stock <= len(self.citizens):
            return

        fertile_pool = [c for c in self.citizens if c.is_fertile]
        RandomService.shuffle(fertile_pool)

        for i in range(0, len(fertile_pool) - 1, 2):
            p1, p2 = fertile_pool[i], fertile_pool[i+1]

            # Base chance: 2% per month, modified by city/village type
            if RandomService.random() < (0.02 * chance_multiplier):
                self._spawn_child(p1, p2)

    def _spawn_child(self, p1, p2):
        """Creates a child with inherited lineage."""
        first_name = NameGenerator.generate_first_name(self.culture)
        family_name = p1.family_name

        child = Human(self.x, self.y, self.culture, self.config, 1, f"{first_name} {family_name}", parents=(p1, p2))

        # Heritage: Small XP boost from parents
        child.experience = int((p1.experience + p2.experience) * 0.05)
        self.citizens.append(child)