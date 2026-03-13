# core/grid_service.py

class SpatialGrid:
    def __init__(self, width, height, cell_size=10):
        self.cell_size = cell_size
        self.width = width
        self.height = height
        # Dictionary using (cx, cy) tuples as keys and sets of entities as values
        self.cells = {}

    def _get_cell_coords(self, x, y):
        """Converts world coordinates into grid cell coordinates."""
        return int(x // self.cell_size), int(y // self.cell_size)

    def clear(self):
        """Resets the grid. Usually called at the start of every cycle."""
        self.cells = {}

    def add_entity(self, entity):
        """Registers an entity into its corresponding cell."""
        cx, cy = self._get_cell_coords(entity.x, entity.y)
        if (cx, cy) not in self.cells:
            self.cells[(cx, cy)] = set()
        self.cells[(cx, cy)].add(entity)

    def get_nearby(self, x, y, radius):
        """
        Returns all entities within the cells covered by the radius.
        This drastically reduces the number of distance checks needed.
        """
        entities = []
        min_cx, min_cy = self._get_cell_coords(x - radius, y - radius)
        max_cx, max_cy = self._get_cell_coords(x + radius, y + radius)

        # Iterate only through the relevant neighboring cells
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                if (cx, cy) in self.cells:
                    entities.extend(self.cells[(cx, cy)])
        return entities