# entities/species/human/farmer.py
from .citizen import Citizen
from core.random_service import RandomService

class Farmer(Citizen):
    def __init__(self, name, age=20):
        super().__init__(name, age)
        self.profession_label = "Farmer"

    def work(self, city, world):
        """Advanced agricultural logic."""
        if self.is_dead: return

        # 1. Environment check (Plains are best)
        tile_h = world['elev'][city.y][city.x]
        fertility = 2.0 if 0.1 <= tile_h <= 0.3 else 1.0

        # 2. Production with Experience bonus
        yield_amount = int(4 * fertility * (1 + self.experience * 0.1))

        city.food_stock = min(city.max_food, city.food_stock + yield_amount)

        # 3. Specific XP gain for farmers
        if RandomService.random() < 0.2:
            self.experience += 1