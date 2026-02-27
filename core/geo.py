import noise
import numpy as np
import math
from core.random_service import RandomService

def generate_geology(width, height, scale=20.0):
    elevation = np.zeros((height, width))

    # On définit les plaques pour les futures cultures
    num_plates = 8
    plates = [
        {"center": (RandomService.randint(0, width - 1), RandomService.randint(0, height - 1))}
        for _ in range(num_plates)
    ]

    off_x, off_y = RandomService.randint(0, 1000), RandomService.randint(0, 1000)

    for y in range(height):
        for x in range(width):
            # Utilisation de 8 octaves pour du relief escarpé
            n = noise.pnoise2(
                (x + off_x) / scale, (y + off_y) / scale, octaves=8, persistence=0.5
            )
            elevation[y][x] = n

    # --- NORMALISATION FORCEE ---
    # On étire les valeurs pour que le point le plus haut soit tjs > 0.8
    v_min, v_max = elevation.min(), elevation.max()
    elevation = (elevation - v_min) / (v_max - v_min) * 2 - 1  # Range -1 to 1

    # Accentuation des sommets (Exposant)
    elevation = np.where(elevation > 0, np.power(elevation, 0.7), elevation)

    return elevation, plates


def simulate_hydrology(width, height, elevation):
    river_map = np.zeros((height, width))
    for _ in range(70):
        cx, cy = RandomService.randint(0, width - 1), RandomService.randint(0, height - 1)
        if elevation[cy][cx] > 0.4:
            for _ in range(150):
                river_map[cy][cx] += 1
                best_n = None
                curr_h = elevation[cy][cx]
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        if elevation[ny][nx] < curr_h:
                            curr_h = elevation[ny][nx]
                            best_n = (nx, ny)
                if not best_n or elevation[best_n[1]][best_n[0]] < -0.1:
                    break
                cx, cy = best_n
    return river_map
