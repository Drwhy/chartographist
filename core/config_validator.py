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
