import math
from .event_registry import register_event
from .base_event import BaseEvent
from core.random_service import RandomService
from core.logger import GameLogger
from entities.constructs.ruins import Ruins
from core.translator import Translator

@register_event
class VolcanoEruption(BaseEvent):
    name = "Éruption Volcanique"
    chance = 0.001

    def trigger(self, world, stats, config):
        volcano_points = [(x, y) for y in range(world['height'])
                          for x in range(world['width']) if world['elev'][y][x] > 0.9]

        if not volcano_points: return

        epicenter = RandomService.choice(volcano_points)
        # Rayon de détection des volcans voisins (chaîne de sommets)
        erupting_cluster = [p for p in volcano_points if math.dist(p, epicenter) < 5]
        GameLogger.log(Translator.translate("events.volcano_start", count=len(erupting_cluster)))

        radius = 3 # Rayon fixe imposé

        for vx, vy in erupting_cluster:
            # 1. Propagation des flammes sur la grille 'road'
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = vx + dx, vy + dy
                    if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                        if math.dist((vx, vy), (nx, ny)) <= radius:
                            world['road'][ny][nx] = "🔥"

            # 2. Destruction et Transformation des entités
            for e in list(world['entities']):
                if math.dist(e.pos, (vx, vy)) <= radius:
                    if hasattr(e, 'population'): # C'est une ville/village
                        # On spawn une ruine avant de supprimer la ville
                        ruin = Ruins(e.x, e.y, e.culture, e.config, e.name)
                        world['entities'].add(ruin)
                        e.is_expired = True
                        GameLogger.log(Translator.translate("events.volcano_ruin", name=e.name))
    def tick(self, world, stats):
        """Gère la dissipation naturelle des flammes sur la carte."""
        for y in range(world['height']):
            for x in range(world['width']):
                if world['road'][y][x] == "🔥":
                    # 5% de chance de s'éteindre ou de devenir de la cendre
                    if RandomService.random() < 0.05:
                        world['road'][y][x] = "  "