import json
import os
import random

def load_template(filepath="template.json"):
    """Charge la configuration complète depuis un fichier JSON."""
    if not os.path.exists(filepath):
        return {
            "world_name": "Fallback",
            "water": {"ocean": " ", "shore": " ", "river": " ", "deep": " "},
            "biomes": {"grassland": " "},
            "cultures": [{"name": "Default", "city": "C", "village": "v", "port": "P", "road": " "}],
            "fauna": [],
            "special": {"ruin": "R", "port": "P"}
        }

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def initialize_civilizations(width, height, elevation, config):
    """Place les premières cités sur la carte au lancement."""
    structures = {}
    cultures = config.get("cultures", [])

    if not cultures:
        return structures

    # On tente de placer une cité pour chaque culture définie dans le JSON
    for culture in cultures:
        placed = False
        attempts = 0
        while not placed and attempts < 100:
            tx = random.randint(0, width - 1)
            ty = random.randint(0, height - 1)

            # Condition d'installation : Terre ferme et pas déjà occupé
            if elevation[ty][tx] > 0.1 and (tx, ty) not in structures:
                from core.names import get_name_by_culture # Import local pour éviter les cycles

                structures[(tx, ty)] = {
                    "name": get_name_by_culture(culture),
                    "type": "city",
                    "culture": culture,
                    "age": 0
                }
                placed = True
            attempts += 1

    return structures