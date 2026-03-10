from .event_registry import register_event
from .base_event import BaseEvent
from core.random_service import RandomService
from core.logger import GameLogger
from entities.constructs.city import City
from core.translator import Translator

@register_event
class Epidemic(BaseEvent):
    name = "Épidémie"
    chance = 0.0008

    def trigger(self, world, stats, config):
        """Déclenche le "Patient Zéro" dans une ville aléatoire."""
        # Filtre précis :
        # 1. Doit être une instance de City
        # 2. Doit avoir une population minimum (> 500)
        # 3. Ne doit pas déjà être en cours d'infection
        cities = [
            e for e in world['entities']
            if isinstance(e, City)
            and e.population > 500
            and not getattr(e, 'is_infected', False)
        ]
        if cities:
            target = RandomService.choice(cities)
            target.is_infected = True
            # On commence avec 5 à 10% de la population touchée
            target.infected_count = int(target.population * RandomService.uniform(0.05, 0.10))
            target.infection_turns = 0
            GameLogger.log(Translator.translate("events.epidemic_start", name=target.name))

    def tick(self, world, stats):
        """Gère l'évolution des villes déjà infectées."""
        for e in world['entities']:
            if getattr(e, 'is_infected', False) and not e.is_expired:
                self._update_infection(e, world)

    def _update_infection(self, entity, world):
        """
        Gère l'évolution de la maladie pour une entité (Cité ou Humain).
        """
        from entities.constructs.ruins import Ruins
        from entities.species.human.base import Human

        # On initialise le compteur si c'est le premier tour
        if not hasattr(entity, 'infection_turns'):
            entity.infection_turns = 0
        entity.infection_turns += 1

        # --- CAS 1 : L'ENTITÉ EST UN HUMAIN (Marchand, Chasseur, etc.) ---
        if isinstance(entity, Human):
            # 1. Émission de peur : Les autres sentent qu'il est malade
            world['influence'].add_influence(entity.x, entity.y, value=-5.0, radius=1)

            # 2. Chance de mort subite (Létalité mobile)
            # Un humain a moins de "réserves" qu'une ville
            if RandomService.random() < 0.05: # 15% de chance de mourir par tour
                entity.is_expired = True
                GameLogger.log(Translator.translate("events.human_epidemic_death", name=entity.name))
                return

            # 3. Chance de guérison (Système immunitaire)
            if RandomService.random() < 0.05:
                entity.is_infected = False
                entity.infection_turns = 0

        # --- CAS 2 : L'ENTITÉ EST UNE CITÉ (Ton code original adapté) ---
        else:
            # On garde ta logique de mortalité de masse
            mortality_rate = 0.22
            deaths = int(entity.infected_count * mortality_rate)
            entity.population -= deaths
            entity.infected_count -= deaths

            # Propagation interne
            transmission_rate = 0.4
            new_cases = int(entity.infected_count * transmission_rate)
            entity.infected_count = min(entity.population, entity.infected_count + new_cases)

            # Courbe de guérison
            cure_chance = 0.01 if entity.infection_turns < 20 else 0.01 + ((entity.infection_turns - 20) * 0.005)

            if RandomService.random() < cure_chance or entity.infected_count <= 0:
                entity.is_infected = False
                entity.infected_count = 0
                GameLogger.log(Translator.translate("events.epidemic_end", name=entity.name))

            # Ruines
            if entity.population <= 10:
                ruin = Ruins(entity.x, entity.y, entity.culture, entity.config, entity.name)
                world['entities'].add(ruin)
                entity.is_expired = True
                GameLogger.log(Translator.translate("events.epidemic_death", name=entity.name))