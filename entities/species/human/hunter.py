import math
from .base import Human
from entities.registry import register_civ
from core.logger import GameLogger
from core.random_service import RandomService
from entities.species.animal.base import Animal
from core.translator import Translator

@register_civ
class Hunter(Human):
    def __init__(self, x, y, culture, config, home_pos, home_city):
        super().__init__(x, y, culture, config, 1.1)
        self.char = culture.get("hunter_emoji", "🏹")
        self.home_pos = home_pos
        self.home_city = home_city
        self.target_prey = None
        self.land_char = culture.get("hunter_emoji", "🏹")
        self.meat_transportation_char = culture.get("food", "🍖")
        self.char = self.land_char

        # New state: food transportation
        self.has_game = False
        self.range_shot = 2
        self._base_perception = 10
        self.fear_sensitivity = 2.5

    @property
    def perception_range(self):
        return self._base_perception + int(self.faith_bonus("perception"))

    def _update_status(self):
        """Adjusts appearance and speed based on the load."""
        if self.has_game:
            self.char = self.meat_transportation_char
            self.speed = 0.7  # The hunter is slowed down by the weight of the game
        else:
            self.char = self.land_char
            self.speed = 1.1  # Normal tracking speed

    def think(self, world):
        """Hunter decision logic."""
        # If the hunter already has game, his sole goal is to return home
        if self.has_game:
            self._update_status()
            return

        # Otherwise, he searches for a target to take down
        self._check_surroundings(world)

    def _check_surroundings(self, world):
        """Checks if wild prey is within firing range."""
        for entity in world['entities']:
            if not isinstance(entity, Animal) or entity.is_expired:
                continue
            if getattr(entity, 'is_flying', False):
                continue
            if math.dist(self.pos, entity.pos) <= self.range_shot:
                # Dangerous prey is harder to bring down with a single shot
                prey_danger = getattr(entity, 'danger_level', 0.0)
                kill_chance = 0.4 * (1.0 - prey_danger * 0.5)
                if RandomService.random() < kill_chance:
                    self._execute_kill(entity)
                    return

        if not self.target_prey:
            self._find_prey(world)

    def _execute_kill(self, entity):
        """Handles target death and stores food value if it exists."""
        entity.is_expired = True

        # Retrieve the entity's nutritional value
        reward = getattr(entity, 'food_value', 0)

        if reward > 0:
            self.has_game = True
            # Store the value for future delivery
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
        """Executes movement or food delivery."""
        # 1. State: Loaded with meat -> Return home
        if self.has_game:
            if math.dist(self.pos, self.home_pos) < 1.5:
                self._deliver_food(world)
            else:
                self._move_towards(self.home_pos, world)
            return

        # 2. State: Hunting -> Pursue target
        if self.target_prey:
            if self.target_prey.is_expired:
                self.target_prey = None
            else:
                self._move_towards(self.target_prey.pos, world)
        else:
            # Wander if no prey is detected
            self._wander(world)

    def _deliver_food(self, world):
        """Drops game at the village, increasing its population."""
        base = getattr(self, 'pending_food_boost', 0) or RandomService.randint(5, 12)
        boost = int(base * (1 + self.faith_bonus("harvest") * 0.1))
        self.home_city.food_stock += boost
        self.pending_food_boost = 0

        self.has_game = False
        self._update_status()
        GameLogger.log(
            Translator.translate(
                "events.hunt_food_delivery",
                hunter_name=self.name,
                hunter_city_name=self.home_city.name
            )
        )

    def _find_prey(self, world):
        """Searches for actual prey or follows scent trails on the heatmap."""
        potential_preys = [
            e for e in world['entities']
            if isinstance(e, Animal)
            and not e.is_expired
            and getattr(e, 'is_edible', False)
            and not getattr(e, 'is_flying', False)
        ]

        if not potential_preys:
            return

        # How urgently the city needs food: 0.0 = well-stocked, 1.0 = starving
        food_stock = getattr(self.home_city, 'food_stock', 50)
        need_level = max(0.0, 1.0 - min(food_stock, 100) / 100.0)

        best_target = None
        max_score = -float('inf')

        for prey in potential_preys:
            dist = math.dist(self.pos, prey.pos)
            if dist > self.perception_range:
                continue

            prey_danger = getattr(prey, 'danger_level', 0.0)

            # Only pursue dangerous prey when the city genuinely needs food.
            # Bear (0.9) requires need_level >= 0.81 (food_stock < 19).
            if need_level < prey_danger * 0.9:
                continue

            food_range = getattr(prey, '_food_value_range', [5, 10])
            avg_food = sum(food_range) / 2.0
            reward = avg_food / 30.0  # normalized: bear gives ~3x more than rabbit

            fear_at_target = world['influence'].get_fear(prey.x, prey.y)
            fear_penalty = abs(fear_at_target) * self.fear_sensitivity * 0.1

            score = (1.0 - dist / self.perception_range) + (reward * (0.5 + need_level)) - fear_penalty

            if score > max_score:
                max_score = score
                best_target = prey

        self.target_prey = best_target

    def _move_towards(self, target_pos, world):
        """Moves toward a target while avoiding obstacles and danger."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        min_dist = math.dist(self.pos, target_pos)

        for nx, ny in possible_moves:
            d = math.dist((nx, ny), target_pos)
            safety = world['influence'].get_fear(nx, ny)

            # Attempt to reduce distance while staying safe
            # If the tile is lethal (lava), safety will be -10, disqualifying the tile
            if safety > -5.0: # Survival threshold
                if d < min_dist:
                    min_dist = d
                    best_move = (nx, ny)

        self.pos = best_move

    def _wander(self, world):
        """Wanders intelligently following scents (Scent) and fleeing fear."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        scored_moves = []
        for nx, ny in possible_moves:
            # Read both grids
            fear = world['influence'].get_fear(nx, ny)
            scent = world['influence'].get_scent(nx, ny)

            # A hunter is attracted to scent (game smell)
            # But repelled by fear (mortal danger)
            score = (fear * self.fear_sensitivity) + (scent * 1.5)

            scored_moves.append(((nx, ny), score + RandomService.random() * 0.2))

        # Choose the best tile (richest in tracks or safest)
        self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def get_defense_power(self):
        """Hunter is armed and dangerous"""
        return 0.6 + self.faith_bonus("defense") * 0.1

    @property
    def danger_level(self):
        return 0.5  # Quite frightening