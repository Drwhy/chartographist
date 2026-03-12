import json
import os

def load_config(filepath="template.json"):
    """
    Loads the complete simulation configuration from a JSON file.
    Returns a fallback configuration if the file is missing.
    """
    if not os.path.exists(filepath):
        # Fallback dictionary using standardized English keys
        return {
            "world_name": "Unknown Lands",
            "water": {
                "ocean": " ",
                "shore": " ",
                "river": " ",
                "deep": " "
            },
            "biomes": {
                "grassland": " "
            },
            "cultures": [
                {
                    "name": "Default",
                    "city": "C",
                    "village": "v",
                    "port": "P",
                    "road": " "
                }
            ],
            "fauna": [],
            "special": {
                "ruin": "R",
                "port": "P"
            }
        }

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # In case of corruption, we should ideally log the error here
        # For now, we return the basic template to prevent a crash
        print(f"Error loading configuration: {e}")
        return {}