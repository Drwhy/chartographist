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
        """Four-phase family system: cleanup → attraction → courtship → births."""
        self._cleanup_partnerships()
        self._handle_attraction()
        self._handle_courtship()
        self._handle_births(chance_multiplier)

    def _cleanup_partnerships(self):
        """Break bonds whose partner has died; clear stale love interests."""
        for citizen in self.citizens:
            if citizen.partner and citizen.partner.is_dead:
                citizen.partner = None
            if citizen.love_interest is not None:
                li = citizen.love_interest
                if li.is_dead or (li.partner is not None and not li.partner.is_dead
                                  and li.partner is not citizen):
                    citizen.love_interest = None
                    citizen.love_score = 0.0

    def _handle_attraction(self):
        """Gradually build romantic attraction between single fertile citizens."""
        singles = [c for c in self.citizens if c.is_fertile and c.is_single]
        if len(singles) < 2:
            return
        citizen_set = set(self.citizens)

        for person in singles:
            if person.love_interest is not None:
                target = person.love_interest
                # Drop interest if target left the settlement, died, or married someone else
                if (target not in citizen_set or target.is_dead
                        or (target.partner is not None and not target.partner.is_dead)):
                    person.love_interest = None
                    person.love_score = 0.0
                    continue
                # Grow attraction tick by tick
                growth = 0.02
                if (isinstance(person.culture, dict) and isinstance(target.culture, dict)
                        and person.culture.get('name') == target.culture.get('name')):
                    growth += 0.015
                if (person.faith and target.faith
                        and person.faith.religion_name == target.faith.religion_name):
                    growth += 0.01
                if abs(person.age - target.age) <= 10:
                    growth += 0.008
                growth += RandomService.random() * 0.015
                person.love_score = min(1.0, person.love_score + growth)
            else:
                # 5% chance per tick to notice someone and develop an initial spark
                if RandomService.random() < 0.05:
                    candidates = [
                        c for c in singles
                        if c is not person and not self._are_related(person, c)
                    ]
                    if candidates:
                        target = RandomService.choice(candidates)
                        person.love_interest = target
                        person.love_score = RandomService.uniform(0.05, 0.2)

    def _handle_courtship(self):
        """When two people are mutually in love (≥0.65 / ≥0.5), they wed."""
        for person in list(self.citizens):
            if not person.is_single or not person.is_fertile:
                continue
            if person.love_interest is None or person.love_score < 0.65:
                continue
            target = person.love_interest
            if not target.is_single or not target.is_fertile:
                person.love_interest = None
                person.love_score = 0.0
                continue
            if target.love_interest is person and target.love_score >= 0.5:
                # Mutual love — they wed
                person.partner = target
                target.partner = person
                person.love_interest = None
                target.love_interest = None
                person.love_score = 0.0
                target.love_score = 0.0
                if RandomService.random() < 0.05:
                    GameLogger.log(Translator.translate(
                        "events.family_married",
                        name1=person.name, name2=target.name, city=self.name
                    ))
            elif target.love_interest is None and RandomService.random() < 0.15:
                # Target begins noticing their admirer
                target.love_interest = person
                target.love_score = RandomService.uniform(0.1, 0.3)

    def _handle_births(self, chance_multiplier=1.0):
        """M+F couples may produce a child when food is sufficient. Fertility bonus applies."""
        if self.food_stock <= len(self.citizens):
            return

        seen = set()
        for citizen in self.citizens:
            if not citizen.is_fertile or citizen.partner is None:
                continue
            partner = citizen.partner
            if not partner.is_fertile:
                continue
            # Biological reproduction requires one male and one female
            if citizen.sex == partner.sex:
                continue
            pair_key = frozenset({id(citizen), id(partner)})
            if pair_key in seen:
                continue
            seen.add(pair_key)
            avg_fertility = (citizen.species_trait('fertility') + partner.species_trait('fertility')) / 2
            birth_chance = 0.02 * chance_multiplier * (1.0 + avg_fertility * 0.15)
            if RandomService.random() < birth_chance:
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
        """Create a child inheriting family name, XP, faith, and sex from parents."""
        first_name = NameGenerator.generate_first_name(self.culture)
        child = Human(
            self.x, self.y, self.culture, self.config, 1,
            f"{first_name} {p1.family_name}",
            parents=(p1, p2)
        )
        child.experience = int((p1.experience + p2.experience) * 0.05)
        child.birth_city = self.name
        for parent in (p1, p2):
            if parent.faith is not None:
                child.faith = parent.faith
                break
        for parent in (p1, p2):
            if parent.species_data is not None:
                child.species_data = parent.species_data
                break
        p1.children.append(child)
        p2.children.append(child)
        self.citizens.append(child)
        if RandomService.random() < 0.05:
            birth_key = "events.family_birth_m" if child.sex == 'M' else "events.family_birth_f"
            GameLogger.log(Translator.translate(
                birth_key, child_name=child.name, city=self.name,
                parent1=p1.name, parent2=p2.name
            ))