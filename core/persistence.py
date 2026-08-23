"""Checkpoints versionnés pour les sauvegardes locales de confiance."""

import os
import pickle
import tempfile
from pathlib import Path

from core import bestiary_tracker
from core import religion as religion_module
from core import species as species_module
from core.entity_ids import EntityIdService
from core.grid_service import SpatialGrid
from core.logger import GameLogger
from core.random_service import RandomService
from events.event_registry import EVENT_CATALOG


SAVE_MAGIC = b"CHARTOGRAPHIST_SAVE\0"
SAVE_VERSION = 1
_VERSION_BYTES = 2


class SaveFormatError(ValueError):
    """Erreur structurée émise lorsqu'un checkpoint ne peut pas être chargé."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def save_engine(engine, path):
    """Écrit atomiquement l'état complet du moteur dans un checkpoint versionné."""
    destination = Path(path)
    payload = {
        "engine": engine,
        "runtime": _capture_runtime_state(),
    }
    serialized = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    header = SAVE_MAGIC + SAVE_VERSION.to_bytes(_VERSION_BYTES, "big")

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(header)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return destination


def load_engine(path):
    """Charge un checkpoint, restaure les états globaux et reconstruit la grille."""
    source = Path(path)
    data = source.read_bytes()
    header_size = len(SAVE_MAGIC) + _VERSION_BYTES
    if len(data) < header_size or not data.startswith(SAVE_MAGIC):
        raise SaveFormatError("invalid_header")

    version = int.from_bytes(data[len(SAVE_MAGIC):header_size], "big")
    if version != SAVE_VERSION:
        raise SaveFormatError("unsupported_version")

    try:
        payload = pickle.loads(data[header_size:])
        engine = payload["engine"]
        runtime = payload["runtime"]
    except (EOFError, KeyError, pickle.PickleError, TypeError) as error:
        raise SaveFormatError("invalid_payload") from error

    if not hasattr(engine, "world") or not hasattr(engine, "stats") or not hasattr(engine, "config"):
        raise SaveFormatError("invalid_engine")

    _restore_runtime_state(runtime)
    width = engine.world["width"]
    height = engine.world["height"]
    engine.world["grid"] = SpatialGrid(width, height, cell_size=10)
    from core.climate import ClimateSystem
    from core.diplomacy import DiplomacyRegistry
    DiplomacyRegistry(engine.world)
    ClimateSystem(engine.world, engine.config)
    engine._refresh_grid()
    return engine


def _capture_runtime_state():
    return {
        "random": RandomService.get_state(),
        "next_entity_id": EntityIdService.get_state(),
        "events": list(EVENT_CATALOG),
        "religion_templates": religion_module._RELIGION_TEMPLATES,
        "domain_defs": religion_module._DOMAIN_DEFS,
        "species_templates": species_module._SPECIES_TEMPLATES,
        "origin_defs": species_module._ORIGIN_DEFS,
        "physiology_defs": species_module._PHYSIOLOGY_DEFS,
        "nature_defs": species_module._NATURE_DEFS,
        "pending_logs": list(GameLogger._logs),
        "pending_log_metadata": list(GameLogger._metadata),
        "bestiary_kills": bestiary_tracker.all_kills(),
        "bestiary_starvations": bestiary_tracker.all_starvations(),
    }


def _restore_runtime_state(runtime):
    RandomService.set_state(runtime["random"])
    EntityIdService.set_state(runtime["next_entity_id"])
    EVENT_CATALOG[:] = runtime["events"]

    religion_module._RELIGION_TEMPLATES[:] = runtime["religion_templates"]
    religion_module._DOMAIN_DEFS = runtime["domain_defs"]
    species_module._SPECIES_TEMPLATES[:] = runtime["species_templates"]
    species_module._ORIGIN_DEFS = runtime["origin_defs"]
    species_module._PHYSIOLOGY_DEFS = runtime["physiology_defs"]
    species_module._NATURE_DEFS = runtime["nature_defs"]

    GameLogger._logs[:] = runtime["pending_logs"]
    GameLogger._metadata[:] = runtime.get("pending_log_metadata", [])
    GameLogger._last_metadata.clear()
    bestiary_tracker.reset()
    bestiary_tracker._kills.update(runtime["bestiary_kills"])
    bestiary_tracker._starvations.update(runtime["bestiary_starvations"])
