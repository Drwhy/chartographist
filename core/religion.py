# ──────────────────────────────────────────────
#  Religion System — Faith, Demographics & Syncretism
# ──────────────────────────────────────────────
from core.random_service import RandomService

# ── Module-Level Religion Data ──────────────────
_RELIGION_TEMPLATES = []
_DOMAIN_DEFS = {}


def init_religion_data(config):
    """
    Load religion templates from config.
    Called once at startup after RandomService is initialized.
    Uses explicit religion definitions from template.json when available,
    otherwise auto-generates one religion per culture.
    """
    global _RELIGION_TEMPLATES, _DOMAIN_DEFS
    _RELIGION_TEMPLATES.clear()

    _DOMAIN_DEFS = config.get("domains", {})

    religions_cfg = config.get("religions", [])
    if religions_cfg:
        for r in religions_cfg:
            # Generate a god name using the religion's dedicated naming table
            god_name = _generate_god_name_from_religion(r)
            template = {
                "name": r["name"],
                "god": god_name,
                "culture": r.get("culture", ""),
                "domain": r.get("domain", "life"),
                "bonuses": dict(r.get("bonuses", {})),
                "emoji": r.get("emoji", "🙏"),
                "naming": r.get("naming", {}),
            }
            _RELIGION_TEMPLATES.append(template)
    else:
        # Fallback: auto-generate one religion per culture
        domains = ["war", "trade", "fertility", "life"]
        for i, culture in enumerate(config.get("cultures", [])):
            domain = domains[i % len(domains)]
            _RELIGION_TEMPLATES.append(_generate_religion_for_culture(culture, domain))


def _generate_god_name_from_religion(religion_cfg):
    """Generate a deity name using the religion's own naming table."""
    naming = religion_cfg.get("naming", {})
    prefixes = naming.get("prefixes", ["Sol"])
    suffixes = naming.get("suffixes", ["us"])
    return RandomService.choice(prefixes) + RandomService.choice(suffixes)


def _generate_religion_for_culture(culture, domain="life"):
    """Create a fallback religion template tied to a culture."""
    name = culture["name"]
    god_name = _generate_god_name_from_culture(culture)
    return {
        "name": f"Faith of {god_name}",
        "god": god_name,
        "culture": name,
        "domain": domain,
        "bonuses": {
            "growth": RandomService.randint(1, 5),
            "perception": RandomService.randint(0, 3),
            "harvest": RandomService.randint(1, 4),
            "trade": RandomService.randint(0, 3),
            "defense": RandomService.randint(0, 2),
        },
        "emoji": RandomService.choice(["⛪", "🕌", "⛩️", "🛕", "🕍", "🪨"]),
        "naming": {},
    }


def _generate_god_name_from_culture(culture):
    """Fallback: generate deity name from culture naming rules."""
    naming = culture.get("naming", {})
    prefixes = naming.get("prefixes", ["Sol"])
    suffixes = naming.get("suffixes_person", ["us"])
    return RandomService.choice(prefixes) + RandomService.choice(suffixes)


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
    """Returns the emoji for a domain (war, trade, fertility, etc.)."""
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
        self.devotion = 1.0  # 0.0 = skeptic, 1.0 = devout
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
    Provides aggregate bonus queries.
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
        """Returns the name of the religion with highest fraction."""
        if not self.fractions:
            return None
        return max(self.fractions, key=self.fractions.get)

    @property
    def dominant_fraction(self):
        """Returns the fraction of the dominant religion."""
        if not self.fractions:
            return 0.0
        return self.fractions.get(self.dominant, 0.0)

    def bonus(self, key, default=0):
        """
        Weighted average of all religion bonuses for a given key.
        Each religion's bonus is scaled by its population fraction.
        """
        total_bonus = 0.0
        for rname, fraction in self.fractions.items():
            template = _find_template(rname)
            if template:
                raw = template.get("bonuses", {}).get(key, default)
                total_bonus += raw * fraction
        return total_bonus

    def influence(self, religion_name, strength=0.05):
        """
        Apply external religious influence (e.g., from a trader).
        Increases the named religion's share and re-normalizes.
        """
        current = self.fractions.get(religion_name, 0.0)
        self.fractions[religion_name] = current + strength
        self._normalize()

    def merge(self, other):
        """Merge another ReligionDemographics into this one (averaging)."""
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
    Produces a new religion template that can be used in PersonalFaith.
    """

    @staticmethod
    def create(religion_a, religion_b):
        """
        Create a syncretic religion from two parent templates.
        God name is built from each religion's own naming table.
        Bonuses are averaged.
        """
        # Generate syncretic god name using both religions' naming tables
        naming_a = religion_a.get("naming", {})
        naming_b = religion_b.get("naming", {})
        prefix_a = RandomService.choice(naming_a.get("prefixes", [religion_a.get("god", "Syn")[:3]]))
        suffix_b = RandomService.choice(naming_b.get("suffixes", [religion_b.get("god", "cret")[-3:]]))
        syncretic_god = prefix_a + suffix_b

        # Average bonuses
        bonuses_a = religion_a.get("bonuses", {})
        bonuses_b = religion_b.get("bonuses", {})
        all_keys = set(bonuses_a.keys()) | set(bonuses_b.keys())
        merged_bonuses = {}
        for k in all_keys:
            merged_bonuses[k] = (bonuses_a.get(k, 0) + bonuses_b.get(k, 0)) / 2.0

        # Syncretic domain: pick the one with higher total bonuses
        domain_a = religion_a.get("domain", "life")
        domain_b = religion_b.get("domain", "life")
        syncretic_domain = domain_a if sum(bonuses_a.values()) >= sum(bonuses_b.values()) else domain_b

        syncretic = {
            "name": f"Faith of {syncretic_god}",
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

        # Register globally so it can be looked up
        _RELIGION_TEMPLATES.append(syncretic)
        return syncretic


# ── Factory Functions ──────────────────────────

def generate_demographics(culture):
    """
    Create initial ReligionDemographics for a settlement.
    Uses the culture's associated religion as dominant (90%)
    with a small fraction of other faiths.
    """
    culture_name = culture.get("name", "") if isinstance(culture, dict) else str(culture)
    primary = get_religion_for_culture(culture_name)

    if not primary:
        return ReligionDemographics()

    fractions = {primary["name"]: 0.9}

    # Add minor presence of other religions
    others = [r for r in _RELIGION_TEMPLATES if r["name"] != primary["name"]]
    if others:
        minor_share = 0.1 / len(others)
        for r in others:
            fractions[r["name"]] = minor_share

    return ReligionDemographics(fractions)


def create_faith_from_demographics(demographics):
    """
    Create a PersonalFaith for an agent based on settlement demographics.
    Randomly selects a religion weighted by population fractions.
    """
    if not demographics or not demographics.fractions:
        return None

    names = list(demographics.fractions.keys())
    weights = [demographics.fractions[n] for n in names]

    # Weighted random selection
    chosen_name = _weighted_choice(names, weights)
    template = _find_template(chosen_name)
    if template:
        faith = PersonalFaith(template)
        # Devotion varies: higher in monocultures, lower in diverse settlements
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
