import random

def evolve_world(width, height, roads, entities, cycle):
    """
    Gère l'évolution des infrastructures passives (routes).
    La transformation des villages est désormais gérée par les entités elles-mêmes.
    """
    new_logs = []

    # 1. RÉSEAU ROUTIER
    # On passe le manager d'entités pour savoir où sont les structures
    _expand_roads(width, height, entities, roads)

    # On ne renvoie que DEUX valeurs pour correspondre à l'appel dans main.py
    return roads, new_logs

def _expand_roads(width, height, entities, roads):
    """Étend les routes autour des entités de type 'construct'."""
    # On récupère les positions de toutes les structures (Villages, Cités)
    struct_positions = [e.pos for e in entities if getattr(e, 'type', '') == 'construct']

    for x, y in struct_positions:
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                if random.random() < 0.05: # Chance d'extension
                    if roads[ny][nx] == "  ":
                        roads[ny][nx] = "··"