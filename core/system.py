# core/system.py
import sys, random
from . import culture
from core.random_service import RandomService

def init_terminal():
    """Prépare le terminal pour le rendu ANSI."""
    sys.stdout.write("\033[2J\033[H\033[?25l")

def restore_terminal():
    """Rétablit le curseur et nettoie la sortie."""
    sys.stdout.write("\033[?25h\n")

def load_arguments():
    """Gère la récupération du template et de la seed."""
    if len(sys.argv) > 1:
        raw_seed = sys.argv[1]
        try:
            # On tente de convertir la chaîne "123" en entier 123
            seed_val = int(raw_seed)
        except ValueError:
            # Si l'utilisateur a entré du texte (ex: "map1"),
            # on utilise le hash du texte pour rester sur un nombre entier
                seed_val = hash(raw_seed)
    else:
        # 2. Génération d'un INT pur si aucun argument n'est fourni
        seed_val = random.randint(0, 99999)
    template_path = sys.argv[2] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else "template.json"
    config = culture.load_template(template_path)

    return config, seed_val