import random
import math
from entities.actor import Actor

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
            """Élimine la proie et consigne l'événement dans les logs."""
            if self.target:
                # 1. On récupère les identités pour le log
                predator_name = self.species.capitalize() # "Loup" ou "Ours"

                # On essaie de déterminer si c'est un chasseur ou un colon
                if hasattr(self.target, 'char'):
                    if self.target.char == "🏹":
                        prey_name = "un chasseur"
                    elif self.target.char == "🚶":
                        prey_name = "un colon"
                    else:
                        prey_name = f"une proie ({self.target.char})"
                else:
                    prey_name = "une proie"

                # 2. On tue la cible
                self.target.is_expired = True

                # 3. On génère le message de log
                msg = f"💀 {self.char} {predator_name} a tué {prey_name} en {self.pos}."

                if 'logs' in world.get('stats', {}):
                    world['stats']['logs'].append(msg)

                # 4. On réinitialise la cible
                self.target = None
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