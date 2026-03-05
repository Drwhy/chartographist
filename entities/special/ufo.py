from core.entities import Entity
from core.random_service import RandomService
from core.translator import Translator
from entities.registry import CIV_UNITS
import math

class UFO(Entity):
    def __init__(self, x, y, char, z_index):
        super().__init__(x, y, char, z_index, 1)
        self.target_entity = None
        self.abducted_entity = None
        self.wait_timer = 0
        self.is_leaving = False

    def update(self, world, stats):
        if self.is_expired: return

        # 1. Si on a fini l'abduction, on s'en va vers le bord de la map
        if self.is_leaving:
            self._move_to_exit(world)
            return

        # 2. Si on est en train de "scanner" (attente au-dessus de la victime)
        if self.wait_timer > 0:
            self.wait_timer -= 1
            if self.wait_timer <= 0:
                self._release_victim(world)
            return

        # 3. Recherche ou poursuite de cible
        if not self.target_entity or self.target_entity.is_expired:
            self._find_civilian_target(world)

        if self.target_entity:
            if math.dist(self.pos, self.target_entity.pos) < 1:
                self._abduct_victim(world)
            else:
                self._move_towards(self.target_entity.pos)
        else:
            self._idle_move(world)

    def _find_civilian_target(self, world):
        civilians = [e for e in world['entities'] if type(e) in CIV_UNITS and not e.is_expired]
        if civilians:
            self.target_entity = min(civilians, key=lambda c: math.dist(self.pos, c.pos))

    def _abduct_victim(self, world):
        self.abducted_entity = self.target_entity
        # On cache la victime (is_abducted doit être géré dans le rendu/update global)
        self.abducted_entity.is_abducted = True
        self.wait_timer = RandomService.randint(10, 20)

        from core.logger import GameLogger
        GameLogger.log(Translator.translate("events.abduction_start", name=self.abducted_entity.name))

    def _release_victim(self, world):
        if self.abducted_entity:
            self.abducted_entity.is_abducted = False
            from core.logger import GameLogger
            GameLogger.log(Translator.translate("events.abduction_end", name=self.abducted_entity.name))
            self.abducted_entity = None
        self.is_expired = True

    def _move_towards(self, target_pos):
        """Déplacement fluide vers une cible."""
        tx, ty = target_pos

        # On calcule les nouvelles coordonnées basées sur la position actuelle
        nx = self.x + (1 if tx > self.x else -1 if tx < self.x else 0)
        ny = self.y + (1 if ty > self.y else -1 if ty < self.y else 0)

        self.pos = (nx, ny)

    def _move_to_exit(self, world):
        # L'UFO fonce vers le haut de la map pour disparaître
        self.pos = (self.x, self.y -1)
        if self.y < 0:
            self.is_expired = True

    def _idle_move(self, world):
        dirs = [(0,1), (0,-1), (1,0), (-1,0)]
        dx, dy = RandomService.choice(dirs)
        self.pos = (dx, dy)