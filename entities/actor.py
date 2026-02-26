from core.entities import Entity

class Actor(Entity):
    def __init__(self, x, y, culture, config):
        # On initialise l'entité de base
        super().__init__(x, y, char="?")
        self.culture = culture # Le dictionnaire de la culture (ex: Empire)
        self.config = config   # Le template.json complet
        self.age = 0
        self.energy = 100
        self.is_dead = False

    def update(self, world, stats):
        """La boucle de vie universelle d'un agent."""
        if self.is_dead or self.is_expired:
            return

        self.age += 1
        # 1. ANALYSE (Perception)
        # 2. DÉCISION (IA) -> self.think(world)
        # 3. ACTION (Mouvement/Interaction) -> self.perform_action(world)

        self.think(world)
        self.perform_action(world)

    def think(self, world):
        """À définir dans les classes filles (Hunter, Wolf, etc.)"""
        pass

    def perform_action(self, world):
        """À définir dans les classes filles"""
        pass