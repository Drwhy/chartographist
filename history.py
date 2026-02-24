import random
import math
import numpy as np
import names


def trace_road(road_map, p1, p2, road_char, width, height):
    """Trace une ligne de caractères entre deux points pour simuler une route."""
    x1, y1 = p1
    x2, y2 = p2
    steps = max(abs(x2 - x1), abs(y2 - y1))
    if steps == 0:
        return
    for i in range(steps + 1):
        rx, ry = int(x1 + (x2 - x1) * i / steps), int(y1 + (y2 - y1) * i / steps)
        if 0 <= ry < height and 0 <= rx < width:
            if road_map[ry][rx] == "  ":
                road_map[ry][rx] = road_char


def evolve_civilization(
    width, height, elevation, river_map, plates, structures, road_map, cycle
):
    """Gère le cycle de vie des structures : naissance, déclin, ruines et expansion."""
    logs = []
    next_gen = structures.copy()

    # --- 1. GESTION DU DÉCLIN (L'ÂGE DES RUINES) ---
    # L'inclinaison axiale (tilt) influence la rudesse de l'hiver
    tilt = math.sin(cycle * 0.15)

    for (x, y), data in list(structures.items()):
        # Calcul de la température locale pour évaluer le risque de survie
        dist_to_equator = abs(y - (height // 2)) / (height // 2)
        # On simule la pénibilité du froid (local_cold > 0.5 = zone de danger)
        local_cold = (dist_to_equator * 0.6) + (tilt * (y / height - 0.5) * 0.5)

        # Chance de base de déclin (0.5% par décennie)
        decay_chance = 0.005

        # Malus de survie en cas de grand froid
        if local_cold > 0.6:
            decay_chance += 0.03

        # Gestion spécifique des RUINES
        if data.get("type") == "ruin":
            # Une ruine finit par disparaître totalement (5% de chance)
            if random.random() < 0.05:
                del next_gen[(x, y)]
                logs.append(
                    f"🪦 La nature a repris ses droits sur les ruines de {data['name']}."
                )
            continue

        # Test de déclin pour les structures vivantes
        if random.random() < decay_chance:
            if data["type"] == "city":
                # Une cité devient un village avant de mourir
                next_gen[(x, y)]["type"] = "village"
                logs.append(
                    f"📉 La cité de {data['name']} a décliné en simple village."
                )
            else:
                # Un village devient une ruine
                next_gen[(x, y)]["type"] = "ruin"
                logs.append(f"🏚️ Le village de {data['name']} est tombé en ruines.")
            continue

    # --- 2. FONDATION INITIALE (RENAISSANCE) ---
    # Si le monde est vide ou presque, de nouvelles cultures apparaissent
    if len(next_gen) < 2:
        candidates = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if 0.1 < elevation[y][x] < 0.4 and river_map[y][x] > 1
        ]

        # Fallback si pas de bord de rivière idéal
        if not candidates:
            candidates = [
                (x, y)
                for y in range(height)
                for x in range(width)
                if 0.1 < elevation[y][x] < 0.5
            ]

        for x, y in random.sample(candidates, min(len(candidates), 3)):
            if (x, y) not in next_gen:
                p_id = np.argmin([math.dist((x, y), p["center"]) for p in plates])
                cult = plates[p_id]["culture"]
                name = names.generate_city_name(cult["name"])
                next_gen[(x, y)] = {"type": "city", "culture": cult, "name": name}
                logs.append(
                    f"✨ Renaissance : {name} est érigée par le peuple {cult['name']}."
                )
        return next_gen, logs

    # --- 3. EXPANSION ET PROMOTION ---
    for (x, y), data in list(next_gen.items()):
        # Les ruines n'agissent pas
        if data["type"] == "ruin":
            continue

        cult = data["culture"]

        # Expansion : Les cités fondent des villages aux alentours
        if data["type"] == "city" and random.random() < 0.12:
            angle = random.uniform(0, 2 * math.pi)
            dist = random.randint(5, 10)
            nx, ny = int(x + math.cos(angle) * dist), int(y + math.sin(angle) * dist)

            if 0 <= nx < width and 0 <= ny < height:
                # On ne construit que sur des terrains praticables et vides
                if 0.05 < elevation[ny][nx] < 0.5 and (nx, ny) not in next_gen:
                    v_name = names.generate_city_name(cult["name"])
                    next_gen[(nx, ny)] = {
                        "type": "village",
                        "culture": cult,
                        "name": v_name,
                    }
                    # Création de la route commerciale
                    trace_road(road_map, (x, y), (nx, ny), cult["road"], width, height)
                    logs.append(f"🏠 {data['name']} a fondé le village de {v_name}.")

        # Promotion : Un village bien placé devient une cité
        if (
            data["type"] == "village"
            and river_map[y][x] >= 1
            and random.random() < 0.08
        ):
            next_gen[(x, y)]["type"] = "city"
            logs.append(f"🏰 Le bourg de {data['name']} s'élève au rang de cité.")

    # --- 4. ÉROSION DES INFRASTRUCTURES ---
    erode_roads(width, height, road_map, next_gen)
    # --- NOUVELLE RÈGLE : CATASTROPHES ---
    handle_volcanoes(width, height, elevation, structures, road_map, logs)
    
    return next_gen, logs


def erode_roads(width, height, road_map, structures):
    """Fait disparaître les routes qui ne sont plus connectées à la vie."""
    for y in range(height):
        for x in range(width):
            if road_map[y][x] != "  ":
                # On vérifie les voisins directs pour voir s'il y a de la vie
                has_life_nearby = False
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        if (nx, ny) in structures and structures[(nx, ny)][
                            "type"
                        ] != "ruin":
                            has_life_nearby = True
                            break

                # Si la route est isolée ou ne mène qu'à des ruines
                # 10% de chance de s'effacer par tour d'abandon
                if not has_life_nearby and random.random() < 0.1:
                    road_map[y][x] = "  "

def handle_volcanoes(width, height, elevation, structures, road_map, logs):
    """Gère le réveil des volcans et leurs dégâts."""
    for y in range(height):
        for x in range(width):
            # Si c'est un sommet très haut (potentiel volcan)
            if elevation[y][x] > 0.9:
                # Chance d'éruption très faible (0.1% par décennie)
                if random.random() < 0.001:
                    logs.append(f"🌋 Le volcan au sommet du {'Nord' if y < height/2 else 'Sud'} s'est réveillé !")
                    
                    # Rayon de destruction (2 à 3 cases)
                    radius = 3
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < height and 0 <= nx < width:
                                # Distance euclidienne pour un cercle d'éruption
                                if math.dist((x, y), (nx, ny)) <= radius:
                                    # Destruction des routes
                                    road_map[ny][nx] = "  "
                                    # Destruction des cités/villages
                                    if (nx, ny) in structures:
                                        name = structures[(nx, ny)]["name"]
                                        del structures[(nx, ny)]
                                        logs.append(f"🔥 {name} a été anéantie par la lave.")
