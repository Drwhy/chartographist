# entities/constructs/city.py
from .base import Construct
from entities.registry import register_structure

@register_structure
class City(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.char = culture.get("city", "🏛️")
        self.subtype = "city"

    def update(self, world, stats):
        """
        La cité est stable. Sa logique de production de colons est
        gérée par le spawn_system, mais on pourrait ajouter ici
        une logique de rayonnement culturel ou de défense.
        """
        pass