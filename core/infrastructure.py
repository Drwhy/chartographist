"""Persistent settlement infrastructures assembled from conserved material kits."""

from copy import deepcopy

from core.materials import MaterialCatalog


_INFRASTRUCTURE_VERSION = 1


def _empty_state():
    return {
        "version": _INFRASTRUCTURE_VERSION,
        "levels": {},
        "last_install_cycle": None,
    }


def ensure_infrastructure_state(settlement, definitions):
    state = getattr(settlement, "infrastructure", None)
    if not isinstance(state, dict):
        state = _empty_state()
        settlement.infrastructure = state
    state.setdefault("version", _INFRASTRUCTURE_VERSION)
    raw_levels = state.get("levels")
    if not isinstance(raw_levels, dict):
        raw_levels = {}
    levels = {}
    for identifier, definition in definitions.items():
        value = raw_levels.get(identifier, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = 0
        levels[identifier] = min(
            int(definition["max_level"]),
            max(0, int(value)),
        )
    state["levels"] = levels
    state.setdefault("last_install_cycle", None)
    return state


class InfrastructureService:
    """Install configured infrastructure levels without creating material."""

    def __init__(self, settlement, config):
        self.settlement = settlement
        self.config = config if isinstance(config, dict) else {}
        self.catalog = MaterialCatalog(self.config)
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
            self.state["levels"][identifier] = level + 1
            installed[identifier] = 1
        if installed:
            stockpile.refresh_capacity()
        return installed
