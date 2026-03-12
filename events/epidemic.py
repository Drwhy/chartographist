from .event_registry import register_event
from .base_event import BaseEvent
from core.random_service import RandomService
from core.logger import GameLogger
from entities.constructs.city import City
from core.translator import Translator

@register_event
class Epidemic(BaseEvent):
    """
    Simulates a disease outbreak within the world.
    Infections can start in large cities and spread to mobile human entities.
    Handles mortality, transmission, and immune recovery logic.
    """
    name = "Epidemic"
    chance = 0.0008

    def trigger(self, world, stats, config):
        """Triggers 'Patient Zero' in a random qualified city."""
        # Filter criteria:
        # 1. Must be a City instance
        # 2. Minimum population threshold (> 500)
        # 3. Not already battling an infection
        cities = [
            entity for entity in world['entities']
            if isinstance(entity, City)
            and entity.population > 500
            and not getattr(entity, 'is_infected', False)
        ]

        if cities:
            target = RandomService.choice(cities)
            target.is_infected = True
            # Initial outbreak touches 5% to 10% of the population
            target.infected_count = int(target.population * RandomService.uniform(0.05, 0.10))
            target.infection_turns = 0
            GameLogger.log(Translator.translate("events.epidemic_start", name=target.name))

    def tick(self, world, stats):
        """Processes the progression of the disease for all infected entities."""
        for entity in world['entities']:
            if getattr(entity, 'is_infected', False) and not entity.is_expired:
                self._update_infection(entity, world)

    def _update_infection(self, entity, world):
        """
        Manages disease progression for a specific entity (City or Human).
        """
        from entities.constructs.ruins import Ruins
        from entities.species.human.base import Human

        # Initialize the turn counter if this is the first day of infection
        if not hasattr(entity, 'infection_turns'):
            entity.infection_turns = 0
        entity.infection_turns += 1

        # --- CASE 1: MOBILE HUMAN ENTITY (Trader, Hunter, etc.) ---
        if isinstance(entity, Human):
            # 1. Fear emission: Others sense the illness (Negative Influence)
            world['influence'].add_influence(entity.x, entity.y, value=-5.0, radius=1)

            # 2. Lethality Check (Mobile units have less resilience than cities)
            if RandomService.random() < 0.05: # 5% daily chance of death
                entity.is_expired = True
                GameLogger.log(Translator.translate("events.human_epidemic_death", name=entity.name))
                return

            # 3. Recovery Chance (Immune System)
            if RandomService.random() < 0.05:
                entity.is_infected = False
                entity.infection_turns = 0

        # --- CASE 2: SETTLEMENT / CITY ---
        else:
            # Mass mortality logic
            mortality_rate = 0.22
            deaths = int(entity.infected_count * mortality_rate)
            entity.population -= deaths
            entity.infected_count -= deaths

            # Internal transmission (Spread within the walls)
            transmission_rate = 0.4
            new_cases = int(entity.infected_count * transmission_rate)
            entity.infected_count = min(entity.population, entity.infected_count + new_cases)

            # Recovery Curve: Increases as time passes (simulating acquired immunity)
            cure_chance = 0.01 if entity.infection_turns < 20 else 0.01 + ((entity.infection_turns - 20) * 0.005)

            if RandomService.random() < cure_chance or entity.infected_count <= 0:
                entity.is_infected = False
                entity.infected_count = 0
                GameLogger.log(Translator.translate("events.epidemic_end", name=entity.name))

            # Total Collapse: If population drops too low, the city becomes a ruin
            if entity.population <= 10:
                ruin = Ruins(entity.x, entity.y, entity.culture, entity.config, entity.name)
                world['entities'].add(ruin)
                entity.is_expired = True
                GameLogger.log(Translator.translate("events.epidemic_death", name=entity.name))