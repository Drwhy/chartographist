from .animal import Animal
from .species.predator import Predator, Wolf, Bear
from .species.flyer import Flyer
from .species.aquatic import Aquatic

# Le dictionnaire de mapping centralisé
# Clé : (type, species) -> Valeur : (Classe, Emoji_Force)
FAUNA_MAP = {
    ("predator", "wolf"): (Wolf, "🐺"),
    ("predator", "bear"): (Bear, "🐻"),
    ("flyer", None): (Flyer, "🦅"),
    ("aquatic", None): (Aquatic, "🐟"),
}


def get_animal_class(a_type, a_species):
    """Retourne la classe et l'emoji forcé pour un type/espèce donné."""
    # On cherche d'abord le mapping précis (type + espèce)
    # Sinon on cherche le mapping générique (type seul)
    # Sinon on retourne la classe de base Animal

    config = FAUNA_MAP.get((a_type, a_species)) or FAUNA_MAP.get((a_type, None))

    if config:
        return config  # Retourne (Classe, Emoji)
    return (Animal, None)  # Par défaut, classe Animal, pas d'emoji forcé
