from .base import Animal
from entities.registry import register_wild
from core.random_service import RandomService

@register_wild
class Wolf(Animal):
    def __init__(self, x, y, culture, config, species_data):
        # C'est cette ligne qui crée self.target en appelant Animal.__init__
        super().__init__(x, y, culture, config, species_data)
        # Tu peux ensuite ajouter des spécificités au loup
        self.perception_range = 6 # Un loup a un meilleur flair que l'animal de base
        self.danger = 0.3
    @staticmethod
    def try_spawn(x, y, world, config):
        h = world['elev'][y][x]
        # Le loup aime la plaine (élévation entre 0.05 et 0.4)
        if 0.05 < h < 0.4:
            if RandomService.random() < 0.05: # 5% de chance de spawn si le terrain est bon
                # Récupère les data du template.json
                species_data = next((f for f in config['fauna'] if f['species'] == 'wolf'), None)
                return Wolf(x, y, None, config, species_data)
        return None
    @property
    def danger_level(self):
        return 0.6  # Très effrayant
    @property
    def food_value(self):
        return RandomService.randint(15, 20)