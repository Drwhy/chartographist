import math
from .base import Human
from entities.registry import register_civ
from core.discovery_service import DiscoveryService
from core.logger import GameLogger
from core.translator import Translator
from core.random_service import RandomService

@register_civ
class Trader(Human):
    def __init__(self, x, y, culture, config, home_city):
        super().__init__(x, y, culture, config, 1.2)
        self.home_city = home_city
        self.target_city = None
        self.char = culture.get("trader_emoji", "⚖️")

        # Risk management
        self.fear_sensitivity = 5.0  # High value = avoids danger at all costs
        self.perception_range = 5

    def think(self, world):
        if self.is_expired: return

        # Target selection: Find a city that isn't where I currently am
        if not self.target_city or self.target_city.is_expired:
            self._find_new_target(world)

    def perform_action(self, world):
        if not self.target_city:
            self._move_safely_random(world)
            return

        # Check if we have arrived (range of 1.5 to allow diagonal arrival)
        if math.dist(self.pos, self.target_city.pos) < 1.5:
            self._do_trade()
        else:
            self._move_smart(world)

    def _find_new_target(self, world):
        """Find the closest active city, excluding the current home."""
        all_cities = DiscoveryService.get_known_settlements(world)
        others = [c for c in all_cities if c != self.home_city and not c.is_expired]

        if others:
            # We still pick the closest for reliability
            self.target_city = min(others, key=lambda c: math.dist(self.pos, c.pos))
        else:
            self.target_city = None

    def _move_smart(self, world):
        """Move toward target while being repelled by the Fear Heatmap."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        max_score = -float('inf')

        for nx, ny in possible_moves:
            # 1. Distance Score (0 to 1 range approx)
            dist = math.dist((nx, ny), self.target_city.pos)
            dist_score = 1.0 / (dist + 0.1)

            # 2. Road Bonus (encourages staying on infrastructure)
            road_bonus = 0.5 if world['road'][ny][nx] != "  " else 0.0

            # 3. Fear Penalty (Uses the influence map)
            # fear is usually negative (e.g., -2.0 for danger)
            fear = world['influence'].get_fear(nx, ny)
            fear_score = fear * self.fear_sensitivity

            # Final Score
            score = dist_score + road_bonus + fear_score

            if score > max_score:
                max_score = score
                best_move = (nx, ny)

        self.pos = best_move

    def _do_trade(self):
        """Exchange population and swap home/target roles."""
        self.target_city.population += 2

        GameLogger.log(Translator.translate("events.trade_success",
            home_city=self.home_city.name,
            target_city=self.target_city.name,
            bonus=2))

        # The target city becomes my new home, and I clear target to find a new one
        self.home_city = self.target_city
        self.target_city = None

    def _move_safely_random(self, world):
        """Wander logic that still respects the fear map when idle."""
        moves = self._get_accessible_neighbors(world)
        if moves:
            # Pick the move with the least fear (highest fear score)
            self.pos = max(moves, key=lambda m: world['influence'].get_fear(m[0], m[1]))

    @property
    def danger_level(self):
        return 0.1 # Merchants are not dangerous