from core.naming import NameGenerator
from core.entities import Entity, Z_CONSTRUCT

class Construct(Entity):
    """Base pour tout ce qui est bâti sur la carte."""
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, "?", Z_CONSTRUCT, 1)
        self.pos = (x, y)
        self.culture = culture
        self.config = config
        self.species = "construct"
        self.is_expired = False
        self.char = "?"
        self.name = NameGenerator.generate_place_name(culture)
    def update(self, world, stats):
        """Méthode à surcharger dans les sous-classes."""
        pass