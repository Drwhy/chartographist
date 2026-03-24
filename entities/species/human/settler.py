import math
from .base import Human
from core.logger import GameLogger
from entities.constructs.village import Village
from history.history_engine import connect_with_road
from entities.registry import register_civ
from core.random_service import RandomService
from entities.registry import STRUCTURE_TYPES
from core.translator import Translator

@register_civ
class Settler(Human):
    def __init__(self, x, y, culture, config, home_city=None):
        # Strictly following the Actor parameter order
        super().__init__(x, y, culture, config, 1)
        self.char = culture.get("settler_emoji", "🚶")
        self.home_city = home_city
        self.group_size = home_city.settler_cost
        self.distance_traveled = 0
        self.min_distance_from_home = 20
        self.max_travel_time = 120
        # Survival parameters
        self.fear_sensitivity = 4.0  # Very cautious: carries the future of the city
        self.perception_range = 10
        # --- Emergence: Group Power ---
        # A higher danger level discourages small predators
        self.danger = 0.5 + (self.group_size * 0.02)
    def think(self, world):
        """Reflection phase: is the settler looking for a spot or fleeing?"""
        if self.is_expired: return

        # The settler does not have a fixed "target"; the goal is the best local score
        self.distance_traveled += 1

        # If too old or lost in a sterile zone
        if self.distance_traveled > self.max_travel_time:
            self.is_expired = True
            GameLogger.log(Translator.translate("events.settler_lost", settler_city_name=self.home_city.name))

    def perform_action(self, world):
        """Movement and foundation phase."""
        # 1. Attempt to found a village if far enough from home
        if self.distance_traveled > self.min_distance_from_home:
            if self._is_ideal_spot(world):
                self._found_village(world)
                return

        # 2. Smart movement (Heatmap-driven)
        self._move_smart(world)

    def _move_smart(self, world):
        """Moves by maximizing safety, potential, and social distance."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        scored_moves = []
        for nx, ny in possible_moves:
            # 1. Classical factors (Fear, Scent, Geography)
            fear = world['influence'].get_fear(nx, ny)
            scent = world['influence'].get_scent(nx, ny)
            h = world['elev'][ny][nx]
            is_river = world['riv'][ny][nx] > 0
            geo_score = (0.5 if is_river else 0) + (0.3 if 0.2 < h < 0.6 else 0)

            # 2. SOCIAL REPULSION ("Communication")
            # Calculate discomfort caused by existing structures
            social_repulsion = 0
            for e in world['entities']:
                if type(e) in STRUCTURE_TYPES and not e.is_expired:
                    dist = math.dist((nx, ny), e.pos)
                    # If too close to a city (less than 15 tiles),
                    # generate a heavy penalty to push the settler further away
                    if dist < 15:
                        social_repulsion += (15 - dist) * 0.5
                if isinstance(e, Settler) and e != self:
                    if math.dist((nx, ny), e.pos) < 5:
                        social_repulsion += 2.0

            # 3. FINAL SCORE
            # Social repulsion is subtracted so the settler flees crowded areas
            score = (fear * self.fear_sensitivity) + (scent * 1.5) + geo_score - social_repulsion

            # Exploration bias: the more they travel, the more they are pushed from the source
            dist_to_home = math.dist((nx, ny), self.home_city.pos) if self.home_city else 0
            exploration_push = (dist_to_home / 50) # Increase influence of distance

            scored_moves.append(((nx, ny), score + exploration_push + RandomService.random() * 0.1))

        self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def _is_ideal_spot(self, world):
        """
        Determines if the tile is valid for founding a village.
        Criteria: No water, no peaks, no urban proximity.
        """
        h = world['elev'][self.y][self.x]

        # 1. GEOGRAPHICAL RULES (0 = Beach, 0.85 = High mountain)
        if not (0 <= h <= 0.85):
            return False

        # 2. NEIGHBORHOOD VALIDATION (Registry & Proximity)
        for e in world['entities']:
            if e.is_expired: continue

            # Prevents spawning two entities at the exact same location
            if e.pos == self.pos and e != self:
                return False

            # DISTANCE RULE: No other structure within a radius of 8
            if type(e) in STRUCTURE_TYPES:
                if math.dist(self.pos, e.pos) < 8:
                    return False

        # 3. FOUNDATION PROBABILITY
        # A river (riv > 0) makes the terrain much more attractive
        is_near_river = world['riv'][self.y][self.x] > 0
        chance = 0.25 if is_near_river else 0.08

        return RandomService.random() < chance

    def _found_village(self, world):
        """Creates the village and traces the road to the mother city."""
        new_village = Village(self.x, self.y, self.culture, self.config)
        world['entities'].add(new_village)

        if self.home_city:
            connect_with_road(
                world['road'],
                self.home_city.pos,
                self.pos,
                world['width'],
                world['height']
            )
            GameLogger.log(Translator.translate("events.settler_found_village",
                                              new_village_char=new_village.char,
                                              new_village_name=new_village.name,
                                              home_city_name=self.home_city.name))
        else:
            GameLogger.log(Translator.translate("events.settler_found_village_independant",
                                              new_village_char=new_village.char,
                                              new_village_name=new_village.name))

        self.is_expired = True