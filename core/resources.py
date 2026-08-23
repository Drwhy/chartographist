"""Deterministic spatial renewable resources for the simulation world."""

from copy import deepcopy
import math

from core.climate import ClimateSystem, climate_enabled


RESOURCE_NAMES = (
    "biomass",
    "soil_fertility",
    "surface_water",
    "fish_stock",
    "forest_cover",
)


def resources_settings(config):
    section = config.get("resources", {}) if isinstance(config, dict) else {}
    return section if isinstance(section, dict) else {}


def resources_enabled(config):
    return resources_settings(config).get("enabled") is True


def _clamp(value, minimum=0.0, maximum=1.0):
    if not math.isfinite(float(value)):
        return minimum
    return min(maximum, max(minimum, float(value)))


def _matrix(width, height, value=0.0):
    return [[float(value) for _ in range(width)] for _ in range(height)]


def _valid_matrix(value, width, height):
    return (
        isinstance(value, list)
        and len(value) == height
        and all(isinstance(row, list) and len(row) == width for row in value)
    )


class ResourceSystem:
    """Own, regenerate and expose compact serializable resource grids."""

    VERSION = 1

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        self.settings = resources_settings(self.config)
        existing = world.get("resources")
        existing_enabled = isinstance(existing, dict) and existing.get("enabled") is True
        self.enabled = resources_enabled(self.config) or existing_enabled

        if not self.enabled:
            state = existing if isinstance(existing, dict) else {}
            state.setdefault("version", self.VERSION)
            state["enabled"] = False
            state.setdefault("last_update_cycle", 0)
            state.setdefault("next_disturbance_id", 1)
            state.setdefault("disturbances", [])
            state["grids"] = {}
            world["resources"] = state
            self.state = state
            return

        if isinstance(existing, dict) and self._state_is_complete(existing):
            existing.setdefault("version", self.VERSION)
            existing["enabled"] = True
            existing.setdefault("last_update_cycle", 0)
            existing.setdefault("next_disturbance_id", 1)
            existing.setdefault("disturbances", [])
            self.state = existing
            return

        generated = self._generate_state()
        if isinstance(existing, dict):
            self._merge_existing(generated, existing)
            existing.clear()
            existing.update(generated)
            state = existing
        else:
            state = generated
        world["resources"] = state
        self.state = state

    def _state_is_complete(self, state):
        grids = state.get("grids")
        if not isinstance(grids, dict):
            return False
        width = int(self.world["width"])
        height = int(self.world["height"])
        return all(
            isinstance(grids.get(name), dict)
            and all(
                _valid_matrix(grids[name].get(key), width, height)
                for key in ("stock", "capacity", "regeneration_rate")
            )
            for name in RESOURCE_NAMES
        )

    def _generate_state(self):
        width = int(self.world["width"])
        height = int(self.world["height"])
        grids = {
            name: {
                "stock": _matrix(width, height),
                "capacity": _matrix(width, height),
                "regeneration_rate": _matrix(width, height),
            }
            for name in RESOURCE_NAMES
        }
        climate = ClimateSystem(self.world, self.config)

        for y in range(height):
            for x in range(width):
                elevation = float(self.world["elev"][y][x])
                river = max(0.0, float(self.world["riv"][y][x]))
                if climate_enabled(self.config):
                    temperature = _clamp(climate.temperature_at(x, y), -1.0, 2.0)
                    moisture = _clamp(climate.moisture_at(x, y))
                else:
                    temperature = _clamp(0.65 - max(0.0, elevation) * 0.5)
                    moisture = _clamp(0.45 + min(0.35, river * 0.1))

                land = 1.0 if elevation >= 0 else 0.0
                shallow_water = 1.0 if elevation < 0 else 0.0
                terrain = _clamp(1.0 - abs(elevation - 0.2) / 0.65)
                warmth = _clamp(1.0 - abs(temperature - 0.6) / 0.8)
                productivity = _clamp((moisture + warmth + terrain) / 3.0)

                capacities = {
                    "biomass": float(
                        self.settings.get("biomass_capacity_scale", 5000.0)
                    ) * land * productivity,
                    "soil_fertility": land * _clamp(0.35 + terrain * 0.4 + moisture * 0.25),
                    "surface_water": min(
                        120.0,
                        100.0 * shallow_water + 20.0 * land * moisture + 40.0 * min(1.0, river),
                    ),
                    "fish_stock": min(
                        float(self.settings.get("fish_capacity_scale", 1000.0)),
                        float(self.settings.get("fish_capacity_scale", 1000.0))
                        * (0.8 * shallow_water + 0.5 * min(1.0, river)),
                    ),
                    "forest_cover": 100.0 * land * productivity * moisture,
                }
                base_rates = {
                    "biomass": self.settings.get("biomass_regeneration_rate", 0.05),
                    "soil_fertility": self.settings.get("soil_regeneration_rate", 0.01),
                    "surface_water": self.settings.get("water_regeneration_rate", 0.08),
                    "fish_stock": self.settings.get("fish_regeneration_rate", 0.04),
                    "forest_cover": self.settings.get("forest_regeneration_rate", 0.005),
                }

                for name in RESOURCE_NAMES:
                    capacity = max(0.0, float(capacities[name]))
                    rate = max(0.0, float(base_rates[name]))
                    if name in {"biomass", "forest_cover"}:
                        rate *= max(0.1, productivity)
                    grids[name]["capacity"][y][x] = round(capacity, 6)
                    grids[name]["stock"][y][x] = round(capacity, 6)
                    grids[name]["regeneration_rate"][y][x] = round(rate, 6)

        return {
            "version": self.VERSION,
            "enabled": True,
            "last_update_cycle": 0,
            "next_disturbance_id": 1,
            "disturbances": [],
            "grids": grids,
        }

    def _merge_existing(self, target, existing):
        width = int(self.world["width"])
        height = int(self.world["height"])
        target["last_update_cycle"] = int(existing.get("last_update_cycle", 0))
        target["next_disturbance_id"] = max(1, int(existing.get("next_disturbance_id", 1)))
        disturbances = existing.get("disturbances", [])
        if isinstance(disturbances, list):
            target["disturbances"] = deepcopy(disturbances)

        old_grids = existing.get("grids", {})
        if not isinstance(old_grids, dict):
            return
        for name in RESOURCE_NAMES:
            old = old_grids.get(name)
            if not isinstance(old, dict):
                continue
            for key in ("stock", "capacity", "regeneration_rate"):
                value = old.get(key)
                if _valid_matrix(value, width, height):
                    target["grids"][name][key] = deepcopy(value)
            self._bound_grid(name, target)

    def _bound_grid(self, name, state=None):
        state = state or self.state
        grid = state["grids"][name]
        for y in range(int(self.world["height"])):
            for x in range(int(self.world["width"])):
                capacity = max(0.0, float(grid["capacity"][y][x]))
                stock = _clamp(grid["stock"][y][x], 0.0, capacity)
                rate = max(0.0, float(grid["regeneration_rate"][y][x]))
                grid["capacity"][y][x] = round(capacity, 6)
                grid["stock"][y][x] = round(stock, 6)
                grid["regeneration_rate"][y][x] = round(rate, 6)

    def _check_position(self, x, y):
        if not 0 <= int(x) < int(self.world["width"]) or not 0 <= int(y) < int(self.world["height"]):
            raise IndexError((x, y))

    def tile_snapshot(self, x, y):
        self._check_position(x, y)
        if not self.enabled:
            return {}
        return {
            name: {
                key: float(self.state["grids"][name][key][y][x])
                for key in ("stock", "capacity", "regeneration_rate")
            }
            for name in RESOURCE_NAMES
        }

    def snapshot(self):
        return deepcopy(self.state)

    def summary(self):
        result = {"enabled": self.enabled, "resources": {}, "disturbances": 0}
        if not self.enabled:
            return result
        for name, grid in self.state["grids"].items():
            stock = sum(sum(float(value) for value in row) for row in grid["stock"])
            capacity = sum(sum(float(value) for value in row) for row in grid["capacity"])
            result["resources"][name] = {
                "stock": round(stock, 6),
                "capacity": round(capacity, 6),
                "ratio": round(stock / capacity, 6) if capacity else 0.0,
            }
        result["disturbances"] = len(self.state["disturbances"])
        return result

    def available(self, name, x, y):
        self._check_position(x, y)
        if not self.enabled:
            return 0.0
        if name not in self.state["grids"]:
            raise KeyError(name)
        return float(self.state["grids"][name]["stock"][y][x])

    def extract(self, name, x, y, amount):
        self._check_position(x, y)
        if name not in self.state.get("grids", {}):
            raise KeyError(name)
        requested = max(0.0, float(amount))
        stock = max(0.0, float(self.state["grids"][name]["stock"][y][x]))
        extracted = min(stock, requested)
        self.state["grids"][name]["stock"][y][x] = round(stock - extracted, 6)
        return float(extracted)

    def restore(self, name, x, y, amount):
        self._check_position(x, y)
        if name not in self.state.get("grids", {}):
            raise KeyError(name)
        grid = self.state["grids"][name]
        capacity = max(0.0, float(grid["capacity"][y][x]))
        stock = max(0.0, float(grid["stock"][y][x]))
        restored = min(max(0.0, float(amount)), capacity - stock)
        grid["stock"][y][x] = round(stock + restored, 6)
        return float(restored)

    def ratio(self, name, x, y):
        self._check_position(x, y)
        if name not in self.state.get("grids", {}):
            raise KeyError(name)
        grid = self.state["grids"][name]
        capacity = float(grid["capacity"][y][x])
        return float(grid["stock"][y][x]) / capacity if capacity else 0.0

    def _record_resource(self, kind, amount):
        from core.simulation_metrics import SimulationMetrics

        return SimulationMetrics(self.world).record_resource(kind, amount)

    def harvest_agriculture(self, x, y, requested):
        """Convert local biomass into food and temporarily deplete soil."""
        if not self.enabled:
            return max(0, int(requested))
        soil_ratio = self.ratio("soil_fertility", x, y)
        water_ratio = self.ratio("surface_water", x, y)
        minimum_support = _clamp(self.settings.get("agriculture_min_support", 0.85))
        support = _clamp(
            minimum_support
            + (1.0 - minimum_support) * (soil_ratio * 0.7 + water_ratio * 0.3)
        )
        potential = max(0, int(float(requested) * support))
        harvested = self.extract("biomass", x, y, potential)
        soil = self.state["grids"]["soil_fertility"]
        soil_capacity = float(soil["capacity"][y][x])
        biomass_capacity = max(
            1.0, float(self.state["grids"]["biomass"]["capacity"][y][x])
        )
        cost_rate = _clamp(self.settings.get("agriculture_soil_cost", 0.02))
        depletion = soil_capacity * cost_rate * harvested / biomass_capacity
        soil["stock"][y][x] = round(
            max(0.0, float(soil["stock"][y][x]) - depletion),
            6,
        )
        self._record_resource("biomass_harvested", harvested)
        self._record_resource("soil_depleted", depletion)
        return int(harvested)

    def harvest_fish(self, x, y, requested):
        """Return the exact integer catch removed from local fish stock."""
        if not self.enabled:
            return max(0, int(requested))
        harvested = int(self.extract("fish_stock", x, y, max(0, int(requested))))
        self._record_resource("fish_harvested", harvested)
        return harvested

    def advance(self):
        if not self.enabled:
            return False
        cycle = int(self.world.get("cycle", 0))
        interval = max(1, int(self.settings.get("regeneration_interval", 3)))
        if cycle <= int(self.state.get("last_update_cycle", 0)) or cycle % interval:
            return False

        climate = self.world.get("climate", {})
        drought = _clamp(climate.get("drought_severity", 0.0))
        flood = _clamp(climate.get("flood_severity", 0.0))
        season = str(climate.get("season", "spring"))
        drought_pressure = _clamp(self.settings.get("drought_pressure", 0.8))
        flood_recovery = _clamp(self.settings.get("flood_recovery", 0.2))
        winter_mortality = _clamp(self.settings.get("winter_mortality_rate", 0.05))

        width = int(self.world["width"])
        height = int(self.world["height"])
        for y in range(height):
            for x in range(width):
                for name in RESOURCE_NAMES:
                    grid = self.state["grids"][name]
                    stock = float(grid["stock"][y][x])
                    capacity = float(grid["capacity"][y][x])
                    rate = float(grid["regeneration_rate"][y][x])
                    pressure = max(0.0, 1.0 - drought * drought_pressure)
                    if name == "surface_water":
                        pressure = max(0.0, pressure + flood * flood_recovery)
                    if name == "soil_fertility":
                        pressure = max(0.0, pressure + flood * flood_recovery)
                    if name == "fish_stock":
                        water_grid = self.state["grids"]["surface_water"]
                        water_capacity = float(water_grid["capacity"][y][x])
                        water_ratio = (
                            float(water_grid["stock"][y][x]) / water_capacity
                            if water_capacity else 0.0
                        )
                        pressure *= water_ratio
                    growth = max(0.0, capacity - stock) * rate * pressure
                    if season == "winter" and name in {"biomass", "forest_cover"}:
                        growth -= stock * winter_mortality
                    grid["stock"][y][x] = round(_clamp(stock + growth, 0.0, capacity), 6)

        self._advance_disturbances(interval)
        self.state["last_update_cycle"] = cycle
        return True

    def _advance_disturbances(self, elapsed):
        active = []
        for disturbance in self.state.get("disturbances", []):
            disturbance["remaining_cycles"] = max(
                0,
                int(disturbance.get("remaining_cycles", 0)) - int(elapsed),
            )
            if disturbance["remaining_cycles"] > 0:
                active.append(disturbance)
        self.state["disturbances"] = active

    def apply_disturbance(self, kind, positions, *, severity, duration):
        if not self.enabled:
            return {}
        if kind not in {"fire", "flood", "drought", "volcano"}:
            raise ValueError(kind)
        normalized = []
        for x, y in positions:
            self._check_position(x, y)
            normalized.append([int(x), int(y)])
        strength = _clamp(severity)
        disturbance = {
            "disturbance_id": int(self.state["next_disturbance_id"]),
            "kind": kind,
            "positions": normalized,
            "severity": strength,
            "remaining_cycles": max(1, int(duration)),
            "started_cycle": int(self.world.get("cycle", 0)),
        }
        self.state["next_disturbance_id"] += 1
        self.state["disturbances"].append(disturbance)
        self._record_resource("disturbances", 1)

        for x, y in normalized:
            if kind in {"fire", "volcano"}:
                for name in ("biomass", "forest_cover"):
                    grid = self.state["grids"][name]
                    grid["stock"][y][x] = round(grid["stock"][y][x] * (1.0 - strength), 6)
            if kind == "drought":
                for name in ("biomass", "surface_water"):
                    grid = self.state["grids"][name]
                    grid["stock"][y][x] = round(grid["stock"][y][x] * (1.0 - strength), 6)
            if kind == "flood":
                soil = self.state["grids"]["soil_fertility"]
                water = self.state["grids"]["surface_water"]
                soil_gain = soil["capacity"][y][x] * strength * _clamp(
                    self.settings.get("flood_recovery", 0.2)
                )
                water_gain = water["capacity"][y][x] * strength
                self.restore("soil_fertility", x, y, soil_gain)
                self.restore("surface_water", x, y, water_gain)
            if kind == "volcano":
                soil = self.state["grids"]["soil_fertility"]
                soil["stock"][y][x] = round(
                    _clamp(
                        soil["stock"][y][x] + soil["capacity"][y][x] * strength * 0.1,
                        0.0,
                        soil["capacity"][y][x],
                    ),
                    6,
                )
        return deepcopy(disturbance)

    def spread_fire(self, origin, *, severity, duration, max_tiles=12):
        """Spread fire deterministically through connected dry vegetation."""
        self._check_position(*origin)
        if not self.enabled:
            return {}
        limit = max(1, int(max_tiles))
        minimum_forest = _clamp(self.settings.get("fire_min_forest_ratio", 0.25))
        maximum_moisture = _clamp(self.settings.get("fire_max_moisture", 0.85))
        climate = ClimateSystem(self.world, self.config)
        queue = [(int(origin[0]), int(origin[1]))]
        visited = set()
        burning = []
        while queue and len(burning) < limit:
            x, y = queue.pop(0)
            if (x, y) in visited:
                continue
            visited.add((x, y))
            is_origin = (x, y) == (int(origin[0]), int(origin[1]))
            if not is_origin and (
                self.ratio("forest_cover", x, y) < minimum_forest
                or _clamp(climate.moisture_at(x, y)) > maximum_moisture
            ):
                continue
            burning.append((x, y))
            for nx, ny in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
                if 0 <= nx < int(self.world["width"]) and 0 <= ny < int(self.world["height"]):
                    if (nx, ny) not in visited:
                        queue.append((nx, ny))
        return self.apply_disturbance(
            "fire", burning, severity=severity, duration=duration
        )

    def apply_global_disturbance(self, kind, severity, duration=12):
        positions = [
            (x, y)
            for y in range(int(self.world["height"]))
            for x in range(int(self.world["width"]))
        ]
        return self.apply_disturbance(
            kind,
            positions,
            severity=severity,
            duration=duration,
        )
