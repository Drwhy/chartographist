from .base import Construct
from entities.registry import register_structure

@register_structure
class Ruins(Construct):
    def __init__(self, x, y, culture, config, original_name):
        # On passe la culture d'origine pour que la ruine garde une trace
        # visuelle de qui habitait là (via les couleurs ou le style)
        super().__init__(x, y, culture, config)

        # Identité visuelle fixe
        self.char = config['special']['ruin']
        self.name = f"Ruines de {original_name}"

        # Les ruines n'ont plus de population
        self.population = 0

    def update(self, world, stats):
        """
        Les ruines sont inertes.
        Elles ne font rien à chaque tour, elles témoignent juste du passé.
        """
        pass