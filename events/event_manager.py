from .event_registry import EVENT_CATALOG
from core.random_service import RandomService

class EventManager:
    @staticmethod
    def update(world, stats, config):
        for event in EVENT_CATALOG:
            event.tick(world, stats)
            # 1. Jet de dés basé sur la chance propre à l'événement
            if RandomService.random() < event.chance:
                # 2. Vérification des conditions spécifiques
                if event.condition(world, stats):
                    # 3. Explosion !
                    event.trigger(world, stats, config)