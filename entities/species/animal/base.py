import math
from core.entities import Entity, Z_ANIMAL
from core.logger import GameLogger
from core.random_service import RandomService

class Animal(Entity):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, species_data['char'], Z_ANIMAL)
        self.pos = (x, y)
        self.species = species_data['species']
        self.char = species_data['char']
        self.name = species_data['name']
        self.target = None
        self.perception_range = 5 # Rayon de détection
        self.danger = 0.1
    def _find_target(self, world):
        """Cherche une cible comestible, accessible et d'une autre espèce."""
        best_target = None
        min_dist = self.perception_range

        for entity in world['entities']:
            if entity.is_expired or entity == self:
                continue

            # 1. ACCESSIBILITÉ : Si la cible vole et que moi non, je ne peux pas l'attraper
            if entity.is_flying and not self.is_flying:
                continue

            # 2. SÉCURITÉ : Pas de cannibalisme
            if entity.species == self.species:
                continue

            # 3. FILTRE MÉTIER : Uniquement ce qui se mange
            if not entity.is_edible:
                continue

            dist = math.dist(self.pos, entity.pos)
            if dist < min_dist:
                min_dist = dist
                best_target = entity

        self.target = best_target

    def _approach_target(self, world):
        if not self.target: return

        # Mouvement vers la cible
        tx, ty = self.target.pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0

        nx, ny = self.x + dx, self.y + dy

        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            # On autorise le mouvement si c'est de la terre (h >= 0)
            # Sauf si l'animal est aquatique ou volant (à adapter selon tes besoins)
            if world['elev'][ny][nx] >= -0.1:
                self.pos = (nx, ny)

        if self.pos == self.target.pos:
            self._attack_target(world)

    def _attack_target(self, world):
        """Méthode de combat basée sur les capacités de défense de la cible."""
        if not self.target or self.target.is_expired:
            return

        defense_base = self.target.get_defense_power()

        # --- CAS : LA CIBLE PEUT SE DÉFENDRE (ex: Hunter) ---
        if defense_base > 0:
            defense_roll = RandomService.random()

            # VICTOIRE DE LA CIBLE (L'animal meurt)
            if defense_roll > (defense_base + self.danger / 2):
                self.is_expired = True
                GameLogger.log(f"🗡️ {self.target.name} a abattu un {self.name} !")
                return

            # MATCH NUL (Fuite)
            elif defense_roll > self.danger:
                GameLogger.log(f"🏃 {self.target.name} a repoussé le {self.name}.")
                self.target = None
                return

        # --- CAS : LA CIBLE EST DÉVORÉE (Défense trop faible ou jet raté) ---
        self.target.is_expired = True
        GameLogger.log(f"🍴 Un {self.name} a dévoré {self.target.name}.")
        self.target = None

    def _wander(self, world, valid_elev_range=(0.0, 1.0)):
            """Mouvement aléatoire restreint par l'élévation."""
            # On choisit une direction au hasard (-1, 0, ou 1)
            dx, dy = RandomService.randint(-1, 1), RandomService.randint(-1, 1)
            nx, ny = self.x + dx, self.y + dy
            # 1. Vérification des limites de la carte
            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                h = world['elev'][ny][nx]
                # 2. Vérification du biome (élévation)
                low, high = valid_elev_range
                if low <= h <= high:
                    self.pos = (nx, ny)

    def can_perceive(self, other):
            """
            Logique générique : un animal terrestre/aquatique ne peut pas
            percevoir (ou attaquer) un animal volant.
            """
            # Si la cible vole et que moi je ne vole pas, je l'ignore
            if getattr(other, 'is_flying', False) and not self.is_flying:
                return False

            # Un animal purement terrestre ignore ce qui est purement aquatique
            # (et inversement), sauf cas particulier (ex: l'ours qui pêche).
            return True
    @property
    def is_edible(self):
        return True