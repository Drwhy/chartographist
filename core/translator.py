import json
import os

class Translator:
    """
    Static service for handling multi-language support.
    Loads and parses JSON locale files to provide formatted strings for the UI.
    """
    _data = {}
    _language = "fr"

    @classmethod
    def load(cls, lang="fr"):
        """Loads the JSON file corresponding to the specified language."""
        file_path = f"locales/textes.{lang}.json"
        if not os.path.exists(file_path):
            fallback_path = "locales/textes.en.json"
            if os.path.exists(fallback_path):
                with open(fallback_path, "r", encoding="utf-8") as fallback_file:
                    cls._data = json.load(fallback_file)
                cls._language = "en"
            print(cls.translate("system.locale_not_found", file_path=file_path))
            return

        with open(file_path, "r", encoding="utf-8") as locale_file:
            cls._data = json.load(locale_file)
        cls._language = lang

    @classmethod
    def current_language(cls):
        """Returns the locale actually loaded, including fallback selection."""
        return cls._language

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