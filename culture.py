import json
import os

def load_template(filepath="template.json"):
    """Charge la configuration complète depuis un fichier JSON."""
    if not os.path.exists(filepath):
        # Template de secours minimal si le fichier est manquant
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