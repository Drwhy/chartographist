"""Versioned, deterministic personal state for optional character simulation."""

from copy import deepcopy
import hashlib


CHARACTER_VERSION = 1
NEED_NAMES = (
    "hunger",
    "security",
    "belonging",
    "status",
    "faith",
    "wealth",
    "fatigue",
)
SKILL_NAMES = (
    "agriculture",
    "hunting",
    "commerce",
    "combat",
    "healing",
    "leadership",
)
TRAIT_NAMES = (
    "prudence",
    "ambition",
    "empathy",
    "greed",
    "fervor",
)


def character_settings(config):
    section = config.get("characters", {}) if isinstance(config, dict) else {}
    return section if isinstance(section, dict) else {}


def characters_enabled(config):
    return character_settings(config).get("enabled") is True


def _clamp(value, minimum=0.0, maximum=100.0):
    return round(min(maximum, max(minimum, float(value))), 6)


def _stable_trait(person, name):
    identity = getattr(person, "entity_id", 0)
    label = getattr(person, "name", "")
    digest = hashlib.sha256(f"{identity}:{label}:{name}".encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], "big")
    return round(integer / ((1 << 64) - 1), 6)


def _initial_skills(person):
    skills = {name: 0.0 for name in SKILL_NAMES}
    role = type(person).__name__.lower()
    role_skill = {
        "farmer": "agriculture",
        "hunter": "hunting",
        "fisherman": "hunting",
        "trader": "commerce",
        "soldier": "combat",
    }.get(role)
    if role_skill:
        skills[role_skill] = 15.0
    experience = max(0.0, float(getattr(person, "experience", 0)))
    if role_skill:
        skills[role_skill] = _clamp(skills[role_skill] + experience)
    return skills


def _default_state(person):
    hunger = _clamp(getattr(person, "hunger", 0))
    family_name = str(getattr(person, "family_name", "") or "")
    return {
        "version": CHARACTER_VERSION,
        "needs": {
            "hunger": hunger,
            "security": 0.0,
            "belonging": 0.0,
            "status": 0.0,
            "faith": 0.0,
            "wealth": 0.0,
            "fatigue": 0.0,
        },
        "skills": _initial_skills(person),
        "traits": {
            name: _stable_trait(person, name)
            for name in TRAIT_NAMES
        },
        "memories": [],
        "next_memory_id": 1,
        "notability": {
            "is_notable": False,
            "score": 0.0,
            "reasons": [],
        },
        "household_id": family_name,
        "last_needs_cycle": None,
        "last_decision_cycle": None,
        "last_decision": {
            "selected": None,
            "options": [],
        },
    }


def _merge_defaults(target, defaults):
    for key, default in defaults.items():
        if key not in target:
            target[key] = deepcopy(default)
        elif isinstance(default, dict):
            if not isinstance(target[key], dict):
                target[key] = deepcopy(default)
            else:
                _merge_defaults(target[key], default)


def ensure_character_state(person, config):
    """Create or migrate personal state without consuming simulation randomness."""
    existing = getattr(person, "character", None)
    if not characters_enabled(config) and not isinstance(existing, dict):
        return {}

    defaults = _default_state(person)
    if isinstance(existing, dict):
        _merge_defaults(existing, defaults)
        existing["version"] = CHARACTER_VERSION
        state = existing
    else:
        state = defaults
        person.character = state

    for name in NEED_NAMES:
        state["needs"][name] = _clamp(state["needs"][name])
    for name in SKILL_NAMES:
        state["skills"][name] = _clamp(state["skills"][name])
    for name in TRAIT_NAMES:
        state["traits"][name] = round(
            min(1.0, max(0.0, float(state["traits"][name]))),
            6,
        )
    state["next_memory_id"] = max(1, int(state.get("next_memory_id", 1)))
    return state


class CharacterService:
    """Headless facade over one optional personal state."""

    def __init__(self, person, config):
        self.person = person
        self.config = config if isinstance(config, dict) else {}
        self.settings = character_settings(self.config)
        self.state = ensure_character_state(person, self.config)

    @property
    def enabled(self):
        return bool(self.state)

    def advance(self, world):
        if not self.enabled:
            return False
        from core.needs import advance_needs

        advanced = advance_needs(self.person, world, self.config)
        if advanced:
            from core.memory import MemoryBook
            MemoryBook(self.person, self.config).decay()
        return advanced

    def decide(self, world):
        if not self.enabled:
            return {"selected": None, "options": []}
        needs = self.state["needs"]
        traits = self.state["traits"]
        from core.memory import MemoryBook

        opinion = MemoryBook(self.person, self.config).opinion()
        mastery = max(float(value) for value in self.state["skills"].values())
        candidates = [
            ("seek_food", float(needs["hunger"]), ["hunger"]),
            (
                "seek_safety",
                float(needs["security"]) + float(opinion["fear"]),
                ["security", "memory.fear"],
            ),
            ("rest", float(needs["fatigue"]), ["fatigue"]),
            (
                "work",
                float(needs["status"]) * 0.45
                + float(needs["wealth"]) * 0.45
                + float(traits["ambition"]) * 10.0
                + float(traits["greed"]) * 5.0
                + mastery * 0.05,
                ["status", "wealth", "ambition", "greed", "skill"],
            ),
            (
                "socialize",
                float(needs["belonging"]) + float(traits["empathy"]) * 5.0,
                ["belonging", "empathy"],
            ),
            (
                "worship",
                float(needs["faith"]) + float(traits["fervor"]) * 5.0,
                ["faith", "fervor"],
            ),
        ]
        ranked = sorted(
            (
                {
                    "action": action,
                    "score": round(max(0.0, float(score)), 6),
                    "drivers": list(drivers),
                }
                for action, score, drivers in candidates
            ),
            key=lambda option: (-option["score"], option["action"]),
        )[:3]
        decision = {
            "selected": ranked[0]["action"] if ranked else None,
            "options": ranked,
        }
        self.state["last_decision_cycle"] = int(world.get("cycle", 0))
        self.state["last_decision"] = deepcopy(decision)
        from core.simulation_metrics import SimulationMetrics
        SimulationMetrics(world).record_activity("characters", "decisions")
        return deepcopy(decision)

    def prepare_action(self, world):
        if not self.enabled:
            return True
        self.advance(world)
        cycle = int(world.get("cycle", 0))
        interval = max(1, int(self.settings.get("decision_interval", 1)))
        entity_id = int(getattr(self.person, "entity_id", 0))
        if interval > 1 and (cycle + entity_id) % interval != 0:
            return True
        decision = self.decide(world)
        if decision["selected"] == "rest":
            from core.needs import satisfy_need

            satisfy_need(self.person, "fatigue", 25.0)
            from core.simulation_metrics import SimulationMetrics
            SimulationMetrics(world).record_activity("characters", "rests")
            return False
        return True

    def record_practice(self, skill, effort=1.0):
        if not self.enabled:
            return 0.0
        from core.skills import practice_skill

        return practice_skill(self.person, skill, effort)

    def snapshot(self):
        return deepcopy(self.state)





from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PopulationCohort:
    """Serializable aggregate view over ordinary settlement citizens."""

    cohort_id: object
    settlement_id: int
    culture: str
    age_band: str
    profession: str
    count: int

    def __post_init__(self):
        if isinstance(self.count, bool) or not isinstance(self.count, int):
            raise ValueError("cohort count must be an integer")
        if self.count < 0:
            raise ValueError("cohort count must be non-negative")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise TypeError("cohort must be a mapping")
        return cls(
            value["cohort_id"],
            int(value["settlement_id"]),
            str(value["culture"]),
            str(value["age_band"]),
            str(value["profession"]),
            value["count"],
        )


def _age_band(person):
    age = float(getattr(person, "age", 0.0))
    if age < 15:
        return "child"
    if age < 50:
        return "adult"
    return "elder"


def cohort_snapshots(settlement):
    """Group ordinary citizens while preserving the underlying object list."""
    groups = {}
    settlement_id = int(getattr(settlement, "entity_id", 0))
    for person in getattr(settlement, "citizens", ()):
        character = getattr(person, "character", {})
        notability = (
            character.get("notability", {})
            if isinstance(character, dict)
            else {}
        )
        if notability.get("is_notable"):
            continue
        culture = getattr(person, "culture", None)
        culture_name = (
            str(culture.get("name", ""))
            if isinstance(culture, dict)
            else str(culture or "")
        )
        key = (culture_name, _age_band(person), type(person).__name__)
        groups[key] = groups.get(key, 0) + 1

    result = []
    for index, (key, count) in enumerate(sorted(groups.items()), start=1):
        culture_name, age_band, profession = key
        result.append(
            PopulationCohort(
                f"{settlement_id}:{index}",
                settlement_id,
                culture_name,
                age_band,
                profession,
                count,
            ).to_dict()
        )
    return result

def transfer_character_state(source, target, config):
    """Copy personal history during a role change without sharing mutable data."""
    source_state = getattr(source, "character", None)
    if not isinstance(source_state, dict):
        return ensure_character_state(target, config)
    target.character = deepcopy(source_state)
    return ensure_character_state(target, config)


def inherit_character_state(child, first_parent, second_parent, config):
    """Transmit stable traits and a small fraction of practiced skills."""
    state = ensure_character_state(child, config)
    if not state:
        return {}
    parents = [parent for parent in (first_parent, second_parent) if parent is not None]
    parent_states = [
        ensure_character_state(parent, config)
        for parent in parents
    ]
    parent_states = [parent for parent in parent_states if parent]
    if not parent_states:
        return state

    for name in TRAIT_NAMES:
        state["traits"][name] = round(
            sum(float(parent["traits"][name]) for parent in parent_states)
            / len(parent_states),
            6,
        )
    for name in SKILL_NAMES:
        inherited = (
            sum(float(parent["skills"][name]) for parent in parent_states)
            / len(parent_states)
            * 0.1
        )
        state["skills"][name] = _clamp(inherited)
    state["household_id"] = str(
        getattr(parents[0], "family_name", state.get("household_id", "")) or ""
    )
    return state

def ensure_notable_storage(world):
    notables = world.get("notables")
    if not isinstance(notables, dict):
        notables = {}
        world["notables"] = notables
    archive = world.get("notable_archive")
    if not isinstance(archive, dict):
        archive = {}
        world["notable_archive"] = archive
    return notables, archive


class NotabilityService:
    """Promote and archive noteworthy people without replacing their identity."""

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.settings = character_settings(self.config)
        self.notables, self.archive_storage = ensure_notable_storage(world)

    @staticmethod
    def _entry(person):
        state = person.character["notability"]
        return {
            "entity_id": int(person.entity_id),
            "name": str(getattr(person, "name", "")),
            "type": type(person).__name__,
            "is_notable": bool(state["is_notable"]),
            "score": round(float(state["score"]), 6),
            "reasons": deepcopy(state["reasons"]),
            "character": deepcopy(person.character),
        }

    def promote(self, person, reason, *, importance, cycle=None):
        state = ensure_character_state(person, self.config)
        if not state:
            return {}
        notability = state["notability"]
        was_notable = bool(notability.get("is_notable"))
        reason_entry = {
            "kind": str(reason),
            "importance": round(max(0.0, float(importance)), 6),
            "cycle": int(
                self.world.get("cycle", 0) if cycle is None else cycle
            ),
        }
        notability["reasons"].append(reason_entry)
        notability["score"] = round(
            float(notability.get("score", 0.0)) + reason_entry["importance"],
            6,
        )
        threshold = max(
            0.0,
            float(self.settings.get("notability_threshold", 20.0)),
        )
        if notability["score"] >= threshold:
            notability["is_notable"] = True
            self.notables[str(person.entity_id)] = self._entry(person)
            if not was_notable:
                from core.simulation_metrics import SimulationMetrics
                SimulationMetrics(self.world).record_activity(
                    "characters", "promotions"
                )
        return deepcopy(notability)

    def archive(self, person, *, cycle=None):
        state = ensure_character_state(person, self.config)
        if not state or not state["notability"].get("is_notable"):
            return {}
        key = str(person.entity_id)
        entry = self.notables.pop(key, self._entry(person))
        entry["character"] = deepcopy(state)
        entry["is_notable"] = False
        entry["archived_cycle"] = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        entry["death"] = bool(
            getattr(person, "is_dead", False)
            or getattr(person, "is_expired", False)
        )
        self.archive_storage[key] = entry
        state["notability"]["is_notable"] = False
        from core.simulation_metrics import SimulationMetrics
        SimulationMetrics(self.world).record_activity("characters", "archives")
        return deepcopy(entry)

    def archive_inactive(self):
        for entity in list(self.world.get("entities", ())):
            candidates = [entity]
            citizens = getattr(entity, "citizens", None)
            if isinstance(citizens, list):
                candidates.extend(citizens)
            for person in candidates:
                if (
                    getattr(person, "is_dead", False)
                    or getattr(person, "is_expired", False)
                ):
                    self.archive(person)
        return len(self.archive_storage)
