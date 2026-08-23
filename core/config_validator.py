"""Validation structurelle rétrocompatible des templates de simulation."""


REQUIRED_SECTIONS = {
    "world_name": str,
    "water": dict,
    "biomes": dict,
    "cultures": list,
    "fauna": list,
    "special": dict,
}

OPTIONAL_SECTION_TYPES = {
    "species": dict,
    "fauna_archetypes": dict,
    "domains": dict,
    "influence_decay": (int, float),
    "initial_cities": int,
    "max_fauna": int,
    "economy": dict,
    "diplomacy": dict,
    "climate": dict,
    "scenario": dict,
    "active_mods": list,
    "ecology": dict,
    "food_balance": dict,
    "resources": dict,
    "characters": dict,
    "materials": dict,
}


class ConfigValidationError(ValueError):
    """Signale une configuration dont la structure ne peut pas être simulée."""

    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__(", ".join(self.errors))


def validate_config(config):
    """
    Valide uniquement les contrats indispensables et les types des extensions connues.

    Les clés supplémentaires restent autorisées afin de préserver les anciens templates
    et de permettre des extensions data-driven sans modifier ce validateur.
    """
    if not isinstance(config, dict):
        raise ConfigValidationError(["type:root:dict"])

    errors = []
    for key, expected_type in REQUIRED_SECTIONS.items():
        if key not in config:
            errors.append(f"missing:{key}")
        elif not isinstance(config[key], expected_type):
            errors.append(f"type:{key}:{expected_type.__name__}")

    for key, expected_type in OPTIONAL_SECTION_TYPES.items():
        if key in config and not isinstance(config[key], expected_type):
            if isinstance(expected_type, tuple):
                type_name = "|".join(item.__name__ for item in expected_type)
            else:
                type_name = expected_type.__name__
            errors.append(f"type:{key}:{type_name}")

    economy = config.get("economy")
    if isinstance(economy, dict):
        enabled = economy.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:economy.enabled:bool")

        numeric_keys = (
            "initial_treasury",
            "base_food_price",
            "min_food_price",
            "max_food_price",
            "food_reserve",
            "trade_capacity",
            "settler_treasury_cost",
            "transport_cost_per_tile",
            "risk_cost_multiplier",
        )
        for key in numeric_keys:
            value = economy.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                errors.append(f"type:economy.{key}:int|float")

        capacity = economy.get("trade_capacity")
        if isinstance(capacity, (int, float)) and not isinstance(capacity, bool) and capacity <= 0:
            errors.append("range:economy.trade_capacity:positive")
        reserve = economy.get("food_reserve")
        if isinstance(reserve, (int, float)) and not isinstance(reserve, bool) and reserve < 0:
            errors.append("range:economy.food_reserve:non_negative")
        for key in ("transport_cost_per_tile", "risk_cost_multiplier"):
            value = economy.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and value < 0
            ):
                errors.append(f"range:economy.{key}:non_negative")
        for key in ("initial_treasury", "settler_treasury_cost"):
            value = economy.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0:
                errors.append(f"range:economy.{key}:non_negative")
        for key in ("base_food_price", "min_food_price", "max_food_price"):
            value = economy.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value <= 0:
                errors.append(f"range:economy.{key}:positive")
        minimum = economy.get("min_food_price")
        maximum = economy.get("max_food_price")
        if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)) and minimum > maximum:
            errors.append("range:economy.food_price_bounds")

    diplomacy = config.get("diplomacy")
    if isinstance(diplomacy, dict):
        enabled = diplomacy.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:diplomacy.enabled:bool")

        numeric_keys = (
            "trade_trust_gain",
            "trade_tension_relief",
            "trade_interdependence_gain",
            "trade_pact_threshold",
            "alliance_threshold",
            "hostility_threshold",
            "war_threshold",
            "truce_duration",
            "war_min_duration",
            "war_exhaustion_rate",
            "trade_pact_capacity_multiplier",
            "alliance_aid_food",
            "alliance_aid_reserve",
        )
        for key in numeric_keys:
            value = diplomacy.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:diplomacy.{key}:int|float")

        for key in (
            "trade_trust_gain",
            "trade_tension_relief",
            "trade_interdependence_gain",
            "war_exhaustion_rate",
            "alliance_aid_food",
            "alliance_aid_reserve",
        ):
            value = diplomacy.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and value < 0
            ):
                errors.append(f"range:diplomacy.{key}:non_negative")

        for key in ("truce_duration", "war_min_duration"):
            value = diplomacy.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and value <= 0
            ):
                errors.append(f"range:diplomacy.{key}:positive")

        multiplier = diplomacy.get("trade_pact_capacity_multiplier")
        if (
            isinstance(multiplier, (int, float))
            and not isinstance(multiplier, bool)
            and multiplier < 1
        ):
            errors.append(
                "range:diplomacy.trade_pact_capacity_multiplier:min_1"
            )

        for key in (
            "trade_pact_threshold",
            "alliance_threshold",
            "hostility_threshold",
            "war_threshold",
        ):
            value = diplomacy.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and not 0 <= value <= 100
            ):
                errors.append(f"range:diplomacy.{key}:0_100")

        pact = diplomacy.get("trade_pact_threshold")
        alliance = diplomacy.get("alliance_threshold")
        if (
            isinstance(pact, (int, float))
            and not isinstance(pact, bool)
            and isinstance(alliance, (int, float))
            and not isinstance(alliance, bool)
            and alliance < pact
        ):
            errors.append(
                "range:diplomacy.alliance_threshold:gte_trade_pact_threshold"
            )

    climate = config.get("climate")
    if isinstance(climate, dict):
        enabled = climate.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:climate.enabled:bool")

        numeric_keys = (
            "seasonal_amplitude",
            "altitude_lapse_rate",
            "base_humidity",
            "river_humidity_bonus",
            "temperature_anomaly_decay",
            "precipitation_anomaly_decay",
            "hazard_decay",
            "anomaly_chance",
            "anomaly_min_severity",
            "anomaly_max_severity",
        )
        for key in numeric_keys:
            value = climate.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:climate.{key}:int|float")

        for key in (
            "base_humidity",
            "temperature_anomaly_decay",
            "precipitation_anomaly_decay",
            "hazard_decay",
            "anomaly_chance",
            "anomaly_min_severity",
            "anomaly_max_severity",
        ):
            value = climate.get(key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and not 0 <= value <= 1
            ):
                errors.append(f"range:climate.{key}:0_1")

        minimum = climate.get("anomaly_min_severity")
        maximum = climate.get("anomaly_max_severity")
        if (
            isinstance(minimum, (int, float))
            and not isinstance(minimum, bool)
            and isinstance(maximum, (int, float))
            and not isinstance(maximum, bool)
            and minimum > maximum
        ):
            errors.append("range:climate.anomaly_severity_bounds")
    scenario = config.get("scenario")
    if isinstance(scenario, dict):
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            errors.append("missing:scenario.id")
        seen_condition_ids = set()
        for section in ("objectives", "defeat_conditions"):
            conditions = scenario.get(section, [])
            if not isinstance(conditions, list):
                errors.append(f"type:scenario.{section}:list")
                continue
            for index, condition in enumerate(conditions):
                path = f"scenario.{section}[{index}]"
                if not isinstance(condition, dict):
                    errors.append(f"type:{path}:dict")
                    continue
                condition_id = condition.get("id")
                if not isinstance(condition_id, str) or not condition_id:
                    errors.append(f"missing:{path}.id")
                elif condition_id in seen_condition_ids:
                    errors.append(f"duplicate:scenario.condition_id:{condition_id}")
                else:
                    seen_condition_ids.add(condition_id)
                if condition.get("metric") not in {"cycle", "population", "settlements", "fauna", "treasury"}:
                    errors.append(f"value:{path}.metric")
                if condition.get("operator") not in {">=", "<=", ">", "<"}:
                    errors.append(f"value:{path}.operator")
                target = condition.get("target")
                if isinstance(target, bool) or not isinstance(target, (int, float)):
                    errors.append(f"type:{path}.target:int|float")
    resources = config.get("resources")
    if isinstance(resources, dict):
        enabled = resources.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:resources.enabled:bool")
        interval = resources.get("regeneration_interval")
        if interval is not None:
            if isinstance(interval, bool) or not isinstance(interval, int):
                errors.append("type:resources.regeneration_interval:int")
            elif interval <= 0:
                errors.append("range:resources.regeneration_interval:positive")
        for key in ("biomass_capacity_scale", "fish_capacity_scale"):
            value = resources.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"type:resources.{key}:int|float")
            elif value <= 0:
                errors.append(f"range:resources.{key}:positive")
        minimum_birth_resource = resources.get("minimum_birth_resource")
        if minimum_birth_resource is not None:
            if isinstance(minimum_birth_resource, bool) or not isinstance(
                minimum_birth_resource, (int, float)
            ):
                errors.append("type:resources.minimum_birth_resource:int|float")
            elif minimum_birth_resource < 0:
                errors.append("range:resources.minimum_birth_resource:nonnegative")
        for key in (
            "biomass_regeneration_rate",
            "soil_regeneration_rate",
            "water_regeneration_rate",
            "fish_regeneration_rate",
            "forest_regeneration_rate",
            "winter_mortality_rate",
            "drought_pressure",
            "flood_recovery",
            "agriculture_soil_cost",
            "agriculture_min_support",
            "fire_min_forest_ratio",
            "fire_max_moisture",
        ):
            value = resources.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"type:resources.{key}:int|float")
            elif not 0 <= value <= 1:
                errors.append(f"range:resources.{key}:0_1")

    ecology = config.get("ecology")
    if isinstance(ecology, dict):
        limits = ecology.get("population_limits")
        if limits is not None and not isinstance(limits, dict):
            errors.append("type:ecology.population_limits:dict")
        elif isinstance(limits, dict):
            enabled = limits.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                errors.append("type:ecology.population_limits.enabled:bool")
            global_capacity = limits.get("global")
            if global_capacity is not None:
                if isinstance(global_capacity, bool) or not isinstance(global_capacity, int):
                    errors.append("type:ecology.population_limits.global:int")
                elif global_capacity < 0:
                    errors.append("range:ecology.population_limits.global:non_negative")
            for section_name in ("per_species", "per_biome"):
                section = limits.get(section_name)
                if section is not None and not isinstance(section, dict):
                    errors.append(f"type:ecology.population_limits.{section_name}:dict")
                    continue
                if isinstance(section, dict):
                    for key, value in section.items():
                        path = f"ecology.population_limits.{section_name}.{key}"
                        if isinstance(value, bool) or not isinstance(value, int):
                            errors.append(f"type:{path}:int")
                        elif value < 0:
                            errors.append(f"range:{path}:non_negative")

    food_balance = config.get("food_balance")
    if isinstance(food_balance, dict):
        enabled = food_balance.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:food_balance.enabled:bool")
        labor_yield = food_balance.get("generic_labor_yield")
        if labor_yield is not None:
            if isinstance(labor_yield, bool) or not isinstance(labor_yield, int):
                errors.append("type:food_balance.generic_labor_yield:int")
            elif labor_yield < 0:
                errors.append("range:food_balance.generic_labor_yield:non_negative")
        loss_rate = food_balance.get("storage_loss_rate")
        if loss_rate is not None:
            if isinstance(loss_rate, bool) or not isinstance(loss_rate, (int, float)):
                errors.append("type:food_balance.storage_loss_rate:int|float")
            elif not 0 <= loss_rate <= 1:
                errors.append("range:food_balance.storage_loss_rate:0_1")

        window = food_balance.get("specialization_window")
        if window is not None:
            if isinstance(window, bool) or not isinstance(window, int):
                errors.append("type:food_balance.specialization_window:int")
            elif window < 2:
                errors.append("range:food_balance.specialization_window:min_2")
        specialization_ratio = food_balance.get("specialization_food_ratio")
        if specialization_ratio is not None:
            if isinstance(specialization_ratio, bool) or not isinstance(
                specialization_ratio, (int, float)
            ):
                errors.append("type:food_balance.specialization_food_ratio:int|float")
            elif not 0 <= specialization_ratio <= 1:
                errors.append("range:food_balance.specialization_food_ratio:0_1")

    characters = config.get("characters")
    if isinstance(characters, dict):
        enabled = characters.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:characters.enabled:bool")
        for key in ("memory_limit", "decision_interval"):
            value = characters.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:characters.{key}:int")
            elif value <= 0:
                errors.append(f"range:characters.{key}:positive")
        decay = characters.get("memory_decay_rate")
        if decay is not None:
            if isinstance(decay, bool) or not isinstance(decay, (int, float)):
                errors.append("type:characters.memory_decay_rate:int|float")
            elif not 0 <= decay <= 1:
                errors.append("range:characters.memory_decay_rate:0_1")
        threshold = characters.get("notability_threshold")
        if threshold is not None:
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
                errors.append("type:characters.notability_threshold:int|float")
            elif threshold < 0:
                errors.append("range:characters.notability_threshold:nonnegative")
        growth = characters.get("need_growth")
        if growth is not None and not isinstance(growth, dict):
            errors.append("type:characters.need_growth:dict")
        elif isinstance(growth, dict):
            for key, value in growth.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(f"type:characters.need_growth.{key}:int|float")
                elif value < 0:
                    errors.append(f"range:characters.need_growth.{key}:nonnegative")

    materials = config.get("materials")
    if isinstance(materials, dict):
        from core.materials import catalog_validation_errors

        errors.extend(catalog_validation_errors(materials))
    cultures = config.get("cultures")
    if isinstance(cultures, list):
        if not cultures:
            errors.append("empty:cultures")
        for index, culture in enumerate(cultures):
            if not isinstance(culture, dict):
                errors.append(f"type:cultures[{index}]:dict")
            elif not isinstance(culture.get("name"), str) or not culture["name"]:
                errors.append(f"missing:cultures[{index}].name")

    if errors:
        raise ConfigValidationError(errors)
    return config
