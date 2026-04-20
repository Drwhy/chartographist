from .base import Human
from core.random_service import RandomService

class Farmer(Human):
    def __init__(self, x, y, culture, config, name=None, parents=None, age=20):
        # On passe tous les arguments requis à Human.__init__
        # Vitesse par défaut pour un fermier : 1.0
        super().__init__(x, y, culture, config, speed=1.0, name=name, parents=parents)

        # On ajuste l'âge si nécessaire (pour les fondateurs)
        self.age = age
        self.profession_label = "Farmer"
        self.experience = 0 # Initialisation de l'XP spécifique au métier

    def work(self, city, world):
        """Logique agricole avancée."""
        if self.is_dead:
            return

        # 1. Vérification de l'environnement (Les plaines sont idéales)
        # On utilise l'élévation pour simuler la fertilité
        tile_h = world['elev'][city.y][city.x]

        # Bonus de fertilité : Entre 0.1 et 0.3 d'élévation (Plaines/Vallées)
        fertility = 2.0 if 0.1 <= tile_h <= 0.3 else 1.0

        # 2. Production avec bonus d'Expérience + espèce
        xp_bonus = 1 + (self.experience * 0.1)
        species_bonus = 1 + self.species_trait("harvest") * 0.1
        yield_amount = int(4 * fertility * xp_bonus * species_bonus)

        # Ajout au stock de la cité (ne dépasse pas max_food)
        city.food_stock = min(city.max_food, city.food_stock + yield_amount)

        # 3. Gain d'XP spécifique (20% de chance par mois de travail)
        if RandomService.random() < 0.2:
            self.experience += 1