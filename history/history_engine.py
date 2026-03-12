def connect_with_road(roads, start_pos, end_pos, width, height):
    """
    Traces a road using a simple line algorithm between two points.
    Typically called by a Settler when founding a new village to connect it
    to its parent city.
    """
    x1, y1 = start_pos
    x2, y2 = end_pos

    curr_x, curr_y = x1, y1

    # Simple step-by-step walk towards the target to trace the path
    while (curr_x, curr_y) != (x2, y2):
        # Horizontal step
        if curr_x < x2:
            curr_x += 1
        elif curr_x > x2:
            curr_x -= 1

        # Vertical step
        if curr_y < y2:
            curr_y += 1
        elif curr_y > y2:
            curr_y -= 1

        # Place the road character if within world boundaries
        if 0 <= curr_x < width and 0 <= curr_y < height:
            # Using double dots to match the 2-character tile width
            roads[curr_y][curr_x] = "··"