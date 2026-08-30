"""Deterministic shortage planning and resource-conserving production orders."""

from copy import deepcopy

from core.materials import runtime_catalog
from core.stockpiles import StockpileService


_PRODUCTION_VERSION = 2


def _empty_state():
    return {
        "version": _PRODUCTION_VERSION,
        "next_order_id": 1,
        "orders": [],
        "last_planning_cycle": None,
        "last_sourcing_cycle": None,
        "tool_durability": {},
        "production_totals": {},
        "specialization": None,
    }

def ensure_production_state(settlement):
    state = getattr(settlement, "production", None)
    if not isinstance(state, dict):
        state = _empty_state()
        settlement.production = state
    state.setdefault("version", _PRODUCTION_VERSION)
    state.setdefault("next_order_id", 1)
    if not isinstance(state.get("orders"), list):
        state["orders"] = []
    state.setdefault("last_planning_cycle", None)
    state.setdefault("last_sourcing_cycle", None)
    durability = state.get("tool_durability")
    if not isinstance(durability, dict):
        durability = {}
    state["tool_durability"] = {
        str(key): max(0.0, float(value))
        for key, value in durability.items()
    }
    totals = state.get("production_totals")
    if not isinstance(totals, dict):
        totals = {}
    state["production_totals"] = {
        str(key): max(0.0, float(value))
        for key, value in totals.items()
    }
    state.setdefault("specialization", None)
    return state


class ProductionService:
    """Plan and advance explainable work orders for a single settlement."""

    def __init__(self, settlement, config):
        self.settlement = settlement
        self.config = config if isinstance(config, dict) else {}
        self.catalog = runtime_catalog(self.config)
        self.enabled = self.catalog.enabled
        self.state = ensure_production_state(settlement) if self.enabled else _empty_state()
        self.stockpile = StockpileService(settlement, self.config)

    def snapshot(self):
        return deepcopy(self.state)

    def tool_durability(self, tool_id):
        identifier = str(tool_id)
        if self.stockpile.quantity(identifier) < 1.0:
            return 0.0
        maximum = float(self.catalog.item(identifier).get("durability", 1.0))
        current = self.state["tool_durability"].get(identifier, maximum)
        return round(min(maximum, max(0.0, float(current))), 6)

    def _consume_tool_durability(self, recipe):
        wear = max(0.0, float(recipe.get("tool_wear", 1.0)))
        if wear <= 0:
            return
        for tool_id in recipe.get("tools", ()):
            identifier = str(tool_id)
            maximum = float(self.catalog.item(identifier).get("durability", 1.0))
            remaining_wear = wear
            durability = self.tool_durability(identifier)
            while remaining_wear >= durability and self.stockpile.quantity(identifier) >= 1.0:
                remaining_wear -= durability
                self.stockpile.withdraw(identifier, 1.0)
                if self.stockpile.quantity(identifier) < 1.0:
                    durability = 0.0
                    break
                durability = maximum
            if durability > 0:
                durability -= remaining_wear
                self.state["tool_durability"][identifier] = round(
                    max(0.0, durability), 6
                )
            else:
                self.state["tool_durability"].pop(identifier, None)

    def plan(self, cycle):
        if not self.enabled:
            return []
        current_cycle = int(cycle)
        if self.state.get("last_planning_cycle") == current_cycle:
            return []
        self.state["last_planning_cycle"] = current_cycle
        created = []
        targets = self.catalog.definition.get("targets", {})
        if not isinstance(targets, dict):
            return created
        recipes = self.catalog.snapshot()["recipes"]
        for good_id, target_quantity in sorted(targets.items()):
            if self._infrastructure_kit_is_saturated(good_id):
                continue
            target = max(0.0, float(target_quantity))
            current = self.stockpile.quantity(good_id)
            pending = sum(
                float(self.catalog.recipe(order["recipe_id"])["outputs"].get(good_id, 0))
                for order in self.state["orders"]
                if order.get("status") in {"waiting", "active"}
            )
            deficit = max(0.0, target - current - pending)
            if deficit <= 0:
                continue
            recipe = next(
                (candidate for candidate in recipes if good_id in candidate.get("outputs", {})),
                None,
            )
            if recipe is None:
                continue
            if any(
                order.get("recipe_id") == recipe["id"]
                and order.get("status") in {"waiting", "active"}
                for order in self.state["orders"]
            ):
                continue
            priority = round(deficit / max(1.0, target), 6)
            created.append(self.create_order(
                recipe["id"],
                reason=f"shortage:{good_id}",
                priority=priority,
                cycle=current_cycle,
            ))
        return created

    def _infrastructure_kit_is_saturated(self, good_id):
        definitions = self.catalog.definition.get("infrastructures", [])
        matching = [
            definition for definition in definitions
            if isinstance(definition, dict)
            and definition.get("kit_good_id") == good_id
        ]
        if not matching:
            return False
        state = getattr(self.settlement, "infrastructure", None)
        levels = state.get("levels", {}) if isinstance(state, dict) else {}
        if not isinstance(levels, dict):
            levels = {}
        return all(
            max(0, int(levels.get(str(definition["id"]), 0)))
            >= int(definition["max_level"])
            for definition in matching
        )

    def create_order(self, recipe_id, *, reason, priority, cycle):
        if not self.enabled:
            return {}
        recipe = self.catalog.recipe(recipe_id)
        order = {
            "order_id": int(self.state["next_order_id"]),
            "recipe_id": str(recipe_id),
            "reason": str(reason),
            "priority": round(max(0.0, float(priority)), 6),
            "status": "waiting",
            "created_cycle": int(cycle),
            "completed_cycle": None,
            "inputs_consumed": False,
            "progress": 0.0,
            "required_work": round(
                float(recipe["cycles"]) * float(recipe["labor"]), 6
            ),
            "worker_skill": 0.0,
        }
        self.state["next_order_id"] += 1
        self.state["orders"].append(order)
        return deepcopy(order)

    def advance(self, *, worker=None, workers=None, cycle):
        if not self.enabled:
            return None
        candidates = [
            order for order in self.state["orders"]
            if order.get("status") in {"waiting", "active"}
        ]
        if not candidates:
            return None
        ranked = sorted(
            candidates,
            key=lambda value: (-float(value.get("priority", 0.0)), int(value["order_id"])),
        )
        order = next(
            (
                candidate for candidate in ranked
                if candidate.get("status") == "active"
                or self._can_start(self.catalog.recipe(candidate["recipe_id"]))
            ),
            None,
        )
        if order is None:
            return deepcopy(ranked[0])
        recipe = self.catalog.recipe(order["recipe_id"])
        if workers is not None:
            living_workers = [
                candidate for candidate in workers
                if not getattr(candidate, "is_dead", False)
            ]
            if living_workers:
                worker = max(
                    living_workers,
                    key=lambda value: self._worker_skill(value, recipe.get("skill")),
                )
        if order["status"] == "waiting":
            for good_id, quantity in recipe["inputs"].items():
                removed = self.stockpile.withdraw(good_id, quantity)
                if removed != float(quantity):
                    raise RuntimeError("production input conservation failure")
            order["inputs_consumed"] = True
            order["status"] = "active"

        skill = self._worker_skill(worker, recipe.get("skill"))
        from core.infrastructure import InfrastructureService
        infrastructure_bonus = InfrastructureService(
            self.settlement, self.config
        ).effect("production_speed_bonus")
        order["worker_skill"] = skill
        order["worker_id"] = (
            None if worker is None
            else int(getattr(worker, "entity_id", 0))
        )
        from core.institutions import settlement_policy_modifier
        labor_multiplier = settlement_policy_modifier(
            self.settlement,
            "labor_efficiency_multiplier",
            default=1.0,
        )
        order["progress"] = round(
            float(order["progress"])
            + (1.0 + skill / 100.0 + infrastructure_bonus) * labor_multiplier,
            6,
        )
        if order["progress"] >= order["required_work"]:
            products = {}
            for field in ("outputs", "byproducts"):
                for good_id, quantity in recipe.get(field, {}).items():
                    products[good_id] = products.get(good_id, 0.0) + float(quantity)
            for good_id, quantity in products.items():
                accepted = self.stockpile.deposit(good_id, quantity)
                if accepted != float(quantity):
                    raise RuntimeError("production output capacity failure")
            quality_scale = max(0.0, float(recipe.get("quality_skill_scale", 0.0)))
            order["output_quality"] = round(1.0 + skill / 100.0 * quality_scale, 6)
            totals = self.state["production_totals"]
            for good_id, quantity in recipe["outputs"].items():
                identifier = str(good_id)
                totals[identifier] = round(
                    float(totals.get(identifier, 0.0)) + float(quantity), 6
                )
            self.state["specialization"] = max(
                sorted(totals.items()),
                key=lambda item: item[1],
            )[0]
            self._consume_tool_durability(recipe)
            order["status"] = "completed"
            order["completed_cycle"] = int(cycle)
        return deepcopy(order)

    def _can_start(self, recipe):
        for good_id, quantity in recipe["inputs"].items():
            if self.stockpile.quantity(good_id) < float(quantity):
                return False
        for tool_id in recipe.get("tools", ()):
            if self.stockpile.quantity(tool_id) < 1.0:
                return False
        released = sum(
            float(quantity) * float(self.catalog.good(good_id)["unit_weight"])
            for good_id, quantity in recipe["inputs"].items()
        )
        produced = sum(
            float(quantity) * float(self.catalog.good(good_id)["unit_weight"])
            for field in ("outputs", "byproducts")
            for good_id, quantity in recipe.get(field, {}).items()
        )
        return self.stockpile.total_weight() - released + produced <= self.stockpile.capacity

    @staticmethod
    def _worker_skill(worker, skill_name):
        state = getattr(worker, "character", None)
        if not isinstance(state, dict):
            return 0.0
        skills = state.get("skills", {})
        if not isinstance(skills, dict):
            return 0.0
        return round(min(100.0, max(0.0, float(skills.get(skill_name, 0.0)))), 6)

def _food_chain(config):
    definition = config.get("materials", {}) if isinstance(config, dict) else {}
    chain = definition.get("food_chain", {}) if isinstance(definition, dict) else {}
    return chain if isinstance(chain, dict) else {}


def consume_material_food(settlement, amount, config=None):
    """Consume stored rations before the legacy settlement food stock."""
    resolved = config if isinstance(config, dict) else getattr(settlement, "config", {})
    settings = resolved.get("materials", {}) if isinstance(resolved, dict) else {}
    if not isinstance(settings, dict) or settings.get("enabled") is not True:
        return 0.0
    chain = _food_chain(resolved)
    if not chain:
        return 0.0
    requested = max(0.0, float(amount))
    ration_id = chain.get("ration_good_id")
    if not ration_id:
        return 0.0
    return StockpileService(settlement, resolved).withdraw(ration_id, requested)


def source_spatial_inputs(service, workers, world):
    """Stage missing recipe inputs from local renewable spatial resources."""
    if not service.enabled:
        return {}
    living_workers = [
        worker for worker in workers
        if not getattr(worker, "is_dead", False)
    ]
    if not living_workers:
        return {}
    cycle = int(world.get("cycle", 0))
    if service.state.get("last_sourcing_cycle") == cycle:
        return {}
    service.state["last_sourcing_cycle"] = cycle

    from core.resources import ResourceSystem
    from core.simulation_metrics import SimulationMetrics

    resources = ResourceSystem(world, service.config)
    if not resources.enabled:
        return {}
    x, y = (int(value) for value in service.settlement.pos)
    sourced = {}
    orders = sorted(
        (
            order for order in service.state["orders"]
            if order.get("status") == "waiting"
        ),
        key=lambda value: (
            -float(value.get("priority", 0.0)),
            int(value["order_id"]),
        ),
    )
    for order in orders:
        recipe = service.catalog.recipe(order["recipe_id"])
        for good_id, required in sorted(recipe["inputs"].items()):
            missing = max(
                0.0,
                float(required) - service.stockpile.quantity(good_id),
            )
            if missing <= 0:
                continue
            definition = service.catalog.good(good_id)
            source = definition.get("source")
            if not isinstance(source, dict):
                continue
            spatial_name = source["spatial_resource"]
            stock_per_unit = float(source["stock_per_unit"])
            skill_name = source.get("skill")
            skill = max(
                service._worker_skill(worker, skill_name)
                for worker in living_workers
            )
            monthly_limit = (
                float(source["max_per_cycle"]) * (1.0 + skill / 100.0)
            )
            weight_limit = (
                service.stockpile.available_weight()
                / float(definition["unit_weight"])
            )
            tile = resources.tile_snapshot(x, y)[spatial_name]
            ecological_floor = (
                float(tile["capacity"]) * float(source["minimum_ratio"])
            )
            harvestable_stock = max(
                0.0, float(tile["stock"]) - ecological_floor
            )
            material_quantity = min(
                missing,
                monthly_limit,
                weight_limit,
                harvestable_stock / stock_per_unit,
            )
            if material_quantity <= 0:
                continue
            extracted = resources.extract(
                spatial_name,
                x,
                y,
                material_quantity * stock_per_unit,
            )
            converted = extracted / stock_per_unit
            accepted = service.stockpile.deposit(good_id, converted)
            if accepted < converted:
                resources.restore(
                    spatial_name,
                    x,
                    y,
                    (converted - accepted) * stock_per_unit,
                )
            if accepted <= 0:
                continue
            quantity = round(float(accepted), 6)
            sourced[good_id] = round(sourced.get(good_id, 0.0) + quantity, 6)
            SimulationMetrics(world).record_material(
                "sourced", quantity, good_id=good_id
            )
    return sourced


def advance_settlement_production(settlement, world):
    """Run one conservative material-production step for a live workforce."""
    config = getattr(settlement, "config", {})
    result = {
        "staged": 0.0,
        "sourced": {},
        "order": None,
        "losses": {},
        "infrastructure": {},
        "maintenance": {},
        "artifacts": [],
    }
    settings = config.get("materials", {}) if isinstance(config, dict) else {}
    if not isinstance(settings, dict) or settings.get("enabled") is not True:
        return result
    service = ProductionService(settlement, config)
    from core.infrastructure import InfrastructureService

    infrastructure = InfrastructureService(settlement, config)
    result["maintenance"] = infrastructure.maintain(
        cycle=world.get("cycle", 0)
    )
    chain = _food_chain(config)
    recipe_id = chain.get("recipe_id")
    raw_good_id = chain.get("raw_good_id")
    workers = [
        worker for worker in getattr(settlement, "citizens", ())
        if not getattr(worker, "is_dead", False)
    ]
    from core.simulation_metrics import SimulationMetrics

    metrics = SimulationMetrics(world)
    result["losses"] = service.stockpile.decay(world.get("cycle", 0))
    for lost_good_id, lost_quantity in result["losses"].items():
        metrics.record_material("lost", lost_quantity, good_id=lost_good_id)
    created = service.plan(world.get("cycle", 0))
    metrics.record_material("orders_created", len(created))
    result["sourced"] = source_spatial_inputs(service, workers, world)
    pending_food = None
    if recipe_id:
        pending_food = next(
            (
                order for order in service.state["orders"]
                if order.get("recipe_id") == recipe_id
                and order.get("status") in {"waiting", "active"}
            ),
            None,
        )
    if pending_food is not None and raw_good_id:
        food_recipe = service.catalog.recipe(recipe_id)
        tools_available = all(
            service.stockpile.quantity(tool_id) >= 1
            for tool_id in food_recipe.get("tools", ())
        )
        if pending_food["status"] == "waiting" and tools_available:
            required = float(food_recipe["inputs"].get(raw_good_id, 0.0))
            missing = max(
                0.0, required - service.stockpile.quantity(raw_good_id)
            )
            available = max(0.0, float(getattr(settlement, "food_stock", 0.0)))
            staged = service.stockpile.deposit(
                raw_good_id, min(missing, available)
            )
            if staged > 0:
                settlement.food_stock = round(available - staged, 6)
                result["staged"] = staged
    if not workers:
        return result
    previous_statuses = {
        int(order["order_id"]): order.get("status")
        for order in service.state["orders"]
    }
    result["order"] = service.advance(
        workers=workers,
        cycle=world.get("cycle", 0),
    )
    if (
        result["order"] is not None
        and result["order"].get("status") == "completed"
        and previous_statuses.get(int(result["order"]["order_id"])) != "completed"
    ):
        recipe = service.catalog.recipe(result["order"]["recipe_id"])
        metrics.record_material("orders_completed")
        for produced_good_id, produced_quantity in recipe["outputs"].items():
            metrics.record_material(
                "produced", produced_quantity, good_id=produced_good_id
            )
        from core.artifacts import promote_completed_order
        result["artifacts"] = promote_completed_order(
            world,
            settlement,
            result["order"],
            recipe,
            config,
        )
    result["infrastructure"] = infrastructure.install_available(
        cycle=world.get("cycle", 0)
    )
    for infrastructure_id, quantity in result["infrastructure"].items():
        metrics.record_material(
            "infrastructure_built", quantity, good_id=infrastructure_id
        )
    return result