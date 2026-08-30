"""Persistent settlement infrastructures assembled from conserved material kits."""

from copy import deepcopy

from core.materials import runtime_catalog


_INFRASTRUCTURE_VERSION = 2


def _empty_state():
    return {
        "version": _INFRASTRUCTURE_VERSION,
        "levels": {},
        "conditions": {},
        "last_install_cycle": None,
        "last_maintenance_cycle": None,
    }


def ensure_infrastructure_state(settlement, definitions):
    state = getattr(settlement, "infrastructure", None)
    if not isinstance(state, dict):
        state = _empty_state()
        settlement.infrastructure = state
    state["version"] = _INFRASTRUCTURE_VERSION
    raw_levels = state.get("levels")
    if not isinstance(raw_levels, dict):
        raw_levels = {}
    raw_conditions = state.get("conditions")
    if not isinstance(raw_conditions, dict):
        raw_conditions = {}
    levels = {}
    conditions = {}
    for identifier, definition in definitions.items():
        value = raw_levels.get(identifier, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = 0
        levels[identifier] = min(
            int(definition["max_level"]),
            max(0, int(value)),
        )
        default_condition = 100.0 if levels[identifier] > 0 else 0.0
        condition = raw_conditions.get(identifier, default_condition)
        if isinstance(condition, bool) or not isinstance(condition, (int, float)):
            condition = default_condition
        conditions[identifier] = round(
            min(100.0, max(0.0, float(condition))),
            6,
        )
    state["levels"] = levels
    state["conditions"] = conditions
    state.setdefault("last_install_cycle", None)
    state.setdefault("last_maintenance_cycle", None)
    return state



class InfrastructureService:
    """Install configured infrastructure levels without creating material."""

    def __init__(self, settlement, config):
        self.settlement = settlement
        self.config = config if isinstance(config, dict) else {}
        self.catalog = runtime_catalog(self.config)
        raw_definitions = self.catalog.definition.get("infrastructures", [])
        self.definitions = {
            str(definition["id"]): deepcopy(definition)
            for definition in raw_definitions
            if isinstance(definition, dict) and definition.get("id")
        }
        self.enabled = self.catalog.enabled and bool(self.definitions)
        self.state = (
            ensure_infrastructure_state(settlement, self.definitions)
            if self.enabled
            else _empty_state()
        )

    def snapshot(self):
        return deepcopy(self.state)

    def level(self, infrastructure_id):
        return max(
            0,
            int(self.state["levels"].get(str(infrastructure_id), 0)),
        )

    def condition(self, infrastructure_id):
        return round(
            min(
                100.0,
                max(0.0, float(self.state["conditions"].get(str(infrastructure_id), 0.0))),
            ),
            6,
        )

    def effect(self, effect_id):
        """Aggregate one configured effect across levels and condition."""
        identifier = str(effect_id)
        total = 0.0
        for infrastructure_id, definition in sorted(self.definitions.items()):
            effects = definition.get("effects", {})
            if not isinstance(effects, dict):
                continue
            value = effects.get(identifier, 0.0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            total += (
                self.level(infrastructure_id)
                * self.condition(infrastructure_id)
                / 100.0
                * float(value)
            )
        return round(max(0.0, total), 6)

    def damage(self, infrastructure_id, amount):
        identifier = str(infrastructure_id)
        if not self.enabled or self.level(identifier) <= 0:
            return 0.0
        quantity = max(0.0, float(amount))
        previous = self.condition(identifier)
        current = round(max(0.0, previous - quantity), 6)
        self.state["conditions"][identifier] = current
        from core.stockpiles import StockpileService
        StockpileService(self.settlement, self.config).refresh_capacity()
        return round(previous - current, 6)

    def maintain(self, *, cycle):
        if not self.enabled:
            return {}
        current_cycle = int(cycle)
        if self.state.get("last_maintenance_cycle") == current_cycle:
            return {}
        self.state["last_maintenance_cycle"] = current_cycle
        from core.stockpiles import StockpileService
        stockpile = StockpileService(self.settlement, self.config)
        repaired = {}
        for identifier, definition in sorted(self.definitions.items()):
            if self.level(identifier) <= 0 or self.condition(identifier) >= 100.0:
                continue
            maintenance = definition.get("maintenance", {})
            if not isinstance(maintenance, dict) or not maintenance:
                continue
            if any(
                stockpile.quantity(good_id) < float(quantity)
                for good_id, quantity in maintenance.items()
            ):
                continue
            for good_id, quantity in sorted(maintenance.items()):
                removed = stockpile.withdraw(good_id, quantity)
                if removed != float(quantity):
                    raise RuntimeError("infrastructure maintenance conservation failure")
            previous = self.condition(identifier)
            repair_amount = max(0.0, float(definition.get("repair_amount", 10.0)))
            current = round(min(100.0, previous + repair_amount), 6)
            self.state["conditions"][identifier] = current
            repaired[identifier] = round(current - previous, 6)
        if repaired:
            stockpile.refresh_capacity()
        return repaired

    def install_available(self, *, cycle):
        if not self.enabled:
            return {}
        current_cycle = int(cycle)
        if self.state.get("last_install_cycle") == current_cycle:
            return {}
        self.state["last_install_cycle"] = current_cycle

        from core.stockpiles import StockpileService

        stockpile = StockpileService(self.settlement, self.config)
        installed = {}
        for identifier, definition in sorted(self.definitions.items()):
            level = self.level(identifier)
            if level >= int(definition["max_level"]):
                continue
            kit_good_id = str(definition["kit_good_id"])
            if stockpile.quantity(kit_good_id) < 1.0:
                continue
            removed = stockpile.withdraw(kit_good_id, 1.0)
            if removed != 1.0:
                raise RuntimeError("infrastructure kit conservation failure")
            self.state["conditions"][identifier] = 100.0
            self.state["levels"][identifier] = level + 1
            installed[identifier] = 1
        if installed:
            stockpile.refresh_capacity()
        return installed


def damage_world_infrastructure(world, config, hazard, *, severity):
    """Apply configured deterministic hazard damage to live settlements."""
    hazard_id = str(hazard)
    pressure = min(1.0, max(0.0, float(severity)))
    if pressure <= 0:
        return {}
    damaged = {}
    entities = sorted(
        world.get("entities", ()),
        key=lambda entity: int(getattr(entity, "entity_id", 0)),
    )
    for settlement in entities:
        if getattr(settlement, "is_expired", False):
            continue
        service = InfrastructureService(settlement, config)
        if not service.enabled:
            continue
        settlement_damage = {}
        for identifier, definition in sorted(service.definitions.items()):
            hazards = definition.get("hazard_damage", {})
            rate = hazards.get(hazard_id, 0.0) if isinstance(hazards, dict) else 0.0
            applied = service.damage(identifier, float(rate) * pressure)
            if applied > 0:
                settlement_damage[identifier] = applied
        if settlement_damage:
            entity_id = int(getattr(settlement, "entity_id", 0))
            damaged[entity_id] = settlement_damage
    return damaged
