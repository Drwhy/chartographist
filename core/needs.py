"""Bounded monthly needs for optional character simulation."""

from core.characters import NEED_NAMES, character_settings, ensure_character_state


def _clamp(value):
    return round(min(100.0, max(0.0, float(value))), 6)


def need_value(person, name):
    if name not in NEED_NAMES:
        raise KeyError(name)
    state = getattr(person, "character", None)
    if not isinstance(state, dict):
        return 0.0
    return float(state.get("needs", {}).get(name, 0.0))


def set_need(person, name, value):
    if name not in NEED_NAMES:
        raise KeyError(name)
    state = getattr(person, "character", None)
    if not isinstance(state, dict):
        raise ValueError("character state is not initialized")
    state["needs"][name] = _clamp(value)
    if name == "hunger":
        person.hunger = state["needs"][name]
    return state["needs"][name]


def satisfy_need(person, name, amount):
    return set_need(person, name, need_value(person, name) - max(0.0, float(amount)))


def increase_need(person, name, amount):
    return set_need(person, name, need_value(person, name) + max(0.0, float(amount)))


def advance_needs(person, world, config):
    """Advance configured pressures at most once for a world cycle."""
    state = ensure_character_state(person, config)
    if not state:
        return False
    cycle = int(world.get("cycle", 0))
    if state.get("last_needs_cycle") == cycle:
        return False

    state["needs"]["hunger"] = _clamp(getattr(person, "hunger", 0.0))
    growth = character_settings(config).get("need_growth", {})
    if not isinstance(growth, dict):
        growth = {}
    for name in NEED_NAMES:
        if name == "hunger":
            continue
        amount = growth.get(name, 0.0)
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            state["needs"][name] = _clamp(state["needs"][name] + max(0.0, float(amount)))
    state["last_needs_cycle"] = cycle
    return True
