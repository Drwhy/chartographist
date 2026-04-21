import math
from .base import Human
from entities.registry import register_civ
from core.discovery_service import DiscoveryService
from core.logger import GameLogger
from core.translator import Translator
from core.random_service import RandomService
from core.religion import SyncreticReligion, _find_template
from history.history_engine import connect_with_road

@register_civ
class Trader(Human):
    def __init__(self, x, y, culture, config, home_city):
        super().__init__(x, y, culture, config, 1.2)
        self.home_city = home_city
        self.base_city = home_city  # permanent origin, used for return trips
        self.target_city = None
        self.char = culture.get("trader_emoji", "⚖️")

        self.fear_sensitivity = 5.0
        self.perception_range = 5
        self.visited_cities = set()
        self.trades_since_home = 0
        self._returning_home = False

    def think(self, world):
        if self.is_expired: return

        # Target selection: Find a city that isn't where I currently am
        if not self.target_city or self.target_city.is_expired:
            self._find_new_target(world)

    def perform_action(self, world):
        if not self.target_city:
            self._move_safely_random(world)
            return

        if math.dist(self.pos, self.target_city.pos) < 1.5:
            if self._returning_home:
                self._arrive_home()
            else:
                self._do_trade(world)
        else:
            self._move_smart(world)

    def _find_new_target(self, world):
        # After 3 trades away from base, head home to reset the route
        if self.trades_since_home >= 3 and not self._returning_home:
            if not self.base_city.is_expired and self.home_city != self.base_city:
                self._returning_home = True
                self.target_city = self.base_city
                return

        all_cities = DiscoveryService.get_known_settlements(world)
        others = [c for c in all_cities if c != self.home_city and not c.is_expired]

        if not others:
            self.target_city = None
            return

        # Prefer unvisited cities; fall back to all others when every city has been seen
        unvisited = [c for c in others if id(c) not in self.visited_cities]
        candidates = unvisited if unvisited else others

        # Score candidates: prefer medium distances over the nearest neighbour to
        # avoid the trader endlessly ping-ponging between the two closest cities.
        def city_score(c):
            d = math.dist(self.pos, c.pos)
            proximity = 1.0 / (1.0 + abs(d - 15) / 10.0)  # sweet spot ~15 tiles away
            return proximity + RandomService.random() * 0.3

        self.target_city = max(candidates, key=city_score)

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

    def _do_trade(self, world):
        """Exchange goods, spread religion, build roads, and move on."""
        trade_bonus = int(self.faith_bonus("trade")) + int(self.species_trait("trade"))
        food_delivered = 10 + trade_bonus
        self.target_city.food_stock += food_delivered

        GameLogger.log(Translator.translate("events.trade_success",
            home_city=self.home_city.name,
            target_city=self.target_city.name,
            bonus=trade_bonus))

        # --- Discovery & Road Building ---
        self._establish_connection(world)

        # --- Religion Spread ---
        self._spread_religion()

        self.visited_cities.add(id(self.target_city))
        self.trades_since_home += 1

        # Use the target city as the new departure point for the next leg
        self.home_city = self.target_city
        self.target_city = None

    def _arrive_home(self):
        """Reset the route after returning to base city."""
        self._returning_home = False
        self.trades_since_home = 0
        self.home_city = self.base_city
        self.visited_cities.clear()
        self.target_city = None

    def _establish_connection(self, world):
        """
        When a trader completes a route, both cities learn about each other.
        On first contact, a road is built connecting them.
        """
        home = self.home_city
        target = self.target_city

        # Both cities need the known_cities attribute (villages evolved to cities may lack it)
        if not hasattr(home, 'known_cities'):
            home.known_cities = set()
        if not hasattr(target, 'known_cities'):
            target.known_cities = set()

        home_id = id(home)
        target_id = id(target)

        # First contact: build a road
        if target_id not in home.known_cities:
            home.known_cities.add(target_id)
            target.known_cities.add(home_id)

            connect_with_road(
                world['road'],
                home.pos,
                target.pos,
                world['width'],
                world['height']
            )

            GameLogger.log(Translator.translate(
                "events.trade_road_built",
                home_city=home.name,
                target_city=target.name
            ))

    def _spread_religion(self):
        """Trader's faith influences the target city's demographics."""
        if not self.faith or not hasattr(self.target_city, 'religion'):
            return
        if not self.target_city.religion:
            return

        # Influence the target city's religion demographics
        target_dominant_before = self.target_city.religion.dominant
        self.target_city.religion.influence(self.faith.primary, strength=0.03)
        target_dominant_after = self.target_city.religion.dominant

        # Log if the dominant religion changed
        if target_dominant_before != target_dominant_after:
            GameLogger.log(Translator.translate(
                "events.religion_city_converts",
                name=self.target_city.name, religion=target_dominant_after
            ))

        # Small chance of trader adopting target city's faith
        if self.target_city.religion.dominant != self.faith.primary:
            if RandomService.random() < 0.1:  # 10% chance of faith adoption
                dominant = self.target_city.religion.dominant
                tmpl = _find_template(dominant)
                if tmpl:
                    # Check for syncretism: merge old and new faith
                    old_tmpl = _find_template(self.faith.primary)
                    if old_tmpl and RandomService.random() < 0.15:
                        syncretic = SyncreticReligion.create(old_tmpl, tmpl)
                        from core.religion import PersonalFaith
                        self.faith = PersonalFaith(syncretic)
                        GameLogger.log(Translator.translate(
                            "events.religion_trader_syncretism",
                            name=self.name, religion=syncretic["name"]
                        ))
                    else:
                        from core.religion import PersonalFaith
                        self.faith = PersonalFaith(tmpl)

    def _move_safely_random(self, world):
        """Wander logic that still respects the fear map when idle."""
        moves = self._get_accessible_neighbors(world)
        if moves:
            # Pick the move with the least fear (highest fear score)
            self.pos = max(moves, key=lambda m: world['influence'].get_fear(m[0], m[1]))

    @property
    def danger_level(self):
        return 0.1 # Merchants are not dangerous