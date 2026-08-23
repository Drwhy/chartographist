"""Optional shared carrying capacities for fauna spawning and reproduction."""


def population_limits(config):
    ecology = config.get("ecology", {}) if isinstance(config, dict) else {}
    if not isinstance(ecology, dict):
        return {}
    limits = ecology.get("population_limits", {})
    return limits if isinstance(limits, dict) else {}


def population_limits_enabled(config):
    return population_limits(config).get("enabled") is True


def _active_animals(world):
    from entities.species.animal.base import Animal
    return [
        entity
        for entity in world.get("entities", ())
        if isinstance(entity, Animal) and not getattr(entity, "is_expired", False)
    ]


def _species_name(species_data):
    return str(species_data.get("species", "")) if isinstance(species_data, dict) else ""


def _biome_identifier(world, config, x, y):
    from core.climate import biome_at

    value = biome_at(x, y, float(world["elev"][y][x]), world, config)
    for section_name in ("biomes", "water"):
        section = config.get(section_name, {}) if isinstance(config, dict) else {}
        if isinstance(section, dict):
            for key, configured_value in section.items():
                if configured_value == value:
                    return key
    return str(value)


def can_add_fauna(world, config, species_data, x=None, y=None):
    """Return whether one individual fits all enabled carrying capacities."""
    if not population_limits_enabled(config):
        return True

    limits = population_limits(config)
    animals = _active_animals(world)
    global_capacity = limits.get("global", config.get("max_fauna", 20))
    if len(animals) >= max(0, int(global_capacity)):
        return False

    species = _species_name(species_data)
    per_species = limits.get("per_species", {})
    if isinstance(per_species, dict) and species in per_species:
        species_count = sum(getattr(animal, "species", None) == species for animal in animals)
        if species_count >= max(0, int(per_species[species])):
            return False

    per_biome = limits.get("per_biome", {})
    if x is not None and y is not None and isinstance(per_biome, dict):
        biome = _biome_identifier(world, config, x, y)
        if biome in per_biome:
            biome_count = sum(
                _biome_identifier(world, config, animal.x, animal.y) == biome
                for animal in animals
            )
            if biome_count >= max(0, int(per_biome[biome])):
                return False

    if x is not None and y is not None:
        from core.resources import (
            ResourceSystem,
            resources_enabled,
            resources_settings,
        )
        if resources_enabled(config):
            diet = str(species_data.get("diet", "carnivore"))
            locomotion = str(species_data.get("locomotion", "land"))
            resource_name = None
            if locomotion == "aquatic":
                resource_name = "fish_stock"
            elif diet != "carnivore":
                resource_name = "biomass"
            if resource_name is not None:
                minimum = max(
                    0.0,
                    float(
                        resources_settings(config).get(
                            "minimum_birth_resource", 1.0
                        )
                    ),
                )
                if ResourceSystem(world, config).available(
                    resource_name, x, y
                ) < minimum:
                    return False

    return True
