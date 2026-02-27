import math
from entities.actor import Actor
from core.logger import GameLogger
from core.random_service import RandomService

class Animal(Actor):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config)
        self._x = x
        self._y = y
        self.pos = (x, y)
        self.species = species_data['species']
        self.char = species_data['char']
        self.type = "animal"
        self.target = None
        self.perception_range = 5 # Rayon de détection
        self.danger = 0.1

    def _find_target(self, world):
        """Cherche l'entité la plus proche dans le rayon de perception."""
        best_target = None
        min_dist = self.perception_range + 1

        for entity in world['entities']:
            # Un animal ne s'attaque pas lui-même ou à sa propre espèce
            if entity == self or getattr(entity, 'species', None) == self.species:
                continue

            dist = math.dist(self.pos, entity.pos)
            if dist < min_dist:
                min_dist = dist
                best_target = entity

        self.target = best_target

    def _approach_target(self, world):
            """Se déplace vers la cible et gère la collision."""
            if not self.target: return

            tx, ty = self.target.pos
            dx = 1 if tx > self.x else -1 if tx < self.x else 0
            dy = 1 if ty > self.y else -1 if ty < self.y else 0

            # On utilise les coordonnées internes _x, _y pour éviter le bug de setter
            nx, ny = self._x + dx, self._y + dy

            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                if world['elev'][ny][nx] >= 0:
                    self._x, self._y = nx, ny
                    self.pos = (self._x, self._y)

            # Vérification si on a atteint la proie
            if self.pos == self.target.pos:
                # SÉCURITÉ : On ne dévore pas les bâtiments !
                if getattr(self.target, 'type', '') == 'construct':
                    self.target = None # On abandonne la cible, c'est un mur de pierre
                    return

                self._attack_target(world)

    def _attack_target(self, world):
        """Méthode de combat universelle : Victoire, Fuite ou Mort du chasseur."""
        if not self.target or self.target.is_expired:
            return

        # 1. CAS DU CHASSEUR : Duel de survie
        if getattr(self.target, 'subtype', '') == "hunter":
            defense_roll = RandomService.random()

            # --- RÉSULTAT A : VICTOIRE DU CHASSEUR ---
            # Il faut un excellent jet qui dépasse le danger
            if defense_roll > (0.6 + self.danger / 2):
                self.is_expired = True
                GameLogger.log(f"🗡️ {self.target.char} a abattu un {self.species} après un combat épique !")
                return

            # --- RÉSULTAT B : FUITE / MATCH NUL ---
            # Le jet est suffisant pour ne pas mourir, mais pas pour tuer
            elif defense_roll > self.danger:
                GameLogger.log(f"🏃 {self.target.char} a réussi à repousser le {self.species} et s'est replié.")
                self.target = None
                return

            # --- RÉSULTAT C : MORT DU CHASSEUR ---
            # Le jet est inférieur au danger de l'animal
            else:
                self.target.is_expired = True
                GameLogger.log(f"💀 Tragédie : {self.target.char} a été massacré par le {self.species}...")
                self.target = None
                return

        # 2. CAS DES AUTRES PROIES (Colons, autres animaux)
        # Ils n'ont aucune chance de défense, ils sont dévorés
        self.target.is_expired = True
        GameLogger.log(f"🍴 Un {self.species} a dévoré un {getattr(self.target, 'subtype', 'animal')}.")
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