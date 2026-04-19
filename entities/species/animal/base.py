import math
from core.entities import Entity, Z_ANIMAL
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

class Animal(Entity):
    """
    Fully data-driven animal entity.
    All species-specific behavior is determined by species_data from template.json.
    No subclassing needed — add a new species by adding a fauna entry in the template.
    """

    def __init__(self, x, y, culture, config, species_data):
        super().__init__(x, y, species_data['char'], Z_ANIMAL, species_data.get('speed', 1.0))
        self.pos = (x, y)
        self.species = species_data['species']
        self.char = species_data['char']
        self.name = species_data['name']
        self.target = None
        self.culture = culture
        self.config = config
        self.species_data = species_data

        # Stats from template (with sensible defaults)
        self.perception_range = species_data.get('perception_range', 5)
        self.danger = species_data.get('danger', 0.1)
        self.energy = species_data.get('energy', 100)
        self.max_energy = species_data.get('max_energy', 150)
        self.hunger_threshold = species_data.get('hunger_threshold', 60)
        self.repro_threshold = species_data.get('repro_threshold', 120)

        # Locomotion: "land", "aquatic", or "flying"
        self._locomotion = species_data.get('locomotion', 'land')
        # Diet: "carnivore" or "herbivore"
        self._diet = species_data.get('diet', 'carnivore')
        # Behavior
        self._fear_sensitivity = species_data.get('fear_sensitivity', 5.0)
        self._danger_level = species_data.get('danger_level', 0.1)
        # Food value range [min, max]
        self._food_value_range = species_data.get('food_value', [5, 10])

    # ── Properties driven by template data ────────────────

    @property
    def is_edible(self):
        return True

    @property
    def is_flying(self):
        return self._locomotion == 'flying'

    @property
    def is_aquatic(self):
        return self._locomotion == 'aquatic'

    @property
    def diet(self):
        return self._diet

    @property
    def fear_sensitivity(self):
        return self._fear_sensitivity

    @property
    def danger_level(self):
        return self._danger_level

    @property
    def food_value(self):
        lo, hi = self._food_value_range
        return RandomService.randint(lo, hi)

    # ── Spawn (static, used by spawn_system) ──────────────

    @staticmethod
    def try_spawn(x, y, world, config, species_data):
        """Generic spawn: checks elevation range and roll from template config."""
        spawn_cfg = species_data.get('spawn', {})
        h = world['elev'][y][x]
        elev_min = spawn_cfg.get('elevation_min', 0.0)
        elev_max = spawn_cfg.get('elevation_max', 1.0)
        chance = spawn_cfg.get('chance', 0.05)

        if elev_min < h < elev_max:
            if RandomService.random() < chance:
                return Animal(x, y, None, config, species_data)
        return None

    # ── Tick hooks ────────────────────────────────────────

    def check_vital_signs(self, world):
        """MEDIUM TICK (every 10 cycles): hunger decay and starvation."""
        loss = 8 if self.is_flying else 5
        self.energy -= loss

        if self.energy <= 0:
            self.is_expired = True
            if self.danger > 0.5:
                GameLogger.log(f"💀 A {self.species} has starved to death.")

    def process_long_term_logic(self, world):
        """SLOW TICK (every 100 cycles): reproduction."""
        if self.energy >= self.repro_threshold:
            self._reproduce(world)

    def _reproduce(self, world):
        """Creates a new instance of the same species nearby."""
        neighbors = self._get_accessible_neighbors(world)
        if neighbors:
            spawn_pos = RandomService.choice(neighbors)
            offspring = Animal(spawn_pos[0], spawn_pos[1], self.culture, self.config, self.species_data)
            world['entities'].add(offspring)
            self.energy /= 2

    # ── AI ────────────────────────────────────────────────

    def update(self, world, stats):
        self._think(world)
        self._perform_action(world)

    def _think(self, world):
        if self.target and (self.target.is_expired or math.dist(self.pos, self.target.pos) > self.perception_range):
            self.target = None

        if self.diet == "carnivore":
            if not self.target and self.energy < self.hunger_threshold:
                self._find_target(world)
        elif self.diet == "herbivore":
            self._graze(world)

    def _perform_action(self, world):
        if self.target:
            if self.pos == self.target.pos:
                self._attack_target(world)
            else:
                self._move_towards(self.target.pos, world)
        else:
            self._wander(world)

    # ── Hunting ───────────────────────────────────────────

    def _find_target(self, world):
        potential_targets = []
        for entity in world['entities']:
            if self._is_valid_prey(entity):
                potential_targets.append(entity)
        self.target = self._evaluate_best_choice(potential_targets, world)

    def _is_valid_prey(self, entity):
        if entity.is_expired or entity == self:
            return False
        if self.diet == "herbivore":
            return False
        if getattr(entity, 'species', None) == self.species:
            return False
        if not entity.is_edible:
            return False
        if getattr(entity, 'is_flying', False) and not self.is_flying:
            return False
        if getattr(entity, 'is_aquatic', False) and not self.is_aquatic and not self.is_flying:
            return False
        return math.dist(self.pos, entity.pos) <= self.perception_range

    def _evaluate_best_choice(self, targets, world):
        best_target = None
        max_score = -float('inf')
        courage_threshold = (self.danger_level * 10) - 15

        for target in targets:
            fear_val = world['influence'].get_fear(target.x, target.y)
            scent_val = world['influence'].get_scent(target.x, target.y)
            dist_score = 1 - (math.dist(self.pos, target.pos) / self.perception_range)
            total_score = dist_score + scent_val + (fear_val * self.fear_sensitivity)

            if total_score > max_score:
                max_score = total_score
                best_target = target

        if max_score < courage_threshold:
            return None
        return best_target

    # ── Combat ────────────────────────────────────────────

    def _attack_target(self, world):
        if not self.target or self.target.is_expired:
            return

        defense_base = self.target.get_defense_power()

        if defense_base > 0:
            defense_roll = RandomService.random()

            if defense_roll > (defense_base + self.danger / 2):
                self.is_expired = True
                GameLogger.log(Translator.translate("events.hunt_success", hunter_name=self.target.name, prey_name=self.name))
                return

            elif defense_roll > self.danger:
                GameLogger.log(Translator.translate("events.hunt_flee", hunter_name=self.target.name, prey_name=self.name))
                self.target = None
                return

        self.target.is_expired = True
        food_value = getattr(self.target, 'food_value', 10)
        self.energy = min(self.max_energy, self.energy + food_value * 2)
        GameLogger.log(Translator.translate("events.hunt_fail", hunter_name=self.name, prey_name=self.target.name))
        self.target = None

    # ── Movement ──────────────────────────────────────────

    def _wander(self, world):
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return

        scored_moves = []
        fear_factor = self.fear_sensitivity

        for nx, ny in possible_moves:
            fear_val = world['influence'].get_fear(nx, ny)
            scent_val = world['influence'].get_scent(nx, ny)
            influence_score = (fear_val * fear_factor) + scent_val
            random_bias = RandomService.random() * 0.3
            scored_moves.append(((nx, ny), influence_score + random_bias))

        best_move = max(scored_moves, key=lambda m: m[1])[0]
        self.pos = best_move

    def _get_accessible_neighbors(self, world):
        accessible = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = self.x + dx, self.y + dy
                if not (0 <= nx < world['width'] and 0 <= ny < world['height']):
                    continue
                if self._can_move_to(world, nx, ny):
                    accessible.append((nx, ny))
        return accessible

    def _can_move_to(self, world, nx, ny):
        if not (0 <= nx < world['width'] and 0 <= ny < world['height']):
            return False
        elevation = world['elev'][ny][nx]
        if self.is_flying: return True
        if self.is_aquatic: return elevation < 0
        return elevation >= 0

    def _move_towards(self, target_pos, world):
        tx, ty = target_pos
        dx = 1 if tx > self.x else -1 if tx < self.x else 0
        dy = 1 if ty > self.y else -1 if ty < self.y else 0
        nx, ny = self.x + dx, self.y + dy

        if self._can_move_to(world, nx, ny):
            self.pos = (nx, ny)
        else:
            self._wander(world)

    def _graze(self, world):
        x, y = self.x, self.y
        elevation = world['elev'][y][x]
        if 0.0 <= elevation <= 0.5:
            grazing_yield = 2
            self.energy = min(self.max_energy, self.energy + grazing_yield)
