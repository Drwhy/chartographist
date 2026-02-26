class Entity:
    def __init__(self, x, y, char):
        # On utilise une liste interne pour la mutabilité,
        # mais on expose une propriété pour la sécurité.
        self._pos = [x, y]
        self.char = char
        self.is_expired = False # Sera utilisé pour supprimer l'entité proprement

    @property
    def pos(self):
        """Retourne la position sous forme de tuple (x, y) pour le rendu."""
        return tuple(self._pos)

    @pos.setter
    def pos(self, value):
        """Permet de mettre à jour la position proprement."""
        self._pos = list(value)

    @property
    def x(self): return self._pos[0]

    @property
    def y(self): return self._pos[1]

class EntityManager:
    def __init__(self):
        self.entities = []

    def add(self, entity):
        if entity:
            self.entities.append(entity)

    def remove_dead(self):
            """Supprime définitivement les entités marquées comme expirées."""
            initial_count = len(self.entities)
            # On ne garde que les entités qui n'ont PAS is_expired à True
            self.entities = [e for e in self.entities if not getattr(e, 'is_expired', False)]

            # Optionnel : renvoyer le nombre de morts pour le log
            return initial_count - len(self.entities)

    def __iter__(self):
        return iter(self.entities)

    def __len__(self):
        return len(self.entities)
