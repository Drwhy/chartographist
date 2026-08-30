import json
import os
from core.config_validator import ConfigValidationError, validate_config
from core.translator import Translator

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
            config = json.load(f)
        return validate_config(config)
    except (json.JSONDecodeError, IOError, ConfigValidationError) as error:
        print(Translator.translate("system.config_load_error", error=error))
        return {}