"""Capacity-bounded stockpiles and conservative transfers between settlements."""

from copy import deepcopy
import math

from core.materials import MaterialCatalog


_STOCKPILE_VERSION = 1


def _quantity(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("quantity must be numeric")
    amount = float(value)
    if not math.isfinite(amount):
        raise ValueError("quantity must be finite")
    if amount < 0:
        raise ValueError("quantity must be nonnegative")
    return round(amount, 6)


def _infrastructure_capacity_bonus(settlement, catalog):
    state = getattr(settlement, "infrastructure", None)
    levels = state.get("levels", {}) if isinstance(state, dict) else {}
    if not isinstance(levels, dict):
        return 0.0
    definitions = catalog.definition.get("infrastructures", [])
    if not isinstance(definitions, list):
        return 0.0
    total = 0.0
    for definition in definitions:
        if not isinstance(definition, dict):
            continue
        identifier = str(definition.get("id", ""))
        level = max(0, int(levels.get(identifier, 0)))
        bonus = max(0.0, float(definition.get("capacity_bonus", 0.0)))
        total += level * bonus
    return round(total, 6)


def _empty_state(capacity):
    return {
        "version": _STOCKPILE_VERSION,
        "capacity": round(max(0.0, float(capacity)), 6),
        "base_capacity": round(max(0.0, float(capacity)), 6),
        "goods": {},
        "losses": {},
        "last_decay_cycle": None,
        "initial_stock_applied": False,
    }


def ensure_stockpile(settlement, config):
    """Create or migrate enabled storage without discarding existing quantities."""
    catalog = MaterialCatalog(config)
    capacity = catalog.definition.get("stockpile_capacity", 0)
    state = getattr(settlement, "stockpile", None)
    if not isinstance(state, dict):
        state = _empty_state(capacity)
        settlement.stockpile = state
    state.setdefault("version", _STOCKPILE_VERSION)
    base_capacity = round(max(0.0, float(capacity)), 6)
    state["base_capacity"] = base_capacity
    state["capacity"] = round(
        base_capacity + _infrastructure_capacity_bonus(settlement, catalog),
        6,
    )
    goods = state.get("goods")
    if not isinstance(goods, dict):
        state["goods"] = {}
    else:
        state["goods"] = {
            str(key): _quantity(value)
            for key, value in goods.items()
            if _quantity(value) > 0
        }
    if not isinstance(state.get("losses"), dict):
        state["losses"] = {}
    state.setdefault("last_decay_cycle", None)
    state.setdefault("initial_stock_applied", False)
    if not state["initial_stock_applied"]:
        initial = catalog.definition.get("initial_stock", {})
        current_weight = sum(
            float(catalog.good(good_id)["unit_weight"]) * float(amount)
            for good_id, amount in state["goods"].items()
        )
        for good_id, requested in sorted(initial.items()):
            definition = catalog.good(good_id)
            unit_weight = float(definition["unit_weight"])
            room = max(0.0, float(state["capacity"]) - current_weight)
            accepted = round(min(float(requested), room / unit_weight), 6)
            if accepted > 0:
                state["goods"][good_id] = round(
                    float(state["goods"].get(good_id, 0.0)) + accepted,
                    6,
                )
                current_weight += accepted * unit_weight
        state["initial_stock_applied"] = True
    return state


class StockpileService:
    """Own all stock mutations for one settlement."""

    def __init__(self, settlement, config):
        self.settlement = settlement
        self.config = config if isinstance(config, dict) else {}
        self.catalog = MaterialCatalog(self.config)
        self.enabled = self.catalog.enabled
        capacity = self.catalog.definition.get("stockpile_capacity", 0)
        self.state = (
            ensure_stockpile(settlement, self.config)
            if self.enabled
            else _empty_state(capacity)
        )

    @property
    def capacity(self):
        return max(0.0, float(self.state.get("capacity", 0.0)))

    def snapshot(self):
        return deepcopy(self.state)

    def refresh_capacity(self):
        self.state = ensure_stockpile(self.settlement, self.config)
        return self.capacity

    def quantity(self, good_id):
        return round(max(0.0, float(self.state["goods"].get(str(good_id), 0.0))), 6)

    def total_weight(self):
        total = 0.0
        for good_id, amount in self.state["goods"].items():
            try:
                weight = float(self.catalog.good(good_id)["unit_weight"])
            except KeyError:
                continue
            total += weight * max(0.0, float(amount))
        return round(total, 6)

    def available_weight(self):
        return round(max(0.0, self.capacity - self.total_weight()), 6)

    def deposit(self, good_id, amount):
        requested = _quantity(amount)
        if not self.enabled or requested == 0:
            return 0.0
        definition = self.catalog.good(good_id)
        unit_weight = float(definition["unit_weight"])
        accepted = min(requested, self.available_weight() / unit_weight)
        accepted = round(max(0.0, accepted), 6)
        if accepted:
            key = str(good_id)
            self.state["goods"][key] = round(self.quantity(key) + accepted, 6)
        return accepted

    def withdraw(self, good_id, amount):
        requested = _quantity(amount)
        if not self.enabled or requested == 0:
            return 0.0
        self.catalog.good(good_id)
        key = str(good_id)
        removed = round(min(requested, self.quantity(key)), 6)
        remaining = round(self.quantity(key) - removed, 6)
        if remaining > 0:
            self.state["goods"][key] = remaining
        else:
            self.state["goods"].pop(key, None)
        return removed

    def decay(self, cycle):
        if not self.enabled:
            return {}
        current_cycle = int(cycle)
        if self.state.get("last_decay_cycle") == current_cycle:
            return {}
        losses = {}
        for good_id in list(self.state["goods"]):
            definition = self.catalog.good(good_id)
            rate = float(definition.get("decay_rate", 0.0))
            amount = self.quantity(good_id)
            lost = round(min(amount, amount * max(0.0, min(1.0, rate))), 6)
            if lost <= 0:
                continue
            self.withdraw(good_id, lost)
            losses[good_id] = lost
            cumulative = float(self.state["losses"].get(good_id, 0.0))
            self.state["losses"][good_id] = round(cumulative + lost, 6)
        self.state["last_decay_cycle"] = current_cycle
        return losses


def transfer_goods(source, target, good_id, amount, config):
    """Move a good atomically up to source stock and target capacity."""
    requested = _quantity(amount)
    source_service = StockpileService(source, config)
    target_service = StockpileService(target, config)
    transferred = 0.0
    if source_service.enabled and target_service.enabled and requested > 0:
        definition = source_service.catalog.good(good_id)
        unit_weight = float(definition["unit_weight"])
        transferred = round(min(
            requested,
            source_service.quantity(good_id),
            target_service.available_weight() / unit_weight,
        ), 6)
        if transferred > 0:
            removed = source_service.withdraw(good_id, transferred)
            accepted = target_service.deposit(good_id, removed)
            if accepted != removed:
                source_service.deposit(good_id, removed - accepted)
            transferred = accepted
    return {
        "good_id": str(good_id),
        "requested": requested,
        "transferred": round(transferred, 6),
        "source_id": int(getattr(source, "entity_id", 0)),
        "target_id": int(getattr(target, "entity_id", 0)),
    }