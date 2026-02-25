from .species import Animal, Wolf, Bear, Eagle, Shark, Flyer, Aquatic, Predator

# Registre des classes disponibles
STR_TO_CLASS = {
    "wolf": Wolf,
    "bear": Bear,
    "eagle": Eagle,
    "shark": Shark,
    "flyer": Flyer,
    "aquatic": Aquatic,
    "predator": Predator
}

def create_animal(x, y, species_name, type_name, char):
    """
    Instancie la classe appropriée avec l'emoji fourni par le JSON.
    """
    # 1. On cherche par espèce (wolf, bear...)
    # 2. Sinon on cherche par type (flyer, aquatic...)
    # 3. Sinon on utilise la classe Animal de base
    TargetClass = STR_TO_CLASS.get(species_name) or STR_TO_CLASS.get(type_name) or Animal

    return TargetClass(x, y, char)