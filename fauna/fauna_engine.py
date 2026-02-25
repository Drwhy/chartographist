import random
# On importe le créateur d'instance depuis le mapper
from .fauna_mapper import create_animal

def spawn_animal(width, height, elevation, structures, theme_fauna):
    """
    Tente de créer un animal en fonction des définitions du template JSON.
    Vérifie que l'animal apparaît sur un terrain compatible.
    """
    if not theme_fauna:
        return None

    # 1. Sélection d'une coordonnée aléatoire
    rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)

    # 2. Sélection d'une définition d'animal dans le template JSON
    animal_def = random.choice(theme_fauna)

    species_name = animal_def.get("species")
    type_name = animal_def.get("type", "standard")
    char = animal_def.get("char", "🐾") # Emoji défini dans le JSON

    # 3. Validation du terrain selon l'élévation (h)
    h = elevation[ry][rx]

    # Empêcher le spawn sur une cité ou un village
    if (rx, ry) in structures:
        return None

    # Règles de spawn par type
    if type_name == "aquatic":
        if h >= 0: return None  # Besoin d'eau
    elif type_name == "flyer":
        if h < -0.2: return None # Pas en plein océan profond
    else:
        # Terrestres (standard, predator, etc.)
        if h <= 0 or h > 0.8: return None # Pas dans l'eau, ni sur les sommets impraticables

    # 4. Instanciation via le Mapper
    # C'est ici que l'emoji du JSON est injecté dans la classe Python
    return create_animal(rx, ry, species_name, type_name, char)

def init_fauna(width, height, elevation, structures, theme_fauna):
    """Initialise la population sauvage au lancement de la carte."""
    fauna_list = []
    # On tente de peupler la carte (ex: 60 tentatives pour 20 animaux max)
    for _ in range(80):
        if len(fauna_list) >= 20:
            break
        new_animal = spawn_animal(width, height, elevation, structures, theme_fauna)
        if new_animal:
            fauna_list.append(new_animal)
    return fauna_list

def update_fauna(width, height, elevation, structures, fauna_list, theme_fauna):
    """
    Gère le cycle de vie à chaque tour de simulation.
    """
    # --- NAISSANCES ---
    # Maintien de la population si elle descend trop bas
    if len(fauna_list) < 30 and random.random() < 0.15:
        new_a = spawn_animal(width, height, elevation, structures, theme_fauna)
        if new_a:
            fauna_list.append(new_a)

    # --- MORTS ---
    # Risque de mort naturelle (5% de chance qu'un animal disparaisse par tour)
    if fauna_list and random.random() < 0.05:
        fauna_list.pop(random.randint(0, len(fauna_list) - 1))

    # --- MOUVEMENTS (POLYMOPHISME) ---
    # Chaque animal utilise sa propre méthode move() définie dans sa classe
    for animal in fauna_list:
        animal.move(width, height, elevation, structures)

    return fauna_list