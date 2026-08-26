"""Guerres causales, armees et logistique deterministes."""

from copy import deepcopy
import math

from core.chronicles import ChronicleBook
from core.diplomacy import DiplomacyRegistry
from core.pathfinding import PathfindingService


class WarfareSystem:
    """Suit le cout, le ravitaillement et l'issue de campagnes explicables."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("warfare", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.config = config if isinstance(config, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if self.enabled:
            state = world.get("warfare")
            if not isinstance(state, dict):
                world["warfare"] = {
                    "version": 1,
                    "next_campaign_id": 1,
                    "last_advanced_cycle": None,
                    "campaigns": [],
                    "history": [],
                    "occupations": [],
                    "total_casualties": 0,
                    "total_prisoners": 0,
                    "total_supply_consumed": 0.0,
                }

    @property
    def state(self):
        return self.world.get("warfare")

    def declare_war(self, attacker_id, defender_id, *, cause, objective, evidence=None):
        if not self.enabled:
            raise RuntimeError("warfare is disabled")
        if not str(cause) or not str(objective):
            raise ValueError("war requires a cause and an objective")
        registry = DiplomacyRegistry(self.world)
        relation = registry.get_or_create(attacker_id, defender_id)
        if relation["status"] != "war":
            registry.transition(
                attacker_id,
                defender_id,
                "war",
                reason=str(cause),
            )
        existing = self._campaign_for(attacker_id, defender_id)
        if existing is not None:
            return deepcopy(existing)
        campaign = self._new_campaign(
            int(attacker_id),
            int(defender_id),
            str(cause),
            str(objective),
            list(evidence or ()),
        )
        self.state["campaigns"].append(campaign)
        entry = self._record_campaign_event(campaign, "war_declared")
        if entry is not None:
            campaign["chronicle_id"] = entry["chronicle_id"]
        return deepcopy(campaign)

    def advance(self):
        if not self.enabled:
            return False
        cycle = int(self.world.get("cycle", 0))
        interval = max(1, int(self.settings.get("advance_interval", 1)))
        if self.state.get("last_advanced_cycle") == cycle or cycle % interval:
            return False

        self._discover_wars()
        self._auto_declare()
        changed = False
        for campaign in list(self.state["campaigns"]):
            if campaign["status"] != "active":
                continue
            self._advance_campaign(campaign)
            changed = True
        self.state["last_advanced_cycle"] = cycle
        return changed

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        active = [
            deepcopy(campaign)
            for campaign in self.state.get("campaigns", ())
            if campaign.get("status") == "active"
        ]
        ended = [deepcopy(campaign) for campaign in self.state.get("history", ())]
        return {
            "enabled": True,
            "active_campaigns": active,
            "ended_campaigns": ended,
            "occupations": deepcopy(self.state.get("occupations", ())),
            "total_casualties": int(self.state.get("total_casualties", 0)),
            "total_prisoners": int(self.state.get("total_prisoners", 0)),
            "total_supply_consumed": round(
                float(self.state.get("total_supply_consumed", 0.0)), 6
            ),
        }

    def _discover_wars(self):
        for relation in DiplomacyRegistry(self.world).query(status="war"):
            if self._campaign_for(relation["first_id"], relation["second_id"]):
                continue
            cause, objective, evidence = self._derive_objective(relation)
            campaign = self._new_campaign(
                relation["first_id"],
                relation["second_id"],
                cause,
                objective,
                evidence,
            )
            self.state["campaigns"].append(campaign)

            entry = self._record_campaign_event(campaign, "war_declared")
            if entry is not None:
                campaign["chronicle_id"] = entry["chronicle_id"]
    def _auto_declare(self):
        if self.settings.get("auto_declare") is not True:
            return
        threshold = float(self.settings.get("war_tension_threshold", 80.0))
        for relation in DiplomacyRegistry(self.world).query():
            if relation["status"] in {"war", "truce", "alliance"}:
                continue
            if float(relation.get("tension", 0.0)) < threshold:
                continue
            cause, objective, evidence = self._derive_objective(relation)
            self.declare_war(
                relation["first_id"],
                relation["second_id"],
                cause=cause,
                objective=objective,
                evidence=evidence,
            )

    def _derive_objective(self, relation):
        reason_kinds = [
            str(reason.get("kind", ""))
            for reason in relation.get("reasons", ())
            if isinstance(reason, dict)
        ]
        cause = reason_kinds[-1] if reason_kinds else "frontier_dispute"
        evidence = [f"diplomacy:{kind}" for kind in reason_kinds[-3:] if kind]
        pair = {int(relation["first_id"]), int(relation["second_id"])}
        if "territorial_dispute" in reason_kinds:
            cause = "territorial_dispute"
            territory = self.world.get("territory", {})
            for key, tile in sorted(territory.get("tiles", {}).items()):
                claimants = {
                    int(claim.get("settlement_id"))
                    for claim in tile.get("claimants", ())
                    if isinstance(claim, dict) and claim.get("settlement_id") is not None
                }
                if tile.get("contested") and pair <= claimants:
                    evidence.append(f"contested_tile:{key}")
                    resources = tile.get("strategic_resources", ())
                    if resources:
                        return (
                            cause,
                            f"control_resource:{sorted(map(str, resources))[0]}",
                            evidence,
                        )
            return cause, "secure_frontier", evidence
        if any(kind in {"raid", "casualties", "revenge"} for kind in reason_kinds):
            return "revenge", "punitive_raid", evidence
        if any("relig" in kind for kind in reason_kinds):
            return "religion", "enforce_faith", evidence
        if any("succession" in kind for kind in reason_kinds):
            return "succession", "install_claimant", evidence
        return cause, "secure_frontier", evidence
    def _record_campaign_event(self, campaign, event_type, caused_by=None):
        history = self.config.get("history", {})
        if not isinstance(history, dict) or history.get("enabled") is not True:
            return None
        attacker = self._settlement(campaign["attacker_id"])
        defender = self._settlement(campaign["defender_id"])
        if attacker is None or defender is None:
            return None
        cycle = int(self.world.get("cycle", 0))
        text_key = "events.war_declared" if event_type == "war_declared" else "events.war_ended"
        text_args = {
            "attacker": getattr(attacker, "name", campaign["attacker_id"]),
            "defender": getattr(defender, "name", campaign["defender_id"]),
        }
        consequences = (
            [{"kind": "mobilization", "objective": campaign["objective"]}]
            if event_type == "war_declared"
            else [{
                "kind": str(campaign.get("end_reason", "peace")),
                "winner_id": campaign.get("winner_id"),
                "costs": deepcopy(campaign.get("costs", {})),
            }]
        )
        return ChronicleBook(self.world, self.config).record(
            None,
            cycle=cycle,
            year=cycle // 12,
            month=(cycle % 12) + 1,
            category="warfare",
            event_type=event_type,
            actors=[
                {"entity_id": campaign["attacker_id"], "role": "attacker"},
                {"entity_id": campaign["defender_id"], "role": "defender"},
            ],
            objects=[{
                "object_id": f"campaign:{campaign['campaign_id']}",
                "role": "campaign",
            }],
            locations=[
                {"location_id": f"tile:{attacker.pos[0]},{attacker.pos[1]}", "role": "attacker_home"},
                {"location_id": f"tile:{defender.pos[0]},{defender.pos[1]}", "role": "defender_home"},
            ],
            causes=[{
                "kind": str(campaign["cause"]),
                "evidence": list(campaign.get("evidence", ())),
            }],
            consequences=consequences,
            facts={
                "campaign_id": campaign["campaign_id"],
                "objective": campaign["objective"],
                "phase": campaign["phase"],
            },
            caused_by=caused_by,
            text_key=text_key,
            text_args=text_args,
        )


    def _new_campaign(self, attacker_id, defender_id, cause, objective, evidence):
        attacker = self._settlement(attacker_id)
        defender = self._settlement(defender_id)
        if attacker is None or defender is None:
            raise ValueError("war settlements must exist")
        campaign = {
            "campaign_id": int(self.state["next_campaign_id"]),
            "attacker_id": int(attacker_id),
            "defender_id": int(defender_id),
            "cause": cause,
            "objective": objective,
            "evidence": list(evidence),
            "status": "active",
            "phase": "mobilization",
            "started_cycle": int(self.world.get("cycle", 0)),
            "last_advanced_cycle": None,
            "armies": {
                str(attacker_id): self._mobilize(attacker, defender),
                str(defender_id): self._mobilize(defender, attacker),
            },
            "costs": {
                "food": 0.0,
                "casualties": 0,
                "prisoners": 0,
                "raided_food": 0.0,
            },
            "family_losses": {},
            "engagements": [],
        }
        self.state["next_campaign_id"] += 1
        return campaign

    def _mobilize(self, settlement, opponent):
        population = len(getattr(settlement, "citizens", ()))
        levy = max(
            int(self.settings.get("minimum_army", 1)),
            int(population * max(0.0, float(self.settings.get("levy_rate", 0.1)))),
        )
        strength = min(population, levy)
        return {
            "settlement_id": int(settlement.entity_id),
            "target_id": int(opponent.entity_id),
            "strength": strength,
            "initial_strength": strength,
            "morale": max(0.0, float(self.settings.get("initial_morale", 100.0))),
            "command": max(0.1, float(self.settings.get("command_base", 1.0))),
            "food": 0.0,
            "supplied": True,
            "supply_cost": None,
            "state": "marching",
        }

    def _advance_campaign(self, campaign):
        cycle = int(self.world.get("cycle", 0))
        for army in campaign["armies"].values():
            self._supply_army(campaign, army)

        collapsed = [
            army
            for army in campaign["armies"].values()
            if army["strength"] <= 0
            or army["morale"] <= float(self.settings.get("retreat_morale", 20.0))
        ]
        if collapsed:
            loser = min(collapsed, key=lambda army: army["settlement_id"])
            winner_id = next(
                (
                    army["settlement_id"]
                    for army in campaign["armies"].values()
                    if army["settlement_id"] != loser["settlement_id"]
                ),
                None,
            )
            loser["state"] = "retreat"
            self._end_campaign(
                campaign,
                winner_id,
                "supply_collapse",
            )
            return

        engagement_interval = max(
            1, int(self.settings.get("engagement_interval", 1))
        )
        elapsed = cycle - int(campaign["started_cycle"])
        if elapsed % engagement_interval == 0:
            self._resolve_engagement(campaign)
        campaign["last_advanced_cycle"] = cycle

    def _supply_army(self, campaign, army):
        home = self._settlement(army["settlement_id"])
        target = self._settlement(army["target_id"])
        if home is None or target is None:
            army["supplied"] = False
            return
        route = PathfindingService(self.world, self.config).find_path(
            home.pos,
            target.pos,
        )
        supply_cost = route["cost"] if route["reachable"] else None
        maximum = max(0.0, float(self.settings.get("max_supply_cost", 50.0)))
        army["supply_cost"] = supply_cost
        army["supplied"] = supply_cost is not None and supply_cost <= maximum
        demand = army["strength"] * max(
            0.0, float(self.settings.get("supply_per_soldier", 0.1))
        )
        if self.world.get("climate", {}).get("season") == "winter":
            demand *= max(
                1.0, float(self.settings.get("winter_supply_multiplier", 1.0))
            )
        delivered = min(max(0.0, float(home.food_stock)), demand) if army["supplied"] else 0.0
        home.food_stock -= delivered
        army["food"] = round(float(army.get("food", 0.0)) + delivered, 6)
        campaign["costs"]["food"] = round(campaign["costs"]["food"] + delivered, 6)
        self.state["total_supply_consumed"] += delivered
        if delivered + 1e-9 < demand:
            army["supplied"] = False
            army["morale"] = round(
                max(
                    0.0,
                    army["morale"]
                    - max(
                        0.0,
                        float(self.settings.get("unsupplied_morale_loss", 20.0)),
                    ),
                ),
                6,
            )
            attrition = min(
                army["strength"],
                max(
                    1,
                    math.ceil(
                        army["strength"]
                        * max(
                            0.0,
                            float(self.settings.get("unsupplied_attrition", 0.1)),
                        )
                    ),
                ),
            )
            self._apply_losses(campaign, army, attrition, prisoner_count=0)

    def _resolve_engagement(self, campaign):
        attacker = campaign["armies"][str(campaign["attacker_id"])]
        defender = campaign["armies"][str(campaign["defender_id"])]
        attacker_power = attacker["strength"] * attacker["morale"] * attacker["command"]
        defender_power = defender["strength"] * defender["morale"] * defender["command"]
        if attacker_power == defender_power:
            winner, loser = (
                (attacker, defender)
                if attacker["settlement_id"] < defender["settlement_id"]
                else (defender, attacker)
            )
        else:
            winner, loser = (
                (attacker, defender)
                if attacker_power > defender_power
                else (defender, attacker)
            )
        rate = min(1.0, max(0.0, float(self.settings.get("casualty_rate", 0.1))))
        loser_losses = min(loser["strength"], max(1, math.ceil(loser["strength"] * rate)))
        winner_losses = min(
            winner["strength"],
            max(0, math.floor(loser_losses * 0.5)),
        )
        prisoners = min(
            loser_losses,
            max(
                0,
                math.floor(
                    loser_losses
                    * max(0.0, float(self.settings.get("prisoner_rate", 0.0)))
                ),
            ),
        )
        self._apply_losses(campaign, loser, loser_losses, prisoners)
        self._apply_losses(campaign, winner, winner_losses, 0)
        loser["morale"] = round(max(0.0, loser["morale"] - loser_losses * 5.0), 6)
        campaign["phase"] = "siege" if loser["morale"] < 50 else "battle"
        if campaign["objective"] == "punitive_raid":
            settlement = self._settlement(loser["settlement_id"])
            raided = min(float(settlement.food_stock), float(loser_losses))
            settlement.food_stock -= raided
            campaign["costs"]["raided_food"] += raided
        campaign["engagements"].append(
            {
                "cycle": int(self.world.get("cycle", 0)),
                "winner_id": winner["settlement_id"],
                "loser_id": loser["settlement_id"],
                "winner_losses": winner_losses,
                "loser_losses": loser_losses,
                "prisoners": prisoners,
            }
        )
        from core.sites import SiteRegistry
        battlefield = SiteRegistry(self.world, self.config).create(
            "battlefield",
            list(self._settlement(loser["settlement_id"]).pos),
            founder_ids=[
                campaign["attacker_id"],
                campaign["defender_id"],
            ],
            origin_chronicle_id=campaign.get("chronicle_id"),
            facts={"campaign_id": campaign["campaign_id"]},
        )
        if battlefield is not None:
            battlefield = SiteRegistry(self.world, self.config).record_event(
                battlefield["site_id"],
                "battle_fought",
                owner_ids=[winner["settlement_id"]],
                resource_changes={
                    "relics": winner_losses + loser_losses,
                },
                actor_ids=[
                    winner["settlement_id"],
                    loser["settlement_id"],
                ],
                facts={
                    "campaign_id": campaign["campaign_id"],
                    "casualties": winner_losses + loser_losses,
                },
                caused_by=[campaign.get("chronicle_id")],
            )
            campaign["engagements"][-1]["site_id"] = battlefield["site_id"]
        from core.artifacts import ArtifactRegistry
        artifacts = ArtifactRegistry(self.world, self.config)
        loot_limit = artifacts._positive_int("loot_per_engagement", 1)
        looted_ids = []
        for artifact in artifacts.query(
            holder_id=loser["settlement_id"],
            status="active",
        )[:loot_limit]:
            transferred = artifacts.transfer(
                artifact["artifact_id"],
                "loot",
                "settlement",
                winner["settlement_id"],
                location=list(self._settlement(winner["settlement_id"]).pos),
                actor_ids=[
                    winner["settlement_id"],
                    loser["settlement_id"],
                ],
                facts={"campaign_id": campaign["campaign_id"]},
                caused_by=[campaign.get("chronicle_id")],
            )
            if transferred is not None:
                looted_ids.append(transferred["artifact_id"])
        if looted_ids:
            campaign["engagements"][-1]["artifact_ids"] = looted_ids
        if loser["strength"] <= 0:
            loser["state"] = "defeated"
            self.state["occupations"].append(
                {
                    "campaign_id": campaign["campaign_id"],
                    "occupier_id": winner["settlement_id"],
                    "settlement_id": loser["settlement_id"],
                    "cycle": int(self.world.get("cycle", 0)),
                }
            )
            self._end_campaign(campaign, winner["settlement_id"], "military_defeat")

    def _apply_losses(self, campaign, army, count, prisoner_count):
        count = min(max(0, int(count)), int(army["strength"]))
        if count <= 0:
            return
        army["strength"] -= count
        settlement = self._settlement(army["settlement_id"])
        people = sorted(
            getattr(settlement, "citizens", ()),
            key=lambda person: (
                self._is_notable(person),
                int(getattr(person, "entity_id", 0)),
            ),
        )[:count]
        lost_ids = {int(getattr(person, "entity_id", 0)) for person in people}
        families = {}
        for person in people:
            person.is_dead = True
            family = str(getattr(person, "family_name", "") or "")
            if family:
                families[family] = families.get(family, 0) + 1
        settlement.citizens = [
            person
            for person in settlement.citizens
            if int(getattr(person, "entity_id", 0)) not in lost_ids
        ]
        family_state = campaign["family_losses"].setdefault(
            str(army["settlement_id"]), {}
        )
        for family, losses in families.items():
            family_state[family] = family_state.get(family, 0) + losses
        campaign["costs"]["casualties"] += count
        campaign["costs"]["prisoners"] += prisoner_count
        self.state["total_casualties"] += count
        self.state["total_prisoners"] += prisoner_count
        politics = self.world.get("politics", {}).get("settlements", {})
        political = politics.get(str(army["settlement_id"]), {})
        institution = political.get("institution", {})
        if isinstance(institution, dict) and "legitimacy" in institution:
            institution["legitimacy"] = round(
                max(0.0, float(institution["legitimacy"]) - count),
                6,
            )

    def _end_campaign(self, campaign, winner_id, reason):
        campaign["status"] = "ended"
        campaign["phase"] = "peace"
        campaign["winner_id"] = winner_id
        campaign["end_reason"] = str(reason)
        campaign["ended_cycle"] = int(self.world.get("cycle", 0))
        registry = DiplomacyRegistry(self.world)
        relation = registry.get(campaign["attacker_id"], campaign["defender_id"])
        if relation is not None and relation["status"] == "war":
            registry.transition(
                campaign["attacker_id"],
                campaign["defender_id"],
                "truce",
                reason=str(reason),
                truce_duration=max(
                    1, int(self.settings.get("truce_duration", 12))
                ),
            )
        entry = self._record_campaign_event(
            campaign, "war_ended", [campaign.get("chronicle_id")]
        )
        if entry is not None:
            campaign["end_chronicle_id"] = entry["chronicle_id"]
        self.state["history"].append(deepcopy(campaign))
        limit = max(1, int(self.settings.get("max_history", 64)))
        if len(self.state["history"]) > limit:
            del self.state["history"][:-limit]
        from core.peace import PeaceSystem
        PeaceSystem(self.world, self.config).conclude(campaign)

    def _campaign_for(self, first_id, second_id):
        pair = {int(first_id), int(second_id)}
        return next(
            (
                campaign
                for campaign in self.state.get("campaigns", ())
                if campaign.get("status") == "active"
                and {
                    int(campaign["attacker_id"]),
                    int(campaign["defender_id"]),
                }
                == pair
            ),
            None,
        )

    def _settlement(self, entity_id):
        return next(
            (
                entity
                for entity in self.world.get("entities", ())
                if int(getattr(entity, "entity_id", -1)) == int(entity_id)
                and hasattr(entity, "citizens")
                and not getattr(entity, "is_expired", False)
            ),
            None,
        )

    @staticmethod
    def _is_notable(person):
        character = getattr(person, "character", None)
        notability = (
            character.get("notability", {}) if isinstance(character, dict) else {}
        )
        return isinstance(notability, dict) and notability.get("is_notable") is True

