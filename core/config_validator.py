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
    "politics": dict,
    "territory": dict,
    "pathfinding": dict,
    "migration": dict,
    "warfare": dict,
    "peace": dict,
    "history": dict,
    "sites": dict,
    "artifacts": dict,
    "legends": dict,
    "presentation": dict,
    "explanations": dict,
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
            "transport_loss_per_tile",
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
        transport_loss = economy.get("transport_loss_per_tile")
        if (
            isinstance(transport_loss, (int, float))
            and not isinstance(transport_loss, bool)
            and not 0 <= transport_loss <= 1
        ):
            errors.append("range:economy.transport_loss_per_tile:0_1")
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
        for key in ("memory_limit", "decision_interval", "cohort_decision_interval"):
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

    knowledge = config.get("knowledge")
    if isinstance(knowledge, dict):
        enabled = knowledge.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:knowledge.enabled:bool")
        for key in ("observation_interval", "max_facts"):
            value = knowledge.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:knowledge.{key}:int")
            elif value <= 0:
                errors.append(f"range:knowledge.{key}:positive")
        radius = knowledge.get("perception_radius")
        if radius is not None:
            if isinstance(radius, bool) or not isinstance(radius, (int, float)):
                errors.append("type:knowledge.perception_radius:int|float")
            elif radius < 0:
                errors.append("range:knowledge.perception_radius:non_negative")
        for key in (
            "reliability_decay",
            "transmission_decay",
            "distance_decay",
            "minimum_reliability",
        ):
            value = knowledge.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"type:knowledge.{key}:int|float")
            elif not 0 <= value <= 1:
                errors.append(f"range:knowledge.{key}:0_1")
    elif knowledge is not None:
        errors.append("type:knowledge:dict")

    politics = config.get("politics")
    if isinstance(politics, dict):
        enabled = politics.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:politics.enabled:bool")
        objectives = set()
        faction_ids = set()
        faction_types = politics.get("faction_types", [])
        if not isinstance(faction_types, list):
            errors.append("type:politics.faction_types:list")
        else:
            for index, definition in enumerate(faction_types):
                path = f"politics.faction_types[{index}]"
                if not isinstance(definition, dict):
                    errors.append(f"type:{path}:dict")
                    continue
                identifier = definition.get("id")
                if not isinstance(identifier, str) or not identifier:
                    errors.append(f"missing:{path}.id")
                elif identifier in faction_ids:
                    errors.append(f"duplicate:politics.faction_type:{identifier}")
                else:
                    faction_ids.add(identifier)
                if definition.get("source") not in {"profession", "faith", "household"}:
                    errors.append(f"value:{path}.source")
                for objective in (definition.get("objective"), definition.get("default_objective")):
                    if isinstance(objective, str) and objective:
                        objectives.add(objective)
                mapping = definition.get("objectives", {})
                if isinstance(mapping, dict):
                    objectives.update(value for value in mapping.values() if isinstance(value, str) and value)

        government_ids = set()
        governments = politics.get("governments", [])
        if not isinstance(governments, list):
            errors.append("type:politics.governments:list")
        else:
            for index, government in enumerate(governments):
                path = f"politics.governments[{index}]"
                if not isinstance(government, dict):
                    errors.append(f"type:{path}:dict")
                    continue
                identifier = government.get("id")
                if not isinstance(identifier, str) or not identifier:
                    errors.append(f"missing:{path}.id")
                elif identifier in government_ids:
                    errors.append(f"duplicate:politics.government:{identifier}")
                else:
                    government_ids.add(identifier)
                offices = government.get("offices", [])
                office_ids = set()
                if not isinstance(offices, list):
                    errors.append(f"type:{path}.offices:list")
                    continue
                for office in offices:
                    if not isinstance(office, dict):
                        errors.append(f"type:{path}.office:dict")
                        continue
                    office_id = office.get("id")
                    if office_id in office_ids:
                        errors.append(f"duplicate:politics.office:{office_id}")
                    elif isinstance(office_id, str) and office_id:
                        office_ids.add(office_id)
                head = government.get("head_office")
                if isinstance(head, str) and head and head not in office_ids:
                    errors.append(f"reference:{path}.head_office:{head}")
        default = politics.get("default_government")
        if isinstance(default, str) and default and default not in government_ids:
            errors.append(f"reference:politics.default_government:{default}")

        policy_ids = set()
        policies = politics.get("policies", [])
        if not isinstance(policies, list):
            errors.append("type:politics.policies:list")
        else:
            for index, policy in enumerate(policies):
                path = f"politics.policies[{index}]"
                if not isinstance(policy, dict):
                    errors.append(f"type:{path}:dict")
                    continue
                identifier = policy.get("id")
                if identifier in policy_ids:
                    errors.append(f"duplicate:politics.policy:{identifier}")
                elif isinstance(identifier, str) and identifier:
                    policy_ids.add(identifier)
                for interest in ("supports", "opposes"):
                    references = policy.get(interest, [])
                    if not isinstance(references, list):
                        errors.append(f"type:{path}.{interest}:list")
                        continue
                    for objective in references:
                        if objective not in objectives:
                            errors.append(f"reference:politics.policy.{identifier}.{interest}:{objective}")

    peace = config.get("peace")
    if isinstance(peace, dict):
        for key in ("enabled", "transfer_territory"):
            value = peace.get(key)
            if value is not None and not isinstance(value, bool):
                errors.append(f"type:peace.{key}:bool")
        maximum = peace.get("max_treaties")
        if maximum is not None and (
            isinstance(maximum, bool) or not isinstance(maximum, int)
        ):
            errors.append("type:peace.max_treaties:int")
        elif maximum is not None and maximum <= 0:
            errors.append("range:peace.max_treaties:positive")
        refugee_rate = peace.get("refugee_rate")
        if refugee_rate is not None and (
            isinstance(refugee_rate, bool)
            or not isinstance(refugee_rate, (int, float))
        ):
            errors.append("type:peace.refugee_rate:int|float")
        elif refugee_rate is not None and not 0 <= refugee_rate <= 1:
            errors.append("range:peace.refugee_rate:0_1")
        for key in (
            "tribute_food_ratio",
            "tribute_base",
            "commercial_rights",
            "postwar_tension",
        ):
            value = peace.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:peace.{key}:int|float")
            elif value is not None and value < 0:
                errors.append(f"range:peace.{key}:non_negative")

    history = config.get("history")
    if isinstance(history, dict):
        enabled = history.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:history.enabled:bool")
        for key in ("max_facts", "max_links"):
            value = history.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:history.{key}:int")
            elif value <= 0:
                errors.append(f"range:history.{key}:positive")

    warfare = config.get("warfare")
    if isinstance(warfare, dict):
        for key in ("enabled", "auto_declare"):
            value = warfare.get(key)
            if value is not None and not isinstance(value, bool):
                errors.append(f"type:warfare.{key}:bool")
        for key in (
            "advance_interval",
            "minimum_army",
            "engagement_interval",
            "truce_duration",
            "max_history",
        ):
            value = warfare.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:warfare.{key}:int")
            elif value <= 0:
                errors.append(f"range:warfare.{key}:positive")
        for key in (
            "levy_rate",
            "unsupplied_attrition",
            "casualty_rate",
            "prisoner_rate",
        ):
            value = warfare.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:warfare.{key}:int|float")
            elif value is not None and not 0 <= value <= 1:
                errors.append(f"range:warfare.{key}:0_1")
        for key in (
            "war_tension_threshold",
            "initial_morale",
            "command_base",
            "supply_per_soldier",
            "max_supply_cost",
            "unsupplied_morale_loss",
            "winter_supply_multiplier",
            "retreat_morale",
        ):
            value = warfare.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:warfare.{key}:int|float")
            elif value is not None and value < 0:
                errors.append(f"range:warfare.{key}:non_negative")

    migration = config.get("migration")
    if isinstance(migration, dict):
        enabled = migration.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:migration.enabled:bool")
        for key in (
            "advance_interval",
            "settlement_capacity",
            "cohort_size",
            "minimum_population",
            "max_history",
        ):
            value = migration.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:migration.{key}:int")
            elif key == "minimum_population" and value < 0:
                errors.append("range:migration.minimum_population:non_negative")
            elif key != "minimum_population" and value <= 0:
                errors.append(f"range:migration.{key}:positive")
        for key in ("integration_rate", "discrimination_penalty"):
            value = migration.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:migration.{key}:int|float")
            elif value is not None and not 0 <= value <= 1:
                errors.append(f"range:migration.{key}:0_1")
        for key in (
            "departure_threshold",
            "hunger_food_ratio",
            "hunger_weight",
            "war_weight",
            "climate_weight",
            "persecution_weight",
            "opportunity_departure_weight",
            "food_attractiveness",
            "capacity_attractiveness",
            "knowledge_bonus",
            "family_bonus",
            "distance_penalty",
        ):
            value = migration.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:migration.{key}:int|float")
            elif value is not None and value < 0:
                errors.append(f"range:migration.{key}:non_negative")

    pathfinding = config.get("pathfinding")
    if isinstance(pathfinding, dict):
        enabled = pathfinding.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:pathfinding.enabled:bool")
        diagonal = pathfinding.get("allow_diagonal")
        if diagonal is not None and not isinstance(diagonal, bool):
            errors.append("type:pathfinding.allow_diagonal:bool")
        for key in ("max_cache_entries", "max_expanded_nodes"):
            value = pathfinding.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:pathfinding.{key}:int")
            elif value <= 0:
                errors.append(f"range:pathfinding.{key}:positive")
        for key in (
            "base_cost",
            "elevation_weight",
            "road_multiplier",
            "weather_weight",
            "danger_weight",
            "unknown_multiplier",
        ):
            value = pathfinding.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"type:pathfinding.{key}:int|float")
            elif key in {"base_cost", "road_multiplier"} and value <= 0:
                errors.append(f"range:pathfinding.{key}:positive")
            elif key == "unknown_multiplier" and value < 1:
                errors.append("range:pathfinding.unknown_multiplier:at_least_one")
            elif value < 0:
                errors.append(f"range:pathfinding.{key}:non_negative")

    territory = config.get("territory")
    if isinstance(territory, dict):
        enabled = territory.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:territory.enabled:bool")
        for key in ("advance_interval", "max_radius"):
            value = territory.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:territory.{key}:int")
            elif value < (1 if key == "advance_interval" else 0):
                qualifier = "positive" if key == "advance_interval" else "non_negative"
                errors.append(f"range:territory.{key}:{qualifier}")
        for key in (
            "base_power",
            "population_scale",
            "distance_decay",
            "road_multiplier",
            "fortification_scale",
            "contest_margin",
            "strategic_resource_bonus",
            "territorial_tension",
        ):
            value = territory.get(key)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                errors.append(f"type:territory.{key}:int|float")
            elif value is not None and value < 0:
                errors.append(f"range:territory.{key}:non_negative")
        if not isinstance(territory.get("strategic_resources", []), list):
            errors.append("type:territory.strategic_resources:list")

    sites = config.get("sites")
    if isinstance(sites, dict):
        enabled = sites.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:sites.enabled:bool")
        for key in (
            "advance_interval",
            "max_sites",
            "max_history_per_site",
            "overgrow_cycles",
        ):
            value = sites.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:sites.{key}:int")
            elif value <= 0:
                errors.append(f"range:sites.{key}:positive")
        for symbol_key in ("symbols", "stage_symbols"):
            symbols = sites.get(symbol_key)
            if symbols is not None and not isinstance(symbols, dict):
                errors.append(f"type:sites.{symbol_key}:dict")
            elif isinstance(symbols, dict):
                for key, value in symbols.items():
                    if not isinstance(key, str) or not isinstance(value, str) or not value:
                        errors.append(f"type:sites.{symbol_key}:str_to_str")
                        break

    artifacts = config.get("artifacts")
    if isinstance(artifacts, dict):
        enabled = artifacts.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:artifacts.enabled:bool")
        for key in (
            "max_artifacts",
            "max_history_per_artifact",
            "max_promotions_per_order",
            "loot_per_engagement",
        ):
            value = artifacts.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:artifacts.{key}:int")
            elif value <= 0:
                errors.append(f"range:artifacts.{key}:positive")
        for key in (
            "promotion_quality",
            "renown_per_event",
            "max_renown",
            "prestige_per_renown",
        ):
            value = artifacts.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"type:artifacts.{key}:int|float")
            elif value < 0:
                errors.append(f"range:artifacts.{key}:non_negative")
        eligible = artifacts.get("eligible_items")
        if eligible is not None and (
            not isinstance(eligible, list)
            or any(not isinstance(value, str) or not value for value in eligible)
        ):
            errors.append("type:artifacts.eligible_items:list[str]")

    legends = config.get("legends")
    if isinstance(legends, dict):
        enabled = legends.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:legends.enabled:bool")
        for key in (
            "max_legends",
            "max_versions_per_legend",
            "max_history_per_legend",
            "advance_interval",
            "max_propagations_per_cycle",
        ):
            value = legends.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:legends.{key}:int")
            elif value <= 0:
                errors.append(f"range:legends.{key}:positive")
        for key in (
            "artifact_renown_threshold",
            "exploration_threshold",
            "war_threshold",
            "cult_threshold",
        ):
            value = legends.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"type:legends.{key}:int|float")
            elif value < 0:
                errors.append(f"range:legends.{key}:non_negative")
        reliability = legends.get("default_reliability")
        if reliability is not None:
            if (
                isinstance(reliability, bool)
                or not isinstance(reliability, (int, float))
            ):
                errors.append("type:legends.default_reliability:int|float")
            elif not 0 <= reliability <= 1:
                errors.append("range:legends.default_reliability:0_1")
        emphases = legends.get("culture_emphases")
        if emphases is not None and not isinstance(emphases, dict):
            errors.append("type:legends.culture_emphases:dict")
        elif isinstance(emphases, dict) and any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not value
            for key, value in emphases.items()
        ):
            errors.append("type:legends.culture_emphases:str_to_str")

    explanations = config.get("explanations")
    if isinstance(explanations, dict):
        enabled = explanations.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("type:explanations.enabled:bool")
        maximum = explanations.get("max_results")
        if maximum is not None:
            if isinstance(maximum, bool) or not isinstance(maximum, int):
                errors.append("type:explanations.max_results:int")
            elif maximum <= 0:
                errors.append("range:explanations.max_results:positive")
        hunger = explanations.get("hunger_ratio")
        if hunger is not None:
            if isinstance(hunger, bool) or not isinstance(hunger, (int, float)):
                errors.append("type:explanations.hunger_ratio:int|float")
            elif not 0 <= hunger <= 1:
                errors.append("range:explanations.hunger_ratio:0_1")

    presentation = config.get("presentation")
    if isinstance(presentation, dict):
        for key in ("max_logs", "max_delta_cells", "max_commands"):
            value = presentation.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"type:presentation.{key}:int")
            elif value <= 0:
                errors.append(f"range:presentation.{key}:positive")

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
