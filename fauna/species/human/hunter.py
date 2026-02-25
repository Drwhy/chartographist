import math
import random
from .base import Human

class Hunter(Human):
    def __init__(self, start_pos, culture_dict):
        super().__init__(start_pos, culture_dict)
        self.char = culture_dict.get("hunter_emoji", "🏹")
        self.home_pos = start_pos
        self.target_prey = None
        self.age = 0
        self.perception_range = 8

        # Nouveaux états pour le repos
        self.is_resting = False
        self.rest_timer = 0

    def update(self, fauna_list, world_map):
        """
        Logique mise à jour avec repos au village et interdiction de l'eau.
        """
        self.age += 1

        # 1. GESTION DU REPOS
        if self.is_resting:
            self.rest_timer -= 1
            if self.rest_timer <= 0:
                self.is_resting = False
            return # Le chasseur ne bouge pas tant qu'il se repose

        # 2. DÉCISION DE RENTRER SE REPOSER
        # S'il est sur son village et n'a pas de proie, chance de faire une pause
        if self.current_pos == self.home_pos and not self.target_prey:
            if random.random() < 0.3: # 30% de chance de s'arrêter
                self.is_resting = True
                self.rest_timer = random.randint(5, 15) # Durée aléatoire
                return

        # 3. RECHERCHE DE PROIE
        if not self.target_prey:
            self.find_prey(fauna_list)

        # 4. MOUVEMENT (Cible ou Errance)
        target_dest = None
        if self.target_prey and self.target_prey in fauna_list:
            target_dest = getattr(self.target_prey, 'pos', None)
        else:
            self.target_prey = None
            # Errance vers un point aléatoire ou retour maison
            if random.random() < 0.2:
                target_dest = self.home_pos
            else:
                dx, dy = random.randint(-1, 1), random.randint(-1, 1)
                target_dest = (self.current_pos[0] + dx, self.current_pos[1] + dy)

        if target_dest:
            self.safe_move(target_dest, world_map)

    def safe_move(self, target, world_map):
        """Déplacement qui refuse d'aller sur l'eau."""
        # On calcule la prochaine position théorique
        next_x, next_y = self.current_pos
        tx, ty = target

        dx = 1 if tx > next_x else -1 if tx < next_x else 0
        dy = 1 if ty > next_y else -1 if ty < next_y else 0

        potential_x = next_x + dx
        potential_y = next_y + dy

        # Vérification des limites de la carte
        h, w = len(world_map), len(world_map[0])
        if 0 <= potential_x < w and 0 <= potential_y < h:
            # INTERDICTION DE L'EAU : On ne bouge que si l'élévation >= 0
            if world_map[potential_y][potential_x] >= 0:
                self.move_towards(target)
            else:
                # Si c'est de l'eau, on annule la cible pour ne pas rester bloqué
                self.target_prey = None

    def find_prey(self, fauna_list):
        best_dist = self.perception_range
        potential_target = None
        for animal in fauna_list:
            if getattr(animal, 'type', 'prey') != 'predator':
                # On ignore aussi les proies qui sont sur l'eau (ex: poissons/sharks)
                ax, ay = animal.pos
                dist = math.sqrt((ax - self.current_pos[0])**2 + (ay - self.current_pos[1])**2)
                if dist < best_dist:
                    best_dist = dist
                    potential_target = animal
        self.target_prey = potential_target