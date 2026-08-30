"""Vues de lecture stables pour inspecter les entités d'un monde."""

from copy import deepcopy

from core.chronicles import ChronicleBook
from core.economy import economy_snapshot


_SNAPSHOT_FIELDS = (
    "name",
    "char",
    "speed",
    "age",
    "sex",
    "health",
    "energy",
    "species",
    "food_stock",
    "max_food",
)


def inspect_entity(world, entity_id):
    """Renvoie un instantané d'entité et ses chroniques, ou ``None``."""
    entity = None
    owner = None
    for candidate in world.get("entities", ()):
        if getattr(candidate, "entity_id", None) == entity_id:
            entity = candidate
            break
        for citizen in getattr(candidate, "citizens", ()):
            if getattr(citizen, "entity_id", None) == entity_id:
                entity = citizen
                owner = candidate
                break
        if entity is not None:
            break
    if entity is None:
        return None

    snapshot = {
        "entity_id": entity.entity_id,
        "type": type(entity).__name__,
        "position": list(entity.pos),
        "is_expired": bool(getattr(entity, "is_expired", False)),
    }
    for field in _SNAPSHOT_FIELDS:
        if hasattr(entity, field):
            snapshot[field] = deepcopy(getattr(entity, field))

    stockpile = getattr(entity, "stockpile", None)
    if isinstance(stockpile, dict):
        snapshot["stockpile"] = deepcopy(stockpile)
    production = getattr(entity, "production", None)
    if isinstance(production, dict):
        snapshot["production"] = deepcopy(production)
    infrastructure = getattr(entity, "infrastructure", None)
    if isinstance(infrastructure, dict):
        snapshot["infrastructure"] = deepcopy(infrastructure)
    character = getattr(entity, "character", None)
    if isinstance(character, dict):
        snapshot["character"] = deepcopy(character)
    culture = getattr(entity, "culture", None)
    if isinstance(culture, dict):
        snapshot["culture"] = culture.get("name")
    citizens = getattr(entity, "citizens", None)
    if citizens is not None:
        snapshot["population"] = len(citizens)
    elif hasattr(entity, "population"):
        snapshot["population"] = int(entity.population)
    if hasattr(entity, "food_stock") and hasattr(entity, "max_food"):
        snapshot["economy"] = economy_snapshot(entity)

    from core.diplomacy import DiplomacyRegistry
    from core.knowledge import KnowledgeService

    config = getattr(entity, "config", {})
    knowledge = KnowledgeService(entity, config)

    result = {
        "entity": snapshot,
        "chronicles": ChronicleBook(world).query(entity_id=entity_id),
        "relationships": DiplomacyRegistry(world).query(entity_id=entity_id),
    }
    if knowledge.enabled or isinstance(getattr(entity, "knowledge", None), dict):
        result["knowledge"] = knowledge.snapshot()
    decision = getattr(entity, "knowledge_decision", None)
    if isinstance(decision, dict):
        result["knowledge_decision"] = deepcopy(decision)
    if owner is not None:
        result["owner_entity_id"] = int(owner.entity_id)
    if citizens is not None:
        from core.characters import cohort_snapshots
        result["cohorts"] = cohort_snapshots(entity)
    political_owner = owner if owner is not None else entity
    political_config = getattr(political_owner, "config", {})
    from core.factions import FactionRegistry
    factions = FactionRegistry(world, political_config)
    if factions.enabled:
        settlement_id = int(political_owner.entity_id)
        political_view = {
            "settlement_id": settlement_id,
            "factions": factions.query(settlement_id=settlement_id),
        }
        if owner is not None:
            political_view["memberships"] = factions.query(
                settlement_id=settlement_id,
                member_id=entity.entity_id,
            )
        from core.institutions import InstitutionService, PolicyService
        institution = InstitutionService(world, political_config, political_owner)
        policies = PolicyService(world, political_config, political_owner)
        political_view["institution"] = institution.snapshot()
        political_view["active_policies"] = policies.snapshot()[
            "active_policies"
        ]
        result["politics"] = political_view
    from core.territory import TerritorySystem
    territory = TerritorySystem(world, political_config)
    if territory.enabled:
        settlement_id = int(political_owner.entity_id)
        tiles = territory.state.get("tiles", {}).values()
        result["territory"] = {
            "settlement_id": settlement_id,
            "owned_tiles": sum(
                tile.get("owner_id") == settlement_id for tile in tiles
            ),
            "contested_tiles": sum(
                tile.get("contested")
                and any(
                    claim.get("settlement_id") == settlement_id
                    for claim in tile.get("claimants", ())
                )
                for tile in tiles
            ),
        }
    from core.migration import MigrationSystem
    migration = MigrationSystem(world, political_config)
    if migration.enabled:
        settlement_id = int(political_owner.entity_id)
        diaspora = migration.state.get("diasporas", {}).get(str(settlement_id), {})
        residents = getattr(political_owner, "citizens", ())
        result["migration"] = {
            "settlement_id": settlement_id,
            "diasporas": deepcopy(diaspora),
            "migrant_residents": sum(
                getattr(person, "migrant_origin_id", None) not in (None, settlement_id)
                for person in residents
            ),
            "recent_cohorts": [
                deepcopy(cohort)
                for cohort in migration.state.get("cohorts", ())
                if settlement_id in (
                    cohort.get("origin_id"),
                    cohort.get("destination_id"),
                )
            ],
        }
    from core.warfare import WarfareSystem
    warfare = WarfareSystem(world, political_config)
    if warfare.enabled:
        settlement_id = int(political_owner.entity_id)
        campaigns = [
            campaign
            for campaign in warfare.state.get("campaigns", ())
            if settlement_id in (
                campaign.get("attacker_id"),
                campaign.get("defender_id"),
            )
        ]
        result["warfare"] = {
            "settlement_id": settlement_id,
            "campaigns": deepcopy(campaigns),
            "occupations": [
                deepcopy(occupation)
                for occupation in warfare.state.get("occupations", ())
                if settlement_id in (
                    occupation.get("occupier_id"),
                    occupation.get("settlement_id"),
                )
            ],
        }
    from core.peace import PeaceSystem
    peace = PeaceSystem(world, political_config)
    if peace.enabled:
        settlement_id = int(political_owner.entity_id)
        result["peace"] = {
            "settlement_id": settlement_id,
            "treaties": [
                deepcopy(treaty)
                for treaty in peace.state.get("treaties", ())
                if settlement_id in (
                    treaty.get("winner_id"),
                    treaty.get("loser_id"),
                )
            ],
            "debts": [
                deepcopy(debt)
                for debt in peace.state.get("debts", ())
                if settlement_id in (
                    debt.get("debtor_id"),
                    debt.get("creditor_id"),
                )
            ],
            "veterans": int(
                peace.state.get("veterans", {}).get(str(settlement_id), 0)
            ),
        }
    from core.artifacts import ArtifactRegistry
    artifacts = ArtifactRegistry(world, political_config)
    if artifacts.enabled:
        result["artifacts"] = {
            "held": artifacts.query(holder_id=entity.entity_id),
            "created": artifacts.query(creator_id=entity.entity_id),
            "prestige_bonus": artifacts.prestige_bonus(entity.entity_id),
        }
    return result