"""Climat headless, saisonnier et retrocompatible."""

from copy import deepcopy
import math


SEASONS = ("winter", "spring", "summer", "autumn")


class ClimateSystem:
    """Calcule le climat courant a partir de l'etat persistant du monde."""

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        cycle = int(world.get("cycle", 0))
        season_index = (cycle % 12) // 3
        defaults = {
            "season": SEASONS[season_index],
            "season_index": season_index,
            "temperature_anomaly": 0.0,
            "precipitation_anomaly": 0.0,
            "drought_severity": 0.0,
            "flood_severity": 0.0,
            "last_update_cycle": cycle,
        }
        state = world.get("climate")
        if not isinstance(state, dict):
            state = {}
            world["climate"] = state
        for key, value in defaults.items():
            state.setdefault(key, value)
        self.state = state

    @property
    def settings(self):
        section = self.config.get("climate", {})
        return section if isinstance(section, dict) else {}

    @property
    def enabled(self):
        return self.settings.get("enabled") is True

    def advance(self):
        cycle = int(self.world.get("cycle", 0))
        season_index = (cycle % 12) // 3
        previous_cycle = int(self.state.get("last_update_cycle", cycle))
        if cycle != previous_cycle:
            self.state["temperature_anomaly"] *= float(
                self.settings.get("temperature_anomaly_decay", 1.0)
            )
            self.state["precipitation_anomaly"] *= float(
                self.settings.get("precipitation_anomaly_decay", 1.0)
            )
            hazard_decay = float(self.settings.get("hazard_decay", 1.0))
            self.state["drought_severity"] *= hazard_decay
            self.state["flood_severity"] *= hazard_decay
            self._maybe_trigger_anomaly(cycle)
        self.state["season"] = SEASONS[season_index]
        self.state["season_index"] = season_index
        self.state["last_update_cycle"] = cycle
        return self.snapshot()

    def _maybe_trigger_anomaly(self, cycle):
        if not self.enabled:
            return
        chance = float(self.settings.get("anomaly_chance", 0.0))
        if chance <= 0:
            return

        from core.logger import GameLogger
        from core.random_service import RandomService
        from core.translator import Translator

        if RandomService.random() >= chance:
            return
        anomaly = RandomService.choice(("drought", "flood", "heatwave", "cold_snap"))
        minimum = float(self.settings.get("anomaly_min_severity", 0.2))
        maximum = float(self.settings.get("anomaly_max_severity", 0.6))
        severity = _clamp(RandomService.uniform(minimum, maximum), 0.0, 1.0)
        if anomaly == "drought":
            self.state["drought_severity"] = max(self.state["drought_severity"], severity)
            self.state["flood_severity"] = 0.0
            self.state["precipitation_anomaly"] -= severity * 0.5
        elif anomaly == "flood":
            self.state["flood_severity"] = max(self.state["flood_severity"], severity)
            self.state["drought_severity"] = 0.0
            self.state["precipitation_anomaly"] += severity * 0.5
        elif anomaly == "heatwave":
            self.state["temperature_anomaly"] += severity * 0.5
        else:
            self.state["temperature_anomaly"] -= severity * 0.5
        self.state["last_anomaly"] = anomaly
        self.state["last_anomaly_cycle"] = int(cycle)
        GameLogger.log(
            Translator.translate(f"events.climate_{anomaly}", severity=round(severity * 100)),
            category="climate",
        )

    def temperature_at(self, x, y):
        width = max(1, int(self.world["width"]))
        height = max(1, int(self.world["height"]))
        elevation = float(self.world["elev"][y][x])
        middle = height / 2.0
        latitude = abs(y - middle) / max(middle, 1.0)
        equatorial_warmth = 1.0 - min(1.0, latitude)
        lapse = float(self.settings.get("altitude_lapse_rate", 0.6))
        amplitude = float(self.settings.get("seasonal_amplitude", 0.2))
        month = int(self.world.get("cycle", 0)) % 12
        seasonal_wave = -math.cos((month / 12.0) * 2.0 * math.pi)
        if y < middle:
            hemisphere = 1.0
        elif y > middle:
            hemisphere = -1.0
        else:
            hemisphere = 0.0
        anomaly = float(self.state.get("temperature_anomaly", 0.0))
        return equatorial_warmth - elevation * lapse + seasonal_wave * amplitude * hemisphere + anomaly

    def moisture_at(self, x, y):
        base = float(self.settings.get("base_humidity", 0.5))
        river_bonus = 0.0
        if float(self.world["riv"][y][x]) > 0:
            river_bonus = float(self.settings.get("river_humidity_bonus", 0.25))
        precipitation = float(self.state.get("precipitation_anomaly", 0.0))
        drought = float(self.state.get("drought_severity", 0.0))
        flood = float(self.state.get("flood_severity", 0.0))
        return _clamp(base + river_bonus + precipitation - drought + flood, 0.0, 1.0)

    def snapshot(self):
        return deepcopy(self.state)


def climate_enabled(config):
    section = config.get("climate", {}) if isinstance(config, dict) else {}
    return isinstance(section, dict) and section.get("enabled") is True


def ecosystem_productivity(world, config, x, y):
    """Multiplicateur local de ressources, neutre quand le climat est inactif."""
    if not climate_enabled(config):
        return 1.0

    climate = ClimateSystem(world, config)
    temperature = climate.temperature_at(x, y)
    moisture = climate.moisture_at(x, y)
    temperature_score = _clamp(1.0 - abs(temperature - 0.6) / 0.6, 0.0, 1.0)
    moisture_score = _clamp(1.0 - abs(moisture - 0.6) / 0.6, 0.0, 1.0)
    drought = _clamp(float(climate.state.get("drought_severity", 0.0)), 0.0, 1.0)
    flood = _clamp(float(climate.state.get("flood_severity", 0.0)), 0.0, 1.0)
    hazard_factor = max(0.2, 1.0 - drought - flood * 0.5)
    return _clamp(
        (0.5 + (temperature_score + moisture_score) / 2.0) * hazard_factor,
        0.2,
        1.5,
    )


def agriculture_yield_multiplier(world, config, x, y):
    """Expose explicitement le contrat agricole du climat."""
    return ecosystem_productivity(world, config, x, y)


def habitat_suitability(world, config, species_data, x, y):
    """Valide les bornes climatiques optionnelles d'une espece."""
    habitat = species_data.get("habitat", {}) if isinstance(species_data, dict) else {}
    if not climate_enabled(config) or not isinstance(habitat, dict) or not habitat:
        return 1.0

    climate = ClimateSystem(world, config)
    temperature = climate.temperature_at(x, y)
    moisture = climate.moisture_at(x, y)
    bounds = (
        ("temperature_min", temperature, lambda value, limit: value >= limit),
        ("temperature_max", temperature, lambda value, limit: value <= limit),
        ("moisture_min", moisture, lambda value, limit: value >= limit),
        ("moisture_max", moisture, lambda value, limit: value <= limit),
    )
    for key, value, predicate in bounds:
        if key in habitat and not predicate(value, float(habitat[key])):
            return 0.0
    return 1.0

def biome_at(x, y, elevation, world, config):
    """Renvoie le biome logique d'une tuile."""
    if not climate_enabled(config):
        return legacy_biome_at(
            x,
            y,
            elevation,
            int(world.get("cycle", 0)),
            int(world["width"]),
            int(world["height"]),
            config,
        )

    climate = ClimateSystem(world, config)
    temperature = climate.temperature_at(x, y)
    moisture = climate.moisture_at(x, y)
    biomes = config.get("biomes", {})
    water = config.get("water", {})
    h = elevation

    if h > 0.90:
        return biomes.get("volcano", "🌋")
    if h > 0.85 or temperature < 0.05:
        return biomes.get("peak", "❄️")
    if h > 0.55:
        return biomes.get("high_mountain", "🏔️")
    if h > 0.35:
        return biomes.get("mountain", "⛰️")
    if h < -0.15:
        return water.get("ocean", "🌊")
    if h < 0:
        return water.get("shore", "💧")
    if h < 0.05:
        return biomes.get("sand", "🏖️")
    if temperature < 0.15:
        return biomes.get("glaciated", "❄️")
    if temperature < 0.3:
        return biomes.get("tundra", biomes.get("boreal_forest", "🌲"))
    if moisture < 0.18:
        return biomes.get("desert", "🏜️")
    if moisture < 0.28:
        return biomes.get("cactus", biomes.get("grassland", "🌵"))
    if temperature > 0.7 and moisture > 0.55:
        return biomes.get("tropical_forest", "🌴")
    if temperature < 0.5:
        return biomes.get("boreal_forest", "🌲")
    if moisture > 0.55:
        return biomes.get("temperate_forest", "🌳")
    return biomes.get("grassland", "🌿")


def legacy_biome_at(x, y, h, cycle, width, height, config):
    """Formule historique extraite du rendu sans changement de seuils."""
    biomes = config.get("biomes", {})
    water = config.get("water", {})
    half_height = height // 2
    dist_to_equator = (
        abs(y - half_height) / half_height if half_height else 0.0
    )
    tilt = math.sin(cycle * 0.15)
    temp = (
        dist_to_equator * 0.6
        + tilt * (y / height - 0.5) * 0.5
        + h * 0.4
    )

    if h > 0.90:
        return biomes.get("volcano", "🌋")
    if h > 0.85 or temp > 0.8:
        return biomes.get("peak", "❄️")
    if h > 0.55:
        return biomes.get("high_mountain", "🏔️")
    if h > 0.35:
        return biomes.get("mountain", "⛰️")
    if h < -0.15:
        return water.get("ocean", "🌊")
    if h < 0:
        return water.get("shore", "💧")
    if h < 0.05:
        return biomes.get("sand", "🏖️")
    if temp > 0.65:
        return (
            biomes.get("boreal_forest", "🌲")
            if h > 0.2
            else biomes.get("glaciated", "❄️")
        )
    if temp > 0.45:
        if h > 0.2 and 0.48 < temp < 0.55:
            return biomes.get("autumn_forest", "🍂")
        return biomes.get("temperate_forest", "🌳")
    if temp < 0.25 and h > 0.12:
        return biomes.get("tropical_forest", "🌴")
    return biomes.get("grassland", "🌿")


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))