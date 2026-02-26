# entities/constructs/village.py
import random
from .base import Construct
from entities.registry import register_structure

@register_structure
class Village(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.char = culture.get("village", "🏘️")
        self.subtype = "village"

    def update(self, world, stats):
        # Logique d'évolution : Un village a une chance de devenir une Cité
        # On utilise une probabilité faible par tour
        if random.random() < 0.001:
            from .city import City # Import local pour éviter les boucles circulaires

            self.is_expired = True # On marque le village pour suppression

            # On crée la cité à la même position
            new_city = City(self.x, self.y, self.culture, self.config)
            world['entities'].add(new_city)

            if 'logs' in stats:
                stats['logs'].append(f"🏛️ {self.culture['name']} : Le village est devenu une cité.")