"""Hôte mono-propriétaire pour piloter un moteur depuis plusieurs adaptateurs."""

from collections import deque
import threading


_ALLOWED_COMMANDS = {"pause", "resume", "step", "speed", "save", "stop"}
_MIN_TICK_INTERVAL = 0.01
_MAX_TICK_INTERVAL = 10.0


class SimulationHost:
    """Sérialise les commandes et réserve les mutations au thread propriétaire."""

    def __init__(
        self,
        engine,
        *,
        tick_interval=0.15,
        max_commands=64,
        save_path=None,
        snapshot_factory=None,
    ):
        if isinstance(max_commands, bool) or int(max_commands) <= 0:
            raise ValueError("max_commands must be a positive integer")
        self.engine = engine
        self._owner_thread_id = threading.get_ident()
        self._lock = threading.Lock()
        self._commands = deque()
        self._max_commands = int(max_commands)
        self._save_path = None if save_path is None else str(save_path)
        self._snapshot_factory = snapshot_factory or _default_snapshot
        self._tick_interval = self._validated_speed(tick_interval)
        self._paused = False
        self._stopped = False
        self._pending_steps = 0
        self._revision = 0
        self._last_snapshot = None

    @property
    def tick_interval(self):
        return self._tick_interval

    @property
    def paused(self):
        return self._paused

    @property
    def stopped(self):
        return self._stopped

    @property
    def revision(self):
        return self._revision

    def submit_command(self, kind, value=None):
        """Valide puis place une commande sans toucher au moteur."""
        normalized = str(kind).strip().lower()
        if normalized not in _ALLOWED_COMMANDS:
            return False
        if normalized == "speed":
            try:
                value = self._validated_speed(value)
            except (TypeError, ValueError):
                return False
        elif value is not None:
            return False
        if normalized == "save" and self._save_path is None:
            return False
        with self._lock:
            if len(self._commands) >= self._max_commands:
                return False
            self._commands.append((normalized, value))
        return True

    def tick(self, *, publish_snapshot=True):
        """Traite les commandes, avance éventuellement un cycle et publie."""
        self._assert_owner()
        changed = self._drain_commands()
        should_step = (
            not self._stopped
            and (not self._paused or self._pending_steps > 0)
        )
        if should_step:
            self.engine.step()
            if self._pending_steps:
                self._pending_steps -= 1
            changed = True
        if changed:
            self._revision += 1
            self._last_snapshot = (
                self._snapshot_factory(self.engine, self._revision)
                if publish_snapshot else None
            )
        elif self._last_snapshot is None and publish_snapshot:
            if self._revision == 0:
                self._revision += 1
            self._last_snapshot = self._snapshot_factory(
                self.engine, self._revision
            )
        return self._last_snapshot if publish_snapshot else None

    def snapshot(self):
        """Retourne le dernier état publié sans avancer la simulation."""
        self._assert_owner()
        if self._last_snapshot is None:
            if self._revision == 0:
                self._revision += 1
            self._last_snapshot = self._snapshot_factory(
                self.engine, self._revision
            )
        from copy import deepcopy
        return deepcopy(self._last_snapshot)

    def _drain_commands(self):
        with self._lock:
            commands = list(self._commands)
            self._commands.clear()
        changed = bool(commands)
        for kind, value in commands:
            if kind == "pause":
                self._paused = True
            elif kind == "resume":
                self._paused = False
            elif kind == "step":
                self._paused = True
                self._pending_steps += 1
            elif kind == "speed":
                self._tick_interval = value
            elif kind == "save":
                self.engine.save(self._save_path)
            elif kind == "stop":
                self._stopped = True
        return changed

    def _assert_owner(self):
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("simulation engine may only advance on owner thread")

    @staticmethod
    def _validated_speed(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("tick interval must be numeric")
        numeric = float(value)
        if not _MIN_TICK_INTERVAL <= numeric <= _MAX_TICK_INTERVAL:
            raise ValueError("tick interval is outside supported bounds")
        return numeric


def _default_snapshot(engine, revision):
    from core.presentation import PresentationProjector
    return PresentationProjector(engine).snapshot(revision=revision)
