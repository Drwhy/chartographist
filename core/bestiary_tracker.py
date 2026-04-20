_kills = {}
_starvations = {}


def track_kill(species_key):
    _kills[species_key] = _kills.get(species_key, 0) + 1


def track_starvation(species_key):
    _starvations[species_key] = _starvations.get(species_key, 0) + 1


def get_kills(species_key):
    return _kills.get(species_key, 0)


def get_starvations(species_key):
    return _starvations.get(species_key, 0)


def all_kills():
    return dict(_kills)


def all_starvations():
    return dict(_starvations)


def reset():
    _kills.clear()
    _starvations.clear()
