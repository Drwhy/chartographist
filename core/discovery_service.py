import math
from entities.registry import STRUCTURE_TYPES
from entities.constructs.ruins import Ruins

class DiscoveryService:
    """
    Handles global geographic intelligence and settlement tracking.
    Centralizes shared knowledge between all human entities.
    """

    @staticmethod
    def get_known_settlements(world):
        """
        Returns a list of active, inhabited, and non-ruined settlements.
        Acts as the primary registry for trade and expansion targets.
        """
        return [
            entity for entity in world['entities']
            if type(entity) in STRUCTURE_TYPES
            and not entity.is_expired
            and not isinstance(entity, Ruins)
            and getattr(entity, 'population', 0) > 0
        ]

    @staticmethod
    def get_nearest_settlement(origin_pos, world, exclude=None):
        """
        Finds the closest valid settlement to a specific position.
        Used for emergency retreats or localized pathfinding.
        """
        settlements = DiscoveryService.get_known_settlements(world)

        if exclude:
            settlements = [s for s in settlements if s != exclude]

        if not settlements:
            return None

        # Distance calculation using the provided origin point
        return min(settlements, key=lambda s: math.dist(origin_pos, s.pos))