import math
from .base import Human
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService
from entities.registry import WILD_SPECIES

@register_civ
class Hunter(Human):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        super().__init__(x, y, culture, config)
        self.char = culture.get("hunter_emoji", "🏹")
        self.home_pos = home_pos
        self.home_city = home_city
        self.target_prey = None
        self.land_char = culture.get("hunter_emoji", "🎣")
        self.meat_transportation_char = culture.get("food", "🍖")
        self.char = self.land_char
        # Nouvel état : transport de nourriture
        self.has_game = False
        self.range_shot = 2
    def _update_status(self):
        """Détermine si le chasseur transporte de la nourriture."""
        if self.has_game:
            self.char = self.meat_transportation_char
        else:
            self.char = self.land_char
    def think(self, world):
        """Logique de décision du chasseur."""
        # Si le chasseur a déjà du gibier, son but unique est de rentrer
        if self.has_game:
            self._update_status()
            return

        # Sinon, il cherche à abattre une cible
        self._check_surroundings(world)

    def _check_surroundings(self, world):
        """Vérifie si une proie sauvage est à portée de tir."""
        for entity in world['entities']:
            # 1. Filtre Registry : Uniquement les espèces sauvages
            if type(entity) not in WILD_SPECIES or entity.is_expired:
                continue

            # 2. Filtre comportemental : On ne tire pas sur ce qui vole
            if getattr(entity, 'is_flying', False):
                continue

            # 3. Vérification de la distance
            if math.dist(self.pos, entity.pos) <= self.range_shot:
                if RandomService.random() < 0.4:  # 40% de réussite
                    self._execute_kill(entity)
                    return

        # Si rien n'est à portée, on cherche une trace
        if not self.target_prey:
            self._find_prey(world)

    def _execute_kill(self, entity):
        """Gère la mort de la cible et stocke la valeur de nourriture si existante."""
        entity.is_expired = True

        # On récupère la valeur nutritive de l'entité
        reward = getattr(entity, 'food_value', 0)

        if reward > 0:
            self.has_game = True
            # On stocke la valeur pour la livraison future
            self.pending_food_boost = reward
            self._update_status()
            msg = f"🏹 {self.name} rapporte du gibier ({entity.species}) à {self.home_city.name}."
        else:
            msg = f"🛡️ {self.name} a éliminé une menace ({entity.species}) pour sécuriser {self.home_city.name}."

        GameLogger.log(msg)
        self.target_prey = None

    def perform_action(self, world):
        """Exécute les mouvements ou la livraison de nourriture."""
        # 1. État : Chargé de viande -> Retour à la maison
        if self.has_game:
            if self.pos == self.home_pos:
                self._deliver_food(world)
            else:
                self._move_towards(self.home_pos, world)
            return

        # 2. État : En chasse -> Poursuite de la cible
        if self.target_prey:
            if self.target_prey.is_expired:
                self.target_prey = None
            else:
                self._move_towards(self.target_prey.pos, world)
        else:
            # Errance si aucune proie n'est détectée
            self._wander(world)

    def _deliver_food(self, world):
        """Dépose le gibier au village, augmentant sa population."""
        boost = RandomService.randint(5, 12)
        self.home_city.population += boost

        self.has_game = False
        self._update_status()
        GameLogger.log(f"🏠 {self.name} a livré de la viande. {self.home_city.name} gagne {boost} habitants.")

    def _find_prey(self, world):
        """Cherche l'espèce sauvage comestible la plus proche."""
        potential_preys = [
            e for e in world['entities']
            if type(e) in WILD_SPECIES
            and not e.is_expired
            and getattr(e, 'is_edible', False)
            and not getattr(e, 'is_flying', False)
        ]

        if potential_preys:
            self.target_prey = min(potential_preys, key=lambda d: math.dist(self.pos, d.pos))

    def _move_towards(self, target_pos, world):
        """Se dirige vers une coordonnée cible."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0: # Ne marche pas sur l'eau
                self.pos = (nx, ny)

    def _wander(self, world):
        """Déplacement aléatoire."""
        dirs = [(0,1), (0,-1), (1,0), (-1,0)]
        dx, dy = RandomService.choice(dirs)
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0:
                self.pos = (nx, ny)
    def get_defense_power(self):
        """Hunter is armed and dangerous"""
        return 0.6 # Sa base de défense
    @property
    def danger_level(self):
        return 0.5  # Très effrayant