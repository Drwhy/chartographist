import json
import os

class Translator:
    _data = {}

    @classmethod
    def load(cls, lang="fr"):
        """Charge le fichier JSON correspondant à la langue."""
        file_path = f"locales/textes.{lang}.json"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                cls._data = json.load(f)
        else:
            print(f"⚠️ Erreur : Fichier de langue {file_path} introuvable.")

    @classmethod
    def translate(cls, path, **kwargs):
        """Récupère et formate le texte depuis le dictionnaire chargé."""
        keys = path.split('.')
        content = cls._data
        try:
            for key in keys:
                content = content[key]
            return content.format(**kwargs)
        except (KeyError, TypeError):
            return f"[MISSING_TEXT: {path}]"