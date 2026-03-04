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

    def _update_infection(self, city, world):
        from entities.constructs.ruins import Ruins

        city.infection_turns += 1

        # 1. MORTALITÉ ACCRUE
        # On passe à 20-25% de décès chez les infectés à chaque tour
        mortality_rate = 0.22
        deaths = int(city.infected_count * mortality_rate)
        city.population -= deaths
        city.infected_count -= deaths

        # 2. PROPAGATION (Vitesse de contagion)
        transmission_rate = 0.4  # Un malade infecte 0.4 personne par tour
        new_cases = int(city.infected_count * transmission_rate)
        city.infected_count = min(city.population, city.infected_count + new_cases)

        # 3. RÉSORPTION RÉALISTE (La courbe en cloche)
        # Au lieu d'une montée linéaire immédiate, on rend la guérison rare au début.
        # On utilise une chance fixe très basse, qui n'augmente qu'après 20 tours.
        if city.infection_turns < 20:
           cure_chance = 0.01  # Quasi impossible de guérir au début
        else:
           # Augmente très lentement après le pic
           cure_chance = 0.01 + ((city.infection_turns - 20) * 0.005)

        # Tentative de guérison
        if RandomService.random() < cure_chance or city.infected_count <= 0:
           city.is_infected = False
           city.infected_count = 0
           GameLogger.log(Translator.translate("events.epidemic_end", name=city.name))

        # 4. TRANSFORMATION EN RUINES
        if city.population <= 10:
           ruin = Ruins(city.x, city.y, city.culture, city.config, city.name)
           world['entities'].add(ruin)
           city.is_expired = True
           GameLogger.log(Translator.translate("events.epidemic_death", name=city.name))