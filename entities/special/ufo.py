from core.entities import Entity
from core.random_service import RandomService
from core.translator import Translator
from entities.registry import CIV_UNITS
import math

class UFO(Entity):
    """
    A special autonomous entity that hunts civilization units.
    The UFO follows a State Machine: Search -> Pursue -> Abduct (Scan) -> Release -> Exit.
    """
    def __init__(self, x, y, char, z_index):
        # Initializing as a high-priority entity with a speed of 1
        super().__init__(x, y, char, z_index, 1)
        self.target_entity = None
        self.abducted_entity = None
        self.wait_timer = 0
        self.is_leaving = False

    def update(self, world, stats):
        """Main update loop for the UFO's behavioral states."""
        if self.is_expired:
            return

        # 1. EXIT STATE: Moving toward the map boundaries to despawn
        if self.is_leaving:
            self._move_to_exit(world)
            return

        # 2. SCANNING STATE: Hovering over the victim during abduction
        if self.wait_timer > 0:
            self.wait_timer -= 1
            if self.wait_timer <= 0:
                self._release_victim(world)
            return

        # 3. PURSUIT STATE: Find a target or move toward the current one
        if not self.target_entity or self.target_entity.is_expired:
            self._find_civilian_target(world)

        if self.target_entity:
            # Check if close enough to initiate abduction
            if math.dist(self.pos, self.target_entity.pos) < 1:
                self._abduct_victim(world)
            else:
                self._move_towards(self.target_entity.pos)
        else:
            # Wander aimlessly if no targets are available
            self._idle_move(world)

    def _find_civilian_target(self, world):
        """Locates the nearest valid human entity from the registry."""
        civilians = [e for e in world['entities'] if type(e) in CIV_UNITS and not e.is_expired]
        if civilians:
            self.target_entity = min(civilians, key=lambda c: math.dist(self.pos, c.pos))

    def _abduct_victim(self, world):
        """Begins the abduction process by disabling the victim's visibility/update."""
        self.abducted_entity = self.target_entity

        # Setting a flag for the victim (must be handled by the victim's update/render logic)
        self.abducted_entity.is_abducted = True
        self.wait_timer = RandomService.randint(10, 20)

        from core.logger import GameLogger
        GameLogger.log(Translator.translate("events.abduction_start", name=self.abducted_entity.name))

    def _release_victim(self, world):
        """Ends the abduction, restores the victim, and flags the UFO for departure."""
        if self.abducted_entity:
            self.abducted_entity.is_abducted = False
            from core.logger import GameLogger
            GameLogger.log(Translator.translate("events.abduction_end", name=self.abducted_entity.name))
            self.abducted_entity = None

        # Once the 'experiment' is done, the UFO expires/leaves
        self.is_expired = True

    def _move_towards(self, target_pos):
        """Calculates a fluid 8-directional move toward target coordinates."""
        tx, ty = target_pos

        nx = self.x + (1 if tx > self.x else -1 if tx < self.x else 0)
        ny = self.y + (1 if ty > self.y else -1 if ty < self.y else 0)

        self.pos = (nx, ny)

    def _move_to_exit(self, world):
        """Ascends toward the top of the map to vanish."""
        self.pos = (self.x, self.y - 1)
        if self.y < 0:
            self.is_expired = True

    def _idle_move(self, world):
        """Performs a random step when no targets are detected."""
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        dx, dy = RandomService.choice(dirs)

        # Boundary-safe movement
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            self.pos = (nx, ny)