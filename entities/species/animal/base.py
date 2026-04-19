import math
from core.entities import Entity, Z_ANIMAL
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator

class Animal(Entity):
    """
    Fully data-driven animal entity.
    All species-specific behaviour is determined by species_data from template.json.
    Add a new species by adding a fauna entry in the template — no subclassing needed.
    """

    def __init__(self, x, y, config, species_data):
        super().__init__(x, y, species_data['char'], Z_ANIMAL, species_data.get('speed', 1.0))
        self.species      = species_data['species']
        self.char         = species_data['char']
        self.name         = species_data['name']
        self.target       = None
        self.config       = config
        self.species_data = species_data

        self.perception_range   = species_data.get('perception_range', 5)
        self.danger             = species_data.get('danger', 0.1)
        self.energy             = species_data.get('energy', 100)
        self.max_energy         = species_data.get('max_energy', 150)
        self.hunger_threshold   = species_data.get('hunger_threshold', 60)
        self.repro_threshold    = species_data.get('repro_threshold', 120)
        self.weight             = species_data.get('weight', 5)
        self._locomotion        = species_data.get('locomotion', 'land')
        self._diet              = species_data.get('diet', 'carnivore')
        self._fear_sensitivity  = species_data.get('fear_sensitivity', 5.0)
        self._danger_level      = species_data.get('danger_level', 0.1)
        self._food_value_range  = species_data.get('food_value', [5, 10])

    # ── Properties ────────────────────────────────────────

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

    # ── Spawn ─────────────────────────────────────────────

    @staticmethod
    def try_spawn(x, y, world, config, species_data):
        spawn_cfg = species_data.get('spawn', {})
        h = world['elev'][y][x]
        elev_min = spawn_cfg.get('elevation_min', 0.0)
        elev_max = spawn_cfg.get('elevation_max', 1.0)
        if elev_min < h < elev_max and RandomService.random() < spawn_cfg.get('chance', 0.05):
            return Animal(x, y, config, species_data)
        return None

    # ── Tick hooks ────────────────────────────────────────

    def check_vital_signs(self, world):
        self.energy -= 8 if self.is_flying else 5
        if self.energy <= 0:
            self.is_expired = True
            if self.danger > 0.5:
                GameLogger.log(Translator.translate("events.animal_starvation", species=self.species))

    def process_long_term_logic(self, world):
        if self.energy >= self.repro_threshold:
            self._reproduce(world)

    def _reproduce(self, world):
        neighbors = self._get_accessible_neighbors(world)
        if neighbors:
            spawn_pos = RandomService.choice(neighbors)
            offspring = Animal(spawn_pos[0], spawn_pos[1], self.config, self.species_data)
            world['entities'].add(offspring)
            self.energy /= 2

    # ── AI ────────────────────────────────────────────────

    def think(self, world):
        if self.target and (self.target.is_expired or math.dist(self.pos, self.target.pos) > self.perception_range):
            self.target = None

        if self.diet == "carnivore":
            if not self.target and self.energy < self.hunger_threshold:
                self._find_target(world)
        else:
            self._graze(world)

    def perform_action(self, world):
        if self.target:
            if self.pos == self.target.pos:
                self._attack_target(world)
            else:
                self._move_towards(self.target.pos, world)
        else:
            self._wander(world)

    # ── Hunting ───────────────────────────────────────────

    def _find_target(self, world):
        targets = [e for e in world['entities'] if self._is_valid_prey(e)]
        self.target = self._evaluate_best_choice(targets, world)

    def _is_valid_prey(self, entity):
        if entity.is_expired or entity is self:
            return False
        if getattr(entity, 'species', None) == self.species:
            return False
        if not entity.is_edible:
            return False
        if getattr(entity, 'is_flying', False) and not self.is_flying:
            return False
        if getattr(entity, 'is_aquatic', False) and not self.is_aquatic and not self.is_flying:
            return False
        if getattr(entity, 'weight', 5) > self.weight:
            return False
        return math.dist(self.pos, entity.pos) <= self.perception_range

    def _evaluate_best_choice(self, targets, world):
        best_target = None
        best_score  = -float('inf')
        hunger_pressure = max(0.0, 1.0 - self.energy / max(self.hunger_threshold, 1))

        for target in targets:
            prey_danger = getattr(target, 'danger_level', 0.0)
            if hunger_pressure < prey_danger * 0.8:
                continue

            avg_food    = sum(getattr(target, '_food_value_range', [5, 10])) / 2.0
            reward      = avg_food / self.max_energy
            dist_score  = 1.0 - math.dist(self.pos, target.pos) / self.perception_range
            fear_penalty = abs(world['influence'].get_fear(target.x, target.y)) * self.fear_sensitivity * 0.1
            score = dist_score + (reward * hunger_pressure * 3.0) - fear_penalty

            if score > best_score:
                best_score  = score
                best_target = target

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
        self.energy = min(self.max_energy, self.energy + getattr(self.target, 'food_value', 10) * 2)
        GameLogger.log(Translator.translate("events.hunt_fail", hunter_name=self.name, prey_name=self.target.name))
        self.target = None

    # ── Movement ──────────────────────────────────────────

    def _wander(self, world):
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return
        scored = [
            ((nx, ny),
             world['influence'].get_fear(nx, ny) * self.fear_sensitivity
             + world['influence'].get_scent(nx, ny)
             + RandomService.random() * 0.3)
            for nx, ny in possible_moves
        ]
        self.pos = max(scored, key=lambda m: m[1])[0]

    def _get_accessible_neighbors(self, world):
        return [
            (self.x + dx, self.y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (0 <= self.x + dx < world['width']
                and 0 <= self.y + dy < world['height']
                and self._can_move_to(world, self.x + dx, self.y + dy))
        ]

    def _can_move_to(self, world, nx, ny):
        elevation = world['elev'][ny][nx]
        if self.is_flying:  return True
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
        if 0.0 <= world['elev'][self.y][self.x] <= 0.5:
            self.energy = min(self.max_energy, self.energy + 2)
