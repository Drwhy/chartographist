# core/system.py
import sys
import random
from . import culture
def init_terminal():
    """Prépare le terminal pour le rendu ANSI."""
    sys.stdout.write("\033[2J\033[H\033[?25l")

def restore_terminal():
    """Rétablit le curseur et nettoie la sortie."""
    sys.stdout.write("\033[?25h\n")

def load_arguments():
    """Gère la récupération du template et de la seed."""
    template_path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else "template.json"
    config = culture.load_template(template_path)
    seed_val = sys.argv[2] if len(sys.argv) > 2 else random.randint(0, 99999)
    return config, seed_val