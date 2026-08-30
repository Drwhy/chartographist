"""Optional food balancing and exact observable food flows."""


def food_balance_settings(subject):
    config = getattr(subject, "config", subject)
    if not isinstance(config, dict):
        return {}
    settings = config.get("food_balance", {})
    return settings if isinstance(settings, dict) else {}


def food_balance_enabled(subject):
    return food_balance_settings(subject).get("enabled") is True


def generic_labor_yield(subject):
    if not food_balance_enabled(subject):
        return 1
    return max(0, int(food_balance_settings(subject).get("generic_labor_yield", 0)))


def add_food(settlement, world, amount, *, source, respect_capacity=True):
    from core.simulation_metrics import SimulationMetrics

    quantity = max(0, int(amount))
    before = max(0, int(getattr(settlement, "food_stock", 0)))
    capacity = max(0, int(getattr(settlement, "max_food", before + quantity)))
    after = min(capacity, before + quantity) if respect_capacity else before + quantity
    settlement.food_stock = after
    created = after - before
    SimulationMetrics(world).record_food("produced", created, source=source)
    return created


def consume_food(settlement, world, amount=1):
    from core.simulation_metrics import SimulationMetrics
    from core.production import consume_material_food

    requested = max(0, int(amount))
    material_consumed = consume_material_food(settlement, requested)
    remaining = max(0.0, requested - material_consumed)
    before = max(0.0, float(getattr(settlement, "food_stock", 0)))
    legacy_consumed = min(before, remaining)
    settlement.food_stock = round(before - legacy_consumed, 6)
    consumed = material_consumed + legacy_consumed
    consumed = int(consumed) if float(consumed).is_integer() else round(consumed, 6)
    SimulationMetrics(world).record_food("consumed", consumed)
    return consumed


def apply_storage_loss(settlement, world):
    from core.simulation_metrics import SimulationMetrics

    if not food_balance_enabled(settlement):
        return 0
    rate = float(food_balance_settings(settlement).get("storage_loss_rate", 0.0))
    rate = min(1.0, max(0.0, rate))
    stock = max(0, int(getattr(settlement, "food_stock", 0)))
    lost = min(stock, int(stock * rate))
    settlement.food_stock = stock - lost
    SimulationMetrics(world).record_food("lost", lost)
    update_food_trend(settlement)
    return lost


def update_food_trend(settlement):
    """Store a bounded food-capacity ratio history for the optional mode."""
    if not food_balance_enabled(settlement):
        return []
    settings = food_balance_settings(settlement)
    window = max(2, int(settings.get("specialization_window", 6)))
    capacity = max(1, int(getattr(settlement, "max_food", 1)))
    ratio = round(max(0, int(getattr(settlement, "food_stock", 0))) / capacity, 6)
    history = getattr(settlement, "food_ratio_history", None)
    if not isinstance(history, list):
        history = []
        settlement.food_ratio_history = history
    history.append(ratio)
    del history[:-window]
    return list(history)


def needs_food_specialization(settlement, *, legacy_threshold):
    """Use the legacy threshold or a sustained ratio trend in balanced mode."""
    if not food_balance_enabled(settlement):
        return getattr(settlement, "food_stock", 0) < legacy_threshold
    settings = food_balance_settings(settlement)
    window = max(2, int(settings.get("specialization_window", 6)))
    threshold = float(settings.get("specialization_food_ratio", 0.25))
    history = getattr(settlement, "food_ratio_history", [])
    if len(history) < window:
        return False
    recent = history[-window:]
    return sum(recent) / len(recent) <= threshold and recent[-1] <= recent[0]
