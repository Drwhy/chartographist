import math
from .base import Human
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

@register_civ
class Fisherman(Human):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        # Initialisation via Actor (gère culture et config)
        super().__init__(x, y, culture, config, 1)
        # Attributs d'identité
        self.home_pos = home_pos
        self.home_city = home_city
        # Visuels (Emojis)
        self.land_char = culture.get("fisherman_emoji", "🎣")
        self.boat_char = culture.get("boat_emoji", "🛶")
        self.char = self.land_char
        # Logique métier
        self.target = None
        self.fishing_cooldown = 0
        self.perception_range = 12  # Bonne vue sur l'horizon marin
        self.fear_sensitivity = 4.0 # Très prudent (une barque coule vite !)

    def think(self, world):
        """Phase de décision (Cerveau)."""
        if self.fishing_cooldown > 0:
            self.fishing_cooldown -= 1
            return

        # 1. Mise à jour visuelle selon le terrain
        self._update_status(world)

        # 2. Recherche de cible si nécessaire
        if not self.target or self.target.is_expired:
            self._find_best_fishing_spot(world)

    def perform_action(self, world):
        """Phase d'exécution (Corps)."""
        if self.fishing_cooldown > 0:
            return

        if self.target:
            dist = math.dist(self.pos, self.target.pos)
            # Portée de pêche (2 cases)
            if dist <= 2.1:
                self._fish_action(world)
            else:
                self._move_towards_with_safety(self.target.pos, world)
        else:
            self._wander_on_coast(world)

    def _find_best_fishing_spot(self, world):
        """Cherche soit un poisson visible, soit une zone riche en 'Scent' aquatique."""
        aquatic_preys = [
            e for e in world['entities']
            if getattr(e, 'is_edible', False) and getattr(e, 'is_aquatic', False) and not e.is_expired
        ]

        if aquatic_preys:
            best_spot = None
            max_score = -float('inf')

            for fish in aquatic_preys:
                dist = math.dist(self.pos, fish.pos)
                if dist > self.perception_range: continue

                # On évalue la sécurité du spot (peur des requins/lave)
                fear = world['influence'].get_fear(fish.x, fish.y)

                # Score = Proximité + Sécurité
                score = (1 - (dist / self.perception_range)) + (fear * 2.0)

                if score > max_score:
                    max_score = score
                    best_spot = fish

            self.target = best_spot

    def _move_towards_with_safety(self, target_pos, world):
        """Se déplace vers le poisson en évitant les zones de danger et les abysses."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        max_score = -float('inf')

        for nx, ny in possible_moves:
            dist_to_target = math.dist((nx, ny), target_pos)
            fear = world['influence'].get_fear(nx, ny)

            # On veut réduire la distance mais la PEUR est un multiplicateur de blocage
            # Si fear < -1.0, on évite activement la case
            score = (1 - (dist_to_target / 50)) + (fear * self.fear_sensitivity)

            if score > max_score:
                max_score = score
                best_move = (nx, ny)

        self.pos = best_move

    def _wander_on_coast(self, world):
        """Si pas de poisson, suit les odeurs de poisson (Scent) le long des côtes."""
        possible_moves = self._get_accessible_neighbors(world)
        scored_moves = []

        for nx, ny in possible_moves:
            fear = world['influence'].get_fear(nx, ny)
            scent = world['influence'].get_scent(nx, ny)
            # Le pêcheur est attiré par les zones où les poissons passent souvent
            score = (fear * self.fear_sensitivity) + (scent * 1.5)
            scored_moves.append(((nx, ny), score + RandomService.random() * 0.2))

        if scored_moves:
            self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def update(self, world, stats):
        if self.is_expired:
            return

        # 1. Gestion du repos après pêche
        if self.fishing_cooldown > 0:
            self.fishing_cooldown -= 1
            return

        # 2. Mise à jour de l'apparence selon le terrain
        self._update_status(world)

        # 3. Intelligence de recherche
        if not self.target or self.target.is_expired:
            self._find_prey_in_water(world)

        # 4. Action ou Déplacement
        if self.target:
            # --- MODIFICATION ICI : Portée de pêche augmentée à 2 cases ---
            dist_to_fish = math.dist(self.pos, self.target.pos)

            if dist_to_fish <= 2.1: # 2.1 pour couvrir les diagonales de 2 cases
                self._fish_action(world)
            else:
                self._move_logic(world, self.target.pos)
        else:
            self._idle_movement(world)
    def _fish_action(self, world):
        if self.target and not self.target.is_expired:
            self.target.is_expired = True
            self.fishing_cooldown = 15 # Un peu plus long pour simuler le temps de pêche

            # Livraison directe via la référence home_city
            boost = RandomService.randint(5, 12)
            self.home_city.population += boost

            self.target = None
            GameLogger.log(
                Translator.translate(
                    "events.fishing_success",
                    fisherman_char=self.char,
                    fisherman_name=self.name,
                    fisherman_city=self.home_city.name
                )
            )

    def _update_status(self, world):
        """Détermine si le pêcheur est à pied ou en barque."""
        h = world['elev'][self.y][self.x]
        if h < 0:
            self.char = self.boat_char
        else:
            self.char = self.land_char

    def _find_prey_in_water(self, world):
        """L'aigle cible n'importe quelle entité comestible aquatique."""

        # On cherche les entités qui sont :
        # 1. Comestibles
        # 2. Aquatiques
        # 3. Non expirées
        aquatic_preys = [
            e for e in world['entities']
            if getattr(e, 'is_edible', False)
            and e.is_aquatic
            and not e.is_expired
        ]

        if aquatic_preys:
            # L'aigle a une vue perçante, il prend la plus proche
            self.target = min(aquatic_preys, key=lambda p: math.dist(self.pos, p.pos))
        else:
            self.target = None

    def _move_logic(self, world, target_pos):
        """Avance vers la cible (Terre ou Eau peu profonde)."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            h = world['elev'][ny][nx]
            # ACCÈS : Terre ferme OU Eau peu profonde (>-0.4)
            if h > -0.4:
                self.pos = (nx, ny)
            # Si c'est des abysses (<-0.4), il ne bouge pas (sécurité)

    def _idle_movement(self, world):
        """Flânerie côtière en attendant que le poisson morde."""
        dx, dy = RandomService.choice([(0,1), (0,-1), (1,0), (-1,0), (0,0)])
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] > -0.4:
                self.pos = (nx, ny)

    @property
    def danger_level(self):
        return 0.3  # Très effrayant