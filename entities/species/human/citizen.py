# entities/species/human/citizen.py
from core.random_service import RandomService

class Citizen:
    def __init__(self, name, age=20):
        self.name = name
        self.age = age
        self.is_dead = False
        self.hunger = 0
        self.experience = 0
        self.profession_label = "Citizen" # For UI/Logs

    def process_monthly_update(self):
        """Common biological logic for everyone."""
        self.age += (1/12)
        self.hunger += 5

        # Natural death risk
        if self.age > 50:
            if RandomService.random() < (self.age - 50) * 0.01:
                self.is_dead = True

    def work(self, city, world):
        """Base citizens provide basic labor (slow food gain)."""
        city.food_stock = min(city.max_food, city.food_stock + 1)
