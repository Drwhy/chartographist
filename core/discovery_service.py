# core/services/discovery_service.py
from entities.registry import STRUCTURE_TYPES
from entities.constructs.ruins import Ruins

class DiscoveryService:
    @staticmethod
    def get_known_settlements(world):
        """
        Retourne la liste des cités actives et habitées.
        Centralise l'intelligence partagée entre les humains.
        """
        return [
            e for e in world['entities']
            if type(e) in STRUCTURE_TYPES
            and not e.is_expired
            and not isinstance(e, Ruins)
            and getattr(e, 'population', 0) > 0
        ]

    @staticmethod
    def get_nearest_settlement(origin_pos, world, exclude=None):
        """Trouve la cité la plus proche, utile pour les replis d'urgence."""
        cities = DiscoveryService.get_known_settlements(world)
        if exclude:
            cities = [c for c in cities if c != exclude]

        if not cities:
            return None

        import math
        return min(cities, key=lambda c: math.dist(origin_pos, c.pos))