import math
from core.naming import NameGenerator
from core.random_service import RandomService
from entities.species.human.base import Human
from core.entities import Entity, Z_CONSTRUCT
from core.logger import GameLogger
from core.translator import Translator
from core.religion import generate_demographics, SyncreticReligion, _find_template
from core.species import get_species_for_culture, PersonalSpecies

class Construct(Entity):
    """
    Base class for all static structures built on the map.
    Handles naming, cultural stability, and the 'Cultural Drift' mechanic.
    """
    _syncretism_chance = 0.01  # Overridden by City (0.02)

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

        # Species template shared by all citizens of this culture
        _tmpl = get_species_for_culture(culture.get('name', ''))
        self._personal_species = PersonalSpecies(_tmpl) if _tmpl else None

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

        # Refresh species for the new culture
        _tmpl = get_species_for_culture(self.culture.get('name', ''))
        self._personal_species = PersonalSpecies(_tmpl) if _tmpl else None

        GameLogger.log(
            Translator.translate(
                "events.cultural_mutation",
                name=self.name,
                old_culture=old_culture_name,
                new_culture=self.culture['name']
            )
        )
    def _assign_species(self, agent):
        """Assign the settlement's species to a spawned agent and apply its speed modifier."""
        if self._personal_species:
            agent.species_data = self._personal_species
            agent.speed = max(0.3, agent.speed + self._personal_species.speed_mod)

    def _handle_reproduction(self, chance_multiplier=1.0):
        """Two-phase family system: courtship first, then births from couples."""
        self._cleanup_partnerships()
        self._handle_courtship()
        self._handle_births(chance_multiplier)

    def _cleanup_partnerships(self):
        """Break bonds whose partner has died."""
        for citizen in self.citizens:
            if citizen.partner and citizen.partner.is_dead:
                citizen.partner = None

    def _handle_courtship(self):
        """Single fertile adults may form a couple (10% chance per pair per tick)."""
        singles = [c for c in self.citizens if c.is_fertile and c.is_single]
        if len(singles) < 2:
            return
        RandomService.shuffle(singles)
        for i in range(0, len(singles) - 1, 2):
            p1, p2 = singles[i], singles[i + 1]
            if not self._are_related(p1, p2) and RandomService.random() < 0.1:
                p1.partner = p2
                p2.partner = p1

    def _handle_births(self, chance_multiplier=1.0):
        """Established couples may produce a child if food is sufficient."""
        if self.food_stock <= len(self.citizens):
            return

        seen = set()
        for citizen in self.citizens:
            if not citizen.is_fertile or citizen.partner is None:
                continue
            partner = citizen.partner
            if not partner.is_fertile:
                continue
            pair_key = frozenset({id(citizen), id(partner)})
            if pair_key in seen:
                continue
            seen.add(pair_key)
            if RandomService.random() < (0.02 * chance_multiplier):
                self._spawn_child(citizen, partner)

    def _are_related(self, p1, p2):
        """Return True if p1 and p2 share a parent or are parent and child."""
        p1_parent_ids = {id(p) for p in (p1.parents or ()) if p is not None}
        p2_parent_ids = {id(p) for p in (p2.parents or ()) if p is not None}
        if p1_parent_ids & p2_parent_ids:   # siblings
            return True
        if id(p2) in p1_parent_ids or id(p1) in p2_parent_ids:  # parent-child
            return True
        return False

    def _check_syncretism(self):
        """Religion fusion when no single faith dominates. Chance varies by settlement size."""
        if not self.religion or not self.religion.fractions:
            return
        if self.religion.dominant_fraction >= 0.7 or len(self.religion.fractions) < 2:
            return
        if RandomService.random() >= self._syncretism_chance:
            return

        sorted_religions = sorted(self.religion.fractions.items(), key=lambda x: -x[1])
        name_a, _ = sorted_religions[0]
        name_b, _ = sorted_religions[1]
        tmpl_a = _find_template(name_a)
        tmpl_b = _find_template(name_b)
        if not tmpl_a or not tmpl_b:
            return

        syncretic = SyncreticReligion.create(tmpl_a, tmpl_b)
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

    def _spawn_child(self, p1, p2):
        """Create a child inheriting family name, XP seed, and faith from parents."""
        first_name = NameGenerator.generate_first_name(self.culture)
        child = Human(
            self.x, self.y, self.culture, self.config, 1,
            f"{first_name} {p1.family_name}",
            parents=(p1, p2)
        )
        child.experience = int((p1.experience + p2.experience) * 0.05)
        # Inherit faith from one parent (preferring the one with faith)
        for parent in (p1, p2):
            if parent.faith is not None:
                child.faith = parent.faith
                break
        # Inherit species from one parent
        for parent in (p1, p2):
            if parent.species_data is not None:
                child.species_data = parent.species_data
                break
        p1.children.append(child)
        p2.children.append(child)
        self.citizens.append(child)