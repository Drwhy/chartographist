import sys
import random
import argparse
from . import culture
from core.translator import Translator

def init_terminal():
    """Prépare le terminal pour le rendu ANSI (Nettoie et cache le curseur)."""
    sys.stdout.write("\033[2J\033[H\033[?25l")

def restore_terminal():
    """Rétablit le curseur et nettoie la sortie."""
    sys.stdout.write("\033[?25h\n")

def load_arguments():
    """Gère la récupération des paramètres nommés (seed, template, lang)."""
    parser = argparse.ArgumentParser(description="Simulation Procedural World Engine")

    # 1. Définition des arguments nommés
    parser.add_argument("--seed", type=str, help="Seed du monde (nombre ou texte)")
    parser.add_argument("--template", type=str, default="template.json", help="Chemin vers le fichier template JSON")
    parser.add_argument("--lang", type=str, default="fr", help="Langue de la simulation (fr, en...)")

    args = parser.parse_args()

    # 2. Gestion de la Seed (Logique de hashage conservée)
    if args.seed:
        try:
            seed_val = int(args.seed)
        except ValueError:
            seed_val = hash(args.seed)
    else:
        seed_val = random.randint(0, 99999)

    # 3. Initialisation de la Locale (Chargement du JSON de langue)
    Translator.load(args.lang)

    # 4. Chargement du Template
    config = culture.load_template(args.template)

    return config, seed_val