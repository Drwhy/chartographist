import noise
import numpy as np
import math
from core.random_service import RandomService

def generate_geology(width, height, scale=20.0):
    """
    Generates the base terrain elevation using Perlin noise.
    Also defines tectonic plates used for cultural distribution.
    Returns:
        elevation (np.array): Normalized elevation map (-1.0 to 1.0).
        plates (list): List of coordinate centers for regional variation.
    """
    elevation = np.zeros((height, width))

    # Define tectonic plates for future cultural zones
    num_plates = 8
    plates = [
        {"center": (RandomService.randint(0, width - 1), RandomService.randint(0, height - 1))}
        for _ in range(num_plates)
    ]

    # Randomized offsets to ensure unique seeds for every world
    offset_x = RandomService.randint(0, 1000)
    offset_y = RandomService.randint(0, 1000)

    for y in range(height):
        for x in range(width):
            # 8 Octaves used for rugged, steep relief
            n = noise.pnoise2(
                (x + offset_x) / scale,
                (y + offset_y) / scale,
                octaves=8,
                persistence=0.5
            )
            elevation[y][x] = n

    # --- FORCED NORMALIZATION ---
    # Stretch values to ensure consistent range across various seeds
    v_min, v_max = elevation.min(), elevation.max()
    # Normalize to -1 to 1 range
    elevation = (elevation - v_min) / (v_max - v_min) * 2 - 1

    # Mountain Accentuation: Sharpen peaks using power function for dramatic slopes
    elevation = np.where(elevation > 0, np.power(np.maximum(elevation, 0), 0.7), elevation)

    return elevation, plates


def simulate_hydrology(width, height, elevation):
    """
    Simulates river carving based on elevation gradient (gravity).
    Rivers start at high altitudes and flow toward the lowest neighboring point.
    """
    river_map = np.zeros((height, width))

    # Simulate 70 distinct springs/river sources
    for _ in range(70):
        # Pick a random starting point
        curr_x = RandomService.randint(0, width - 1)
        curr_y = RandomService.randint(0, height - 1)

        # Rivers only start at higher elevations (e.g., mountains/hills)
        if elevation[curr_y][curr_x] > 0.4:
            for _ in range(150): # Max river length
                river_map[curr_y][curr_x] += 1
                best_neighbor = None
                lowest_h = elevation[curr_y][curr_x]

                # Check cardinal neighbors for steepest descent
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = curr_y + dy, curr_x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        if elevation[ny][nx] < lowest_h:
                            lowest_h = elevation[ny][nx]
                            best_neighbor = (nx, ny)

                # Stop if no lower neighbor is found or if we hit the sea
                if not best_neighbor or elevation[best_neighbor[1]][best_neighbor[0]] < -0.1:
                    break

                curr_x, curr_y = best_neighbor

    return river_map