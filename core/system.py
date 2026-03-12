import sys
import random
import argparse
from . import culture
from core.translator import Translator

def init_terminal():
    """
    Prepares the terminal for ANSI rendering.
    Clears the screen, moves the cursor to the home position, and hides it.
    """
    # \033[2J: Clear screen | \033[H: Home position | \033[?25l: Hide cursor
    sys.stdout.write("\033[2J\033[H\033[?25l")
    sys.stdout.flush()

def restore_terminal():
    """
    Restores the terminal state by showing the cursor and adding a newline.
    Should be called upon simulation exit.
    """
    # \033[?25h: Show cursor
    sys.stdout.write("\033[?25h\n")
    sys.stdout.flush()

def load_arguments():
    """
    Handles command-line argument parsing for world generation and simulation settings.
    Processes seeds, templates, and language localization.

    Returns:
        tuple: (config_dict, seed_value)
    """
    parser = argparse.ArgumentParser(description="Procedural World Engine Simulation")

    # 1. Argument definitions
    parser.add_argument("--seed", type=str, help="World seed (integer or string)")
    parser.add_argument("--template", type=str, default="template.json", help="Path to the JSON template file")
    parser.add_argument("--lang", type=str, default="fr", help="Simulation language (en, fr, etc.)")

    args = parser.parse_args()

    # 2. Seed management (Deterministic hashing logic)
    if args.seed:
        try:
            seed_val = int(args.seed)
        except ValueError:
            # Hash string seeds into integers for the RandomService
            seed_val = hash(args.seed)
    else:
        seed_val = random.randint(0, 99999)

    # 3. Locale initialization (Loads the language JSON)
    Translator.load(args.lang)

    # 4. Configuration loading
    config = culture.load_config(args.template)

    return config, seed_val