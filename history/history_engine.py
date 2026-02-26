import random

def evolve_world(width, height, roads, entities, cycle):
    """Gère uniquement l'évolution des infrastructures passives (routes)."""
    # Ici, on pourrait imaginer une dégradation des routes avec le temps
    # ou laisser les entités (Settlers) tracer les routes en marchant.
    return roads, []

def connect_with_road(roads, start_pos, end_pos, width, height):
    """
    Trace une route (simple algorithme de ligne) entre deux points.
    Appelé par un Settler lorsqu'il fonde un village.
    """
    x1, y1 = start_pos
    x2, y2 = end_pos

    curr_x, curr_y = x1, y1

    # Simple marche vers la cible pour tracer la route
    while (curr_x, curr_y) != (x2, y2):
        if curr_x < x2: curr_x += 1
        elif curr_x > x2: curr_x -= 1

        if curr_y < y2: curr_y += 1
        elif curr_y > y2: curr_y -= 1

        # On place le caractère de route
        if 0 <= curr_x < width and 0 <= curr_y < height:
            roads[curr_y][curr_x] = "··"