import sys
import random
import argparse
import hashlib
from dataclasses import dataclass
from . import culture
from core.translator import Translator
from core.config_validator import ConfigValidationError, validate_config
from core.scenarios import ScenarioValidationError, load_config_layers

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


def _web_port(value):
    numeric = int(value)
    if not 1 <= numeric <= 65535:
        raise argparse.ArgumentTypeError(Translator.translate("cli.port_error"))
    return numeric


def _tick_interval(value):
    numeric = float(value)
    if not 0.01 <= numeric <= 10.0:
        raise argparse.ArgumentTypeError(
            Translator.translate("cli.tick_speed_error")
        )
    return numeric


@dataclass(frozen=True)
class LaunchOptions:
    config: dict
    seed: int
    load_path: str | None = None
    save_path: str | None = None
    scenario_path: str | None = None
    mod_paths: tuple[str, ...] = ()
    renderer: str = "terminal"
    web_host: str = "127.0.0.1"
    web_port: int = 8765
    tick_speed: float = 0.15


def load_launch_options():
    """Parse les options complètes utilisées par l'adaptateur terminal."""
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--lang", default="fr")
    language_args, _ = language_parser.parse_known_args()
    Translator.load(language_args.lang)

    parser = argparse.ArgumentParser(description=Translator.translate("cli.description"))
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
    parser.add_argument(
        "--scenario",
        dest="scenario_path",
        help=Translator.translate("cli.scenario_help"),
    )
    parser.add_argument(
        "--mod",
        dest="mod_paths",
        action="append",
        default=[],
        help=Translator.translate("cli.mod_help"),
    )
    parser.add_argument(
        "--load",
        dest="load_path",
        help=Translator.translate("cli.load_help"),
    )
    parser.add_argument(
        "--save",
        dest="save_path",
        help=Translator.translate("cli.save_help"),
    )
    parser.add_argument(
        "--renderer",
        choices=("terminal", "web"),
        default="terminal",
        help=Translator.translate("cli.renderer_help"),
    )
    parser.add_argument(
        "--host",
        dest="web_host",
        default="127.0.0.1",
        help=Translator.translate("cli.host_help"),
    )
    parser.add_argument(
        "--port",
        dest="web_port",
        type=_web_port,
        default=8765,
        help=Translator.translate("cli.port_help"),
    )
    parser.add_argument(
        "--tick-speed",
        type=_tick_interval,
        default=0.15,
        help=Translator.translate("cli.tick_speed_help"),
    )
    args = parser.parse_args()

    seed = stable_seed(args.seed) if args.seed else random.randint(0, 99999)
    if args.load_path:
        config = {}
    elif args.scenario_path or args.mod_paths:
        try:
            config = validate_config(load_config_layers(
                args.template,
                scenario_path=args.scenario_path,
                mod_paths=tuple(args.mod_paths),
            ))
        except (ConfigValidationError, ScenarioValidationError) as error:
            print(Translator.translate("system.config_load_error", error=error))
            config = {}
    else:
        config = culture.load_config(args.template)
    return LaunchOptions(
        config,
        seed,
        args.load_path,
        args.save_path,
        args.scenario_path,
        tuple(args.mod_paths),
        renderer=args.renderer,
        web_host=args.web_host,
        web_port=args.web_port,
        tick_speed=args.tick_speed,
    )


def load_arguments():
    """Retourne le contrat historique ``(config, seed)``."""
    options = load_launch_options()
    return options.config, options.seed