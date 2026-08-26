"""Political cadence, dissent, internal conflicts and responses."""

from copy import deepcopy

from core.factions import (
    FactionRegistry,
    ensure_settlement_politics,
    politics_enabled,
    politics_settings,
)
from core.institutions import InstitutionService, PolicyService, policy_modifier


def _bounded(value):
    return round(min(100.0, max(0.0, float(value))), 6)


def _is_settlement(entity):
    return (
        not getattr(entity, "is_expired", False)
        and hasattr(entity, "citizens")
        and hasattr(entity, "food_stock")
        and hasattr(entity, "max_food")
    )


class PoliticsService:
    """Advance optional politics without consuming simulation randomness."""

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.settings = politics_settings(self.config)
        self.enabled = politics_enabled(self.config)
        self.registry = FactionRegistry(world, self.config)
        self.institutions = {}
        self.policies = {}
        self.institution = None

    def sync(self, settlement):
        if not self.enabled:
            return []
        factions = self.registry.sync(settlement)
        key = int(settlement.entity_id)
        self.institutions[key] = InstitutionService(
            self.world,
            self.config,
            settlement,
        )
        self.policies[key] = PolicyService(
            self.world,
            self.config,
            settlement,
        )
        self.institution = self.institutions[key]
        return factions

    def _services(self, settlement):
        key = int(settlement.entity_id)
        if key not in self.institutions:
            self.sync(settlement)
        self.institution = self.institutions[key]
        return self.institutions[key], self.policies[key]

    def _at_war(self, settlement):
        identifier = int(settlement.entity_id)
        diplomacy = self.world.get("diplomacy", {})
        relations = diplomacy.values() if isinstance(diplomacy, dict) else ()
        return any(
            isinstance(relation, dict)
            and relation.get("status") == "war"
            and identifier in {
                int(relation.get("first_id", 0)),
                int(relation.get("second_id", 0)),
            }
            for relation in relations
        )

    def _apply_pressures(self, settlement, factions):
        ratio = (
            max(0.0, float(settlement.food_stock))
            / max(1.0, float(settlement.max_food))
        )
        famine = ratio < float(self.settings.get("famine_ratio", 0.25))
        tax_rate = max(
            0.0,
            policy_modifier(
                self.world,
                settlement,
                "tax_rate",
                default=0.0,
            ),
        )
        at_war = self._at_war(settlement)
        tolerance = policy_modifier(
            self.world,
            settlement,
            "religious_tolerance_multiplier",
            default=1.0,
        )
        for faction in factions:
            faction_id = faction["faction_id"]
            if famine:
                self.registry.adjust_satisfaction(
                    faction_id,
                    -float(self.settings.get("famine_penalty", 20.0)),
                    reason="famine",
                )
            if tax_rate > 0:
                self.registry.adjust_satisfaction(
                    faction_id,
                    -tax_rate * float(
                        self.settings.get("tax_dissent_scale", 50.0)
                    ),
                    reason="taxes",
                )
            if at_war:
                self.registry.adjust_satisfaction(
                    faction_id,
                    -float(self.settings.get("war_dissent", 5.0)),
                    reason="war",
                )
            if faction.get("kind") == "faith" and tolerance < 1.0:
                self.registry.adjust_satisfaction(
                    faction_id,
                    -(1.0 - tolerance) * 20.0,
                    reason="discrimination",
                )
        return {"famine": famine, "tax_rate": tax_rate, "at_war": at_war}

    def _try_reform(self, settlement, faction, policy_service, cycle):
        institution = self.institution
        legitimacy = float(institution.state.get("legitimacy", 0.0))
        if legitimacy < float(
            self.settings.get("reform_min_legitimacy", 60.0)
        ):
            return False
        objective = str(faction.get("objective", ""))
        for policy_id, definition in sorted(policy_service.definitions.items()):
            if objective not in {
                str(value) for value in definition.get("supports", ())
            }:
                continue
            proposal = policy_service.propose(
                policy_id,
                faction["faction_id"],
                cycle=cycle,
            )
            resolved = policy_service.resolve(
                proposal["proposal_id"],
                cycle=cycle,
            )
            if resolved.get("status") == "enacted":
                return True
        return False

    def _outcome(self, settlement, faction, pressures, policy_service, cycle):
        dissatisfaction = 100.0 - float(faction.get("satisfaction", 0.0))
        revolt = float(self.settings.get("revolt_threshold", 90.0))
        sabotage = float(self.settings.get("sabotage_threshold", 75.0))
        if dissatisfaction > revolt:
            if (
                pressures["famine"]
                and self._try_reform(
                    settlement,
                    faction,
                    policy_service,
                    cycle,
                )
            ):
                return "reform"
            military = (
                faction.get("kind") == "profession"
                and str(faction.get("key", "")).lower()
                in {"soldier", "military"}
            )
            influence = float(faction.get("influence", 0.0))
            capability = float(
                self.settings.get("coup_min_influence", 60.0)
            )
            if military and influence >= capability:
                return "coup"
            if influence >= capability:
                return "revolt"
            return "exodus"
        if (
            dissatisfaction > sabotage
            and float(faction.get("influence", 0.0))
            >= float(self.settings.get("sabotage_min_influence", 30.0))
        ):
            return "sabotage"
        return "protest"

    def _new_conflict(
        self,
        settlement,
        faction,
        kind,
        *,
        cycle,
        state,
    ):
        conflict_id = int(state.get("next_conflict_id", 1))
        state["next_conflict_id"] = conflict_id + 1
        conflict = {
            "conflict_id": conflict_id,
            "settlement_id": int(settlement.entity_id),
            "faction_id": int(faction["faction_id"]),
            "kind": str(kind),
            "cycle": int(cycle),
            "satisfaction": float(faction.get("satisfaction", 0.0)),
            "influence": float(faction.get("influence", 0.0)),
            "response": None,
            "response_cycle": None,
        }
        state["conflicts"].append(conflict)
        limit = max(1, int(self.settings.get("conflict_limit", 256)))
        overflow = len(state["conflicts"]) - limit
        if overflow > 0:
            del state["conflicts"][:overflow]
        metric = {
            "protest": "protests",
            "sabotage": "sabotage",
            "coup": "coups",
            "revolt": "revolts",
            "reform": "reforms",
            "exodus": "exodus",
        }[str(kind)]
        from core.simulation_metrics import SimulationMetrics
        SimulationMetrics(self.world).record_politics(metric)
        from core.logger import GameLogger
        from core.translator import Translator
        GameLogger.log(
            Translator.translate(
                "events.politics_conflict",
                settlement=settlement.name,
                faction=faction.get("key", faction["faction_id"]),
                kind=Translator.translate(
                    f"events.politics_conflict_{kind}"
                ),
            ),
            category="politics", entity_ids=[settlement.entity_id],
            position=settlement.pos,
        )
        return conflict

    def _apply_conflict(self, settlement, faction, conflict):
        kind = conflict["kind"]
        institution = self.institution
        legitimacy = float(institution.state.get("legitimacy", 0.0))
        if kind == "protest":
            institution.state["legitimacy"] = _bounded(legitimacy - 3.0)
        elif kind == "sabotage":
            loss = min(
                max(0.0, float(settlement.food_stock)),
                float(self.settings.get("sabotage_food_loss", 10.0)),
            )
            settlement.food_stock = round(float(settlement.food_stock) - loss, 6)
            conflict["food_lost"] = round(loss, 6)
            institution.state["legitimacy"] = _bounded(legitimacy - 5.0)
        elif kind in {"coup", "revolt"}:
            penalty = 15.0 if kind == "coup" else 20.0
            institution.state["legitimacy"] = _bounded(legitimacy - penalty)
            head_id = str(institution.government.get("head_office", ""))
            if (
                head_id in institution.state.get("offices", {})
                and institution.state["offices"][head_id].get("holder_id")
                is not None
            ):
                institution.vacate(head_id)
        elif kind == "exodus":
            amount = max(
                1.0,
                (100.0 - float(faction["satisfaction"])) / 10.0,
            )
            state = ensure_settlement_politics(
                self.world,
                settlement.entity_id,
            )
            state["migration_pressure"] = round(
                float(state.get("migration_pressure", 0.0)) + amount,
                6,
            )
            conflict["migration_pressure"] = round(amount, 6)
        elif kind == "reform":
            self.registry.adjust_satisfaction(
                faction["faction_id"],
                20.0,
                reason="reform",
            )
            institution.state["legitimacy"] = _bounded(legitimacy + 5.0)

    def _collect_taxes(self, settlement, tax_rate, state):
        if tax_rate <= 0:
            return 0.0
        population = sum(
            not getattr(person, "is_dead", False)
            for person in getattr(settlement, "citizens", ())
        )
        amount = round(population * float(tax_rate), 6)
        economy = getattr(settlement, "economy", None)
        if isinstance(economy, dict):
            economy["treasury"] = round(
                float(economy.get("treasury", 0.0)) + amount,
                6,
            )
        state["taxes_collected"] = round(
            float(state.get("taxes_collected", 0.0)) + amount,
            6,
        )
        from core.simulation_metrics import SimulationMetrics
        SimulationMetrics(self.world).record_politics("taxes", amount)
        return amount

    def advance(self, *, cycle=None):
        if not self.enabled:
            return {
                "new_conflicts": [],
                "settlements": 0,
            }
        current_cycle = int(
            self.world.get("cycle", 0) if cycle is None else cycle
        )
        interval = max(1, int(self.settings.get("advance_interval", 12)))
        new_conflicts = []
        processed = 0
        latest_result = {
            "new_conflicts": new_conflicts,
            "settlements": 0,
        }
        for settlement in self.world.get("entities", ()):
            if not _is_settlement(settlement):
                continue
            state = ensure_settlement_politics(
                self.world,
                settlement.entity_id,
            )
            if state.get("last_advanced_cycle") == current_cycle:
                continue
            factions = self.sync(settlement)
            state["last_advanced_cycle"] = current_cycle
            if current_cycle % interval != 0:
                continue
            institution, policies = self._services(settlement)
            institution.advance(cycle=current_cycle)
            policies.advance(cycle=current_cycle)
            pressures = self._apply_pressures(settlement, factions)
            self._collect_taxes(settlement, pressures["tax_rate"], state)
            cooldown = max(
                1,
                int(self.settings.get("conflict_cooldown", interval)),
            )
            for faction in self.registry.query(
                settlement_id=settlement.entity_id,
                active=True,
            ):
                dissatisfaction = 100.0 - float(faction["satisfaction"])
                if dissatisfaction < float(
                    self.settings.get("protest_threshold", 50.0)
                ):
                    continue
                if (
                    faction.get("last_conflict_cycle") is not None
                    and current_cycle - int(faction["last_conflict_cycle"])
                    < cooldown
                ):
                    continue
                kind = self._outcome(
                    settlement,
                    faction,
                    pressures,
                    policies,
                    current_cycle,
                )
                conflict = self._new_conflict(
                    settlement,
                    faction,
                    kind,
                    cycle=current_cycle,
                    state=state,
                )
                self._apply_conflict(settlement, faction, conflict)
                stored = self.registry._find(faction["faction_id"])
                stored["last_conflict_cycle"] = current_cycle
                new_conflicts.append(deepcopy(conflict))
            state["last_advanced_cycle"] = current_cycle
            processed += 1
            latest_result = {
                "new_conflicts": new_conflicts,
                "settlements": processed,
                "institution": institution.snapshot(),
                "migration_pressure": float(
                    state.get("migration_pressure", 0.0)
                ),
                "taxes_collected": float(
                    state.get("taxes_collected", 0.0)
                ),
            }
        return latest_result

    def respond(self, conflict_id, response, *, cycle=None):
        allowed = {"negotiate", "repress", "reform"}
        if response not in allowed:
            raise ValueError("unknown_conflict_response")
        wanted = int(conflict_id)
        for settlement_id, state in self.registry.storage["settlements"].items():
            for conflict in state.get("conflicts", ()):
                if int(conflict.get("conflict_id", 0)) != wanted:
                    continue
                faction_id = int(conflict["faction_id"])
                institution = self.institutions.get(int(settlement_id))
                if institution is None:
                    settlement = next(
                        entity
                        for entity in self.world.get("entities", ())
                        if int(getattr(entity, "entity_id", 0))
                        == int(settlement_id)
                    )
                    institution, _ = self._services(settlement)
                if response == "negotiate":
                    self.registry.adjust_satisfaction(
                        faction_id,
                        20.0,
                        reason="negotiation",
                    )
                    institution.state["legitimacy"] = _bounded(
                        institution.state["legitimacy"] + 2.0
                    )
                elif response == "repress":
                    self.registry.adjust_satisfaction(
                        faction_id,
                        -15.0,
                        reason="repression",
                    )
                    institution.state["legitimacy"] = _bounded(
                        institution.state["legitimacy"] - 10.0
                    )
                    faction = self.registry._find(faction_id)
                    faction["influence"] = _bounded(
                        float(faction.get("influence", 0.0)) - 10.0
                    )
                else:
                    self.registry.adjust_satisfaction(
                        faction_id,
                        25.0,
                        reason="reform_response",
                    )
                    institution.state["legitimacy"] = _bounded(
                        institution.state["legitimacy"] + 5.0
                    )
                conflict["response"] = response
                conflict["response_cycle"] = int(
                    self.world.get("cycle", 0) if cycle is None else cycle
                )
                from core.simulation_metrics import SimulationMetrics
                from core.logger import GameLogger
                from core.translator import Translator
                GameLogger.log(
                    Translator.translate(
                        "events.politics_response",
                        settlement=next(
                            entity.name for entity in self.world.get("entities", ())
                            if int(getattr(entity, "entity_id", 0)) == int(settlement_id)
                        ),
                        response=Translator.translate(
                            f"events.politics_response_{response}"
                        ),
                    ),
                    category="politics", entity_ids=[int(settlement_id)],
                )
                SimulationMetrics(self.world).record_politics("responses")
                return deepcopy(conflict)
        raise KeyError(wanted)


def world_political_summary(world, config):
    """Return a defensive aggregate without creating political state."""
    enabled = politics_enabled(config)
    politics = world.get("politics", {})
    settlements = politics.get("settlements", {}) if isinstance(politics, dict) else {}
    empty = {
        "enabled": enabled,
        "settlements": 0,
        "factions": 0,
        "active_policies": 0,
        "conflicts": 0,
        "vacancies": 0,
        "average_legitimacy": 0.0,
        "taxes_collected": 0.0,
        "migration_pressure": 0.0,
    }
    if not enabled or not isinstance(settlements, dict):
        return empty
    factions = conflicts = active_policies = vacancies = 0
    taxes = migration = 0.0
    legitimacies = []
    for state in settlements.values():
        if not isinstance(state, dict):
            continue
        settlement_factions = state.get("factions", ())
        if isinstance(settlement_factions, dict):
            settlement_factions = settlement_factions.values()
        factions += sum(
            isinstance(faction, dict) and faction.get("active", True)
            for faction in settlement_factions
        )
        conflicts += len(state.get("conflicts", ()))
        taxes += float(state.get("taxes_collected", 0.0))
        migration += float(state.get("migration_pressure", 0.0))
        institution = state.get("institution", {})
        if not isinstance(institution, dict):
            continue
        legitimacy = institution.get("legitimacy")
        if isinstance(legitimacy, (int, float)) and not isinstance(legitimacy, bool):
            legitimacies.append(float(legitimacy))
        active_policies += len(institution.get("active_policies", ()))
        offices = institution.get("offices", {})
        if isinstance(offices, dict):
            vacancies += sum(
                isinstance(office, dict) and office.get("holder_id") is None
                for office in offices.values()
            )
    return {
        "enabled": True,
        "settlements": len(settlements),
        "factions": factions,
        "active_policies": active_policies,
        "conflicts": conflicts,
        "vacancies": vacancies,
        "average_legitimacy": round(sum(legitimacies) / len(legitimacies), 6)
        if legitimacies else 0.0,
        "taxes_collected": round(taxes, 6),
        "migration_pressure": round(migration, 6),
    }

