# Display Priority Scale (Z-Index)
# Higher values render "on top" of others.
Z_FLOOR = 0      # Biomes, Water (Handled by the rendering engine)
Z_DECOR = 10     # Roads, Ruins, Dead Trees
Z_CONSTRUCT = 20 # Cities, Villages, Ports
Z_ANIMAL = 30    # Wolves, Bears, Fish
Z_HUMAN = 40     # Hunters, Fishermen, Settlers
Z_EFFECT = 50    # Blood, Explosions, Smoke

class Entity:
    """
    Base class for all interactive objects in the simulation.
    Handles positioning, energy accumulation (speed), and influence.
    """
    def __init__(self, x, y, char, z_index, speed):
        # Internal list for mutability, exposed via properties for safety.
        self._pos = [x, y]
        self.char = char
        self.is_expired = False
        self.z_index = z_index
        self.speed = speed
        self.action_meter = 0.0

    @property
    def can_act(self):
        """Checks if the entity has accumulated enough energy to perform an action."""
        return self.action_meter >= 1.0

    @property
    def pos(self):
        """Returns position as a (x, y) tuple for rendering and distance calculations."""
        return tuple(self._pos)

    @pos.setter
    def pos(self, value):
        """Updates internal position coordinates."""
        self._pos = list(value)

    @property
    def x(self): return self._pos[0]

    @property
    def y(self): return self._pos[1]

    def update(self, world, stats):
        """Main logic loop: defines how an entity thinks and acts during a turn."""
        if self.is_expired:
            return

        # 1. Thought phase (finding targets, assessing threats)
        self.think(world)

        # 2. Action phase (moving, attacking, interacting)
        self.perform_action(world)

    def think(self, world):
        """Logic implementation for child classes (AI/Behavior)."""
        pass

    def perform_action(self, world):
        """Action implementation for child classes."""
        pass

    def get_defense_power(self):
        """Returns defensive strength. 0.0 by default."""
        return 0.0

    @property
    def is_edible(self):
        """Defines if the entity can be consumed as food."""
        return False

    @property
    def danger_level(self):
        """0.0 = Harmless, >0.5 = Threatening to prey."""
        return 0.0

    def is_in_water(self, world):
        """Checks if the entity's current elevation is below sea level."""
        return world['elev'][self.y][self.x] < 0

    @property
    def food_value(self):
        """Growth value provided to a city when consumed or harvested."""
        return 0

    @property
    def is_flying(self):
        """Standard entities are ground-based by default."""
        return False

    @property
    def is_aquatic(self):
        """Standard entities are terrestrial by default."""
        return False

    def update_influence(self, world):
        """Projects the entity's danger or attraction onto the global influence heatmap."""
        if self.is_expired:
            return

        danger = getattr(self, 'danger_level', 0)

        if danger > 0:
            # Dangerous entities push others away (negative influence)
            value = danger * -5.0
            radius = int(danger * 5) + 1
            world['influence'].add_influence(self.x, self.y, value, radius)

        # Edible animals leave a scent trail that predators and hunters can follow
        if self.is_edible:
            food_range = getattr(self, '_food_value_range', None)
            if food_range:
                avg_food = sum(food_range) / 2.0
                scent_value = avg_food / 20.0  # heavier prey = stronger smell
                world['influence'].add_influence(self.x, self.y, scent_value, 2)

    def process_turn(self, world, stats):
        """
        Accumulates energy based on speed.
        Triggers update() multiple times if energy exceeds 1.0 (multi-action ticks).
        """
        if self.is_expired:
            return

        self.action_meter += self.speed

        while self.action_meter >= 1.0:
            self.update(world, stats)
            self.action_meter -= 1.0

class EntityManager:
    """
    Collection manager for all entities.
    Handles spawning, cleanup of dead entities, and iteration.
    """
    def __init__(self):
        self.entities = []

    def add(self, entity):
        """Adds a new entity to the simulation."""
        if entity:
            self.entities.append(entity)

    def remove_dead(self):
        """Permanently deletes entities marked as expired."""
        initial_count = len(self.entities)
        self.entities = [e for e in self.entities if not getattr(e, 'is_expired', False)]
        return initial_count - len(self.entities)

    def remove(self, entity):
        """Manual removal of a specific entity."""
        if entity in self.entities:
            self.entities.remove(entity)

    def __iter__(self):
        return iter(self.entities)

    def __len__(self):
        return len(self.entities)