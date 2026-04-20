# ──────────────────────────────────────────────
#  Species System — Procedural Humanoid Species
#  One species per culture, generated at runtime
#  from origin × physiology × nature combinations.
# ──────────────────────────────────────────────
from core.random_service import RandomService

_SPECIES_TEMPLATES = []
_ORIGIN_DEFS = {}
_PHYSIOLOGY_DEFS = {}
_NATURE_DEFS = {}

_TRAIT_KEYS = ["strength", "perception", "speed", "fertility", "harvest", "trade", "defense"]


def init_species_data(config):
    global _SPECIES_TEMPLATES, _ORIGIN_DEFS, _PHYSIOLOGY_DEFS, _NATURE_DEFS
    _SPECIES_TEMPLATES.clear()

    species_cfg = config.get("species", {})
    _ORIGIN_DEFS = species_cfg.get("origins", {})
    _PHYSIOLOGY_DEFS = species_cfg.get("physiologies", {})
    _NATURE_DEFS = species_cfg.get("natures", {})

    if not (_ORIGIN_DEFS and _PHYSIOLOGY_DEFS and _NATURE_DEFS):
        return

    origin_names = list(_ORIGIN_DEFS.keys())
    physiology_names = list(_PHYSIOLOGY_DEFS.keys())
    nature_names = list(_NATURE_DEFS.keys())

    for culture in config.get("cultures", []):
        origin_key = RandomService.choice(origin_names)
        physiology_key = RandomService.choice(physiology_names)
        nature_key = RandomService.choice(nature_names)

        template = _build_species(
            culture,
            origin_key, _ORIGIN_DEFS[origin_key],
            physiology_key, _PHYSIOLOGY_DEFS[physiology_key],
            nature_key, _NATURE_DEFS[nature_key],
        )
        _SPECIES_TEMPLATES.append(template)


def _build_species(culture, origin_key, origin, physiology_key, physiology, nature_key, nature):
    origin_naming = origin.get("naming", {})
    nature_naming = nature.get("naming", {})

    prefix = RandomService.choice(origin_naming.get("prefixes", ["Homo"]))
    suffix = RandomService.choice(nature_naming.get("suffixes", ["us"]))
    name = prefix + suffix

    origin_w = origin.get("bonus_weights", {})
    physio_w = physiology.get("bonus_weights", {})
    nature_w = nature.get("bonus_weights", {})

    bonuses = {}
    for key in _TRAIT_KEYS:
        base = RandomService.randint(0, 3)
        w = origin_w.get(key, 1.0) * physio_w.get(key, 1.0) * nature_w.get(key, 1.0)
        bonuses[key] = round(base * w, 1)

    speed_mod = physiology.get("speed_mod", 0.0) + nature.get("speed_mod", 0.0)

    return {
        "name": name,
        "culture": culture.get("name", ""),
        "origin": origin_key,
        "physiology": physiology_key,
        "nature": nature_key,
        "emojis": [
            origin.get("emoji", "🌍"),
            physiology.get("emoji", "🧬"),
            nature.get("emoji", "🌀"),
        ],
        "bonuses": bonuses,
        "speed_mod": round(speed_mod, 3),
    }


def get_species_templates():
    return list(_SPECIES_TEMPLATES)


def get_species_for_culture(culture_name):
    for s in _SPECIES_TEMPLATES:
        if s.get("culture") == culture_name:
            return s
    if _SPECIES_TEMPLATES:
        return RandomService.choice(_SPECIES_TEMPLATES)
    return None


# ── PersonalSpecies ─────────────────────────────
class PersonalSpecies:
    """
    An entity's species instance. Provides trait queries
    (like PersonalFaith.bonus) and a speed modifier applied
    at spawn time.
    """

    def __init__(self, template):
        self._template = template
        self._bonuses = dict(template.get("bonuses", {}))
        self._speed_mod = template.get("speed_mod", 0.0)

    def trait(self, key, default=0):
        """Returns the additive trait value for a given key."""
        return self._bonuses.get(key, default)

    @property
    def speed_mod(self):
        return self._speed_mod

    @property
    def name(self):
        return self._template.get("name", "Unknown")

    @property
    def origin(self):
        return self._template.get("origin", "")

    @property
    def physiology(self):
        return self._template.get("physiology", "")

    @property
    def nature(self):
        return self._template.get("nature", "")

    @property
    def emojis(self):
        return self._template.get("emojis", ["🌍", "🧬", "🌀"])

    @property
    def emoji_str(self):
        return " ".join(self.emojis)

    def __repr__(self):
        return f"PersonalSpecies({self.name} [{self.origin}/{self.physiology}/{self.nature}])"
