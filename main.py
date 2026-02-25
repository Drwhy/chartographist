import sys, time, random, math
import numpy as np
import geo, culture, history, names, fauna

WIDTH, HEIGHT = 60, 30

def get_char(x, y, elevation, river_map, structures, road_map, config, cycle, fauna_list=[]):
    """
    Rendu graphique basé sur le template JSON chargé.
    """
    h = elevation[y][x]
    r = river_map[y][x]
    rd = road_map[y][x]

    # Raccourcis vers les sections du template
    bio = config["biomes"]
    wat = config["water"]
    spec = config["special"]

    # --- 1. CLIMAT ---
    dist_to_equator = abs(y - (HEIGHT // 2)) / (HEIGHT // 2)
    tilt = math.sin(cycle * 0.15)
    local_temp = (dist_to_equator * 0.6) + (tilt * (y / HEIGHT - 0.5) * 0.5) + (h * 0.4)

    # --- 2. STRUCTURES (Priorité 1) ---
    if (x, y) in structures:
        s = structures[(x, y)]
        if s["type"] == "ruin": return spec["ruin"]
        # Logique de port dynamique
        if s["type"] == "village":
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < HEIGHT and 0 <= nx < WIDTH:
                    if elevation[ny][nx] < 0: return spec["port"]
        return s["culture"][s["type"]]

    # --- 3. FAUNE (Priorité 2) ---
    for animal in fauna_list:
        if animal.pos == (x, y):
            return animal.char

    # --- 4. RÉSEAUX ---
    if rd != "  " and h >= 0: return rd
    if r > 0 and h >= 0: return wat["river"]

    # --- 5. RELIEF & BIOMES ---
    if h > 0.90: return bio["volcano"]
    if h > 0.85 or local_temp > 0.8: return bio["peak"]
    if h > 0.55: return bio["high_mountain"]
    if h > 0.35: return bio["mountain"]

    if h < -0.15: return wat["ocean"]
    if h < 0: return wat["shore"]
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

def draw(elevation, river_map, structures, road_map, seed, year, config, logs, cycle, fauna_list=[], radial_reveal=False):
    """Affiche la carte dans le terminal."""
    current_display = [["  " for _ in range(WIDTH)] for _ in range(HEIGHT)]
    pop = sum(15000 if s["type"] == "city" else 1500 for s in structures.values())

    status = "SOLSTICE" if abs(math.sin(cycle * 0.15)) > 0.7 else "ÉQUINOXE"

    if radial_reveal:
        center_x, center_y = WIDTH // 2, HEIGHT // 2
        coords = [(x, y) for y in range(HEIGHT) for x in range(WIDTH)]
        coords.sort(key=lambda c: math.dist(c, (center_x, center_y)) + random.uniform(-1, 1))

        for i, (x, y) in enumerate(coords):
            current_display[y][x] = get_char(x, y, elevation, river_map, structures, road_map, config, cycle, fauna_list)
            if i % 12 == 0 or i == len(coords) - 1:
                sys.stdout.write("\033[H")
                print(f"--- 📜 GENÈSE : {config.get('world_name', 'Monde')} | SEED: {seed} ---")
                bar = int((i / len(coords)) * (WIDTH * 2))
                print("▕" + "█" * bar + "░" * (WIDTH * 2 - bar) + "▏")
                for row in current_display: print("".join(row))
                sys.stdout.flush()
                time.sleep(0.005)
    else:
        sys.stdout.write("\033[H")
        print(f"--- 🗺️  {config.get('world_name', 'SIMULATION').upper()} | {status} ---")
        print(f"⏳ AN: {year} | 👥 POP: {pop:,} | 🐾 FAUNE: {len(fauna_list)}")
        print("=" * WIDTH * 2)
        for y in range(HEIGHT):
            line = "".join([get_char(x, y, elevation, river_map, structures, road_map, config, cycle, fauna_list) for x in range(WIDTH)])
            print(line)
        print("=" * WIDTH * 2)
        for l in logs[-5:]: print(f" > {l}")
        sys.stdout.flush()

if __name__ == "__main__":
    # Nettoyage terminal et masquage curseur
    sys.stdout.write("\033[2J\033[H\033[?25l")

    # 1. Chargement de la Configuration (Template JSON)
    template_path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else "template.json"
    world_config = culture.load_template(template_path)

    # 2. Paramètres de base
    seed_val = sys.argv[2] if len(sys.argv) > 2 else random.randint(0, 99999)

    # 3. Génération Géo & Hydrologie
    elev, plates = geo.generate_geology(WIDTH, HEIGHT, seed_val)

    # Attribution des cultures depuis le template
    for p in plates:
        p["culture"] = random.choice(world_config["cultures"])

    riv = geo.simulate_hydrology(WIDTH, HEIGHT, elev)

    road_grid = [["  " for _ in range(WIDTH)] for _ in range(HEIGHT)]
    civ = {}
    all_logs = [f"Démarrage de l'univers : {world_config.get('world_name')}"]

    # 4. Initialisation Faune
    fauna_list = fauna.init_fauna(WIDTH, HEIGHT, elev, civ, world_config["fauna"])

    # 5. Rendu initial (Genèse)
    draw(elev, riv, civ, road_grid, seed_val, 0, world_config, all_logs, 0, fauna_list, radial_reveal=True)

    # 6. Boucle de Simulation
    try:
        for cycle in range(1, 1001):
            year = cycle * 10

            # Évolution des cités
            civ, new_logs = history.evolve_civilization(WIDTH, HEIGHT, elev, riv, plates, civ, road_grid, cycle)
            all_logs.extend(new_logs)

            # Évolution de la faune
            fauna_list = fauna.update_fauna(WIDTH, HEIGHT, elev, civ, fauna_list, world_config["fauna"])

            # Affichage
            draw(elev, riv, civ, road_grid, seed_val, year, world_config, all_logs, cycle, fauna_list)
            time.sleep(0.3)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h\n") # Rétablir le curseur