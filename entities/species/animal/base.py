import math
from core.entities import Entity, Z_ANIMAL
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

class Animal(Entity):
    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, species_data['char'], Z_ANIMAL, species_data.get('speed', 1.0))
        self.pos = (x, y)
        self.species = species_data['species']
        self.char = species_data['char']
        self.name = species_data['name']
        self.target = None
        self.perception_range = 5 # Detection radius
        self.danger = 0.1
        self.culture = culture
        self.config = config
        self.species_data = species_data

        self.energy = 100           # Starting energy
        self.max_energy = 150
        self.hunger_threshold = 60  # Level at which the animal starts hunting
        self.repro_threshold = 120  # Energy required to spawn offspring

    def check_vital_signs(self, world):
        """
        Called during the MEDIUM TICK (every 10 cycles).
        Manages hunger decay and starvation.
        """
        # Passive energy loss
        loss = 5
        if getattr(self, 'is_flying', False): loss = 8 # Flying is exhausting

        self.energy -= loss

        # Starvation check
        if self.energy <= 0:
            self.is_expired = True
            # Optional: Log death only for important species to avoid spam
            if self.danger > 0.5:
                GameLogger.log(f"💀 A {self.species} has starved to death.")

    def process_long_term_logic(self, world):
            """
            Called during the SLOW TICK (every 100 cycles).
            Handles biological reproduction.
            """
            if self.energy >= self.repro_threshold:
                self._reproduce(world)

    def _reproduce(self, world):
        """Creates a new instance of the same species nearby."""
        # Find a free adjacent tile
        neighbors = self._get_accessible_neighbors(world)
        if neighbors:
            spawn_pos = RandomService.choice(neighbors)

            # Create offspring (Logic varies slightly depending on your Factory setup)
            # For this example, we assume a generic constructor call
            offspring = self.__class__(spawn_pos[0], spawn_pos[1], self.culture, self.config, self.species_data)

            world['entities'].add(offspring)

            # Reproduction costs half the parent's energy
            self.energy /= 2
    @property
    def is_edible(self):
        return True

    @property
    def fear_sensitivity(self):
        return 5.0

    @property
    def diet(self):
        return "carnivore"

    def _find_target(self, world):
        """Orchestrates target searching by combining vision and instinct (Heat Map)."""
        potential_targets = []

        for entity in world['entities']:
            if self._is_valid_prey(entity):
                potential_targets.append(entity)

        # We evaluate each potential target to find the best benefit/risk ratio
        self.target = self._evaluate_best_choice(potential_targets, world)

    def _is_valid_prey(self, entity):
        """Business filter to determine if the entity is a legitimate prey."""
        if entity.is_expired or entity == self:
            return False
        if self.diet == "herbivore":
            return False
        # Safety: No cannibalism (via getattr for robustness)
        if getattr(entity, 'species', None) == self.species:
            return False

        if not entity.is_edible:
            return False

        # Accessibility according to environment (Land, Aquatic, Flying)
        # 1. If the prey flies and I don't, impossible.
        if getattr(entity, 'is_flying', False) and not self.is_flying:
            return False

        # 2. If the prey is aquatic and I am land-based (or vice versa)
        # We check if the entity is in water via world tiles if necessary
        # But here we rely on movement attributes
        if getattr(entity, 'is_aquatic', False) and not self.is_aquatic and not self.is_flying:
            return False

        return math.dist(self.pos, entity.pos) <= self.perception_range

    def _evaluate_best_choice(self, targets, world):
        best_target = None
        max_score = -float('inf')

        # 1. We define the entity's danger tolerance
        # The more dangerous the entity is itself, the more it tolerates negative influence
        # A bear (0.9) will be much braver than a doe (0.1)
        courage_threshold = (self.danger_level * 10) - 15
        # Example:
        # Doe (0.1) -> Threshold at -14 (very cautious)
        # Bear (0.9) -> Threshold at -6 (much braver)

        for target in targets:
            fear_val = world['influence'].get_fear(target.x, target.y)
            scent_val = world['influence'].get_scent(target.x, target.y)

            # Score calculation...
            dist_score = 1 - (math.dist(self.pos, target.pos) / self.perception_range)
            total_score = dist_score + scent_val + (fear_val * self.fear_sensitivity)

            if total_score > max_score:
                max_score = total_score
                best_target = target

        # 2. FINAL VALIDATION: Indexed on danger_level
        # If the best choice remains below our courage, we give up.
        if max_score < courage_threshold:
            return None

        return best_target

    def _approach_target(self, world):
        if not self.target: return

        # Movement toward the target
        tx, ty = self.target.pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0

        nx, ny = self.x + dx, self.y + dy

        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            # We allow movement if it's land (h >= 0)
            # Except if the animal is aquatic or flying (to be adapted according to your needs)
            if world['elev'][ny][nx] >= -0.1:
                self.pos = (nx, ny)

        if self.pos == self.target.pos:
            self._attack_target(world)

    def _attack_target(self, world):
        """Combat method based on the target's defense capabilities."""
        if not self.target or self.target.is_expired:
            return

        defense_base = self.target.get_defense_power()

        # --- CASE: THE TARGET CAN DEFEND ITSELF (e.g., Hunter) ---
        if defense_base > 0:
            defense_roll = RandomService.random()

            # TARGET VICTORY (The animal dies)
            if defense_roll > (defense_base + self.danger / 2):
                self.is_expired = True
                GameLogger.log(Translator.translate("events.hunt_success", hunter_name=self.target.name, prey_name=self.name))
                return

            # DRAW (Flee)
            elif defense_roll > self.danger:
                GameLogger.log(Translator.translate("events.hunt_flee", hunter_name=self.target.name, prey_name=self.name))
                self.target = None
                return

        # --- CASE: THE TARGET IS DEVOURED (Defense too low or failed roll) ---
        self.target.is_expired = True
        food_value = getattr(self.target, 'food_value', 10)
        self.energy = min(self.max_energy, self.energy + food_value * 2)
        GameLogger.log(Translator.translate("events.hunt_fail", hunter_name=self.name, prey_name=self.target.name))
        self.target = None

    def _wander(self, world):
        """Erratic movement but guided by survival (Fear) and interest (Scent)."""
        # 1. We get the tiles where the animal can physically go
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return

        scored_moves = []

        # We get the fear sensitivity (e.g., 5.0 for a doe, 1.0 for a lion)
        fear_factor = getattr(self, 'fear_sensitivity', 2.0)

        for nx, ny in possible_moves:
            # 2. Reading the two Heatmap layers
            fear_val = world['influence'].get_fear(nx, ny)   # Negative value (Danger)
            scent_val = world['influence'].get_scent(nx, ny) # Positive value (Interest)

            # 3. Calculation of the tile score
            # Fear is multiplied by the fear_factor to dominate the choice.
            # Scent attracts the animal toward comfort zones.
            influence_score = (fear_val * fear_factor) + scent_val

            # 4. Adding random "noise" (Random Bias)
            # This prevents animals from staying frozen or following lines that are too straight.
            random_bias = RandomService.random() * 0.3

            scored_moves.append(((nx, ny), influence_score + random_bias))

        # 5. Selection of the best move (the highest score)
        # If fear_val is very low (e.g., -5.0), the score will be very low,
        # forcing the animal to move away from this tile.
        best_move = max(scored_moves, key=lambda m: m[1])[0]

        self.pos = best_move

    def _get_accessible_neighbors(self, world):
        """Filters adjacent tiles according to the animal's capabilities."""
        accessible = []
        # We include the current position (staying in place is a valid choice)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = self.x + dx, self.y + dy

                # Map boundaries
                if not (0 <= nx < world['width'] and 0 <= ny < world['height']):
                    continue

                if self._can_move_to(world, nx, ny):
                    accessible.append((nx, ny))
        return accessible

    def _can_move_to(self, world, nx, ny):
        """Checks boundaries and biome (Elevation)."""
        if not (0 <= nx < world['width'] and 0 <= ny < world['height']):
            return False

        elevation = world['elev'][ny][nx]
        water_limit = 0 # Arbitrary land/water threshold

        if self.is_flying: return True
        if self.is_aquatic: return elevation < water_limit
        return elevation >= water_limit

    def update(self, world, stats):
        self._think(world)
        self._perform_action(world)

    def _think(self, world):
        """Modified decision logic: Hunt if carnivore, Graze if herbivore."""
        if self.target and (self.target.is_expired or math.dist(self.pos, self.target.pos) > self.perception_range):
            self.target = None

        # 1. CARNIVORE LOGIC: Search for prey
        if self.diet == "carnivore":
            if not self.target and self.energy < self.hunger_threshold:
                self._find_target(world)

        # 2. HERBIVORE LOGIC: Automatic Grazing
        elif self.diet == "herbivore":
            self._graze(world)

    def _perform_action(self, world):
        """Execution of movement or attack."""
        if self.target:
            if self.pos == self.target.pos:
                self._attack_target(world)
            else:
                self._move_towards(self.target.pos, world)
        else:
            self._wander(world)

    def _move_towards(self, target_pos, world):
        """Intelligent movement toward a target respecting the environment."""
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0

        nx, ny = self.x + dx, self.y + dy

        # We check if the tile is passable by this species
        if self._can_move_to(world, nx, ny):
            self.pos = (nx, ny)
        else:
            # If blocked (e.g., shark hitting the shore), we try a small detour
            self._wander(world)

    def _graze(self, world):
        """
        Herbivores automatically feed on fertile tiles.
        This provides a steady energy gain without needing a 'target'.
        """
        x, y = self.x, self.y
        elevation = world['elev'][y][x]

        # Check if the tile is fertile (Plains or Forest biomes)
        # Assuming elevation 0.0 to 0.5 represents green land
        if 0.0 <= elevation <= 0.5:
            # Grazing provides a small but constant energy boost
            grazing_yield = 2
            self.energy = min(self.max_energy, self.energy + grazing_yield)

            # Note: In a future update, we could reduce the 'fertility'
            # of the tile to simulate overgrazing.