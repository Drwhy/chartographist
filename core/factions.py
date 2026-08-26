"""Stable, deterministic faction registry for optional settlement politics."""

from copy import deepcopy


POLITICS_VERSION = 1
FACTION_MIN = 0.0
FACTION_MAX = 100.0


def politics_settings(config):
    section = config.get("politics", {}) if isinstance(config, dict) else {}
    return section if isinstance(section, dict) else {}


def politics_enabled(config):
    return politics_settings(config).get("enabled") is True


def _bounded(value):
    return round(min(FACTION_MAX, max(FACTION_MIN, float(value))), 6)


def ensure_politics_state(world):
    state = world.get("politics")
    if not isinstance(state, dict):
        state = {}
        world["politics"] = state
    state["version"] = POLITICS_VERSION
    state["next_faction_id"] = max(1, int(state.get("next_faction_id", 1)))
    state["next_proposal_id"] = max(1, int(state.get("next_proposal_id", 1)))
    settlements = state.get("settlements")
    if not isinstance(settlements, dict):
        settlements = {}
        state["settlements"] = settlements
    return state


def ensure_settlement_politics(world, settlement_id):
    state = ensure_politics_state(world)
    key = str(int(settlement_id))
    settlement = state["settlements"].get(key)
    if not isinstance(settlement, dict):
        settlement = {}
        state["settlements"][key] = settlement
    settlement["version"] = POLITICS_VERSION
    settlement["settlement_id"] = int(settlement_id)
    if not isinstance(settlement.get("factions"), dict):
        settlement["factions"] = {}
    if not isinstance(settlement.get("proposals"), list):
        settlement["proposals"] = []
    if not isinstance(settlement.get("conflicts"), list):
        settlement["conflicts"] = []
    settlement.setdefault("last_advanced_cycle", None)
    settlement.setdefault("migration_pressure", 0.0)
    settlement.setdefault("taxes_collected", 0.0)
    return settlement


def _profession(person):
    explicit = getattr(person, "profession", None)
    return str(explicit or type(person).__name__)


def _faith(person):
    faith = getattr(person, "faith", None)
    name = getattr(faith, "religion_name", None)
    if not name:
        name = getattr(faith, "primary", None)
    return str(name or "")


def _household(person):
    character = getattr(person, "character", None)
    if isinstance(character, dict):
        value = character.get("household_id")
        if value:
            return str(value)
    return str(getattr(person, "family_name", "") or "")


_SOURCE_READERS = {
    "profession": _profession,
    "faith": _faith,
    "household": _household,
}


class FactionRegistry:
    """Derive memberships while preserving stable faction identities."""

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.settings = politics_settings(self.config)
        self.enabled = politics_enabled(self.config)
        self.storage = ensure_politics_state(world) if self.enabled else None

    def sync(self, settlement):
        if not self.enabled:
            return []
        settlement_id = int(settlement.entity_id)
        state = ensure_settlement_politics(self.world, settlement_id)
        citizens = [
            person
            for person in getattr(settlement, "citizens", ())
            if not getattr(person, "is_dead", False)
            and not getattr(person, "is_expired", False)
        ]
        population = max(1, len(citizens))
        active_keys = set()
        definitions = self.settings.get("faction_types", ())
        if not isinstance(definitions, list):
            definitions = ()

        for definition in definitions:
            if not isinstance(definition, dict):
                continue
            kind = str(definition.get("id", ""))
            source = str(definition.get("source", ""))
            reader = _SOURCE_READERS.get(source)
            if not kind or reader is None:
                continue
            groups = {}
            for person in citizens:
                value = reader(person)
                if value:
                    groups.setdefault(value, []).append(int(person.entity_id))
            maximum = max(1, int(definition.get(
                "max_factions",
                self.settings.get("max_factions_per_type", 32),
            )))
            ranked_groups = sorted(
                groups.items(), key=lambda item: (-len(item[1]), str(item[0]))
            )[:maximum]
            for group_key, member_ids in sorted(ranked_groups):
                identity = f"{kind}:{group_key}"
                active_keys.add(identity)
                faction = state["factions"].get(identity)
                created = not isinstance(faction, dict)
                previous_members = (
                    []
                    if created
                    else sorted(set(faction.get("member_ids", ())))
                )
                if created:
                    faction = self._create_faction(
                        settlement_id,
                        kind,
                        group_key,
                        definition,
                    )
                    state["factions"][identity] = faction
                current_members = sorted(set(member_ids))
                faction["member_ids"] = current_members
                faction["active"] = True
                base = float(definition.get("base_influence", 10.0))
                if created or previous_members != current_members:
                    faction["influence"] = _bounded(
                        base + len(current_members) / population * 50.0
                    )
                else:
                    faction["influence"] = _bounded(
                        faction.get("influence", base)
                    )
                faction["satisfaction"] = _bounded(
                    faction.get(
                        "satisfaction",
                        self.settings.get("initial_satisfaction", 60.0),
                    )
                )
                faction["objective"] = self._objective(definition, group_key)
                opposed = definition.get("opposes", {})
                if isinstance(opposed, dict):
                    opposed = opposed.get(faction["objective"], ())
                faction["opposed_objectives"] = sorted({
                    str(value) for value in opposed or () if str(value)
                })

        for identity, faction in state["factions"].items():
            if identity not in active_keys and isinstance(faction, dict):
                faction["member_ids"] = []
                faction["active"] = False
                faction["influence"] = 0.0
        return self.query(settlement_id=settlement_id, active=True)

    def _create_faction(self, settlement_id, kind, key, definition):
        faction_id = int(self.storage["next_faction_id"])
        self.storage["next_faction_id"] += 1
        return {
            "faction_id": faction_id,
            "settlement_id": int(settlement_id),
            "kind": str(kind),
            "key": str(key),
            "member_ids": [],
            "influence": _bounded(definition.get("base_influence", 10.0)),
            "satisfaction": _bounded(
                self.settings.get("initial_satisfaction", 60.0)
            ),
            "objective": self._objective(definition, key),
            "opposed_objectives": [],
            "grievances": [],
            "resources": 0.0,
            "active": True,
        }

    @staticmethod
    def _objective(definition, key):
        objectives = definition.get("objectives")
        if isinstance(objectives, dict):
            return str(objectives.get(str(key), objectives.get("default", "")))
        return str(definition.get("objective", ""))

    def _find(self, faction_id):
        if not self.enabled:
            return None
        wanted = int(faction_id)
        for settlement in self.storage["settlements"].values():
            factions = settlement.get("factions", {})
            for faction in factions.values():
                if (
                    isinstance(faction, dict)
                    and int(faction.get("faction_id", 0)) == wanted
                ):
                    return faction
        return None

    def adjust_satisfaction(self, faction_id, amount, *, reason=None, cycle=None):
        faction = self._find(faction_id)
        if faction is None:
            raise KeyError(int(faction_id))
        faction["satisfaction"] = _bounded(
            float(faction.get("satisfaction", 0.0)) + float(amount)
        )
        if reason:
            grievances = faction.setdefault("grievances", [])
            grievances.append({
                "reason": str(reason),
                "amount": round(float(amount), 6),
                "cycle": int(
                    self.world.get("cycle", 0) if cycle is None else cycle
                ),
            })
            limit = max(1, int(self.settings.get("grievance_limit", 32)))
            if len(grievances) > limit:
                del grievances[:-limit]
        return deepcopy(faction)

    def set_influence(self, faction_id, value):
        faction = self._find(faction_id)
        if faction is None:
            raise KeyError(int(faction_id))
        faction["influence"] = _bounded(value)
        return deepcopy(faction)

    def query(
        self,
        *,
        settlement_id=None,
        faction_id=None,
        kind=None,
        member_id=None,
        active=None,
    ):
        if not self.enabled:
            return []
        results = []
        for settlement in self.storage["settlements"].values():
            if not isinstance(settlement, dict):
                continue
            if (
                settlement_id is not None
                and int(settlement.get("settlement_id", 0)) != int(settlement_id)
            ):
                continue
            for faction in settlement.get("factions", {}).values():
                if not isinstance(faction, dict):
                    continue
                if faction_id is not None and int(faction["faction_id"]) != int(faction_id):
                    continue
                if kind is not None and faction.get("kind") != str(kind):
                    continue
                if member_id is not None and int(member_id) not in faction.get("member_ids", ()):
                    continue
                if active is not None and bool(faction.get("active")) is not bool(active):
                    continue
                results.append(deepcopy(faction))
        return sorted(results, key=lambda value: int(value["faction_id"]))
