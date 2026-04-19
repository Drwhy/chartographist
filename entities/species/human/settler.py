import math
from .base import Human
from core.logger import GameLogger
from entities.constructs.village import Village
from history.history_engine import connect_with_road
from entities.registry import register_civ
from core.random_service import RandomService
from entities.registry import STRUCTURE_TYPES
from core.translator import Translator
from core.religion import ReligionDemographics

@register_civ
class Settler(Human):
    def __init__(self, x, y, culture, config, home_city=None):
        # Strictly following the Actor parameter order
        super().__init__(x, y, culture, config, 1)
        self.land_char = culture.get("settler_emoji", "🚶")
        self.boat_char = culture.get("boat_emoji", "🛶")
        self.char = self.land_char
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
    def _get_accessible_neighbors(self, world):
        """
        Override: settlers can traverse shallow water (boats).
        Allows coastal tiles and shallow seas (elev > -0.4) but not deep ocean.
        """
        neighbors = []
        for dx, dy in [(0,0), (0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                h = world['elev'][ny][nx]
                # Land OR shallow water (not deep ocean)
                if h > -0.4:
                    neighbors.append((nx, ny))
        return neighbors

    def _update_terrain_status(self, world):
        """Switch appearance and speed based on land vs water."""
        h = world['elev'][self.y][self.x]
        if h < 0:
            self.char = self.boat_char
            self.speed = 0.6  # Slower at sea
        else:
            self.char = self.land_char
            self.speed = 1.0

    def think(self, world):
        """Reflection phase: is the settler looking for a spot or fleeing?"""
        if self.is_expired: return

        self._update_terrain_status(world)

        self.distance_traveled += 1

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

            # Water penalty: settlers prefer land but can cross shallow seas
            if h < 0:
                geo_score = -0.5  # Penalty for being at sea
            else:
                geo_score = (0.5 if is_river else 0) + (0.3 if 0.2 < h < 0.6 else 0)

            # 2. SOCIAL REPULSION — use the spatial grid to avoid O(n) full scan
            social_repulsion = 0
            for e in world['grid'].get_nearby(nx, ny, 15):
                if e.is_expired:
                    continue
                if type(e) in STRUCTURE_TYPES:
                    dist = math.dist((nx, ny), e.pos)
                    if dist < 15:
                        social_repulsion += (15 - dist) * 0.5
                elif isinstance(e, Settler) and e is not self:
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

        # 2. NEIGHBORHOOD VALIDATION — spatial grid avoids O(n) full scan
        for e in world['grid'].get_nearby(self.x, self.y, 8):
            if e.is_expired or e is self:
                continue
            if e.pos == self.pos:
                return False
            if type(e) in STRUCTURE_TYPES and math.dist(self.pos, e.pos) < 8:
                return False

        # 3. FOUNDATION PROBABILITY
        # A river (riv > 0) makes the terrain much more attractive
        is_near_river = world['riv'][self.y][self.x] > 0
        chance = 0.25 if is_near_river else 0.08

        return RandomService.random() < chance

    def _found_village(self, world):
        """Creates the village and traces the road to the mother city."""
        new_village = Village(self.x, self.y, self.culture, self.config)

        # Transfer settler's faith as the founding religion
        if self.faith:
            new_village.religion = ReligionDemographics({self.faith.primary: 1.0})
            GameLogger.log(Translator.translate(
                "events.religion_village_founded",
                emoji=self.faith.emoji, name=new_village.name,
                religion=self.faith.primary
            ))

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