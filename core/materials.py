"""Data-driven material, item and recipe catalog for optional production chains."""

from copy import deepcopy


SPATIAL_RESOURCE_NAMES = {
    "biomass",
    "soil_fertility",
    "surface_water",
    "fish_stock",
    "forest_cover",
}


class MaterialCatalogError(ValueError):
    """Raised when a material catalog cannot satisfy its structural contracts."""

    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__(", ".join(self.errors))


def _is_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _validate_positive_number(value, path, errors):
    if not _is_number(value):
        errors.append(f"type:{path}:int|float")
    elif value <= 0:
        errors.append(f"range:{path}:positive")


def _validate_rate(value, path, errors):
    if not _is_number(value):
        errors.append(f"type:{path}:int|float")
    elif not 0 <= value <= 1:
        errors.append(f"range:{path}:0_1")


def catalog_validation_errors(section):
    """Return stable validation codes without mutating the supplied definition."""
    if section is None:
        return []
    if not isinstance(section, dict):
        return []

    errors = []
    enabled = section.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append("type:materials.enabled:bool")
    capacity = section.get("stockpile_capacity")
    if capacity is not None:
        _validate_positive_number(capacity, "materials.stockpile_capacity", errors)

    goods = {}
    item_ids = set()
    for collection_name in ("resources", "items"):
        definitions = section.get(collection_name, [])
        if not isinstance(definitions, list):
            errors.append(f"type:materials.{collection_name}:list")
            continue
        for index, definition in enumerate(definitions):
            prefix = f"materials.{collection_name}[{index}]"
            if not isinstance(definition, dict):
                errors.append(f"type:{prefix}:dict")
                continue
            identifier = definition.get("id")
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"missing:{prefix}.id")
                continue
            if identifier in goods:
                errors.append(f"duplicate:materials.good:{identifier}")
            else:
                goods[identifier] = collection_name
            if collection_name == "items":
                item_ids.add(identifier)
            _validate_positive_number(
                definition.get("unit_weight"),
                f"materials.{collection_name}.{identifier}.unit_weight",
                errors,
            )
            _validate_rate(
                definition.get("decay_rate"),
                f"materials.{collection_name}.{identifier}.decay_rate",
                errors,
            )
            if collection_name == "resources":
                source = definition.get("source")
                if source is not None and not isinstance(source, dict):
                    errors.append(
                        f"type:materials.resources.{identifier}.source:dict"
                    )
                elif isinstance(source, dict):
                    spatial_name = source.get("spatial_resource")
                    if spatial_name not in SPATIAL_RESOURCE_NAMES:
                        errors.append(
                            "reference:materials.resources."
                            f"{identifier}.source.spatial_resource:{spatial_name}"
                        )
                    _validate_positive_number(
                        source.get("stock_per_unit"),
                        f"materials.resources.{identifier}.source.stock_per_unit",
                        errors,
                    )
                    _validate_positive_number(
                        source.get("max_per_cycle"),
                        f"materials.resources.{identifier}.source.max_per_cycle",
                        errors,
                    )
                    _validate_rate(
                        source.get("minimum_ratio"),
                        f"materials.resources.{identifier}.source.minimum_ratio",
                        errors,
                    )
                    skill = source.get("skill")
                    if skill is not None and (
                        not isinstance(skill, str) or not skill
                    ):
                        errors.append(
                            f"type:materials.resources.{identifier}.source.skill:str"
                        )
            if collection_name == "items":
                value = definition.get("base_value")
                if not _is_number(value):
                    errors.append(
                        f"type:materials.items.{identifier}.base_value:int|float"
                    )
                elif value < 0:
                    errors.append(
                        f"range:materials.items.{identifier}.base_value:nonnegative"
                    )
                durability = definition.get("durability")
                if durability is not None:
                    _validate_positive_number(
                        durability,
                        f"materials.items.{identifier}.durability",
                        errors,
                    )

    initial_stock = section.get("initial_stock", {})
    if not isinstance(initial_stock, dict):
        errors.append("type:materials.initial_stock:dict")
    else:
        for good_id, quantity in initial_stock.items():
            if good_id not in goods:
                errors.append(f"reference:materials.initial_stock:{good_id}")
            if not _is_number(quantity):
                errors.append(f"type:materials.initial_stock.{good_id}:int|float")
            elif quantity < 0:
                errors.append(f"range:materials.initial_stock.{good_id}:nonnegative")
    targets = section.get("targets", {})
    if not isinstance(targets, dict):
        errors.append("type:materials.targets:dict")
    else:
        for good_id, target in targets.items():
            if good_id not in goods:
                errors.append(f"reference:materials.targets:{good_id}")
            if not _is_number(target):
                errors.append(f"type:materials.targets.{good_id}:int|float")
            elif target < 0:
                errors.append(f"range:materials.targets.{good_id}:nonnegative")
    trade_reserve = section.get("trade_reserve", {})
    if not isinstance(trade_reserve, dict):
        errors.append("type:materials.trade_reserve:dict")
    else:
        for good_id, reserve in trade_reserve.items():
            if good_id not in goods:
                errors.append(f"reference:materials.trade_reserve:{good_id}")
            if not _is_number(reserve):
                errors.append(f"type:materials.trade_reserve.{good_id}:int|float")
            elif reserve < 0:
                errors.append(f"range:materials.trade_reserve.{good_id}:nonnegative")
    recipes = section.get("recipes", [])
    if not isinstance(recipes, list):
        errors.append("type:materials.recipes:list")
        return errors
    recipe_ids = set()
    for index, recipe in enumerate(recipes):
        prefix = f"materials.recipes[{index}]"
        if not isinstance(recipe, dict):
            errors.append(f"type:{prefix}:dict")
            continue
        identifier = recipe.get("id")
        if not isinstance(identifier, str) or not identifier:
            errors.append(f"missing:{prefix}.id")
            continue
        if identifier in recipe_ids:
            errors.append(f"duplicate:materials.recipe:{identifier}")
        recipe_ids.add(identifier)
        cycles = recipe.get("cycles")
        if isinstance(cycles, bool) or not isinstance(cycles, int):
            errors.append(f"type:materials.recipes.{identifier}.cycles:int")
        elif cycles <= 0:
            errors.append(f"range:materials.recipes.{identifier}.cycles:positive")
        _validate_positive_number(
            recipe.get("labor"),
            f"materials.recipes.{identifier}.labor",
            errors,
        )
        skill = recipe.get("skill")
        if not isinstance(skill, str) or not skill:
            errors.append(f"missing:materials.recipes.{identifier}.skill")
        for field in ("inputs", "outputs"):
            quantities = recipe.get(field)
            if not isinstance(quantities, dict):
                errors.append(f"type:materials.recipes.{identifier}.{field}:dict")
                continue
            if not quantities:
                errors.append(f"empty:materials.recipes.{identifier}.{field}")
            for good_id, quantity in quantities.items():
                if good_id not in goods:
                    errors.append(
                        f"reference:materials.recipes.{identifier}.{field}:{good_id}"
                    )
                _validate_positive_number(
                    quantity,
                    f"materials.recipes.{identifier}.{field}.{good_id}",
                    errors,
                )
        tools = recipe.get("tools", [])
        if not isinstance(tools, list):
            errors.append(f"type:materials.recipes.{identifier}.tools:list")
        else:
            for tool_id in tools:
                if not isinstance(tool_id, str) or tool_id not in item_ids:
                    errors.append(
                        f"reference:materials.recipes.{identifier}.tools:{tool_id}"
                    )
    infrastructures = section.get("infrastructures", [])
    if not isinstance(infrastructures, list):
        errors.append("type:materials.infrastructures:list")
    else:
        infrastructure_ids = set()
        for index, definition in enumerate(infrastructures):
            prefix = f"materials.infrastructures[{index}]"
            if not isinstance(definition, dict):
                errors.append(f"type:{prefix}:dict")
                continue
            identifier = definition.get("id")
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"missing:{prefix}.id")
                continue
            if identifier in infrastructure_ids:
                errors.append(
                    f"duplicate:materials.infrastructure:{identifier}"
                )
            infrastructure_ids.add(identifier)
            kit_good_id = definition.get("kit_good_id")
            if kit_good_id not in item_ids:
                errors.append(
                    "reference:materials.infrastructures."
                    f"{identifier}.kit_good_id:{kit_good_id}"
                )
            max_level = definition.get("max_level")
            if isinstance(max_level, bool) or not isinstance(max_level, int):
                errors.append(
                    f"type:materials.infrastructures.{identifier}.max_level:int"
                )
            elif max_level <= 0:
                errors.append(
                    f"range:materials.infrastructures.{identifier}.max_level:positive"
                )
            _validate_positive_number(
                definition.get("capacity_bonus"),
                f"materials.infrastructures.{identifier}.capacity_bonus",
                errors,
            )
    food_chain = section.get("food_chain")
    if food_chain is not None:
        if not isinstance(food_chain, dict):
            errors.append("type:materials.food_chain:dict")
        else:
            references = {
                "recipe_id": recipe_ids,
                "raw_good_id": set(goods),
                "ration_good_id": set(goods),
            }
            for key, identifiers in references.items():
                value = food_chain.get(key)
                if not isinstance(value, str) or value not in identifiers:
                    errors.append(
                        f"reference:materials.food_chain.{key}:{value}"
                    )
    return errors


class MaterialCatalog:
    """Own immutable catalog definitions and expose defensive snapshots."""

    def __init__(self, config):
        definition = config.get("materials") if isinstance(config, dict) else None
        self.definition = deepcopy(definition) if isinstance(definition, dict) else {}
        errors = catalog_validation_errors(self.definition)
        if errors:
            raise MaterialCatalogError(errors)
        self.enabled = bool(self.definition.get("enabled", False))
        self._resources = {
            value["id"]: deepcopy(value)
            for value in self.definition.get("resources", [])
        }
        self._items = {
            value["id"]: deepcopy(value)
            for value in self.definition.get("items", [])
        }
        self._recipes = {
            value["id"]: deepcopy(value)
            for value in self.definition.get("recipes", [])
        }

    def snapshot(self):
        return {
            "resources": deepcopy(list(self._resources.values())),
            "items": deepcopy(list(self._items.values())),
            "recipes": deepcopy(list(self._recipes.values())),
        }

    def resource(self, identifier):
        return deepcopy(self._resources[str(identifier)])

    def item(self, identifier):
        return deepcopy(self._items[str(identifier)])

    def recipe(self, identifier):
        return deepcopy(self._recipes[str(identifier)])

    def good(self, identifier):
        key = str(identifier)
        if key in self._resources:
            result = deepcopy(self._resources[key])
            result["kind"] = "resource"
            return result
        if key in self._items:
            result = deepcopy(self._items[key])
            result["kind"] = "item"
            return result
        raise KeyError(key)