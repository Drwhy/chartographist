import random

def evolve_world(width, height, elevation, rivers, _, structures, roads, cycle):
    """
    Gère l'évolution structurelle du monde :
    - Transformation des villages en cités.
    - Dégradation des structures isolées en ruines.
    - Expansion des routes.
    """
    new_logs = []

    # On itère sur une copie pour pouvoir modifier le dictionnaire en cours de route
    for pos, data in list(structures.items()):
        stype = data.get('type')
        culture = data.get('culture', {})
        name = data.get('name', "Lieu-dit")

        # 1. ÉVOLUTION : VILLAGE -> CITY
        # Une cité est nécessaire pour générer des colons (Settlers)
        if stype == "village":
            # Condition d'évolution : proximité de l'eau ou simple chance au fil du temps
            is_near_water = rivers[pos[1]][pos[0]] > 0 or elevation[pos[1]][pos[0]] < 0
            evolution_chance = 0.005 if is_near_water else 0.001

            if random.random() < evolution_chance:
                data['type'] = "city"
                new_logs.append(f"🏛️  {name} s'est développée en une cité majestueuse.")

        # 2. DÉGRADATION : RUINES
        # Si une structure est très ancienne ou isolée, elle peut tomber en ruine
        if stype not in ["ruin", "site"]:
            if random.random() < 0.0001: # Très rare
                data['type'] = "ruin"
                new_logs.append(f"🏚️  La structure à {pos} est tombée en ruine.")

    # 3. RÉSEAU ROUTIER (Optionnel)
    # Les routes s'étendent naturellement autour des structures existantes
    _expand_roads(width, height, structures, roads)

    return structures, new_logs, []

def _expand_roads(width, height, structures, roads):
    """Petite logique simple pour étendre les routes autour des centres civils."""
    for pos in structures:
        x, y = pos
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                if random.random() < 0.05: # Chance d'extension
                    # On place un caractère de route si ce n'est pas déjà occupé
                    if roads[ny][nx] == "  ":
                        roads[ny][nx] = "··"