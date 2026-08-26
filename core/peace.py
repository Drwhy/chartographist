"""Traites causaux et consequences persistantes de l'apres-guerre."""

from copy import deepcopy
import math

from core.diplomacy import DiplomacyRegistry
from core.chronicles import ChronicleBook


class PeaceSystem:
    """Applique une paix concrete a partir du bilan d'une campagne."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("peace", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.config = config if isinstance(config, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if self.enabled:
            state = world.get("peace")
            if not isinstance(state, dict):
                world["peace"] = {
                    "version": 1,
                    "next_treaty_id": 1,
                    "treaties": [],
                    "debts": [],
                    "veterans": {},
                    "refugees": 0,
                    "ruins": 0,
                }

    @property
    def state(self):
        return self.world.get("peace")

    def conclude(self, campaign):
        if not self.enabled:
            return None
        campaign_id = int(campaign["campaign_id"])
        existing = next(
            (
                treaty
                for treaty in self.state["treaties"]
                if int(treaty["campaign_id"]) == campaign_id
            ),
            None,
        )
        if existing is not None:
            return deepcopy(existing)

        winner_id = campaign.get("winner_id")
        if winner_id is None:
            return None
        winner_id = int(winner_id)
        participants = {
            int(campaign["attacker_id"]),
            int(campaign["defender_id"]),
        }
        loser_id = next(identifier for identifier in participants if identifier != winner_id)
        winner = self._settlement(winner_id)
        loser = self._settlement(loser_id)
        if winner is None or loser is None:
            return None

        relation = DiplomacyRegistry(self.world).get(winner_id, loser_id)
        if relation is not None and relation["status"] == "war":
            DiplomacyRegistry(self.world).transition(
                winner_id,
                loser_id,
                "truce",
                reason=str(campaign.get("end_reason", "peace")),
                truce_duration=12,
            )

        territory_tiles = self._transfer_territory(
            winner_id,
            loser_id,
            campaign,
        )
        tribute, debt = self._transfer_tribute(winner, loser)
        hostages = max(0, int(campaign.get("costs", {}).get("prisoners", 0)))
        commercial_rights = max(
            0.0, float(self.settings.get("commercial_rights", 0.0))
        )
        postwar_tension = max(
            0.0, float(self.settings.get("postwar_tension", 0.0))
        )
        DiplomacyRegistry(self.world).adjust(
            winner_id,
            loser_id,
            interdependence=commercial_rights,
            tension=postwar_tension,
            reason="postwar_settlement",
        )

        veterans = {
            str(int(army["settlement_id"])): max(0, int(army.get("strength", 0)))
            for army in campaign.get("armies", {}).values()
            if isinstance(army, dict)
        }
        refugees = math.ceil(
            max(0, int(campaign.get("costs", {}).get("casualties", 0)))
            * min(1.0, max(0.0, float(self.settings.get("refugee_rate", 0.0))))
        )
        ruins = (
            1
            if campaign.get("end_reason") == "military_defeat"
            or any(
                occupation.get("campaign_id") == campaign_id
                for occupation in self.world.get("warfare", {}).get("occupations", ())
            )
            else 0
        )
        consequences = {
            "veterans": veterans,
            "refugees": refugees,
            "debt": round(debt, 6),
            "ruins": ruins,
            "grievance": "postwar_settlement",
        }
        treaty = {
            "treaty_id": int(self.state["next_treaty_id"]),
            "campaign_id": campaign_id,
            "cycle": int(self.world.get("cycle", 0)),
            "winner_id": winner_id,
            "loser_id": loser_id,
            "cause": str(campaign.get("cause", "")),
            "objective": str(campaign.get("objective", "")),
            "end_reason": str(campaign.get("end_reason", "")),
            "war_costs": deepcopy(campaign.get("costs", {})),
            "terms": {
                "territory": territory_tiles,
                "tribute_food": round(tribute, 6),
                "hostages": hostages,
                "commercial_rights": commercial_rights,
            },
            "consequences": consequences,
        }
        history = self.config.get("history", {})
        if isinstance(history, dict) and history.get("enabled") is True:
            entry = ChronicleBook(self.world, self.config).record(
                None,
                cycle=treaty["cycle"],
                year=treaty["cycle"] // 12,
                month=(treaty["cycle"] % 12) + 1,
                category="peace",
                event_type="peace_treaty",
                actors=[
                    {"entity_id": winner_id, "role": "winner"},
                    {"entity_id": loser_id, "role": "loser"},
                ],
                objects=[{
                    "object_id": f"treaty:{treaty['treaty_id']}",
                    "role": "treaty",
                }],
                causes=[{"kind": treaty["end_reason"]}],
                consequences=[
                    {"kind": "settlement", **deepcopy(consequences)},
                ],
                facts={
                    "treaty_id": treaty["treaty_id"],
                    "campaign_id": campaign_id,
                    "terms": deepcopy(treaty["terms"]),
                },
                caused_by=[campaign.get("end_chronicle_id")],
                text_key="events.peace_treaty",
                text_args={
                    "winner": getattr(winner, "name", winner_id),
                    "loser": getattr(loser, "name", loser_id),
                },
            )
            if entry is not None:
                treaty["chronicle_id"] = entry["chronicle_id"]
        self.state["next_treaty_id"] += 1
        self.state["treaties"].append(treaty)
        maximum = max(1, int(self.settings.get("max_treaties", 64)))
        if len(self.state["treaties"]) > maximum:
            del self.state["treaties"][:-maximum]
        if debt > 0:
            self.state["debts"].append(
                {
                    "treaty_id": treaty["treaty_id"],
                    "debtor_id": loser_id,
                    "creditor_id": winner_id,
                    "food": round(debt, 6),
                }
            )
        for settlement_id, count in veterans.items():
            self.state["veterans"][settlement_id] = (
                self.state["veterans"].get(settlement_id, 0) + count
            )
        self.state["refugees"] += refugees
        self.state["ruins"] += ruins
        return deepcopy(treaty)

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        treaties = deepcopy(self.state.get("treaties", ()))
        return {
            "enabled": True,
            "treaties": len(treaties),
            "last_treaty": treaties[-1] if treaties else None,
            "debts": deepcopy(self.state.get("debts", ())),
            "veterans": deepcopy(self.state.get("veterans", {})),
            "refugees": int(self.state.get("refugees", 0)),
            "ruins": int(self.state.get("ruins", 0)),
        }

    def _transfer_territory(self, winner_id, loser_id, campaign):
        if self.settings.get("transfer_territory") is not True:
            return []
        territory = self.world.get("territory")
        if not isinstance(territory, dict):
            return []
        overrides = territory.setdefault("treaty_overrides", {})
        transferred = []
        pair = {winner_id, loser_id}
        for key, tile in sorted(territory.get("tiles", {}).items()):
            claimants = {
                int(claim.get("settlement_id"))
                for claim in tile.get("claimants", ())
                if isinstance(claim, dict) and claim.get("settlement_id") is not None
            }
            if not tile.get("contested") or not pair <= claimants:
                continue
            tile["owner_id"] = winner_id
            tile["contested"] = False
            tile["treaty_id"] = int(self.state["next_treaty_id"])
            overrides[key] = winner_id
            transferred.append(key)
        territory["contested_tiles"] = sum(
            bool(tile.get("contested"))
            for tile in territory.get("tiles", {}).values()
        )
        territory["revision"] = int(territory.get("revision", 0)) + 1
        return transferred

    def _transfer_tribute(self, winner, loser):
        ratio = max(0.0, float(self.settings.get("tribute_food_ratio", 0.0)))
        base = max(0.0, float(self.settings.get("tribute_base", 0.0)))
        target = max(base, max(0.0, float(loser.food_stock)) * ratio)
        paid = min(max(0.0, float(loser.food_stock)), target)
        loser.food_stock -= paid
        winner.food_stock += paid
        return paid, max(0.0, target - paid)

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

