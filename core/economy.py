"""Marché alimentaire déterministe et comptes économiques des établissements."""

from copy import deepcopy
from dataclasses import dataclass
import math


_DEFAULT_ACCOUNT = {
    "treasury": 100.0,
    "food_imported": 0,
    "food_exported": 0,
    "trade_spent": 0.0,
    "trade_earned": 0.0,
    "transactions": 0,
    "last_food_price": 0.0,
    "goods_imported": {},
    "goods_lost_in_transit": {},
    "goods_exported": {},
    "last_material_prices": {},
}


@dataclass(frozen=True)
class TradeTransaction:
    """Résultat immuable d'un transfert commercial de nourriture."""

    quantity: float
    unit_price: float
    value: float
    good_id: str = "food"
    transport_cost: float = 0.0
    lost_quantity: float = 0.0
    shipped_quantity: float = 0.0


def economy_settings(settlement):
    """Renvoie les paramètres économiques, ou un dictionnaire vide."""
    config = getattr(settlement, "config", {})
    if not isinstance(config, dict):
        return {}
    settings = config.get("economy", {})
    return settings if isinstance(settings, dict) else {}


def economy_enabled(settlement):
    """Indique si le nouveau marché est activé pour cet établissement."""
    return economy_settings(settlement).get("enabled", False) is True


def _infrastructure_effect(settlement, effect_id):
    config = getattr(settlement, "config", {})
    if not isinstance(config, dict):
        return 0.0
    from core.infrastructure import InfrastructureService
    return InfrastructureService(
        settlement, config
    ).effect(effect_id)


def ensure_economy(settlement):
    """Crée ou complète paresseusement le compte d'un ancien établissement."""
    settings = economy_settings(settlement)
    defaults = deepcopy(_DEFAULT_ACCOUNT)
    defaults["treasury"] = float(settings.get("initial_treasury", defaults["treasury"]))

    account = getattr(settlement, "economy", None)
    if not isinstance(account, dict):
        account = {}
        settlement.economy = account
    for key, value in defaults.items():
        account.setdefault(key, value)
    return account


def can_afford(settlement, amount):
    """Teste un coût sans muter le compte."""
    return ensure_economy(settlement)["treasury"] >= max(0.0, float(amount))


def spend(settlement, amount):
    """Débite un coût si possible, sans autoriser de trésorerie négative."""
    cost = max(0.0, float(amount))
    account = ensure_economy(settlement)
    if account["treasury"] < cost:
        return False
    account["treasury"] = round(account["treasury"] - cost, 2)
    return True


def food_price(settlement):
    """Calcule un prix borné qui augmente lorsque les réserves diminuent."""
    settings = economy_settings(settlement)
    stock = max(0.0, float(getattr(settlement, "food_stock", 0)))
    capacity = max(1.0, float(getattr(settlement, "max_food", 1)))
    stock_ratio = min(1.0, stock / capacity)
    base_price = float(settings.get("base_food_price", 1.0))
    minimum = float(settings.get("min_food_price", 0.5))
    maximum = float(settings.get("max_food_price", 5.0))
    price = base_price * (0.5 + 1.5 * (1.0 - stock_ratio))
    return round(min(maximum, max(minimum, price)), 2)


def execute_food_trade(origin, target, *, capacity):
    """Transfère nourriture et richesse sans en créer ni en détruire."""
    origin_account = ensure_economy(origin)
    target_account = ensure_economy(target)
    settings = economy_settings(origin)

    reserve = max(0, int(settings.get("food_reserve", 0)))
    available = max(0, int(getattr(origin, "food_stock", 0) - reserve))
    room = max(0, int(getattr(target, "max_food", 0) - getattr(target, "food_stock", 0)))
    unit_price = food_price(target)
    affordable = int(target_account["treasury"] // unit_price) if unit_price > 0 else 0
    quantity = min(max(0, int(capacity)), available, room, affordable)

    if quantity <= 0:
        return TradeTransaction(0, unit_price, 0.0)

    value = round(quantity * unit_price, 2)
    origin.food_stock -= quantity
    target.food_stock += quantity
    origin_account["treasury"] = round(origin_account["treasury"] + value, 2)
    target_account["treasury"] = round(target_account["treasury"] - value, 2)
    origin_account["food_exported"] += quantity
    target_account["food_imported"] += quantity
    origin_account["trade_earned"] = round(origin_account["trade_earned"] + value, 2)
    target_account["trade_spent"] = round(target_account["trade_spent"] + value, 2)
    origin_account["transactions"] += 1
    target_account["transactions"] += 1
    origin_account["last_food_price"] = unit_price
    target_account["last_food_price"] = unit_price
    return TradeTransaction(quantity, unit_price, value)


def economy_snapshot(settlement):
    """Renvoie une copie enrichie du compte pour le rendu et l'inspection."""
    snapshot = deepcopy(ensure_economy(settlement))
    snapshot["food_price"] = food_price(settlement)
    snapshot["enabled"] = economy_enabled(settlement)
    return snapshot


def world_economic_summary(world):
    """Agrège les comptes des établissements économiques actifs."""
    summary = {
        "active_markets": 0,
        "treasury": 0.0,
        "food_imported": 0,
        "food_exported": 0,
        "transactions": 0,
    }
    for entity in world.get("entities", ()):
        if getattr(entity, "is_expired", False) or not economy_enabled(entity):
            continue
        if not hasattr(entity, "food_stock") or not hasattr(entity, "max_food"):
            continue
        account = ensure_economy(entity)
        summary["active_markets"] += 1
        summary["treasury"] += account["treasury"]
        summary["food_imported"] += account["food_imported"]
        summary["food_exported"] += account["food_exported"]
        summary["transactions"] += account["transactions"]
    summary["treasury"] = round(summary["treasury"], 2)
    return summary


def material_price(settlement, good_id):
    """Price one catalog good from local scarcity and its configured base value."""
    from core.materials import runtime_catalog
    from core.stockpiles import StockpileService

    catalog = runtime_catalog(getattr(settlement, "config", {}))
    definition = catalog.good(good_id)
    stock = StockpileService(settlement, settlement.config).quantity(good_id)
    targets = catalog.definition.get("targets", {})
    target = max(1.0, float(targets.get(good_id, 1.0)))
    ratio = min(1.0, stock / target)
    base = float(definition.get("base_value", 1.0))
    settings = economy_settings(settlement)
    minimum = float(settings.get("min_food_price", 0.5))
    maximum = float(settings.get("max_food_price", 5.0))
    price = base * (0.5 + 1.5 * (1.0 - ratio))
    return round(min(maximum, max(minimum, price)), 2)


def execute_material_trade(origin, target, good_id, *, capacity):
    """Transfer one catalog good and its payment without creating either."""
    from core.materials import runtime_catalog
    from core.stockpiles import StockpileService

    config = getattr(origin, "config", {})
    catalog = runtime_catalog(config)
    unit_price = material_price(target, good_id)
    if not catalog.enabled:
        return TradeTransaction(0.0, unit_price, 0.0, str(good_id))
    origin_account = ensure_economy(origin)
    target_account = ensure_economy(target)
    origin_stock = StockpileService(origin, config)
    target_stock = StockpileService(target, config)
    reserve_settings = catalog.definition.get("trade_reserve", {})
    reserve = max(0.0, float(reserve_settings.get(good_id, 0.0)))
    available = max(0.0, origin_stock.quantity(good_id) - reserve)
    unit_weight = float(catalog.good(good_id)["unit_weight"])
    settings = economy_settings(origin)
    cost_reduction = min(0.95, _infrastructure_effect(origin, "transport_cost_reduction"))
    loss_reduction = min(0.95, _infrastructure_effect(origin, "transport_loss_reduction"))
    origin_pos = getattr(origin, "pos", (0, 0))
    target_pos = getattr(target, "pos", origin_pos)
    distance = math.dist(origin_pos, target_pos)
    risk = max(0.0, float(getattr(target, "trade_risk", 0.0)))
    transport_cost = round(
        (
            distance * max(0.0, float(settings.get("transport_cost_per_tile", 0.0)))
            + risk * max(0.0, float(settings.get("risk_cost_multiplier", 0.0)))
        ) * (1.0 - cost_reduction),
        2,
    )
    loss_per_tile = max(0.0, float(settings.get("transport_loss_per_tile", 0.0)))
    loss_rate = min(0.95, distance * loss_per_tile * (1.0 - loss_reduction))
    room = target_stock.available_weight() / unit_weight
    shipped = float(max(0, math.floor(min(
        max(0.0, float(capacity)), available
    ))))
    delivered = 0.0
    while shipped > 0:
        delivered = float(math.floor(shipped * (1.0 - loss_rate)))
        total_due = round(delivered * unit_price + transport_cost, 2)
        if (
            delivered > 0
            and delivered <= room
            and total_due <= target_account["treasury"]
        ):
            break
        shipped -= 1.0
    if shipped <= 0:
        return TradeTransaction(0.0, unit_price, 0.0, str(good_id))
    removed = origin_stock.withdraw(good_id, shipped)
    transferred = target_stock.deposit(good_id, delivered)
    if removed != shipped or transferred != delivered:
        raise RuntimeError("material transport conservation failure")
    lost = round(shipped - transferred, 6)
    value = round(transferred * unit_price, 2)
    total_payment = round(value + transport_cost, 2)
    origin_account["treasury"] = round(origin_account["treasury"] + total_payment, 2)
    target_account["treasury"] = round(target_account["treasury"] - total_payment, 2)
    origin_account["trade_earned"] = round(
        origin_account["trade_earned"] + total_payment, 2
    )
    target_account["trade_spent"] = round(
        target_account["trade_spent"] + total_payment, 2
    )
    origin_account["transactions"] += 1
    target_account["transactions"] += 1
    exported = origin_account["goods_exported"]
    imported = target_account["goods_imported"]
    losses = origin_account["goods_lost_in_transit"]
    exported[str(good_id)] = round(float(exported.get(str(good_id), 0.0)) + shipped, 6)
    imported[str(good_id)] = round(float(imported.get(str(good_id), 0.0)) + transferred, 6)
    if lost > 0:
        losses[str(good_id)] = round(
            float(losses.get(str(good_id), 0.0)) + lost, 6
        )
    origin_account["last_material_prices"][str(good_id)] = unit_price
    target_account["last_material_prices"][str(good_id)] = unit_price
    return TradeTransaction(
        transferred,
        unit_price,
        value,
        str(good_id),
        transport_cost,
        lost,
        shipped,
    )


def select_material_market(origin, candidates, good_id, *, capacity):
    """Rank reachable markets by expected net value without consuming randomness."""
    settings = economy_settings(origin)
    distance_cost = max(0.0, float(settings.get("transport_cost_per_tile", 0.0)))
    risk_multiplier = max(0.0, float(settings.get("risk_cost_multiplier", 0.0)))
    loss_per_tile = max(0.0, float(settings.get("transport_loss_per_tile", 0.0)))
    cost_reduction = min(0.95, _infrastructure_effect(origin, "transport_cost_reduction"))
    loss_reduction = min(0.95, _infrastructure_effect(origin, "transport_loss_reduction"))
    ranked = []
    origin_pos = getattr(origin, "pos", (0, 0))
    for target in candidates:
        if getattr(target, "is_expired", False) or target is origin:
            continue
        price = material_price(target, good_id)
        target_pos = getattr(target, "pos", origin_pos)
        distance = math.dist(origin_pos, target_pos)
        risk = max(0.0, float(getattr(target, "trade_risk", 0.0)))
        transport = round(
            (distance * distance_cost + risk * risk_multiplier) * (1.0 - cost_reduction), 2
        )
        loss_rate = min(0.95, distance * loss_per_tile * (1.0 - loss_reduction))
        delivered = max(0.0, float(capacity)) * (1.0 - loss_rate)
        expected = round(delivered * price - transport, 2)
        ranked.append({
            "target": target,
            "good_id": str(good_id),
            "unit_price": price,
            "distance": round(distance, 6),
            "risk": risk,
            "transport_cost": transport,
            "loss_rate": round(loss_rate, 6),
            "expected_profit": expected,
        })
    if not ranked:
        return None
    return sorted(
        ranked,
        key=lambda choice: (
            -choice["expected_profit"],
            int(getattr(choice["target"], "entity_id", 0)),
        ),
    )[0]