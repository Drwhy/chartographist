"""
Package Core : Regroupe les utilitaires système, les générateurs de noms 
et l'usine de création du monde.
"""

# Import des fonctions système (Plomberie)
from .system import (
    init_terminal, 
    restore_terminal, 
    load_arguments
)

# Import de la Factory (Usine à mondes)
from .world_factory import assemble_world

# Import du générateur de noms (Identité)
from .names import (
    generate_name, 
    get_name_by_culture
)