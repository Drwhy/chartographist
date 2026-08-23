"""Serializable, deterministic observability for headless simulations."""

from copy import deepcopy


_METRIC_DEFAULTS = {
    "version": 1,
    "flows": {
        "food": {
            "produced": 0,
            "consumed": 0,
            "imported": 0,
            "pillaged": 0,
            "lost": 0,
        },
        "food_sources": {},
        "demography": {"births": 0, "deaths": 0},
        "fauna": {"spawned": 0, "births": 0, "deaths": 0},
        "economy": {"transactions": 0},
        "combat": {"raids": 0},
        "climate": {"events": 0},
        "characters": {
            "promotions": 0,
            "archives": 0,
            "decisions": 0,
            "rests": 0,
        },
        "materials": {
            "orders_created": 0,
            "orders_completed": 0,
            "trades": 0,
            "produced": {},
            "lost": {},
            "sourced": {},
            "infrastructure_built": {},
            "traded": {},
        },
        "resources": {
            "biomass_harvested": 0,
            "fish_harvested": 0,
            "soil_depleted": 0.0,
            "disturbances": 0,
        },
    },
    "initialization": {
        "requested_settlements": 0,
        "placed_settlements": 0,
        "fallback_used": False,
        "status": "not_started",
    },
}


def initial_metrics_state():
    """Return independent JSON-serializable metric storage."""
    return deepcopy(_METRIC_DEFAULTS)


def _merge_defaults(target, defaults):
    for key, default in defaults.items():
        if key not in target or not isinstance(target[key], type(default)):
            target[key] = deepcopy(default)
        elif isinstance(default, dict):
            _merge_defaults(target[key], default)


def _is_active(entity):
    return not getattr(entity, "is_expired", False)


def _is_settlement(entity):
    return (
        _is_active(entity)
        and hasattr(entity, "citizens")
        and hasattr(entity, "food_stock")
        and hasattr(entity, "max_food")
    )


def _culture_key(culture):
    if isinstance(culture, dict):
        return str(culture.get("name", ""))
    return str(culture or "")


class SimulationMetrics:
    """Collect state and cumulative flows without consuming randomness."""

    def __init__(self, world):
        self.world = world
        storage = world.get("metrics")
        if not isinstance(storage, dict):
            storage = {}
            world["metrics"] = storage
        _merge_defaults(storage, _METRIC_DEFAULTS)
        self.storage = storage

    def record_food(self, kind, amount, *, source=None):
        food = self.storage["flows"]["food"]
        if kind not in food:
            raise ValueError(f"unknown food flow: {kind}")
        quantity = max(0, int(amount))
        food[kind] += quantity
        if source and quantity:
            sources = self.storage["flows"]["food_sources"]
            sources[source] = sources.get(source, 0) + quantity
        return quantity

    def record_demography(self, kind, amount=1):
        demography = self.storage["flows"]["demography"]
        if kind not in demography:
            raise ValueError(f"unknown demographic flow: {kind}")
        quantity = max(0, int(amount))
        demography[kind] += quantity
        return quantity

    def record_fauna(self, kind, amount=1):
        fauna = self.storage["flows"]["fauna"]
        if kind not in fauna:
            raise ValueError(f"unknown fauna flow: {kind}")
        quantity = max(0, int(amount))
        fauna[kind] += quantity
        return quantity

    def record_activity(self, section, kind, amount=1):
        flows = self.storage["flows"]
        if section not in flows or not isinstance(flows[section], dict):
            raise ValueError(f"unknown activity section: {section}")
        if kind not in flows[section]:
            raise ValueError(f"unknown activity flow: {section}.{kind}")
        quantity = max(0, int(amount))
        flows[section][kind] += quantity
        return quantity

    def record_material(self, kind, amount=1, *, good_id=None):
        materials = self.storage["flows"]["materials"]
        if kind not in materials:
            raise ValueError(f"unknown material flow: {kind}")
        if isinstance(materials[kind], dict):
            if not good_id:
                raise ValueError(f"material flow requires good id: {kind}")
            quantity = max(0.0, float(amount))
            current = float(materials[kind].get(str(good_id), 0.0))
            materials[kind][str(good_id)] = round(current + quantity, 6)
            return quantity
        quantity = max(0, int(amount))
        materials[kind] += quantity
        return quantity
    def record_resource(self, kind, amount):
        resources = self.storage["flows"]["resources"]
        if kind not in resources:
            raise ValueError(f"unknown resource flow: {kind}")
        quantity = max(0.0, float(amount))
        current = resources[kind]
        updated = round(float(current) + quantity, 6)
        resources[kind] = int(updated) if isinstance(current, int) else updated
        return quantity

    def _state_snapshot(self):
        settlements = []
        fauna_count = 0
        cultures = set()
        population = 0
        food_stock = 0
        food_capacity = 0
        treasury = 0.0
        transactions = 0
        prices = []
        stockpile_goods = {}
        stockpile_weight = 0.0
        stockpile_capacity = 0.0
        active_production_orders = 0

        for entity in self.world.get("entities", ()):
            if not _is_active(entity):
                continue
            if _is_settlement(entity):
                settlements.append(entity)
                living = [
                    citizen for citizen in getattr(entity, "citizens", ())
                    if not getattr(citizen, "is_dead", False)
                ]
                population += len(living)
                food_stock += max(0, int(getattr(entity, "food_stock", 0)))
                food_capacity += max(0, int(getattr(entity, "max_food", 0)))
                culture = _culture_key(getattr(entity, "culture", None))
                if culture:
                    cultures.add(culture)
                stockpile = getattr(entity, "stockpile", None)
                if isinstance(stockpile, dict):
                    stockpile_capacity += max(0.0, float(stockpile.get("capacity", 0.0)))
                    goods = stockpile.get("goods", {})
                    if isinstance(goods, dict):
                        from core.materials import MaterialCatalog
                        catalog = MaterialCatalog(getattr(entity, "config", {}))
                        for good_id, amount in goods.items():
                            quantity = max(0.0, float(amount))
                            stockpile_goods[good_id] = round(
                                float(stockpile_goods.get(good_id, 0.0)) + quantity,
                                6,
                            )
                            try:
                                unit_weight = float(catalog.good(good_id)["unit_weight"])
                            except KeyError:
                                unit_weight = 0.0
                            stockpile_weight += quantity * unit_weight
                production = getattr(entity, "production", None)
                if isinstance(production, dict):
                    active_production_orders += sum(
                        order.get("status") in {"waiting", "active"}
                        for order in production.get("orders", ())
                        if isinstance(order, dict)
                    )
                account = getattr(entity, "economy", None)
                if isinstance(account, dict):
                    treasury += float(account.get("treasury", 0.0))
                    transactions += int(account.get("transactions", 0))
                    price = float(account.get("last_food_price", 0.0))
                    if price > 0:
                        prices.append(price)
                continue

            if self._is_animal(entity):
                fauna_count += 1

        diplomacy = {}
        for relation in self.world.get("diplomacy", {}).values():
            if not isinstance(relation, dict):
                continue
            status = str(relation.get("status", "neutral"))
            diplomacy[status] = diplomacy.get(status, 0) + 1

        saturation = food_stock / food_capacity if food_capacity else 0.0
        average_price = sum(prices) / len(prices) if prices else 0.0
        resource_ratios = {}
        resource_state = self.world.get("resources", {})
        grids = resource_state.get("grids", {}) if isinstance(resource_state, dict) else {}
        for name in ("biomass", "fish_stock", "soil_fertility", "forest_cover"):
            grid = grids.get(name, {}) if isinstance(grids, dict) else {}
            stocks = grid.get("stock", ()) if isinstance(grid, dict) else ()
            capacities = grid.get("capacity", ()) if isinstance(grid, dict) else ()
            stock = sum(sum(float(value) for value in row) for row in stocks)
            capacity = sum(sum(float(value) for value in row) for row in capacities)
            resource_ratios[name] = round(stock / capacity, 6) if capacity else 0.0
        return {
            "population": population,
            "settlements": len(settlements),
            "fauna": fauna_count,
            "food_stock": food_stock,
            "food_capacity": food_capacity,
            "food_saturation": round(saturation, 6),
            "treasury": round(treasury, 2),
            "transactions": transactions,
            "average_food_price": round(average_price, 2),
            "cultures": len(cultures),
            "diplomacy": diplomacy,
            "biomass_ratio": resource_ratios["biomass"],
            "fish_ratio": resource_ratios["fish_stock"],
            "soil_fertility_ratio": resource_ratios["soil_fertility"],
            "forest_ratio": resource_ratios["forest_cover"],
            "notables": len(self.world.get("notables", {})),
            "archived_notables": len(self.world.get("notable_archive", {})),
            "stockpile_goods": dict(sorted(stockpile_goods.items())),
            "stockpile_weight": round(stockpile_weight, 6),
            "stockpile_capacity": round(stockpile_capacity, 6),
            "active_production_orders": active_production_orders,
        }

    @staticmethod
    def _is_animal(entity):
        try:
            from entities.species.animal.base import Animal
            return isinstance(entity, Animal)
        except ImportError:
            return False

    def snapshot(self):
        return {
            "cycle": int(self.world.get("cycle", 0)),
            "state": self._state_snapshot(),
            "flows": deepcopy(self.storage["flows"]),
            "initialization": deepcopy(self.storage["initialization"]),
        }
