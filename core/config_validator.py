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
