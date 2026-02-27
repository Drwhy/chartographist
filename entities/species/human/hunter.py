import math
from entities.actor import Actor
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService

@register_civ
class Hunter(Actor):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        super().__init__(x, y, culture, config)
        self.char = culture.get("hunter_emoji", "🏹")
        self.home_pos = home_pos
        self.home_city = home_city
        self.target_prey = None
        self.type = "human"
        self.subtype = "hunter"
        self.land_char = culture.get("hunter_emoji", "🎣")
        self.meat_transportation_char = culture.get("food", "🍖")
        self.char = self.land_char
        # Nouvel état : transport de nourriture
        self.has_game = False
    def _update_status(self, world):
        """Détermine si le chasseur transporte de la nourriture."""

        if self.has_game:
            self.char = self.meat_transportation_char
        else:
            self.char = self.land_char
    def think(self, world):
        """Logique de décision du chasseur."""
        # Si le chasseur a déjà du gibier, son but unique est de rentrer
        if self.has_game:
            self._update_status(world)
            return

        # Sinon, il cherche à abattre une cible
        self._check_surroundings(world)

    def _check_surroundings(self, world):
        range_shot = 1

        for entity in world['entities']:
            if getattr(entity, 'type', '') == 'animal' and not entity.is_expired:
                # On ne chasse pas les volants (Aigles) selon notre règle
                if getattr(entity, 'is_flying', False):
                    continue

                dist = math.dist(self.pos, entity.pos)

                if dist <= range_shot:
                    if RandomService.random() < 0.4: # 40% de chance
                        entity.is_expired = True

                        # Si c'est une biche, on récupère le gibier
                        if getattr(entity, 'subtype', '') == 'deer':
                            self.has_game = True
                            self._update_status(world)
                            msg = f"🏹 {self.name} a abattu une biche ! Il rapporte la viande à {self.home_city.name}."
                        else:
                            # Si c'est un prédateur (loup/ours), on le tue juste pour la sécurité
                            msg = f"{self.char} {self.name} de {self.home_city.name} a éliminé un {entity.name} !"

                        GameLogger.log(msg)
                        self.target_prey = None
                        return

        if not self.target_prey:
            self._find_prey(world)

    def perform_action(self, world):
        """Exécution du mouvement ou de la livraison."""

        # 1. Retour au village si chargé
        if self.has_game:
            if self.pos == self.home_pos:
                self._deliver_food(world)
            else:
                self._move_towards(self.home_pos, world)
            return

        # 2. Chasse si une cible est en vue
        if self.target_prey:
            if self.target_prey.is_expired:
                self.target_prey = None
            else:
                self._move_towards(self.target_prey.pos, world)
        else:
            self._wander(world)

    def _deliver_food(self, world):
        """Livraison de la nourriture à la ville d'origine."""
        # On booste la population de la home_city (l'objet passé à l'init)
        boost = RandomService.randint(5, 12)
        self.home_city.population += boost

        # Reset de l'état
        self.has_game = False
        self._update_status(world)
        GameLogger.log(f"🏠 {self.name} est rentré. {self.home_city.name} gagne {boost} habitants grâce au gibier.")

    def _find_prey(self, world):
        """Cherche la biche la plus proche."""
        deers = [e for e in world['entities'] if getattr(e, 'subtype', '') == 'deer' and not e.is_expired]
        if deers:
            self.target_prey = min(deers, key=lambda d: math.dist(self.pos, d.pos))

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