import sys
import random
import argparse
import hashlib
from . import culture
from core.translator import Translator

_saved_term = None


def init_terminal():
    """
    Prepares the terminal for ANSI rendering.
    Clears the screen, moves the cursor to the home position, and hides it.
    Also sets cbreak mode so single keypresses are readable without Enter.
    """
    global _saved_term
    sys.stdout.write("\033[2J\033[H\033[?25l")
    sys.stdout.flush()
    try:
        import tty, termios
        _saved_term = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
    except Exception:
        pass


def restore_terminal():
    """
    Restores the terminal state by showing the cursor and adding a newline.
    Should be called upon simulation exit.
    """
    global _saved_term
    sys.stdout.write("\033[?25h\n")
    sys.stdout.flush()
    if _saved_term is not None:
        try:
            import termios
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _saved_term)
            _saved_term = None
        except Exception:
            pass

def stable_seed(value):
    """Convert a numeric or text seed to a process-stable integer."""
    try:
        return int(value)
    except (TypeError, ValueError):
        encoded = str(value).encode("utf-8")
        digest = hashlib.sha256(encoded).digest()
        return int.from_bytes(digest[:8], "big")


def load_arguments():
    """
    Handles command-line argument parsing for world generation and simulation settings.
    Processes seeds, templates, and language localization.

    Returns:
        tuple: (config_dict, seed_value)
    """
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--lang", default="fr")
    language_args, _ = language_parser.parse_known_args()
    Translator.load(language_args.lang)

    parser = argparse.ArgumentParser(description=Translator.translate("cli.description"))

    # 1. Argument definitions
    parser.add_argument("--seed", type=str, help=Translator.translate("cli.seed_help"))
    parser.add_argument(
        "--template",
        type=str,
        default="template.json",
        help=Translator.translate("cli.template_help"),
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="fr",
        help=Translator.translate("cli.lang_help"),
    )

    args = parser.parse_args()

    # 2. Seed management (Deterministic hashing logic)
    if args.seed:
        seed_val = stable_seed(args.seed)
    else:
        seed_val = random.randint(0, 99999)

    # 3. Configuration loading
    config = culture.load_config(args.template)

    return config, seed_val