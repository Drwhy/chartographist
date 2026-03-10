from core.naming import NameGenerator
from core.random_service import RandomService
from core.entities import Entity, Z_CONSTRUCT
from core.logger import GameLogger
from core.translator import Translator

class Construct(Entity):
    """Base pour tout ce qui est bâti sur la carte."""
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, "?", Z_CONSTRUCT, 1)
        self.pos = (x, y)
        self.culture = culture
        self.original_culture = culture
        self.ticks_since_founded = 0
        self.stability = 1.0
        self.config = config
        self.species = "construct"
        self.is_expired = False
        self.char = "?"
        self.name = NameGenerator.generate_place_name(culture)
    def update(self, world, stats):
        """Méthode à surcharger dans les sous-classes."""
        pass
    def _check_cultural_drift(self, world):
        """Calcule si le village décide de changer de culture."""
        from entities.constructs.ruins import Ruins
        if self.is_expired or isinstance(self, Ruins):
            return
        self.ticks_since_founded += 1
        # 1. Calcul de la distance à la capitale (home_city)
        # On part du principe que la distance affaiblit l'influence culturelle
        dist_to_origin = 0
        if hasattr(self, 'home_city') and self.home_city:
            dist_to_origin = math.dist(self.pos, self.home_city.pos)

        # 2. Facteurs de dérive : Temps + Distance
        # Chaque 1000 ticks et chaque 50 cases augmentent les chances
        drift_chance = (self.ticks_since_founded / 5000) + (dist_to_origin / 500)

        # 3. Événement de mutation
        if RandomService.random() < drift_chance * 0.01: # Probabilité très faible par tick
            self._mutate_culture(world)

    def _mutate_culture(self, world):
        """Change la culture du village pour une autre au hasard."""
        from entities.constructs.city import City
        from entities.constructs.village import Village
        all_cultures = self.config['cultures']
        # On filtre pour ne pas reprendre la même
        new_culture = RandomService.choice([c for c in all_cultures if c['name'] != self.culture['name']])

        old_name = self.culture['name']
        self.culture = new_culture

        # On rafraîchit les visuels (Emojis)
        # --- MISE À JOUR VISUELLE PAR TYPE ---
        # On vérifie si l'instance est une Ville ou un Village pour choisir l'emoji
        if isinstance(self, City):
            self.char = self.culture.get('city', '🏙️')
        elif isinstance(self, Village):
            self.char = self.culture.get('village', '🏡')
        GameLogger.log(
            Translator.translate(
                "events.cultural_mutation",
                name=self.name,
                old_culture=old_name,
                new_culture=new_culture['name']
            )
        )