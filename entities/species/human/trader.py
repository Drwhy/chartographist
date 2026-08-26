import math
from copy import deepcopy
from .base import Human
from entities.registry import register_civ
from core.discovery_service import DiscoveryService
from core.economy import (
    economy_enabled,
    economy_settings,
    execute_food_trade,
    execute_material_trade,
)
from core.diplomacy import (
    diplomacy_enabled,
    record_trade,
    trade_allowed,
    trade_capacity_multiplier,
)
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

        from core.knowledge import KnowledgeService, knowledge_enabled
        knowledge_book = None
        if knowledge_enabled(self.config):
            knowledge_book = KnowledgeService(self.home_city, self.config)
            knowledge_book.observe(world)
            knowledge_book.observe_tile(world, self.pos)
            all_cities = knowledge_book.known_settlements(world)
        else:
            all_cities = DiscoveryService.get_known_settlements(world)
        others = [c for c in all_cities if c != self.home_city and not c.is_expired]

        if not others:
            self.target_city = None
            return

        # Prefer unvisited cities; fall back to all others when every city has been seen
        unvisited = [c for c in others if c.entity_id not in self.visited_cities]
        candidates = unvisited if unvisited else others

        # Score candidates: prefer medium distances over the nearest neighbour to
        # avoid the trader endlessly ping-ponging between the two closest cities.
        def city_score(c):
            d = math.dist(self.pos, c.pos)
            proximity = 1.0 / (1.0 + abs(d - 15) / 10.0)  # sweet spot ~15 tiles away
            if knowledge_book is not None:
                fact = knowledge_book.best_fact(
                    "settlement", c.entity_id, claim="state"
                )
                value = fact.get("value", {}) if isinstance(fact, dict) else {}
                ratio = (
                    float(value.get("food_ratio", 0.5))
                    if isinstance(value, dict) else 0.5
                )
                reliability = float(fact.get("reliability", 0.0)) if fact else 0.0
                return proximity + (1.0 - min(1.0, max(0.0, ratio))) * reliability
            return proximity + RandomService.random() * 0.3

        self.target_city = max(candidates, key=city_score)
        if knowledge_book is not None:
            fact = (
                knowledge_book.best_fact(
                    "settlement", self.target_city.entity_id, claim="state"
                )
                or knowledge_book.best_fact(
                    "settlement", self.target_city.entity_id
                )
            )
            if fact is not None:
                self.knowledge_decision = deepcopy(fact)

    def _move_smart(self, world):
        """Move toward target while being repelled by the Fear Heatmap."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return
        from core.pathfinding import PathfindingService, known_tiles_for
        pathfinder = PathfindingService(world, getattr(self, "config", {}))
        if pathfinder.enabled:
            route = pathfinder.find_path(
                self.pos,
                self.target_city.pos,
                known_tiles=known_tiles_for(self),
            )
            if route["reachable"] and len(route["path"]) > 1:
                next_tile = tuple(route["path"][1])
                if next_tile in possible_moves:
                    self.pos = next_tile
                    self.pathfinding_decision = {
                        "target": list(self.target_city.pos),
                        "next_tile": list(next_tile),
                        "cost": route["cost"],
                        "cache_hit": route["cache_hit"],
                    }
                    return

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
        """Echange des ressources, diffuse la foi, construit une route et repart."""
        trade_bonus = int(self.faith_bonus("trade")) + int(self.species_trait("trade"))
        related_ids = [self.home_city.entity_id, self.target_city.entity_id, self.entity_id]
        blocked = not trade_allowed(world, self.home_city, self.target_city)
        trade_succeeded = False

        if blocked:
            message = Translator.translate(
                "events.trade_blocked_by_war",
                home_city=self.home_city.name,
                target_city=self.target_city.name,
            )
        elif economy_enabled(self.home_city):
            base_capacity = int(economy_settings(self.home_city).get("trade_capacity", 10))
            multiplier = trade_capacity_multiplier(world, self.home_city, self.target_city)
            from core.institutions import settlement_policy_modifier
            multiplier *= settlement_policy_modifier(
                self.home_city,
                "trade_capacity_multiplier",
                default=1.0,
            )
            capacity = int(base_capacity * multiplier) + trade_bonus
            transaction = None
            from core.infrastructure import InfrastructureService
            capacity += int(
                InfrastructureService(
                    self.home_city, self.home_city.config
                ).effect("trade_capacity_bonus")
            )
            material_settings = self.home_city.config.get("materials", {})
            if material_settings.get("enabled") is True:
                food_chain = material_settings.get("food_chain", {})
                ration_id = food_chain.get("ration_good_id")
                if ration_id:
                    transaction = execute_material_trade(
                        self.home_city,
                        self.target_city,
                        ration_id,
                        capacity=capacity,
                    )
            if transaction is None or transaction.quantity <= 0:
                transaction = execute_food_trade(
                    self.home_city,
                    self.target_city,
                    capacity=capacity,
                )
            trade_succeeded = transaction.quantity > 0
            from core.simulation_metrics import SimulationMetrics
            metrics = SimulationMetrics(world)
            metrics.record_food("imported", transaction.quantity)
            metrics.record_activity(
                "economy", "transactions", int(transaction.quantity > 0)
            )
            if transaction.good_id != "food" and transaction.quantity > 0:
                metrics.record_material("trades")
                metrics.record_material(
                    "traded", transaction.quantity, good_id=transaction.good_id
                )
            if trade_succeeded:
                message = Translator.translate(
                    "events.trade_market_success",
                    home_city=self.home_city.name,
                    target_city=self.target_city.name,
                    quantity=transaction.quantity,
                    value=f"{transaction.value:.2f}",
                    price=f"{transaction.unit_price:.2f}",
                )
            else:
                message = Translator.translate(
                    "events.trade_no_surplus",
                    home_city=self.home_city.name,
                    target_city=self.target_city.name,
                )
        else:
            food_delivered = 10 + trade_bonus
            from core.food_balance import add_food
            delivered = add_food(
                self.target_city,
                world,
                food_delivered,
                source="legacy_trade",
                respect_capacity=False,
            )
            from core.simulation_metrics import SimulationMetrics
            SimulationMetrics(world).record_food("imported", delivered)
            trade_succeeded = True
            message = Translator.translate(
                "events.trade_success",
                home_city=self.home_city.name,
                target_city=self.target_city.name,
                bonus=trade_bonus,
            )

        if trade_succeeded:
            from core.characters import CharacterService, characters_enabled
            character_config = getattr(
                self, "config", getattr(self.home_city, "config", {})
            )
            if characters_enabled(character_config):
                from core.memory import MemoryBook
                MemoryBook(self, character_config).remember(
                    "trade",
                    cycle=int(world.get("cycle", 0)),
                    target_id=self.target_city.entity_id,
                    position=self.target_city.pos,
                    intensity=20.0,
                    reliability=1.0,
                    sentiment=1.0,
                )
                CharacterService(self, character_config).record_practice(
                    "commerce", 1.0
                )
            record_trade(world, self.home_city, self.target_city)

        GameLogger.log(
            message,
            category="diplomacy" if blocked else "economy",
            entity_ids=related_ids,
            position=self.target_city.pos,
        )

        if not blocked:
            self._establish_connection(world)
            self._spread_religion()
        self.visited_cities.add(self.target_city.entity_id)
        self.trades_since_home += 1
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

        home_id = home.entity_id
        target_id = target.entity_id

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
        from core.knowledge import KnowledgeService, knowledge_enabled
        if knowledge_enabled(getattr(home, "config", {})):
            home_book = KnowledgeService(home, home.config)
            target_book = KnowledgeService(target, target.config)
            home_facts = home_book.query()
            target_facts = target_book.query()
            cycle = int(world.get("cycle", 0))
            distance = math.dist(home.pos, target.pos)
            for observer_book, observer, subject in (
                (home_book, home, target),
                (target_book, target, home),
            ):
                observer_book.learn(
                    kind="settlement",
                    subject_id=subject.entity_id,
                    claim="state",
                    value={
                        "exists": True,
                        "name": str(getattr(subject, "name", "")),
                        "population": int(getattr(subject, "population", 0)),
                        "food_ratio": round(
                            max(0.0, float(getattr(subject, "food_stock", 0.0)))
                            / max(1.0, float(getattr(subject, "max_food", 1.0))),
                            6,
                        ),
                    },
                    cycle=cycle,
                    source_id=observer.entity_id,
                    source_type="observed",
                    reliability=1.0,
                    position=subject.pos,
                )
            home_book.transmit_to(
                target, cycle=cycle, distance=distance, facts=home_facts
            )
            target_book.transmit_to(
                home, cycle=cycle, distance=distance, facts=target_facts
            )


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