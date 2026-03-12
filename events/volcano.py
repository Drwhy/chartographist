import math
from .event_registry import register_event
from .base_event import BaseEvent
from core.random_service import RandomService
from core.logger import GameLogger
from entities.constructs.ruins import Ruins
from core.translator import Translator

@register_event
class VolcanoEruption(BaseEvent):
    """
    Simulates a volcanic eruption event.
    High-altitude points (> 0.9) trigger lava flows that destroy structures,
    kill non-flying entities, and leave persistent ruins.
    """
    name = "Volcanic Eruption"
    chance = 0.001

    def trigger(self, world, stats, config):
        # Identify all volcanic peaks based on elevation
        volcano_points = [(x, y) for y in range(world['height'])
                          for x in range(world['width']) if world['elev'][y][x] > 0.9]

        if not volcano_points:
            return

        epicenter = RandomService.choice(volcano_points)

        # Determine the cluster of erupting peaks (neighboring summits)
        erupting_cluster = [p for p in volcano_points if math.dist(p, epicenter) < 5]

        GameLogger.log(
            Translator.translate("events.volcano_start", count=len(erupting_cluster))
        )

        impact_radius = 3

        for vx, vy in erupting_cluster:
            # 1. Spread flames and fear on the world grids
            for dy in range(-impact_radius, impact_radius + 1):
                for dx in range(-impact_radius, impact_radius + 1):
                    nx, ny = vx + dx, vy + dy
                    if 0 <= nx < world['width'] and 0 <= ny < world['height']:
                        if math.dist((vx, vy), (nx, ny)) <= impact_radius:
                            # Set the ground on fire and generate high fear
                            world['road'][ny][nx] = "🔥"
                            world['influence'].add_influence(nx, ny, value=-10.0, radius=2)

            # 2. Destruction and Entity Transformation
            # Iterate through a copy of the list to allow safe modification during loops
            for entity in list(world['entities']):
                if math.dist(entity.pos, (vx, vy)) <= impact_radius:
                    if hasattr(entity, 'population'): # Check if it's a City or Village
                        # Replace the thriving settlement with a Ruin
                        ruin = Ruins(entity.x, entity.y, entity.culture, entity.config, entity.name)
                        world['entities'].add(ruin)
                        entity.is_expired = True

                        GameLogger.log(
                            Translator.translate("events.volcano_ruin", name=entity.name)
                        )

    def tick(self, world, stats):
        """
        Handles the natural dissipation of flames and ongoing lethality of lava.
        """
        for y in range(world['height']):
            for x in range(world['width']):
                if world['road'][y][x] == "🔥":
                    # Ongoing fire creates a local fear field
                    world['influence'].add_influence(x, y, value=-5.0, radius=1)

                    # LETHALITY CHECK
                    # Any non-flying entity standing on fire is consumed
                    for entity in world['entities']:
                        if not entity.is_expired and entity.pos == (x, y):
                            if not getattr(entity, 'is_flying', False):
                                entity.is_expired = True
                                GameLogger.log(
                                    Translator.translate("events.volcano_kill", name=entity.char)
                                )

                    # 5% chance per tick for the fire to extinguish
                    if RandomService.random() < 0.05:
                        world['road'][y][x] = "  "