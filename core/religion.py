# ──────────────────────────────────────────────
#  Religion System — Procedural Faith Generation
#  Religions are built at runtime from domain
#  definitions (template.json) and culture naming.
# ──────────────────────────────────────────────
from core.random_service import RandomService

# ── Module-Level State ──────────────────────────
_RELIGION_TEMPLATES = []
_DOMAIN_DEFS = {}

# Base bonus keys and their default random range
_BONUS_KEYS = ["growth", "perception", "harvest", "trade", "defense"]


def init_religion_data(config):
    """
    Procedurally generate one religion per culture.
    Each religion picks a random domain, generates a god name
    from the domain's naming table, and rolls bonuses weighted
    by the domain's bonuses_weight map.
    """
    global _RELIGION_TEMPLATES, _DOMAIN_DEFS
    _RELIGION_TEMPLATES.clear()

    _DOMAIN_DEFS = config.get("domains", {})
    domain_names = list(_DOMAIN_DEFS.keys())

    if not domain_names:
        return

    for culture in config.get("cultures", []):
        domain_key = RandomService.choice(domain_names)
        domain = _DOMAIN_DEFS[domain_key]

        religion = _build_religion(culture, domain_key, domain)
        _RELIGION_TEMPLATES.append(religion)


def _build_religion(culture, domain_key, domain_def):
    """
    Build a single religion template procedurally.

    God name: domain naming prefix + domain naming suffix
    Religion name: procedural title using domain naming titles
    Bonuses: random 0-5 for each key, multiplied by domain weight
    Emoji: from domain definition
    """
    # God name from domain-specific naming table
    naming = domain_def.get("naming", {})
    god_prefix = RandomService.choice(naming.get("prefixes", ["Deus"]))
    god_suffix = RandomService.choice(naming.get("suffixes", ["us"]))
    god_name = god_prefix + god_suffix

    # Religion title from domain titles
    titles = naming.get("titles", ["the Unknown"])
    title = RandomService.choice(titles)

    # Roll bonuses weighted by domain
    weights = domain_def.get("bonuses_weight", {})
    bonuses = {}
    for key in _BONUS_KEYS:
        base = RandomService.randint(0, 3)
        weight = weights.get(key, 1.0)
        bonuses[key] = round(base * weight)

    # Build the naming table for this religion (used by syncretism later)
    # Merges domain naming with culture naming for richer output
    culture_naming = culture.get("naming", {})
    religion_naming = {
        "prefixes": naming.get("prefixes", []) + culture_naming.get("prefixes", [])[:5],
        "suffixes": naming.get("suffixes", []) + culture_naming.get("suffixes_person", [])[:5],
    }

    return {
        "name": f"{god_name} {title}",
        "god": god_name,
        "culture": culture.get("name", ""),
        "domain": domain_key,
        "bonuses": bonuses,
        "emoji": domain_def.get("emoji", "🙏"),
        "naming": religion_naming,
    }


def get_religion_templates():
    """Returns the loaded religion templates."""
    return list(_RELIGION_TEMPLATES)


def get_religion_for_culture(culture_name):
    """Find the religion template matching a culture, or pick random."""
    for r in _RELIGION_TEMPLATES:
        if r.get("culture") == culture_name:
            return r
    if _RELIGION_TEMPLATES:
        return RandomService.choice(_RELIGION_TEMPLATES)
    return None


def get_domain_emoji(domain_name):
    """Returns the emoji for a domain."""
    domain = _DOMAIN_DEFS.get(domain_name, {})
    return domain.get("emoji", "🙏")


# ── PersonalFaith ───────────────────────────────
class PersonalFaith:
    """
    An agent's individual faith. Holds a primary religion reference
    and provides additive bonus queries via bonus(key, default).
    """

    def __init__(self, religion_template):
        self.primary = religion_template["name"]
        self._bonuses = dict(religion_template.get("bonuses", {}))
        self.devotion = 1.0
        self._template = religion_template

    def bonus(self, key, default=0):
        """Returns the additive bonus for a given key, scaled by devotion."""
        raw = self._bonuses.get(key, default)
        return raw * self.devotion

    @property
    def religion_name(self):
        return self.primary

    @property
    def god_name(self):
        return self._template.get("god", "Unknown")

    @property
    def domain(self):
        return self._template.get("domain", "life")

    @property
    def emoji(self):
        return self._template.get("emoji", "🙏")

    def __repr__(self):
        return f"PersonalFaith({self.primary}, devotion={self.devotion:.1f})"


# ── ReligionDemographics ───────────────────────
class ReligionDemographics:
    """
    Population-weighted religion fractions for a settlement.
    Maps religion_name -> fraction (0.0 to 1.0), sums to 1.0.
    """

    def __init__(self, fractions=None):
        self.fractions = dict(fractions or {})
        self._normalize()

    def _normalize(self):
        total = sum(self.fractions.values())
        if total > 0:
            for k in self.fractions:
                self.fractions[k] /= total

    @property
    def dominant(self):
        if not self.fractions:
            return None
        return max(self.fractions, key=self.fractions.get)

    @property
    def dominant_fraction(self):
        if not self.fractions:
            return 0.0
        return self.fractions.get(self.dominant, 0.0)

    def bonus(self, key, default=0):
        """Weighted average of all religion bonuses for a given key."""
        total_bonus = 0.0
        for rname, fraction in self.fractions.items():
            template = _find_template(rname)
            if template:
                raw = template.get("bonuses", {}).get(key, default)
                total_bonus += raw * fraction
        return total_bonus

    def influence(self, religion_name, strength=0.05):
        """Apply external religious influence and re-normalize."""
        current = self.fractions.get(religion_name, 0.0)
        self.fractions[religion_name] = current + strength
        self._normalize()

    def merge(self, other):
        """Merge another ReligionDemographics into this one."""
        for rname, fraction in other.fractions.items():
            current = self.fractions.get(rname, 0.0)
            self.fractions[rname] = (current + fraction) / 2.0
        self._normalize()

    def __repr__(self):
        parts = [f"{k}: {v:.0%}" for k, v in sorted(self.fractions.items(), key=lambda x: -x[1])]
        return f"Demographics({', '.join(parts)})"


# ── SyncreticReligion ──────────────────────────
class SyncreticReligion:
    """
    Fusion of two parent religions creating a new merged god.
    God name is built from each religion's naming table.
    Bonuses are averaged. Domain inherited from the stronger parent.
    """

    @staticmethod
    def create(religion_a, religion_b):
        naming_a = religion_a.get("naming", {})
        naming_b = religion_b.get("naming", {})

        prefix = RandomService.choice(naming_a.get("prefixes", [religion_a.get("god", "Syn")[:3]]))
        suffix = RandomService.choice(naming_b.get("suffixes", [religion_b.get("god", "cret")[-3:]]))
        syncretic_god = prefix + suffix

        # Average bonuses
        bonuses_a = religion_a.get("bonuses", {})
        bonuses_b = religion_b.get("bonuses", {})
        all_keys = set(bonuses_a.keys()) | set(bonuses_b.keys())
        merged_bonuses = {}
        for k in all_keys:
            merged_bonuses[k] = (bonuses_a.get(k, 0) + bonuses_b.get(k, 0)) / 2.0

        domain_a = religion_a.get("domain", "life")
        domain_b = religion_b.get("domain", "life")
        syncretic_domain = domain_a if sum(bonuses_a.values()) >= sum(bonuses_b.values()) else domain_b

        syncretic = {
            "name": f"{syncretic_god} the Twofold",
            "god": syncretic_god,
            "culture": "syncretic",
            "domain": syncretic_domain,
            "bonuses": merged_bonuses,
            "emoji": "🔮",
            "naming": {
                "prefixes": naming_a.get("prefixes", []) + naming_b.get("prefixes", []),
                "suffixes": naming_a.get("suffixes", []) + naming_b.get("suffixes", []),
            },
            "parents": [religion_a["name"], religion_b["name"]],
        }

        _RELIGION_TEMPLATES.append(syncretic)
        return syncretic


# ── Factory Functions ──────────────────────────

def generate_demographics(culture):
    """
    Create initial ReligionDemographics for a settlement.
    Dominant religion at 90%, rest split among others.
    """
    culture_name = culture.get("name", "") if isinstance(culture, dict) else str(culture)
    primary = get_religion_for_culture(culture_name)

    if not primary:
        return ReligionDemographics()

    fractions = {primary["name"]: 0.9}

    others = [r for r in _RELIGION_TEMPLATES if r["name"] != primary["name"]]
    if others:
        minor_share = 0.1 / len(others)
        for r in others:
            fractions[r["name"]] = minor_share

    return ReligionDemographics(fractions)


def create_faith_from_demographics(demographics):
    """
    Create a PersonalFaith for an agent based on settlement demographics.
    Weighted random selection from the population fractions.
    """
    if not demographics or not demographics.fractions:
        return None

    names = list(demographics.fractions.keys())
    weights = [demographics.fractions[n] for n in names]

    chosen_name = _weighted_choice(names, weights)
    template = _find_template(chosen_name)
    if template:
        faith = PersonalFaith(template)
        faith.devotion = 0.5 + (demographics.dominant_fraction * 0.5)
        return faith
    return None


# ── Internal Helpers ───────────────────────────

def _find_template(religion_name):
    """Look up a religion template by name."""
    for r in _RELIGION_TEMPLATES:
        if r["name"] == religion_name:
            return r
    return None


def _weighted_choice(items, weights):
    """Simple weighted random choice."""
    total = sum(weights)
    if total == 0:
        return RandomService.choice(items) if items else None
    r = RandomService.random() * total
    cumulative = 0
    for item, w in zip(items, weights):
        cumulative += w
        if r <= cumulative:
            return item
    return items[-1] if items else None
