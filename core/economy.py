"""Marché alimentaire déterministe et comptes économiques des établissements."""

from copy import deepcopy
from dataclasses import dataclass


_DEFAULT_ACCOUNT = {
    "treasury": 100.0,
    "food_imported": 0,
    "food_exported": 0,
    "trade_spent": 0.0,
    "trade_earned": 0.0,
    "transactions": 0,
    "last_food_price": 0.0,
}


@dataclass(frozen=True)
class TradeTransaction:
    """Résultat immuable d'un transfert commercial de nourriture."""

    quantity: int
    unit_price: float
    value: float


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


def ensure_economy(settlement):
    """Crée ou complète paresseusement le compte d'un ancien établissement."""
    settings = economy_settings(settlement)
    defaults = dict(_DEFAULT_ACCOUNT)
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
