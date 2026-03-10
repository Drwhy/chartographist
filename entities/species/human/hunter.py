import math
from .base import Human
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService
from entities.registry import WILD_SPECIES
from core.translator import Translator

@register_civ
class Hunter(Human):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        super().__init__(x, y, culture, config, 1.1)
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
        self.perception_range = 10
        self.fear_sensitivity = 2.5
    def _update_status(self):
        """Ajuste l'apparence et la vitesse selon la charge."""
        if self.has_game:
            self.char = self.meat_transportation_char
            self.speed = 0.7  # Le chasseur est ralenti par le poids du gibier
        else:
            self.char = self.land_char
            self.speed = 1.1  # Vitesse de traque normale
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
            msg = Translator.translate(
                            "events.hunter_mission_success",
                            hunter_name=self.name,
                            species=entity.species,
                            hunter_city_name=self.home_city.name
                        )
        else:
            msg = Translator.translate(
                "events.hunter_secure_city",
                hunter_name=self.name,
                species=entity.species,
                hunter_city_name=self.home_city.name
            )

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
        GameLogger.log(
            Translator.translate(
                "events.hunt_food_delivery",
                hunter_name=self.name,
                hunter_city_name=self.home_city.name,
                new_pop=boost
            )
        )

    def _find_prey(self, world):
            """Cherche une proie réelle ou suit les traces sur la Heatmap."""
            # 1. On cherche d'abord une proie visible
            potential_preys = [
                e for e in world['entities']
                if type(e) in WILD_SPECIES
                and not e.is_expired
                and getattr(e, 'is_edible', False)
                and not getattr(e, 'is_flying', False)
            ]

            if potential_preys:
                # On évalue la meilleure cible (Distance vs Danger autour d'elle)
                best_target = None
                max_score = -float('inf')

                for prey in potential_preys:
                    dist = math.dist(self.pos, prey.pos)
                    if dist > self.perception_range: continue

                    # On récupère le danger à la position de la proie
                    fear_at_target = world['influence'].get_fear(prey.x, prey.y)

                    # Score : Proximité + Sécurité (on n'attaque pas un cerf à côté d'un ours)
                    score = (1 - (dist / self.perception_range)) + (fear_at_target * 2.0)

                    if score > max_score:
                        max_score = score
                        best_target = prey

                self.target_prey = best_target

    def _move_towards(self, target_pos, world):
        """Se déplace vers une cible en évitant les obstacles et le danger."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        min_dist = math.dist(self.pos, target_pos)
        max_safety = -float('inf')

        for nx, ny in possible_moves:
            d = math.dist((nx, ny), target_pos)
            safety = world['influence'].get_fear(nx, ny)

            # On cherche à réduire la distance tout en restant en sécurité
            # Si la case est mortelle (lave), safety sera -10, ce qui disqualifie la case
            if safety > -5.0: # Seuil de survie
                if d < min_dist:
                    min_dist = d
                    best_move = (nx, ny)

        self.pos = best_move

    def _wander(self, world):
        """Erre intelligemment en suivant les odeurs (Scent) et fuyant la peur."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        scored_moves = []
        for nx, ny in possible_moves:
            # On lit les deux grilles
            fear = world['influence'].get_fear(nx, ny)
            scent = world['influence'].get_scent(nx, ny)

            # Un chasseur est attiré par le scent (odeur de gibier)
            # Mais repoussé par la peur (danger mortel)
            score = (fear * self.fear_sensitivity) + (scent * 1.5)

            scored_moves.append(((nx, ny), score + RandomService.random() * 0.2))

        # On choisit la meilleure case (la plus riche en traces ou la plus sûre)
        self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def get_defense_power(self):
        """Hunter is armed and dangerous"""
        return 0.6 # Sa base de défense
    @property
    def danger_level(self):
        return 0.5  # Très effrayant