"""Bounded structured memories and derived personal opinions."""

from copy import deepcopy

from core.characters import character_settings, ensure_character_state


def _clamp(value, minimum=0.0, maximum=100.0):
    return round(min(maximum, max(minimum, float(value))), 6)


def _signed(value):
    return round(min(1.0, max(-1.0, float(value))), 6)


def _position(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    raise ValueError("position must contain two coordinates")


class MemoryBook:
    """Own a person's important facts without unbounded pairwise relations."""

    def __init__(self, person, config):
        self.person = person
        self.config = config if isinstance(config, dict) else {}
        self.settings = character_settings(self.config)
        self.state = ensure_character_state(person, self.config)
        if not self.state:
            raise ValueError("character simulation is disabled")

    @property
    def memories(self):
        return self.state["memories"]

    def remember(
        self,
        kind,
        *,
        cycle,
        target_id=None,
        position=None,
        intensity,
        reliability,
        sentiment=0.0,
        fear=0.0,
        grievance=0.0,
        source="experienced",
    ):
        if not isinstance(kind, str) or not kind:
            raise ValueError("memory kind is required")
        normalized_position = _position(position)
        target = int(target_id) if target_id is not None else None
        matching = next(
            (
                memory
                for memory in self.memories
                if memory.get("kind") == kind
                and memory.get("target_id") == target
                and memory.get("position") == normalized_position
            ),
            None,
        )
        if matching is None:
            matching = {
                "memory_id": int(self.state["next_memory_id"]),
                "kind": kind,
                "witness_id": int(getattr(self.person, "entity_id", 0)),
                "target_id": target,
                "position": normalized_position,
                "cycle": int(cycle),
                "intensity": _clamp(intensity),
                "reliability": _clamp(reliability, 0.0, 1.0),
                "sentiment": _signed(sentiment),
                "fear": _clamp(fear, 0.0, 1.0),
                "grievance": _clamp(grievance, 0.0, 1.0),
                "source": str(source),
            }
            self.state["next_memory_id"] += 1
            self.memories.append(matching)
        else:
            matching["cycle"] = max(int(matching.get("cycle", 0)), int(cycle))
            matching["intensity"] = _clamp(
                float(matching.get("intensity", 0.0)) + max(0.0, float(intensity))
            )
            matching["reliability"] = max(
                float(matching.get("reliability", 0.0)),
                _clamp(reliability, 0.0, 1.0),
            )
            matching["sentiment"] = _signed(
                (float(matching.get("sentiment", 0.0)) + _signed(sentiment)) / 2.0
            )
            matching["fear"] = max(
                float(matching.get("fear", 0.0)),
                _clamp(fear, 0.0, 1.0),
            )
            matching["grievance"] = max(
                float(matching.get("grievance", 0.0)),
                _clamp(grievance, 0.0, 1.0),
            )

        self._trim()
        return deepcopy(matching)

    @staticmethod
    def _importance(memory):
        return (
            float(memory.get("intensity", 0.0))
            * float(memory.get("reliability", 0.0))
        )

    def _trim(self):
        limit = max(1, int(self.settings.get("memory_limit", 24)))
        self.memories.sort(
            key=lambda memory: (
                -self._importance(memory),
                -int(memory.get("cycle", 0)),
                int(memory.get("memory_id", 0)),
            )
        )
        del self.memories[limit:]

    def decay(self):
        rate = _clamp(self.settings.get("memory_decay_rate", 0.02), 0.0, 1.0)
        retained = []
        for memory in self.memories:
            memory["intensity"] = round(
                float(memory.get("intensity", 0.0)) * (1.0 - rate),
                6,
            )
            memory["reliability"] = round(
                float(memory.get("reliability", 0.0)) * (1.0 - rate),
                6,
            )
            if memory["intensity"] >= 0.5 and memory["reliability"] >= 0.01:
                retained.append(memory)
        self.state["memories"] = retained
        return len(retained)

    def opinion(self, target_id=None):
        trust = 0.0
        fear = 0.0
        grievance = 0.0
        for memory in self.memories:
            if target_id is not None and memory.get("target_id") != int(target_id):
                continue
            weight = (
                float(memory.get("intensity", 0.0))
                * float(memory.get("reliability", 0.0))
            )
            trust += weight * float(memory.get("sentiment", 0.0))
            fear += weight * float(memory.get("fear", 0.0))
            grievance += weight * float(memory.get("grievance", 0.0))
        return {
            "trust": round(min(100.0, max(-100.0, trust)), 6),
            "fear": round(min(100.0, max(-100.0, fear)), 6),
            "grievance": round(min(100.0, max(-100.0, grievance)), 6),
        }

    def snapshot(self):
        return deepcopy(self.memories)
