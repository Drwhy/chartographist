import random

def event_volcanic_eruption(width, height, elevation, structures):
    """Trouve un volcan et détruit ce qu'il y a autour."""
    volcanoes = [(x, y) for y in range(height) for x in range(width) if elevation[y][x] > 0.90]
    if not volcanoes: return None

    vx, vy = random.choice(volcanoes)
    logs = []

    # Impact sur un rayon de 2 cases
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = vx + dx, vy + dy
            if (nx, ny) in structures:
                victim = structures.pop((nx, ny))
                logs.append(f"🌋 CATASTROPHE : Le volcan a anéanti {victim['name']} !")

    return logs[0] if logs else "🌋 Le volcan gronde au loin..."

def event_plague(structures, pos):
    """Une épidémie frappe une cité et la transforme en ville fantôme."""
    s = structures[pos]

    # On ne frappe que les cités ou les villages vivants
    if s["type"] in ["city", "village"]:
        original_name = s["name"]

        # TRANSFORMATION
        s["type"] = "ruin"
        # On peut même renommer pour le log
        s["name"] = f"Ruines de {original_name}"

        return f"💀 PESTE : L'épidémie a transformé {original_name} en ville fantôme."

    return None

# Registre des catastrophes (stochastiques)
# Format : (Probabilité, Fonction, Type)
RANDOM_INCIDENTS = [
    (0.01, event_volcanic_eruption, "map"),
    (0.005, event_plague, "city")
]