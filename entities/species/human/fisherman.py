import math
from .base import Human
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

@register_civ
class Fisherman(Human):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        # Initialization via Actor (handles culture and config)
        super().__init__(x, y, culture, config, 1)
        # Identity attributes
        self.home_pos = home_pos
        self.home_city = home_city
        # Visuals (Emojis)
        self.land_char = culture.get("fisherman_emoji", "🎣")
        self.boat_char = culture.get("boat_emoji", "🛶")
        self.char = self.land_char
        # Business logic
        self.target = None
        self.fishing_cooldown = 0
        self._base_perception = 12  # Good view of the sea horizon
        self.fear_sensitivity = 4.0 # Very cautious (a small boat sinks fast!)

    @property
    def perception_range(self):
        return self._base_perception + int(self.faith_bonus("perception")) + int(self.species_trait("perception"))

    def think(self, world):
        """Decision phase (Brain)."""
        if self.fishing_cooldown > 0:
            self.fishing_cooldown -= 1
            return

        # 1. Visual update based on terrain
        self._update_status(world)

        # 2. Search for target if necessary
        if not self.target or self.target.is_expired:
            self._find_best_fishing_spot(world)

    def perform_action(self, world):
        """Execution phase (Body)."""
        if self.fishing_cooldown > 0:
            return

        if self.target:
            dist = math.dist(self.pos, self.target.pos)
            # Fishing range (2 tiles)
            if dist <= 2.1:
                self._fish_action(world)
            else:
                self._move_towards_with_safety(self.target.pos, world)
        else:
            self._wander_on_coast(world)

    def _find_best_fishing_spot(self, world):
        """Searches for either a visible fish or a spot rich in aquatic 'Scent'."""
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

                # Evaluate spot safety (fear of sharks/lava)
                fear = world['influence'].get_fear(fish.x, fish.y)

                # Score = Proximity + Safety
                score = (1 - (dist / self.perception_range)) + (fear * 2.0)

                if score > max_score:
                    max_score = score
                    best_spot = fish

            self.target = best_spot

    def _move_towards_with_safety(self, target_pos, world):
        """Moves toward the fish while avoiding danger zones and deep abysses."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        max_score = -float('inf')

        for nx, ny in possible_moves:
            dist_to_target = math.dist((nx, ny), target_pos)
            fear = world['influence'].get_fear(nx, ny)

            # We want to reduce distance, but FEAR is a blocking multiplier
            # If fear < -1.0, we actively avoid the tile
            score = (1 - (dist_to_target / 50)) + (fear * self.fear_sensitivity)

            if score > max_score:
                max_score = score
                best_move = (nx, ny)

        self.pos = best_move

    def _wander_on_coast(self, world):
        """If no fish, follows fish scents (Scent) along the coasts."""
        possible_moves = self._get_accessible_neighbors(world)
        scored_moves = []

        for nx, ny in possible_moves:
            fear = world['influence'].get_fear(nx, ny)
            scent = world['influence'].get_scent(nx, ny)
            # The fisherman is attracted to areas where fish pass frequently
            score = (fear * self.fear_sensitivity) + (scent * 1.5)
            scored_moves.append(((nx, ny), score + RandomService.random() * 0.2))

        if scored_moves:
            self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def _fish_action(self, world):
        if self.target and not self.target.is_expired:
            self.target.is_expired = True
            self.fishing_cooldown = 15 # Slightly longer to simulate fishing time

            # Direct delivery via home_city reference
            boost = RandomService.randint(5, 12)
            # Faith harvest bonus
            boost = int(boost * (1 + self.faith_bonus("harvest") * 0.1))
            self.home_city.food_stock += boost

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
        """Determines if the fisherman is on foot or in a boat."""
        h = world['elev'][self.y][self.x]
        if h < 0:
            self.char = self.boat_char
        else:
            self.char = self.land_char

    @property
    def danger_level(self):
        return 0.3