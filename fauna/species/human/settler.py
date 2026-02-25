from .base import Human

class Settler(Human):
    """
    Représente un groupe de colons en mouvement.
    Leur but unique est d'atteindre une coordonnée cible pour fonder un village.
    """
    def __init__(self, start_pos, target_pos, culture_dict):
        # Initialise la position, la culture et l'état de vie via la classe mère
        super().__init__(start_pos, culture_dict)

        self.target = target_pos
        self.reached = False

        # Récupération dynamique de l'apparence depuis le template.json
        # Si 'settler_emoji' n'existe pas dans la culture, on utilise 🏃 par défaut.
        self.char = culture_dict.get("settler_emoji", "🏃")

    def update(self):
        """
        Logique de cycle de vie du colon.
        À chaque tour, il avance vers sa destination.
        """
        if not self.reached:
            self.move_towards(self.target)

            # Vérification de l'arrivée à destination
            if self.current_pos == self.target:
                self.reached = True

    def __repr__(self):
        return f"Settler({self.culture['name']} @ {self.current_pos} -> {self.target})"