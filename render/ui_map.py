import math
import time
import sys
from core.random_service import RandomService

def get_char_at(x, y, world_data, config):
    """Détermine le caractère unique pour une coordonnée (x, y) avec logique climatique complète."""
    # 1. EXTRACTION DES DONNÉES
    h = world_data['elev'][y][x]
    r = world_data['riv'][y][x]
    rd = world_data['road'][y][x]
    cycle = world_data.get('cycle', 0)
    width = world_data['width']
    height = world_data['height']

    # 2. PRIORITÉ 1 : ENTITÉS (Humain > Animal > Structure)
    entities_at_pos = [e for e in world_data['entities'] if e.pos == (x, y)]
    if entities_at_pos:
        # On trie pour que les acteurs (🚶, 🏹) s'affichent par-dessus les villages (🏠)
        entities_at_pos.sort(key=lambda e: 10 if e.type == 'actor' else (5 if e.type == 'construct' else 1))
        entity = entities_at_pos[-1]

        # Logique spécifique aux ports (si village au bord de l'eau)
        if getattr(entity, 'subtype', '') == "village":
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    if world_data['elev'][ny][nx] < 0:
                        return entity.culture.get("port", config.get("special", {}).get("port", "⚓"))

        return entity.char

    # 3. PRIORITÉ 2 : INFRASTRUCTURES (Routes et Rivières)
    if rd and rd != "  " and h >= 0:
        return rd
    if r > 0 and h >= 0:
        return config.get("water", {}).get("river", "~~")

    # 4. PRIORITÉ 3 : TERRAIN ET BIOMES (Logique climatique procédurale)
    return _calculate_complex_biome(x, y, h, cycle, width, height, config)

def _calculate_complex_biome(x, y, h, cycle, width, height, config):
    """Calcule le biome en fonction de l'altitude, de la latitude et des saisons (tilt)."""
    bio = config.get("biomes", {})
    wat = config.get("water", {})

    # --- CALCUL DE LA TEMPÉRATURE ---
    # Latitude (plus froid aux pôles, chaud à l'équateur)
    dist_to_equator = abs(y - (height // 2)) / (height // 2)
    # Inclinaison axiale (simule les saisons au fil des cycles)
    tilt = math.sin(cycle * 0.15)
    # Formule combinée : Latitude + Saison + Altitude (plus haut = plus froid)
    temp = (dist_to_equator * 0.6) + (tilt * (y / height - 0.5) * 0.5) + (h * 0.4)

    # --- SEUILS D'ÉLÉVATION ---
    if h > 0.90: return bio.get("volcano", "🌋")
    if h > 0.85 or temp > 0.8: return bio.get("peak", "❄️")
    if h > 0.55: return bio.get("high_mountain", "🏔️")
    if h > 0.35: return bio.get("mountain", "⛰️")

    # --- SEUILS D'EAU ---
    if h < -0.15: return wat.get("ocean", "🌊")
    if h < 0: return wat.get("shore", "💧")
    if h < 0.05: return bio.get("sand", "🏖️")

    # --- DISTRIBUTION PAR TEMPÉRATURE (Végétation) ---
    if temp > 0.65:
        return bio.get("boreal_forest", "🌲") if h > 0.2 else bio.get("glaciated", "❄️")

    if temp > 0.45:
        # Forêt d'automne si conditions spécifiques
        if h > 0.2 and 0.48 < temp < 0.55:
            return bio.get("autumn_forest", "🍂")
        return bio.get("temperate_forest", "🌳")

    if temp < 0.25 and h > 0.12:
        return bio.get("tropical_forest", "🌴")

    # FALLBACK : La plaine par défaut
    return bio.get("grassland", "🌿")

def render_map(width, height, world_data, config):
    """Affiche la grille de la carte ligne par ligne."""
    # On s'assure que world_data contient les dimensions pour get_char_at
    world_data['width'] = width
    world_data['height'] = height

    for y in range(height):
        line = "".join([get_char_at(x, y, world_data, config) for x in range(width)])
        print(line)

def radial_reveal(renderer, world_data, stats):
    """Animation de genèse radiale."""
    width, height = renderer.width, renderer.height
    world_data['width'], world_data['height'] = width, height

    current_display = [["  " for _ in range(width)] for _ in range(height)]
    coords = [(x, y) for y in range(height) for x in range(width)]
    center = (width // 2, height // 2)
    coords.sort(key=lambda c: math.dist(c, center) + RandomService.uniform(-1, 1))

    for i, (x, y) in enumerate(coords):
        current_display[y][x] = get_char_at(x, y, world_data, renderer.config)
        if i % 15 == 0 or i == len(coords) - 1:
            sys.stdout.write("\033[H")
            print(f"--- 📜 GENÈSE : {stats['seed']} ---")
            for row in current_display:
                print("".join(row))
            sys.stdout.flush()
            time.sleep(0.005)