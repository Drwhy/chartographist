import math

class InfluenceSystem:
    """
    Manages environmental signals through persistent heatmaps.
    Features a Fear layer (negative repulsion) and a Scent layer (positive attraction).
    """
    def __init__(self, width, height, config):
        self.width = width
        self.height = height

        # Initialize grids: Fear (negative signals) and Scent (positive signals)
        self.fear_grid = [[0.0 for _ in range(width)] for _ in range(height)]
        self.scent_grid = [[0.0 for _ in range(width)] for _ in range(height)]

        # Decay rate: e.g., 0.90 means 10% of the signal evaporates per tick
        self.decay = config.get('influence_decay', 0.90)

    def update(self):
        """
        Processes global signal evaporation across the entire map.
        Calculates the gradual disappearance of smells and trail markings.
        """
        for y in range(self.height):
            for x in range(self.width):
                self.fear_grid[y][x] *= self.decay
                self.scent_grid[y][x] *= self.decay

    def add_influence(self, x, y, value, radius=1):
        """
        Deposits a signal footprint into the appropriate grid layer.
        Impact diminishes linearly from the center point to the radius edge.
        """
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy

                if 0 <= nx < self.width and 0 <= ny < self.height:
                    # Circular distance check
                    dist = math.sqrt(dx**2 + dy**2)
                    if dist <= radius:
                        # Linear falloff calculation
                        impact = value * (1 - (dist / (radius + 1)))

                        if value < 0:
                            # --- FEAR MANAGEMENT ---
                            # We use min() so the most extreme danger (lowest value)
                            # is always prioritized and never diluted by lesser fears.
                            self.fear_grid[ny][nx] = min(self.fear_grid[ny][nx], impact)
                        else:
                            # --- SCENT MANAGEMENT ---
                            # Scents are cumulative (e.g., a cluster of food smells stronger)
                            # We update the current grid with the new added impact.
                            self.scent_grid[ny][nx] += impact

    def get_fear(self, x, y):
        """Returns the fear level at specific coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.fear_grid[y][x]
        return 0.0

    def get_scent(self, x, y):
        """Returns the scent level at specific coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.scent_grid[y][x]
        return 0.0