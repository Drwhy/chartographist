from .event_registry import register_event
from .base_event import BaseEvent
from core.random_service import RandomService
from core.logger import GameLogger
from core.translator import Translator
from core.entities import Z_EFFECT
import math
from entities.registry import CIV_UNITS
from entities.special.ufo import UFO

@register_event
class Abduction(BaseEvent):
    """
    Spawns a UFO entity that roams the map to abduct human units.
    Only triggers if targets are available and no other UFO is currently active.
    """
    name = "Abduction"
    chance = 0.002

    def condition(self, world, stats):
        """Validates existence of targets and ensures no other UFO is present."""
        # 1. Are there any humans available for abduction?
        has_targets = any(type(e) in CIV_UNITS for e in world['entities'] if not e.is_expired)

        # 2. Is there already an active UFO on the map?
        # Using isinstance for robustness
        no_ufo_present = not any(isinstance(e, UFO) for e in world['entities'] if not e.is_expired)

        return has_targets and no_ufo_present

    def trigger(self, world, stats, config):
        """Spawns the UFO entity at a random entry point on the top edge."""
        # 1. Determine entry point (Top edge of the map)
        spawn_x = RandomService.randint(0, world['width'] - 1)
        spawn_y = 0

        # 2. Create the UFO entity
        # Passing species data from the config and setting its Z-Index
        ufo = UFO(
            spawn_x,
            spawn_y,
            config['special']['ufo'],
            Z_EFFECT
        )

        # 3. Add to the world entity manager
        world['entities'].add(ufo)

        # Optional: Mysterious log entry for the observant player
        # GameLogger.log(Translator.translate("events.ufo_sightings"))