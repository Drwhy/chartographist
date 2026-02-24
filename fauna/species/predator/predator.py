from fauna.animal import Animal


class Predator(Animal):
    def move(self, width, height, elevation, structures):
        # Un prédateur fait deux pas pour simuler la traque
        for _ in range(2):
            super().move(width, height, elevation, structures)
