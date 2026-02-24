import random

# On importe le mapper qui contient la logique de sélection des classes
from .fauna_mapper import get_animal_class


def spawn_animal(width, height, elevation, structures, theme_fauna):
    """
    Crée une instance d'animal en utilisant le mapping centralisé.
    Vérifie la cohérence entre le type d'animal et le terrain.
    """
    if not theme_fauna:
        return None

    # 1. Sélection aléatoire d'une définition dans le thème
    rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)
    animal_def = random.choice(theme_fauna)

    a_type = animal_def["type"]
    a_species = animal_def.get("species")
    a_char_default = animal_def["char"]

    # 2. Consultation du Mapper pour obtenir la Classe et l'Emoji forcé
    AnimalClass, forced_char = get_animal_class(a_type, a_species)
    char_to_use = forced_char if forced_char else a_char_default

    # 3. Validation du terrain (Élévation)
    h = elevation[ry][rx]

    # Sécurité : On ne spawn pas sur une structure (ville/village)
    if (rx, ry) in structures:
        return None

    # Logique spécifique par grand type de mouvement
    if a_type == "aquatic":
        if h >= 0:
            return None  # Les aquatiques ont besoin d'eau (h < 0)
    elif a_type == "flyer":
        if h < -0.2:
            return None  # Les oiseaux ne spawnent pas en plein océan profond
    else:
        # Terrestres (Standard, Predator, Wolf, Bear)
        if h <= 0 or h > 0.8:
            return None  # Pas dans l'eau, pas sur les pics impraticables

    # 4. Instanciation dynamique
    return AnimalClass(rx, ry, char_to_use)


def init_fauna(width, height, elevation, structures, theme_fauna):
    """Initialise la population au début de la simulation."""
    fauna_list = []
    # Tentatives de peuplement initial
    for _ in range(60):
        if len(fauna_list) >= 18:
            break
        new_animal = spawn_animal(width, height, elevation, structures, theme_fauna)
        if new_animal:
            fauna_list.append(new_animal)
    return fauna_list


def update_fauna(width, height, elevation, structures, fauna_list, theme_fauna):
    """
    Cycle de vie à chaque tour :
    - Naissances (selon quota)
    - Morts naturelles
    - Mouvements (Polymorphisme)
    """

    # --- NAISSANCES ---
    # On maintient une population dynamique
    if len(fauna_list) < 25 and random.random() < 0.2:
        new_a = spawn_animal(width, height, elevation, structures, theme_fauna)
        if new_a:
            fauna_list.append(new_a)

    # --- MORTS ---
    # Risque de disparition (vieillesse, famine ou sortie de carte)
    if fauna_list and random.random() < 0.05:
        fauna_list.pop(random.randint(0, len(fauna_list) - 1))

    # --- MOUVEMENTS ---
    # Chaque instance (Loup, Ours, Oiseau) exécute sa propre méthode move()
    for animal in fauna_list:
        animal.move(width, height, elevation, structures)

    return fauna_list
