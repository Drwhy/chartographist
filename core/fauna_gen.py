# ──────────────────────────────────────────────
#  Fauna Generator — Procedural Animal Species
#  Generates all wildlife at runtime from archetype
#  definitions in template.json (fauna_archetypes).
#  Output is a list of species_data dicts compatible
#  with the existing Animal class.
# ──────────────────────────────────────────────
from core.random_service import RandomService

_GENERATED_FAUNA = []


def generate_fauna(config):
    """
    Build the full fauna list from fauna_archetypes config.
    Returns a list of species_data dicts. If no archetypes
    are defined, returns an empty list (caller keeps static fauna).
    """
    global _GENERATED_FAUNA
    _GENERATED_FAUNA.clear()

    archetypes = config.get("fauna_archetypes", {})
    if not archetypes:
        return []

    for archetype_key, archetype in archetypes.items():
        count = archetype.get("count", 2)
        for _ in range(count):
            _GENERATED_FAUNA.append(_generate_species(archetype_key, archetype))

    return list(_GENERATED_FAUNA)


def _generate_species(archetype_key, archetype):
    emoji_pool = archetype.get("emoji_pool", ["🐾"])
    char = RandomService.choice(emoji_pool)

    naming = archetype.get("naming", {})
    prefix = RandomService.choice(naming.get("prefixes", ["Anim"]))
    suffix = RandomService.choice(naming.get("suffixes", ["us"]))
    name = prefix + suffix
    species_key = f"{archetype_key}_{name.lower()}"

    size_lo, size_hi = archetype.get("size_range", [5, 20])
    spd_lo, spd_hi = archetype.get("speed_range", [0.8, 1.2])
    dng_lo, dng_hi = archetype.get("danger_range", [0.0, 0.5])
    prc_lo, prc_hi = archetype.get("perception_range", [3, 8])
    elv_lo, elv_hi = archetype.get("spawn_elev_range", [0.05, 0.6])

    weight = RandomService.randint(size_lo, size_hi)
    speed = round(RandomService.uniform(spd_lo, spd_hi), 2)
    danger = round(RandomService.uniform(dng_lo, dng_hi), 2)
    danger_level = min(1.0, round(danger * 1.1, 2))
    perception = RandomService.randint(prc_lo, prc_hi)
    # Timid animals are more fearful; dangerous ones are bolder
    fear_sens = round(RandomService.uniform(1.0, 7.0) * (1.1 - danger), 1)

    return {
        "species": species_key,
        "char": char,
        "name": name,
        "speed": speed,
        "locomotion": archetype.get("locomotion", "land"),
        "diet": archetype.get("diet", "herbivore"),
        "weight": weight,
        "perception_range": perception,
        "danger": danger,
        "danger_level": danger_level,
        "fear_sensitivity": max(0.5, fear_sens),
        "food_value": [max(1, weight // 2), max(2, weight)],
        "energy": 100,
        "max_energy": 150,
        "hunger_threshold": 60,
        "repro_threshold": 120,
        "spawn": {
            "elevation_min": elv_lo,
            "elevation_max": elv_hi,
            "chance": archetype.get("spawn_chance", 0.05),
        },
    }
