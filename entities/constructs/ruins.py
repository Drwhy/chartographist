from .base import Construct
from entities.registry import register_structure

@register_structure
class Ruins(Construct):
    """
    Represents the remains of a destroyed City or Village.
    Ruins are inert structures that preserve the memory of a fallen settlement.
    They can be rediscovered or repopulated by Settlers.
    """
    def __init__(self, x, y, culture, config, original_name):
        # We pass the original culture so the ruin maintains a visual
        # or data link to the civilization that built it.
        super().__init__(x, y, culture, config)

        # Static visual identity
        self.char = config['special']['ruin']

        # Name preservation: "Ruins of [Original Name]"
        self.name = f"Ruins of {original_name}"

        # Ruins are uninhabited
        self.population = 0

    def update(self, world, stats):
        """
        Ruins are inert.
        They perform no actions per tick; they serve as geographic markers
        of past events (e.g., wars, eruptions, or plagues).
        """
        pass