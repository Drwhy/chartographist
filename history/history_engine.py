from collections import deque


def connect_with_road(
    roads,
    start_pos,
    end_pos,
    width,
    height,
    *,
    elevations=None,
):
    """
    Trace une route orthogonale en L entre deux points.

    Avec le relief, cherche un chemin terrestre cardinal afin de ne pas créer de
    tronçons invisibles sous l'eau. Sans relief, conserve le tracé historique en
    L pour les anciens appelants.
    Typically called by a Settler when founding a new village to connect it
    to its parent city.
    """
    x1, y1 = map(int, start_pos)
    x2, y2 = map(int, end_pos)

    curr_x, curr_y = x1, y1

    def place_road(x, y):
        if 0 <= x < width and 0 <= y < height:
            roads[y][x] = "··"

    if elevations is None:
        # Finir l'axe horizontal avant de tourner sur l'axe vertical empêche les
        # diagonales et garantit un unique coude déterministe.
        while curr_x != x2:
            curr_x += 1 if curr_x < x2 else -1
            place_road(curr_x, curr_y)

        while curr_y != y2:
            curr_y += 1 if curr_y < y2 else -1
            place_road(curr_x, curr_y)
        return

    path = _land_path(
        (x1, y1),
        (x2, y2),
        width,
        height,
        elevations,
    )
    if path is None:
        return
    for x, y in path[1:]:
        place_road(x, y)


def _land_path(start, end, width, height, elevations):
    """Plus court chemin cardinal terrestre, stable et sans tirage aléatoire."""
    def in_bounds(position):
        x, y = position
        return 0 <= x < width and 0 <= y < height

    def is_land(position):
        x, y = position
        try:
            return float(elevations[y][x]) >= 0
        except (IndexError, TypeError, ValueError):
            return False

    if not in_bounds(start) or not in_bounds(end):
        return None
    if not is_land(start) or not is_land(end):
        return None

    horizontal = 1 if end[0] >= start[0] else -1
    vertical = 1 if end[1] >= start[1] else -1
    directions = (
        (horizontal, 0),
        (0, vertical),
        (-horizontal, 0),
        (0, -vertical),
    )
    parents = {start: None}
    frontier = deque((start,))
    while frontier:
        current = frontier.popleft()
        if current == end:
            break
        x, y = current
        for dx, dy in directions:
            neighbor = (x + dx, y + dy)
            if (
                neighbor not in parents
                and in_bounds(neighbor)
                and is_land(neighbor)
            ):
                parents[neighbor] = current
                frontier.append(neighbor)

    if end not in parents:
        return None
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = parents[current]
    path.reverse()
    return path
