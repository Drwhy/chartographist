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
        Gère la progression de la maladie pour une entité spécifique (Cité ou Humain).
        """
        from entities.constructs.ruins import Ruins
        from entities.species.human.base import Human

        # Initialisation du compteur de tours
        if not hasattr(entity, 'infection_turns'):
            entity.infection_turns = 0
        entity.infection_turns += 1

        # --- CAS 1 : ENTITÉ HUMAINE MOBILE (Trader, Hunter, etc.) ---
        if isinstance(entity, Human):
            # 1. Émission de peur (Influence négative sur la heatmap)
            world['influence'].add_influence(entity.x, entity.y, -5.0, radius=1)

            # 2. Test de létalité pour l'individu
            if RandomService.random() < 0.05: # 5% de chance de mourir par tick
                entity.is_dead = True # On marque l'humain comme mort
                entity.is_expired = True # On retire l'entité de la carte
                GameLogger.log(Translator.translate("events.human_epidemic_death", name=entity.name))
                return

            # 3. Chance de guérison (Immunité)
            if RandomService.random() < 0.05:
                entity.is_infected = False
                entity.infection_turns = 0

        # --- CAS 2 : COLONIE / CITÉ / VILLAGE ---
        else:
            # 1. LOGIQUE DE MORTALITÉ MASSIVE
            mortality_rate = 0.22
            # Le nombre de morts dépend du nombre de malades actuels
            death_target = int(entity.infected_count * mortality_rate)

            deaths_occurred = 0
            if death_target > 0:
                # On tue des citoyens au hasard dans la liste
                # Note: On mélange pour ne pas tuer que les derniers arrivés (bébés)
                RandomService.shuffle(entity.citizens)

                # On retire les X premiers citoyens de la liste
                for _ in range(death_target):
                    if entity.citizens:
                        victim = entity.citizens.pop()
                        victim.is_dead = True # Optionnel pour tracking
                        deaths_occurred += 1

                # On met à jour le compte des infectés (certains infectés sont morts)
                entity.infected_count -= deaths_occurred

            # 2. TRANSMISSION INTERNE (Propagation dans les murs)
            # Plus il y a de monde, plus ça se propage vite
            transmission_rate = 0.4
            new_cases = int(entity.infected_count * transmission_rate)
            # Le nombre d'infectés ne peut pas dépasser la population réelle (len(citizens))
            entity.infected_count = min(len(entity.citizens), entity.infected_count + new_cases)

            # 3. COURBE DE GUÉRISON : Augmente avec le temps (immunité acquise)
            cure_chance = 0.01 if entity.infection_turns < 20 else 0.01 + ((entity.infection_turns - 20) * 0.005)

            if RandomService.random() < cure_chance or entity.infected_count <= 0:
                entity.is_infected = False
                entity.infected_count = 0
                GameLogger.log(Translator.translate("events.epidemic_end", name=entity.name))

            # 4. EFFONDREMENT TOTAL : Si la liste de citoyens est trop courte
            if len(entity.citizens) <= 3: # Seuil critique
                ruin = Ruins(entity.x, entity.y, entity.culture, entity.config, entity.name)
                world['entities'].add(ruin)
                entity.is_expired = True
                GameLogger.log(Translator.translate("events.epidemic_death", name=entity.name))