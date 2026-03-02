from core.entities import Entity, Z_HUMAN
from core.naming import NameGenerator

class Human(Entity):
    def __init__(self, x, y, culture, config):
        # On initialise l'entité de base
        super().__init__(x, y, "?", Z_HUMAN)
        self.culture = culture # Le dictionnaire de la culture (ex: Empire)
        self.config = config   # Le template.json complet
        self.age = 0
        self.energy = 100
        self.is_dead = False
        self.species = 'human'
        if culture is not None:
            self.name = NameGenerator.generate_person_name(culture)
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
    @property
    def is_edible(self):
        return True
    @property
    def danger_level(self):
        return 0.2  #  pas Très effrayant