import random
import math

def seed_civilization(width, height, elevation, riv, plates, config_cultures):
    """Crée les premières colonies sur la carte."""
    initial_civ = {}
    # On tente de placer 5 à 8 colonies de départ
    for _ in range(random.randint(5, 8)):
        rx, ry = random.randint(0, width - 1), random.randint(0, height - 1)

        # Conditions : sur terre, pas trop haut, près de l'eau si possible
        if 0 <= elevation[ry][rx] < 0.4:
            # On récupère la culture de la plaque tectonique locale
            # (ou une culture aléatoire si non définie)
            local_culture = random.choice(config_cultures)

            # Création de la structure
            initial_civ[(rx, ry)] = {
                "name": f"Colonie {random.randint(1, 99)}", # Tu peux utiliser ton module names ici
                "type": "village",
                "culture": local_culture,
                "age": 0
            }
    return initial_civ

def grow_population(structures):
    """Gère l'évolution des villages en cités."""
    logs = []
    for pos, s in structures.items():
        if s["type"] == "village" and random.random() < 0.01:
            s["type"] = "city"
            logs.append(f"La colonie de {s['name']} est devenue une cité.")
    return logs
def expand_civilization(width, height, elevation, structures, config_cultures):
    """Logique de migration : les cités créent de nouveaux villages alentour."""
    logs = []
    current_cities = [pos for pos, s in structures.items() if s["type"] == "city"]

    for pos in current_cities:
        # 0.5% de chance par tour qu'une ville envoie des colons
        if random.random() < 0.005:
            cx, cy = pos
            # Tentative de placement dans un rayon de 3 à 5 cases
            dist = random.randint(3, 5)
            angle = random.uniform(0, 6.28)
            nx = int(cx + math.cos(angle) * dist)
            ny = int(cy + math.sin(angle) * dist)

            # Vérification des limites et du terrain
            if 0 <= nx < width and 0 <= ny < height:
                if elevation[ny][nx] >= 0 and (nx, ny) not in structures:
                    # Le village hérite de la culture de sa cité mère
                    parent_culture = structures[pos]["culture"]

                    structures[(nx, ny)] = {
                        "name": f"Nouveau {structures[pos]['name']}",
                        "type": "village",
                        "culture": parent_culture,
                        "age": 0
                    }
                    logs.append(f"Des colons de {structures[pos]['name']} ont fondé un nouveau village.")
    return logs

def build_roads(width, height, elevation, structures, road_map):
    """
    Trace des routes simples entre les colonies proches.
    Note : road_map est une grille de caractères (WIDTH x HEIGHT).
    """
    coords = list(structures.keys())
    if len(coords) < 2:
        return

    # On choisit deux points au hasard pour tenter de les relier
    p1 = random.choice(coords)
    p2 = random.choice(coords)

    if p1 == p2:
        return

    # Tracer une route simple (algorithme de ligne droite assisté)
    curr_x, curr_y = p1
    dest_x, dest_y = p2

    # On limite la distance des routes pour éviter de traverser toute la carte
    if abs(curr_x - dest_x) + abs(curr_y - dest_y) > 15:
        return

    # Déplacement vers la cible
    for _ in range(20): # Limite de pas pour éviter les boucles infinies
        if (curr_x, curr_y) == (dest_x, dest_y):
            break

        # Choisir la direction
        if curr_x < dest_x: curr_x += 1
        elif curr_x > dest_x: curr_x -= 1
        elif curr_y < dest_y: curr_y += 1
        elif curr_y > dest_y: curr_y -= 1

        # Ne poser une route que sur terre ferme et si pas de structure
        if 0 <= curr_x < width and 0 <= curr_y < height:
            if elevation[curr_y][curr_x] >= 0 and (curr_x, curr_y) not in structures:
                # Récupération du style de route de la culture locale
                culture_style = structures[p1]["culture"]
                road_map[curr_y][curr_x] = culture_style.get("road", ". ")