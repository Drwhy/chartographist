# Échelle de priorité d'affichage (Z-Index)
# Plus la valeur est élevée, plus l'entité s'affiche "au-dessus" des autres.
Z_FLOOR = 0      # Biomes, Eau (géré par le moteur de rendu)
Z_DECOR = 10     # Routes, Ruines, Arbres morts
Z_CONSTRUCT = 20 # Villes, Villages, Ports
Z_ANIMAL = 30    # Loups, Ours, Poissons
Z_HUMAN = 40     # Chasseurs, Pêcheurs, Colons
Z_EFFECT = 50    # Sang, Explosions, Fumée

class Entity:
    def __init__(self, x, y, char, z_index):
        # On utilise une liste interne pour la mutabilité,
        # mais on expose une propriété pour la sécurité.
        self._pos = [x, y]
        self.char = char
        self.is_expired = False # Sera utilisé pour supprimer l'entité proprement
        self.z_index = z_index #height on the map
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
    def update(self, world, stats):
            """À définir dans les classes filles (Hunter, Wolf, etc.)"""
            if self.is_expired:
                return

            # 1. On réfléchit (trouver une proie, etc.)
            self.think(world)

            # 2. On agit (bouger, attaquer)
            self.perform_action(world)
    def think(self, world):
        """À définir dans les classes filles (Hunter, Wolf, etc.)"""
        pass

    def perform_action(self, world):
        """À définir dans les classes filles"""
        pass
    def get_defense_power(self):
        """By default no defense"""
        return 0.0
    @property
    def is_edible(self):
        """Par défaut, une entité n'est pas comestible (ex: rochers, bâtiments)."""
        return False
    @property
    def danger_level(self):
        """0.0 = Inoffensif, >0.5 = Effrayant pour les proies."""
        return 0.0
    def is_in_water(self, world):
        """Vérifie si l'entité est sur une case d'élévation négative."""
        return world['elev'][self.y][self.x] < 0
    @property
    def food_value(self):
        """Valeur de croissance apportée à la cité. 0 par défaut."""
        return 0
    @property
    def is_flying(self):
        """Par défaut, personne ne vole."""
        return False
    @property
    def is_aquatic(self):
        """Par défaut, les entités ne sont pas purement aquatiques."""
        return False
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
    def remove(self, entity):
        """Supprime une entité de la collection."""
        if entity in self.entities: # En supposant que tu stockes dans self.entities
            self.entities.remove(entity)
    def __iter__(self):
        return iter(self.entities)

    def __len__(self):
        return len(self.entities)
