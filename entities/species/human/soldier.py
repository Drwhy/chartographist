import math
from .base import Human
from entities.registry import register_civ, CIV_UNITS
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator


@register_civ
class Soldier(Human):
    """
    Military unit spawned by a city at war.
    Marches toward an enemy settlement, fights hostile soldiers,
    and raids the target city on arrival.
    """

    def __init__(self, x, y, culture, config, home_city, target_city):
        super().__init__(x, y, culture, config, 1.0)
        self.char = culture.get("soldier_emoji", "⚔️")
        self.home_city = home_city
        self.home_pos = (home_city.x, home_city.y)
        self.target_city = target_city
        self.strength = 1.0 + self.faith_bonus("defense") * 0.15
        self._base_perception = 8
        self.fear_sensitivity = 1.0  # Soldiers don't scare easily
        self.retreating = False

    @property
    def perception_range(self):
        return self._base_perception + int(self.faith_bonus("perception"))

    @property
    def danger_level(self):
        return 0.8

    def think(self, world):
        if self.is_expired or self.is_dead:
            return

        # Target city destroyed or expired — mission over, retreat
        if self.target_city.is_expired or getattr(self.target_city, 'population', 0) <= 0:
            self.retreating = True
            return

        # Check for enemy soldiers nearby — engage in combat
        self._scan_for_enemies(world)

    def perform_action(self, world):
        if self.is_expired or self.is_dead:
            return

        if self.retreating:
            if math.dist(self.pos, self.home_pos) < 1.5:
                self.is_expired = True  # Returned home, dissolve
                return
            self._move_towards(self.home_pos, world)
            return

        # Arrived at target city — raid it
        if math.dist(self.pos, self.target_city.pos) < 1.5:
            self._raid_city(world)
        else:
            self._move_towards(self.target_city.pos, world)

    def _scan_for_enemies(self, world):
        """Look for enemy soldiers or military units nearby and fight them."""
        for entity in world['entities']:
            if entity.is_expired or entity is self:
                continue

            # Fight enemy soldiers from a different culture
            if isinstance(entity, Soldier) and not entity.is_dead:
                if entity.home_city != self.home_city and self._is_enemy_culture(entity):
                    if math.dist(self.pos, entity.pos) <= 1.5:
                        self._fight(entity, world)
                        return

    def _is_enemy_culture(self, other):
        """Two soldiers are enemies if their home cities' cultures differ."""
        my_culture = getattr(self.home_city, 'culture', {}).get('name', '')
        their_culture = getattr(other.home_city, 'culture', {}).get('name', '')
        return my_culture != their_culture

    def _fight(self, enemy, world):
        """Resolve combat between two soldiers. Strength + randomness."""
        my_roll = self.strength + RandomService.random() * 0.5
        enemy_roll = enemy.strength + RandomService.random() * 0.5

        if my_roll >= enemy_roll:
            enemy.is_dead = True
            enemy.is_expired = True
            GameLogger.log(Translator.translate(
                "events.soldier_kills",
                winner=self.name, loser=enemy.name,
                winner_city=self.home_city.name
            ))
            # Gain experience from victory
            self.strength += 0.1
        else:
            self.is_dead = True
            self.is_expired = True
            GameLogger.log(Translator.translate(
                "events.soldier_kills",
                winner=enemy.name, loser=self.name,
                winner_city=enemy.home_city.name
            ))
            enemy.strength += 0.1

    def _raid_city(self, world):
        """Attack the target city — kill citizens and steal food."""
        target = self.target_city
        if target.is_expired:
            self.retreating = True
            return

        raid_power = int(self.strength * 5)

        # Kill citizens
        kills = min(len(target.citizens), raid_power)
        for _ in range(kills):
            if target.citizens:
                victim = RandomService.choice(target.citizens)
                victim.is_dead = True

        # Loot food
        loot = min(target.food_stock, int(self.strength * 20))
        target.food_stock -= loot

        GameLogger.log(Translator.translate(
            "events.soldier_raids",
            soldier=self.name, city=target.name,
            kills=kills, home_city=self.home_city.name
        ))

        # Soldier dies in the raid (one-shot attack)
        self.is_dead = True
        self.is_expired = True

        # Deliver loot to home city if it still exists
        if not self.home_city.is_expired:
            self.home_city.food_stock += loot

    def _move_towards(self, target_pos, world):
        """March toward a target, preferring roads."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return

        best_move = self.pos
        max_score = -float('inf')

        for nx, ny in possible_moves:
            dist = math.dist((nx, ny), target_pos)
            dist_score = 1.0 / (dist + 0.1)

            # Road bonus
            road_bonus = 0.3 if world['road'][ny][nx] != "  " else 0.0

            # Fear (soldiers are brave but not suicidal)
            fear = world['influence'].get_fear(nx, ny)
            fear_score = fear * self.fear_sensitivity

            score = dist_score + road_bonus + fear_score

            if score > max_score:
                max_score = score
                best_move = (nx, ny)

        self.pos = best_move
