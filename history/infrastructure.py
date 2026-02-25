import random

def build_roads(width, height, elevation, structures, road_map):
    coords = list(structures.keys())
    if len(coords) < 2: return
    p1, p2 = random.sample(coords, 2)

    curr_x, curr_y = p1
    dest_x, dest_y = p2

    if abs(curr_x - dest_x) + abs(curr_y - dest_y) > 15: return

    for _ in range(20):
        if (curr_x, curr_y) == (dest_x, dest_y): break
        if curr_x < dest_x: curr_x += 1
        elif curr_x > dest_x: curr_x -= 1
        elif curr_y < dest_y: curr_y += 1
        elif curr_y > dest_y: curr_y -= 1

        if 0 <= curr_x < width and 0 <= curr_y < height:
            if elevation[curr_y][curr_x] >= 0 and (curr_x, curr_y) not in structures:
                culture_style = structures[p1]["culture"]
                road_map[curr_y][curr_x] = culture_style.get("road", ". ")