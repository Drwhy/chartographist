import random
import math
from entities.actor import Actor
from core.logger import GameLogger

class Animal(Actor):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, culture, config)
        self.species = species_data['species']
        self.char = species_data['char']
        self.type = "animal"
        self.target = None
        self.perception_range = 5 # Rayon de détection

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
        """Se déplace d'une case vers la cible."""
        if not self.target: return

        tx, ty = self.target.pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0

        nx, ny = self.x + dx, self.y + dy

        # Vérification des limites et de l'élévation (pas d'eau pour les terrestres)
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0:
                self.pos = (nx, ny)

        # Si on est sur la même case que la cible : ATTAQUE
        if self.pos == self.target.pos:
            self._attack_target(world)

    def _attack_target(self, world):
        if not self.target or self.target.is_expired: return

        # Si la cible est un Chasseur, il se défend !
        if getattr(self.target, 'char', '') == "🏹":
            defense_roll = random.random()

            if defense_roll < 0.4: # 40% de chance que le chasseur gagne au corps-à-corps
                self.is_expired = True
                msg = f"🗡️ {self.target.char} a terrassé le {self.species} au corps-à-corps !"
                GameLogger.log(msg)
                return
            elif defense_roll < 0.6: # 20% de chance de match nul (les deux fuient)
                msg = f"🏃 Combat acharné ! Le {self.species} et le chasseur se sont repliés."
                GameLogger.log(msg)
                self.target = None
                return

        # Sinon (ou si le chasseur rate sa défense), l'animal gagne
        self.target.is_expired = True
        msg = f"💀 {self.char} {self.species.capitalize()} a dévoré sa proie."
        GameLogger.log(msg)

    def _wander(self, world, valid_elev_range=(0.0, 1.0)):
            """Mouvement aléatoire restreint par l'élévation."""
            # On choisit une direction au hasard (-1, 0, ou 1)
            dx, dy = random.randint(-1, 1), random.randint(-1, 1)
            nx, ny = self.x + dx, self.y + dy

            # 1. Vérification des limites de la carte
            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                h = world['elev'][ny][nx]

                # 2. Vérification du biome (élévation)
                low, high = valid_elev_range
                if low <= h <= high:
                    self.pos = (nx, ny)