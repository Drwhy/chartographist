"""Data-driven governments, offices and deterministic succession."""

from copy import deepcopy

from core.factions import (
    ensure_settlement_politics,
    politics_enabled,
    politics_settings,
)


def _bounded(value):
    return round(min(100.0, max(0.0, float(value))), 6)


class InstitutionService:
    """Manage one settlement institution without replacing person identities."""

    def __init__(self, world, config, settlement):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.settings = politics_settings(self.config)
        self.settlement = settlement
        self.enabled = politics_enabled(self.config)
        self.state = {}
        self.government = {}
        self.office_definitions = {}
        if self.enabled:
            self._initialize()

    def _initialize(self):
        governments = self.settings.get("governments", ())
        definitions = {
            str(value.get("id")): value
            for value in governments
            if isinstance(value, dict) and value.get("id")
        }
        government_id = str(
            self.settings.get("default_government", "")
            or next(iter(definitions), "council")
        )
        self.government = definitions.get(government_id, {"id": government_id})
        self.office_definitions = {
            str(value.get("id")): value
            for value in self.government.get("offices", ())
            if isinstance(value, dict) and value.get("id")
        }
        political = ensure_settlement_politics(
            self.world,
            self.settlement.entity_id,
        )
        institution = political.get("institution")
        if not isinstance(institution, dict):
            institution = {}
            political["institution"] = institution
        institution["version"] = 1
        institution.setdefault("government_id", government_id)
        institution["legitimacy"] = _bounded(
            institution.get(
                "legitimacy",
                self.settings.get("initial_legitimacy", 50.0),
            )
        )
        institution.setdefault("regent_id", None)
        institution.setdefault("succession_crises", 0)
        institution.setdefault("last_crisis_cycle", None)
        if not isinstance(institution.get("offices"), dict):
            institution["offices"] = {}
        if not isinstance(institution.get("active_policies"), list):
            institution["active_policies"] = []
        for office_id, definition in self.office_definitions.items():
            office = institution["offices"].get(office_id)
            if not isinstance(office, dict):
                office = {}
                institution["offices"][office_id] = office
            office.update({
                "office_id": office_id,
                "skill": str(definition.get("skill", "leadership")),
                "term_cycles": max(1, int(definition.get("term_cycles", 120))),
            })
            office.setdefault("holder_id", None)
            office.setdefault("term_started_cycle", None)
            office.setdefault("term_ends_cycle", None)
            office.setdefault("succession_count", 0)
            office["status"] = (
                "occupied" if office.get("holder_id") is not None else "vacant"
            )
        self.state = institution

    def snapshot(self):
        return deepcopy(self.state)

    def _person(self, entity_id):
        if entity_id is None:
            return None
        wanted = int(entity_id)
        for person in getattr(self.settlement, "citizens", ()):
            if int(getattr(person, "entity_id", 0)) == wanted:
                return person
        return None

    @staticmethod
    def _notability(person):
        state = getattr(person, "character", None)
        if not isinstance(state, dict):
            return {}
        value = state.get("notability", {})
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _skill(person, skill):
        state = getattr(person, "character", None)
        skills = state.get("skills", {}) if isinstance(state, dict) else {}
        return float(skills.get(skill, 0.0)) if isinstance(skills, dict) else 0.0

    def _held_office(self, person):
        identifier = int(person.entity_id)
        return next(
            (
                office_id
                for office_id, office in self.state["offices"].items()
                if office.get("holder_id") == identifier
            ),
            None,
        )

    def eligible(self, office_id, person, *, allow_current=False):
        definition = self.office_definitions.get(str(office_id))
        if definition is None or person not in getattr(self.settlement, "citizens", ()):
            return False
        if getattr(person, "is_dead", False) or getattr(person, "is_expired", False):
            return False
        notability = self._notability(person)
        if notability.get("is_notable") is not True:
            return False
        minimum = max(0.0, float(definition.get("minimum_notability", 0.0)))
        if float(notability.get("score", 0.0)) < minimum:
            return False
        roles = definition.get("roles")
        if isinstance(roles, list) and roles:
            profession = str(getattr(person, "profession", type(person).__name__))
            if profession not in {str(role) for role in roles}:
                return False
        held = self._held_office(person)
        return allow_current or held is None or held == str(office_id)

    def appoint(self, office_id, person, *, cycle=None):
        return self._appoint(office_id, person, cycle=cycle, succession=False)

    def _appoint(self, office_id, person, *, cycle=None, succession):
        key = str(office_id)
        if key not in self.state.get("offices", {}):
            raise KeyError(key)
        if not self.eligible(key, person):
            raise ValueError("ineligible_office_holder")
        current_cycle = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        office = self.state["offices"][key]
        office["holder_id"] = int(person.entity_id)
        office["term_started_cycle"] = current_cycle
        office["term_ends_cycle"] = (
            current_cycle + int(office["term_cycles"])
        )
        office["status"] = "occupied"
        if succession:
            office["succession_count"] = int(
                office.get("succession_count", 0)
            ) + 1
            from core.simulation_metrics import SimulationMetrics
            SimulationMetrics(self.world).record_politics("successions")
            from core.logger import GameLogger
            from core.translator import Translator
            GameLogger.log(
                Translator.translate(
                    "events.politics_succession",
                    settlement=self.settlement.name,
                    office=key,
                    holder=getattr(person, "name", person.entity_id),
                ),
                category="politics", entity_ids=[self.settlement.entity_id, person.entity_id],
                position=self.settlement.pos,
            )
        if key == str(self.government.get("head_office", "")):
            self.state["regent_id"] = None
        return deepcopy(office)

    def vacate(self, office_id):
        key = str(office_id)
        office = self.state["offices"].get(key)
        if office is None:
            raise KeyError(key)
        office["holder_id"] = None
        office["term_started_cycle"] = None
        office["term_ends_cycle"] = None
        office["status"] = "vacant"
        return deepcopy(office)

    def _ranked_candidates(self, office_id):
        definition = self.office_definitions[str(office_id)]
        skill = str(definition.get("skill", "leadership"))
        candidates = [
            person
            for person in getattr(self.settlement, "citizens", ())
            if self.eligible(office_id, person)
        ]
        return sorted(
            candidates,
            key=lambda person: (
                -self._skill(person, skill),
                -float(self._notability(person).get("score", 0.0)),
                int(person.entity_id),
            ),
        )

    def advance(self, *, cycle=None):
        if not self.enabled:
            return {}
        current_cycle = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        for office_id in self.office_definitions:
            office = self.state["offices"][office_id]
            holder = self._person(office.get("holder_id"))
            expired = (
                office.get("term_ends_cycle") is not None
                and current_cycle >= int(office["term_ends_cycle"])
            )
            invalid = (
                office.get("holder_id") is not None
                and (
                    holder is None
                    or getattr(holder, "is_dead", False)
                    or getattr(holder, "is_expired", False)
                    or expired
                )
            )
            if invalid:
                self.vacate(office_id)
            if self.state["offices"][office_id]["holder_id"] is None:
                candidates = self._ranked_candidates(office_id)
                if candidates:
                    self._appoint(
                        office_id,
                        candidates[0],
                        cycle=current_cycle,
                        succession=True,
                    )

        head_id = str(self.government.get("head_office", ""))
        head = self.state["offices"].get(head_id)
        if head is not None and head.get("holder_id") is None:
            officers = sorted(
                int(office["holder_id"])
                for office in self.state["offices"].values()
                if office.get("holder_id") is not None
            )
            self.state["regent_id"] = officers[0] if officers else None
            if self.state.get("last_crisis_cycle") != current_cycle:
                self.state["succession_crises"] = int(
                    self.state.get("succession_crises", 0)
                ) + 1
                self.state["last_crisis_cycle"] = current_cycle
                self.state["legitimacy"] = _bounded(
                    float(self.state["legitimacy"])
                    - float(self.settings.get("succession_crisis_penalty", 5.0))
                )
                from core.simulation_metrics import SimulationMetrics
                from core.logger import GameLogger
                from core.translator import Translator
                GameLogger.log(
                    Translator.translate(
                        "events.politics_crisis",
                        settlement=self.settlement.name,
                        legitimacy=self.state["legitimacy"],
                    ),
                    category="politics", entity_ids=[self.settlement.entity_id],
                    position=self.settlement.pos,
                )
                SimulationMetrics(self.world).record_politics("crises")
        elif head is not None:
            self.state["regent_id"] = None
        return self.snapshot()

class PolicyService:
    """Turn faction interests into traceable temporary policies."""

    def __init__(self, world, config, settlement):
        from core.factions import FactionRegistry

        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.settings = politics_settings(self.config)
        self.settlement = settlement
        self.enabled = politics_enabled(self.config)
        self.registry = FactionRegistry(world, self.config)
        self.institution = InstitutionService(
            world,
            self.config,
            settlement,
        )
        self.definitions = {
            str(value.get("id")): value
            for value in self.settings.get("policies", ())
            if isinstance(value, dict) and value.get("id")
        }
        self.political = (
            ensure_settlement_politics(world, settlement.entity_id)
            if self.enabled
            else {}
        )
        if self.enabled:
            self._refresh_modifiers()

    def _refresh_modifiers(self):
        keys = set()
        for policy in self.institution.state.get("active_policies", ()):
            modifiers = policy.get("modifiers", {}) if isinstance(policy, dict) else {}
            if isinstance(modifiers, dict):
                keys.update(modifiers)
        composed = {}
        for key in sorted(keys):
            default = 1.0 if str(key).endswith("_multiplier") else 0.0
            composed[key] = policy_modifier(
                self.world,
                self.settlement,
                key,
                default=default,
            )
        self.settlement.political_modifiers = composed
        return composed

    def snapshot(self):
        if not self.enabled:
            return {"proposals": [], "active_policies": []}
        return {
            "proposals": deepcopy(self.political["proposals"]),
            "active_policies": deepcopy(
                self.institution.state["active_policies"]
            ),
        }

    def _proposal(self, proposal_id):
        wanted = int(proposal_id)
        return next(
            (
                proposal
                for proposal in self.political.get("proposals", ())
                if int(proposal.get("proposal_id", 0)) == wanted
            ),
            None,
        )

    def propose(self, policy_id, sponsor_faction_id, *, cycle=None):
        if not self.enabled:
            return {}
        identifier = str(policy_id)
        if identifier not in self.definitions:
            raise KeyError(identifier)
        sponsor = self.registry.query(
            settlement_id=self.settlement.entity_id,
            faction_id=sponsor_faction_id,
            active=True,
        )
        if not sponsor:
            raise ValueError("invalid_policy_sponsor")
        current_cycle = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        proposal_id = int(self.registry.storage["next_proposal_id"])
        self.registry.storage["next_proposal_id"] += 1
        proposal = {
            "proposal_id": proposal_id,
            "settlement_id": int(self.settlement.entity_id),
            "policy_id": identifier,
            "sponsor_faction_id": int(sponsor_faction_id),
            "created_cycle": current_cycle,
            "resolved_cycle": None,
            "status": "proposed",
            "supporter_ids": [],
            "opponent_ids": [],
            "support_score": 0.0,
            "opposition_score": 0.0,
            "information_score": 0.0,
            "causes": [],
            "winners": [],
            "losers": [],
        }
        self.political["proposals"].append(proposal)
        from core.simulation_metrics import SimulationMetrics
        SimulationMetrics(self.world).record_politics("proposals")
        return deepcopy(proposal)


    def _information_score(self):
        knowledge = getattr(self.settlement, "knowledge", None)
        facts = knowledge.get("facts", ()) if isinstance(knowledge, dict) else ()
        reliabilities = [
            min(1.0, max(0.0, float(fact.get("reliability", 0.0))))
            for fact in facts
            if isinstance(fact, dict)
        ]
        return (
            round(sum(reliabilities) / len(reliabilities), 6)
            if reliabilities
            else 0.0
        )

    @staticmethod
    def _weight(faction):
        influence = max(0.0, float(faction.get("influence", 0.0)))
        satisfaction = min(
            100.0,
            max(0.0, float(faction.get("satisfaction", 0.0))),
        )
        return influence * (0.5 + satisfaction / 200.0)

    def resolve(self, proposal_id, *, cycle=None):
        proposal = self._proposal(proposal_id)
        if proposal is None:
            raise KeyError(int(proposal_id))
        if proposal["status"] != "proposed":
            return deepcopy(proposal)
        definition = self.definitions[proposal["policy_id"]]
        supports = {str(value) for value in definition.get("supports", ())}
        opposes = {str(value) for value in definition.get("opposes", ())}
        factions = self.registry.query(
            settlement_id=self.settlement.entity_id,
            active=True,
        )
        supporters = [
            faction for faction in factions
            if faction.get("objective") in supports
        ]
        opponents = [
            faction for faction in factions
            if faction.get("objective") in opposes
        ]
        supporter_ids = sorted(
            int(faction["faction_id"]) for faction in supporters
        )
        opponent_ids = sorted(
            int(faction["faction_id"]) for faction in opponents
        )
        legitimacy = float(
            self.institution.state.get("legitimacy", 0.0)
        )
        information = self._information_score()
        sponsor = self.registry.query(
            faction_id=proposal["sponsor_faction_id"],
        )[0]
        sponsor_members = set(sponsor.get("member_ids", ()))

        def relationship_weight(faction):
            members = set(faction.get("member_ids", ()))
            union = sponsor_members | members
            if not union:
                return 0.0
            overlap = len(sponsor_members & members) / len(union)
            return overlap * self._weight(faction) * 0.1

        relationship_support = sum(
            relationship_weight(faction) for faction in supporters
        )
        relationship_opposition = sum(
            relationship_weight(faction) for faction in opponents
        )
        support_score = (
            sum(self._weight(faction) for faction in supporters)
            + float(sponsor.get("influence", 0.0)) * 0.1
            + relationship_support
            + legitimacy * 0.1
            + information * 5.0
        )
        opposition_score = (
            sum(self._weight(faction) for faction in opponents)
            + relationship_opposition
        )
        threshold = max(
            0.0,
            float(self.settings.get("proposal_threshold", 0.0)),
        )
        enacted = (
            support_score >= threshold
            and support_score > opposition_score
        )
        current_cycle = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        proposal.update({
            "resolved_cycle": current_cycle,
            "status": "enacted" if enacted else "rejected",
            "supporter_ids": supporter_ids,
            "opponent_ids": opponent_ids,
            "support_score": round(support_score, 6),
            "opposition_score": round(opposition_score, 6),
            "information_score": information,
            "relationship_support": round(relationship_support, 6),
            "relationship_opposition": round(relationship_opposition, 6),
            "relationship_score": round(
                relationship_support - relationship_opposition, 6
            ),
            "causes": [
                "faction_interests",
                "satisfaction",
                "relationships",
                "legitimacy",
                "information",
            ],
            "winners": supporter_ids if enacted else opponent_ids,
            "losers": opponent_ids if enacted else supporter_ids,
        })

        from core.simulation_metrics import SimulationMetrics
        from core.logger import GameLogger
        from core.translator import Translator
        status = Translator.translate(
            "events.politics_status_enacted"
            if enacted else "events.politics_status_rejected"
        )
        GameLogger.log(
            Translator.translate(
                "events.politics_policy_result",
                settlement=self.settlement.name,
                policy=proposal["policy_id"],
                status=status,
                supporters=len(supporter_ids),
                opponents=len(opponent_ids),
            ),
            category="politics", entity_ids=[self.settlement.entity_id],
            position=self.settlement.pos,
        )
        SimulationMetrics(self.world).record_politics("enacted" if enacted else "rejected")
        if enacted:
            duration = max(
                1,
                int(definition.get("duration_cycles", 12)),
            )
            active = self.institution.state["active_policies"]
            active[:] = [
                policy for policy in active
                if policy.get("policy_id") != proposal["policy_id"]
            ]
            active.append({
                "proposal_id": int(proposal["proposal_id"]),
                "policy_id": proposal["policy_id"],
                "enacted_cycle": current_cycle,
                "expires_cycle": current_cycle + duration,
                "modifiers": deepcopy(definition.get("modifiers", {})),
                "winner_ids": supporter_ids,
                "loser_ids": opponent_ids,
            })
        self._refresh_modifiers()
        return deepcopy(proposal)

    def advance(self, *, cycle=None):
        if not self.enabled:
            return self.snapshot()
        current_cycle = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        active = self.institution.state["active_policies"]
        active[:] = [
            policy
            for policy in active
            if int(policy.get("expires_cycle", 0)) > current_cycle
        ]
        self._refresh_modifiers()
        return self.snapshot()


def policy_modifier(world, settlement, key, *, default):
    """Compose active policy values without mutating political state."""
    politics = world.get("politics", {})
    settlements = (
        politics.get("settlements", {})
        if isinstance(politics, dict)
        else {}
    )
    political = settlements.get(str(int(settlement.entity_id)), {})
    institution = (
        political.get("institution", {})
        if isinstance(political, dict)
        else {}
    )
    active = (
        institution.get("active_policies", ())
        if isinstance(institution, dict)
        else ()
    )
    current_cycle = int(world.get("cycle", 0))
    values = [
        float(policy.get("modifiers", {}).get(key))
        for policy in active
        if isinstance(policy, dict)
        and int(policy.get("expires_cycle", 0)) > current_cycle
        and isinstance(policy.get("modifiers", {}).get(key), (int, float))
        and not isinstance(policy.get("modifiers", {}).get(key), bool)
    ]
    result = float(default)


    if str(key).endswith("_multiplier"):
        for value in values:
            result *= value
    else:
        result += sum(values)
    return round(result, 6)


def settlement_policy_modifier(settlement, key, *, default):
    """Read the composed policy cache used by hot simulation paths."""
    modifiers = getattr(settlement, "political_modifiers", None)
    if not isinstance(modifiers, dict):
        return float(default)
    value = modifiers.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return float(default)
    return round(float(value), 6)

