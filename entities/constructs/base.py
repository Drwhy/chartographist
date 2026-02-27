from core.naming import NameGenerator

class Construct:
    """Base pour tout ce qui est bâti sur la carte."""
    def __init__(self, x, y, culture, config):
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.culture = culture
        self.config = config
        self.type = "construct"
        self.is_expired = False
        self.char = "?"
        self.name = NameGenerator.generate_place_name(culture)
    def update(self, world, stats):
        """Méthode à surcharger dans les sous-classes."""
        pass