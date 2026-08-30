"""Bounded practice-based skills with deterministic diminishing returns."""

from core.characters import SKILL_NAMES


def _state(person):
    state = getattr(person, "character", None)
    if not isinstance(state, dict):
        raise ValueError("character state is not initialized")
    return state


def skill_value(person, name):
    if name not in SKILL_NAMES:
        raise KeyError(name)
    state = getattr(person, "character", None)
    if not isinstance(state, dict):
        return 0.0
    return float(state.get("skills", {}).get(name, 0.0))


def practice_skill(person, name, effort=1.0):
    """Increase one skill; the same effort yields less near mastery."""
    if name not in SKILL_NAMES:
        raise KeyError(name)
    state = _state(person)
    current = min(100.0, max(0.0, skill_value(person, name)))
    requested = max(0.0, float(effort))
    gained = requested * (1.0 - current / 100.0)
    updated = min(100.0, current + gained)
    state["skills"][name] = round(updated, 6)
    return round(updated - current, 6)
