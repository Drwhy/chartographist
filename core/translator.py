import json
import os

class Translator:
    """
    Static service for handling multi-language support.
    Loads and parses JSON locale files to provide formatted strings for the UI.
    """
    _data = {}

    @classmethod
    def load(cls, lang="fr"):
        """Loads the JSON file corresponding to the specified language."""
        file_path = f"locales/textes.{lang}.json"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                cls._data = json.load(f)
        else:
            print(f"⚠️ Error: Language file {file_path} not found.")

    @classmethod
    def translate(cls, path, **kwargs):
        """Retrieves and formats text from the loaded dictionary."""
        keys = path.split('.')
        content = cls._data
        try:
            for key in keys:
                content = content[key]
            return content.format(**kwargs)
        except (KeyError, TypeError):
            return f"[MISSING_TEXT: {path}]"