from core.discovery_service import DiscoveryService
from core.logger import GameLogger
from core.translator import Translator
from core.random_service import RandomService
from entities.registry import register_civ, STRUCTURE_TYPES
from entities.constructs.ruins import Ruins
from .base import Human
import math

@register_civ
class Trader(Human):
    def __init__(self, x, y, culture, config, home_city):
        # The merchant is fast (1.2) as they often use pack animals
        super().__init__(x, y, culture, config, 1.2)
        self.home_city = home_city
        self.target_city = None
        self.inventory = 0
        self.max_capacity = 50
        self.char = culture.get("trader_emoji", "⚖️")
        self.visited_cities = [] # Short-term memory
        self.max_memory = 3
        self.fear_sensitivity = 5.0  # Very fearful, they carry riches!
        self.perception_range = 15

    def think(self, world):
        """Decides on the next commercial destination."""
        if self.is_expired: return

        # If no target city, look for one other than our current home
        if not self.target_city or self.target_city.is_expired:
            self._select_next_destination(world)

    def perform_action(self, world):
        """Moves between cities or performs a trade exchange."""
        if not self.target_city:
            self._wander_on_roads(world)
            return

        dist = math.dist(self.pos, self.target_city.pos)

        if dist < 1: # Arrived at destination
            self._trade_and_swap(world)
        else:
            self._move_smart_on_roads(world)

    def _move_smart_on_roads(self, world):
        """
        Movement favoring roads (speed) and avoiding danger.
        """
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        max_score = -float('inf')

        for nx, ny in possible_moves:
            # 1. Distance calculation toward the target
            dist_score = 1 - (math.dist((nx, ny), self.target_city.pos) / 100)

            # 2. Road bonus (a merchant prefers to stay on the pavement)
            road_bonus = 0.5 if world['road'][ny][nx] != "  " else 0

            # 3. Fear factor (Heatmap)
            fear = world['influence'].get_fear(nx, ny)

            score = dist_score + road_bonus + (fear * self.fear_sensitivity)

            if score > max_score:
                max_score = score
                best_move = (nx, ny)

        self.pos = best_move

    def _trade_and_swap(self, world):
        """Handles the trade exchange and plague propagation."""
        # Called when the merchant arrives at destination.

        # 1. TRADE TRANSMISSION : City -> Merchant
        # Check if the current city is infected
        city_is_plagued = getattr(self.target_city, 'is_infected', False)
        if city_is_plagued and not self.is_infected:
            if RandomService.random() < 0.3: # 30% chance to catch the plague
                self.is_infected = True

        # 2. TRADE TRANSMISSION : Merchant -> City
        elif self.is_infected and not city_is_plagued:
            if RandomService.random() < 0.5: # 50% chance to infect the city
                self.target_city.is_infected = True
                GameLogger.log(
                    Translator.translate("events.epidemic_spread",
                                       merchant_name=self.name,
                                       city_name=self.target_city.name)
                )

        # Boost the population of the visited city
        self.target_city.population += 2
        GameLogger.log(
            Translator.translate(
                "events.trade_success",
                home_city=self.home_city.name,
                target_city=self.target_city.name,
                bonus=2
            )
        )

        # Update memory
        self.visited_cities.append(self.target_city)
        if len(self.visited_cities) > self.max_memory:
            self.visited_cities.pop(0) # Forget the oldest entry

        # Swapping: the old target becomes the new home and vice-versa for the next leg
        old_home = self.home_city
        self.home_city = self.target_city
        self.target_city = old_home

        # Choose the next destination for the tour
        self._select_next_destination(world)

    def _wander_on_roads(self, world):
        """
        Wanders along roads if no city is found.
        Prioritizes road tiles to stay on commercial axes.
        """
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return

        scored_moves = []
        for nx, ny in possible_moves:
            # Random base score to avoid perfect back-and-forth loops
            score = RandomService.random() * 0.2

            # Road Bonus: If the tile contains a road, massively boost the score
            is_road = world['road'][ny][nx] != "  "
            if is_road:
                score += 2.0

            # Danger avoidance (Fear Heatmap)
            fear = world['influence'].get_fear(nx, ny)
            score += (fear * self.fear_sensitivity)

            scored_moves.append(((nx, ny), score))

        if scored_moves:
            self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def _select_next_destination(self, world):
        """The merchant consults the city registry to plan their route."""

        # 1. Access shared knowledge via service
        all_cities = DiscoveryService.get_known_settlements(world)

        # 2. Memory filtering (do not backtrack immediately)
        # Exclude current city and recently visited cities
        possible_targets = [
            c for c in all_cities
            if c != self.target_city and c not in self.visited_cities
        ]

        if not possible_targets:
            # If everything was visited or world is empty, go home
            self.visited_cities.clear()
            self.target_city = self.home_city
            return

        # Weighting by distance and opportunity (Population)
        scored_targets = []
        for city in possible_targets:
            dist = math.dist(self.pos, city.pos)
            # Closer is better, but favor larger cities
            score = (city.population / 100) / (dist + 1)
            scored_targets.append((city, score))

        # Roulette selection to maintain unpredictability
        total = sum(s for _, s in scored_targets)
        pick = RandomService.random() * total
        current = 0
        for city, score in scored_targets:
            current += score
            if current >= pick:
                self.target_city = city
                break