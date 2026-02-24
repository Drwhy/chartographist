import sys, time, random, math
import numpy as np
import geo, culture, history, names, fauna

WIDTH, HEIGHT = 60, 30

def get_char(x, y, elevation, river_map, structures, road_map, theme, cycle, fauna_list=[]):
    """
    Rendu graphique. Gère la priorité d'affichage des instances d'objets.
    """
    h = elevation[y][x]
    r = river_map[y][x]
    rd = road_map[y][x]
    bio = theme["biomes"]
    spec = theme["special"]

    # --- 1. CLIMAT & SAISONS ---
    dist_to_equator = abs(y - (HEIGHT // 2)) / (HEIGHT // 2)
    tilt = math.sin(cycle * 0.15)
    local_temp = (dist_to_equator * 0.6) + (tilt * (y / HEIGHT - 0.5) * 0.5) + (h * 0.4)

    # --- 2. STRUCTURES (Priorité 1) ---
    if (x, y) in structures:
        s = structures[(x, y)]
        if s["type"] == "ruin": return spec["ruin"]
        if s["type"] == "village":
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < HEIGHT and 0 <= nx < WIDTH:
                    if elevation[ny][nx] < 0: return spec["port"]
        return s["culture"][s["type"]]

    # --- 3. FAUNE (Priorité 2 : Instances Loup, Ours, etc.) ---
    for animal in fauna_list:
        if animal.pos == (x, y):
            return animal.char

    # --- 4. RÉSEAUX (Routes & Rivières) ---
    if rd != "  " and h >= 0: return rd
    if r > 0 and h >= 0: return theme["water"]["river"]

    # --- 5. BIOMES & RELIEF ---
    if h > 0.90: return bio["volcano"]
    if h > 0.85 or local_temp > 0.8: return bio["peak"]
    if h > 0.55: return bio["high_mountain"]
    if h > 0.35: return bio["mountain"]
    
    if h < -0.15: return theme["water"]["ocean"]
    if h < 0: return theme["water"]["shore"]
    if h < 0.05: return bio["sand"]

    # Biomes dynamiques selon température
    if local_temp > 0.65:
        return bio["boreal_forest"] if h > 0.2 else bio["glaciated"]
    elif local_temp > 0.45:
        if h > 0.2 and 0.48 < local_temp < 0.55: return bio["autumn_forest"]
        return bio["temperate_forest"] if h > 0.2 else bio["grassland"]
    elif local_temp < 0.25:
        return bio["tropical_forest"] if h > 0.12 else bio["grassland"]
    else:
        return bio["temperate_forest"] if h > 0.2 else bio["grassland"]

def draw(elevation, river_map, structures, road_map, seed, year, theme_name, logs, cycle, fauna_list=[], radial_reveal=False):
    theme = culture.THEMES[theme_name]
    current_display = [["  " for _ in range(WIDTH)] for _ in range(HEIGHT)]
    pop = sum(15000 if s["type"] == "city" else 1500 for s in structures.values())
    
    status = "SOLSTICE" if abs(math.sin(cycle * 0.15)) > 0.7 else "ÉQUINOXE"

    if radial_reveal:
        center_x, center_y = WIDTH // 2, HEIGHT // 2
        coords = [(x, y) for y in range(HEIGHT) for x in range(WIDTH)]
        coords.sort(key=lambda c: math.dist(c, (center_x, center_y)) + random.uniform(-1, 1))

        for i, (x, y) in enumerate(coords):
            current_display[y][x] = get_char(x, y, elevation, river_map, structures, road_map, theme, cycle, fauna_list)
            if i % 10 == 0 or i == len(coords) - 1:
                sys.stdout.write("\033[H")
                print(f"--- 📜 GENÈSE PLANÉTAIRE | SEED: {seed} ---")
                bar = int((i / len(coords)) * (WIDTH * 2))
                print("▕" + "█" * bar + "░" * (WIDTH * 2 - bar) + "▏")
                for row in current_display: print("".join(row))
                sys.stdout.flush()
                time.sleep(0.005)
    else:
        sys.stdout.write("\033[H")
        print(f"--- 🗺️  CHARTOGRAPHIST | {theme_name.upper()} | {status} ---")
        print(f"⏳ AN: {year} | 👥 POP: {pop:,} | 🐾 FAUNE: {len(fauna_list)}")
        print("=" * WIDTH * 2)
        for y in range(HEIGHT):
            line = "".join([get_char(x, y, elevation, river_map, structures, road_map, theme, cycle, fauna_list) for x in range(WIDTH)])
            print(line)
        print("=" * WIDTH * 2)
        for l in logs[-5:]: print(f" > {l}")
        sys.stdout.flush()

if __name__ == "__main__":
    sys.stdout.write("\033[2J\033[H\033[?25l")
    
    theme_choice = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in culture.THEMES else "fantasy"
    seed_val = sys.argv[2] if len(sys.argv) > 2 else random.randint(0, 99999)

    # 1. Génération Géo
    elev, plates = geo.generate_geology(WIDTH, HEIGHT, seed_val)
    for p in plates: p["culture"] = random.choice(culture.CULTURES)
    riv = geo.simulate_hydrology(WIDTH, HEIGHT, elev)
    
    road_grid = [["  " for _ in range(WIDTH)] for _ in range(HEIGHT)]
    civ = {}
    all_logs = ["La chronique commence."]

    # 2. Initialisation Faune (Le package fauna gère ses propres sous-classes)
    theme_fauna_defs = culture.THEMES[theme_choice].get("fauna", [])
    fauna_list = fauna.init_fauna(WIDTH, HEIGHT, elev, civ, theme_fauna_defs)

    # 3. Genèse
    draw(elev, riv, civ, road_grid, seed_val, 0, theme_choice, all_logs, 0, fauna_list, radial_reveal=True)

    # 4. Simulation
    try:
        for cycle in range(1, 501):
            year = cycle * 10
            civ, new_logs = history.evolve_civilization(WIDTH, HEIGHT, elev, riv, plates, civ, road_grid, cycle)
            all_logs.extend(new_logs)
            
            # Mise à jour de la faune (instances spécifiques Loup/Ours bougent ici)
            fauna_list = fauna.update_fauna(WIDTH, HEIGHT, elev, civ, fauna_list, theme_fauna_defs)
            
            draw(elev, riv, civ, road_grid, seed_val, year, theme_choice, all_logs, cycle, fauna_list)
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass

    sys.stdout.write("\033[?25h\n")