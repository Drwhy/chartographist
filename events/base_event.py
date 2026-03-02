class BaseEvent:
    name = "Base Event"
    chance = 0.001  # Probabilité par tour

    @staticmethod
    def condition(world, stats):
        """Vérifie si l'événement PEUT se produire."""
        return True

    @staticmethod
    def trigger(world, stats):
        """Exécute l'événement."""
        pass
    def tick(self, world, stats):
        """Optionnel : Logique de maintenance à chaque tour (ex: dissipation)."""
        pass