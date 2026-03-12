"""
Centralized registry for entity classification.
Decorators are used to categorize classes into global catalogs,
allowing systems like the SpawnSystem or RenderEngine to filter entities by type.
"""

# Empty catalogs at initialization
WILD_SPECIES = []
CIV_UNITS = []
STRUCTURE_TYPES = []

def register_wild(cls):
    """Decorator to register a wild species (Animals, Monsters, etc.)."""
    WILD_SPECIES.append(cls)
    return cls

def register_civ(cls):
    """Decorator to register a civilization unit (Humans, Traders, Settlers, etc.)."""
    CIV_UNITS.append(cls)
    return cls

def register_structure(cls):
    """Decorator to register a structure or construct (Cities, Ruins, Ports, etc.)."""
    STRUCTURE_TYPES.append(cls)
    return cls