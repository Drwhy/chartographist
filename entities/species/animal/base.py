import math
from core.entities import Entity, Z_ANIMAL
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

class Animal(Entity):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, species_data['char'], Z_ANIMAL, species_data.get('speed', 1.0))
        self.pos = (x, y)
        self.species = species_data['species']
        self.char = species_data['char']
        self.name = species_data['name']
        self.target = None
        self.perception_range = 5 # Rayon de détection
        self.danger = 0.1
    @property
    def is_edible(self):
        return True
    @property
    def fear_sensitivity(self):
        return 5.0
    @property
    def diet(self):
        return "carnivore"
    def _find_target(self, world):
        """Orchestre la recherche de cible en combinant vision et instinct (Heat Map)."""
        potential_targets = []

        for entity in world['entities']:
            if self._is_valid_prey(entity):
                potential_targets.append(entity)

        # On évalue chaque cible potentielle pour trouver le meilleur ratio bénéfice/risque
        self.target = self._evaluate_best_choice(potential_targets, world)

    def _is_valid_prey(self, entity):
        """Filtre métier pour savoir si l'entité est une proie légitime."""
        if entity.is_expired or entity == self:
            return False
        if self.diet == "herbivore":
            return False
        # Sécurité : Pas de cannibalisme (via getattr pour la robustesse)
        if getattr(entity, 'species', None) == self.species:
            return False

        if not entity.is_edible:
            return False

        # Accessibilité selon le milieu (Terrestre, Aquatique, Volant)
        # 1. Si la proie vole et pas moi, impossible.
        if getattr(entity, 'is_flying', False) and not self.is_flying:
            return False

        # 2. Si la proie est aquatique et que je suis terrestre (ou inversement)
        # On vérifie si l'entité est dans l'eau via les tuiles du monde si nécessaire
        # Mais ici on se base sur les attributs de mouvement
        if getattr(entity, 'is_aquatic', False) and not self.is_aquatic and not self.is_flying:
            return False

        return math.dist(self.pos, entity.pos) <= self.perception_range

    def _evaluate_best_choice(self, targets, world):
        best_target = None
        max_score = -float('inf')

        # 1. On définit la tolérance au danger de l'entité
        # Plus l'entité est dangereuse elle-même, plus elle tolère l'influence négative
        # Un ours (0.9) sera beaucoup plus brave qu'une biche (0.1)
        courage_threshold = (self.danger_level * 10) - 15
        # Exemple :
        # Biche (0.1) -> Seuil à -14 (très prudente)
        # Ours (0.9)  -> Seuil à -6  (beaucoup plus brave)

        for target in targets:
            fear_val = world['influence'].get_fear(target.x, target.y)
            scent_val = world['influence'].get_scent(target.x, target.y)

            # Calcul du score...
            dist_score = 1 - (math.dist(self.pos, target.pos) / self.perception_range)
            total_score = dist_score + scent_val + (fear_val * self.fear_sensitivity)

            if total_score > max_score:
                max_score = total_score
                best_target = target

        # 2. VALIDATION FINALE : Indexée sur le danger_level
        # Si le meilleur choix reste en dessous de notre courage, on abandonne.
        if max_score < courage_threshold:
            return None

        return best_target

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
                GameLogger.log(Translator.translate("events.hunt_success", hunter_name=self.target.name, prey_name=self.name))
                return

            # MATCH NUL (Fuite)
            elif defense_roll > self.danger:
                GameLogger.log(Translator.translate("events.hunt_flee", hunter_name=self.target.name, prey_name=self.name))
                self.target = None
                return

        # --- CAS : LA CIBLE EST DÉVORÉE (Défense trop faible ou jet raté) ---
        self.target.is_expired = True
        GameLogger.log(Translator.translate("events.hunt_fail", hunter_name=self.name, prey_name=self.target.name))
        self.target = None

    def _wander(self, world):
        """Déplacement erratique mais guidé par la survie (Peur) et l'intérêt (Odeur)."""
        # 1. On récupère les cases où l'animal peut physiquement aller
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return

        scored_moves = []

        # On récupère la sensibilité à la peur (ex: 5.0 pour une biche, 1.0 pour un lion)
        fear_factor = getattr(self, 'fear_sensitivity', 2.0)

        for nx, ny in possible_moves:
            # 2. Lecture des deux couches de la Heatmap
            fear_val = world['influence'].get_fear(nx, ny)   # Valeur négative (Danger)
            scent_val = world['influence'].get_scent(nx, ny) # Valeur positive (Intérêt)

            # 3. Calcul du score de la case
            # La peur est multipliée par le fear_factor pour dominer le choix.
            # L'odeur (scent) attire l'animal vers les zones de confort.
            influence_score = (fear_val * fear_factor) + scent_val

            # 4. Ajout d'un "bruit" aléatoire (Random Bias)
            # Cela évite que les animaux ne restent figés ou ne suivent des lignes trop droites.
            random_bias = RandomService.random() * 0.3

            scored_moves.append(((nx, ny), influence_score + random_bias))

        # 5. Sélection du meilleur mouvement (le score le plus élevé)
        # Si fear_val est très bas (ex: -5.0), le score sera très faible,
        # forçant l'animal à s'éloigner de cette case.
        best_move = max(scored_moves, key=lambda m: m[1])[0]

        self.pos = best_move

    def _get_accessible_neighbors(self, world):
        """Filtre les cases adjacentes selon les capacités de l'animal."""
        accessible = []
        # On inclut la position actuelle (rester sur place est un choix valide)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = self.x + dx, self.y + dy

                # Limites de la carte
                if not (0 <= nx < world['width'] and 0 <= ny < world['height']):
                    continue

                if self._can_move_to(world,nx, ny):
                    accessible.append((nx, ny))
        return accessible

    def _can_move_to(self, world, nx, ny):
        """Vérifie les limites et le biome (Élévation)."""
        if not (0 <= nx < world['width'] and 0 <= ny < world['height']):
            return False

        elevation = world['elev'][ny][nx]
        water_limit = 0 # Seuil arbitraire terre/eau

        if self.is_flying: return True
        if self.is_aquatic: return elevation < water_limit
        return elevation >= water_limit

    def update(self, world, stats):
        self._think(world)
        self._perform_action(world)
    def _think(self, world):
            """Logique de décision : Chasse ou Errance ?"""
            # Si on a une cible mais qu'elle est morte ou trop loin, on l'oublie
            if self.target and (self.target.is_expired or math.dist(self.pos, self.target.pos) > self.perception_range):
                self.target = None

            # Si on n'a pas de cible, on en cherche une
            if not self.target:
                self._find_target(world)

    def _perform_action(self, world):
        """Exécution du mouvement ou de l'attaque."""
        if self.target:
            if self.pos == self.target.pos:
                self._attack_target(world)
            else:
                self._move_towards(self.target.pos, world)
        else:
            self._wander(world)

    def _move_towards(self, target_pos, world):
        """Déplacement intelligent vers une cible respectant le milieu."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0

        nx, ny = self.x + dx, self.y + dy

        # On vérifie si la case est praticable par cette espèce
        if self._can_move_to(world, nx, ny):
            self.pos = (nx, ny)
        else:
            # Si bloqué (ex: requin qui bute sur le rivage), on tente un petit détour
            self._wander(world)