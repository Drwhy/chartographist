"""Pathfinding deterministe, mesurable et cache pour la simulation."""

from copy import deepcopy
import heapq
import math


class PathfindingService:
    """Calcule des chemins dont chaque facteur de cout reste inspectable."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("pathfinding", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if self.enabled:
            state = world.get("pathfinding")
            if not isinstance(state, dict):
                state = {
                    "version": 1,
                    "revision": 0,
                    "cache": {},
                    "cache_order": [],
                    "stamp": None,
                    "queries": 0,
                    "cache_hits": 0,
                    "invalidations": 0,
                    "expanded_nodes": 0,
                    "last_cost": None,
                }
                world["pathfinding"] = state
            state.setdefault("cache", {})
            state.setdefault("cache_order", [])
            state.setdefault("queries", 0)
            state.setdefault("cache_hits", 0)
            state.setdefault("invalidations", 0)
            state.setdefault("expanded_nodes", 0)
            if state.get("stamp") is None:
                state["stamp"] = self._environment_stamp()

    @property
    def state(self):
        return self.world.get("pathfinding")

    def find_path(self, start, goal, *, known_tiles=None):
        start = self._position(start)
        goal = self._position(goal)
        if not self.enabled:
            return self._legacy_path(start, goal)

        self._sync_environment()
        self.state["queries"] += 1
        known = self._known_set(known_tiles)
        key = self._cache_key(start, goal, known)
        cached = self.state["cache"].get(key)
        if cached is not None:
            self.state["cache_hits"] += 1
            result = deepcopy(cached)
            result["cache_hit"] = True
            return result

        if not self._in_bounds(*start) or not self._in_bounds(*goal):
            result = self._unreachable()
            self._store(key, result)
            return deepcopy(result)

        result = self._astar(start, goal, known)
        self.state["expanded_nodes"] += result["expanded_nodes"]
        self.state["last_cost"] = result["cost"] if result["reachable"] else None
        self._store(key, result)
        return deepcopy(result)

    def measure_path(self, path, *, known_tiles=None):
        known = self._known_set(known_tiles)
        total = 0.0
        for index in range(1, len(path)):
            previous = self._position(path[index - 1])
            current = self._position(path[index])
            total += self._step_details(previous, current, known)["cost"]
        return round(total, 6)

    def invalidate(self, reason="manual"):
        if not self.enabled:
            return False
        self.state["cache"].clear()
        self.state["cache_order"].clear()
        self.state["revision"] = int(self.state.get("revision", 0)) + 1
        self.state["invalidations"] += 1
        self.state["last_invalidation_reason"] = str(reason)
        self.state["stamp"] = self._environment_stamp()
        return True

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "revision": int(self.state.get("revision", 0)),
            "queries": int(self.state.get("queries", 0)),
            "cache_hits": int(self.state.get("cache_hits", 0)),
            "cache_entries": len(self.state.get("cache", {})),
            "invalidations": int(self.state.get("invalidations", 0)),
            "expanded_nodes": int(self.state.get("expanded_nodes", 0)),
            "last_cost": self.state.get("last_cost"),
        }

    def _astar(self, start, goal, known):
        frontier = [(0.0, 0, start)]
        came_from = {}
        costs = {start: 0.0}
        expanded = 0
        sequence = 0
        maximum = max(1, int(self.settings.get("max_expanded_nodes", 5000)))

        while frontier and expanded < maximum:
            _, _, current = heapq.heappop(frontier)
            if current == goal:
                break
            expanded += 1
            for neighbour in self._neighbours(current):
                details = self._step_details(current, neighbour, known)
                candidate = costs[current] + details["cost"]
                if candidate >= costs.get(neighbour, math.inf):
                    continue
                costs[neighbour] = candidate
                came_from[neighbour] = current
                sequence += 1
                priority = candidate + self._heuristic(neighbour, goal)
                heapq.heappush(frontier, (priority, sequence, neighbour))

        if goal not in costs:
            return self._unreachable(expanded)
        current = goal
        path = [list(goal)]
        while current != start:
            current = came_from[current]
            path.append(list(current))
        path.reverse()
        breakdown = self._path_breakdown(path, known)
        return {
            "reachable": True,
            "path": path,
            "cost": round(costs[goal], 6),
            "cost_breakdown": breakdown,
            "expanded_nodes": expanded,
            "cache_hit": False,
        }

    def _neighbours(self, position):
        x, y = position
        offsets = ((1, 0), (0, 1), (-1, 0), (0, -1))
        if self.settings.get("allow_diagonal") is True:
            offsets += ((1, 1), (-1, 1), (-1, -1), (1, -1))
        for dx, dy in offsets:
            candidate = (x + dx, y + dy)
            if self._in_bounds(*candidate):
                yield candidate

    def _step_details(self, previous, current, known):
        x, y = current
        px, py = previous
        diagonal = x != px and y != py
        base = max(0.001, float(self.settings.get("base_cost", 1.0)))
        if diagonal:
            base *= math.sqrt(2.0)
        elevation = abs(
            float(self.world.get("elev", [[0]])[y][x])
            - float(self.world.get("elev", [[0]])[py][px])
        ) * max(0.0, float(self.settings.get("elevation_weight", 0.0)))

        climate = self.world.get("climate", {})
        drought = max(0.0, float(climate.get("drought_severity", 0.0)))
        flood = max(0.0, float(climate.get("flood_severity", 0.0)))
        river = self.world.get("riv", ())
        try:
            flood_exposure = flood if float(river[y][x]) > 0 else 0.0
        except (IndexError, TypeError, ValueError):
            flood_exposure = 0.0
        weather = (drought + flood_exposure) * max(
            0.0, float(self.settings.get("weather_weight", 0.0))
        )

        influence = self.world.get("influence")
        fear_grid = getattr(influence, "fear_grid", ())
        try:
            fear = abs(min(0.0, float(fear_grid[y][x])))
        except (IndexError, TypeError, ValueError):
            fear = 0.0
        danger = fear * max(0.0, float(self.settings.get("danger_weight", 0.0)))

        subtotal = base + elevation + weather + danger
        if self._has_road(x, y):
            subtotal *= max(0.001, float(self.settings.get("road_multiplier", 1.0)))
        unknown_multiplier = max(
            1.0, float(self.settings.get("unknown_multiplier", 1.0))
        )
        knowledge_multiplier = (
            unknown_multiplier if known is not None and current not in known else 1.0
        )
        return {
            "cost": subtotal * knowledge_multiplier,
            "base": base,
            "elevation": elevation,
            "weather": weather,
            "danger": danger,
            "knowledge_multiplier": knowledge_multiplier,
        }

    def _path_breakdown(self, path, known):
        totals = {
            "base": 0.0,
            "elevation": 0.0,
            "weather": 0.0,
            "danger": 0.0,
            "knowledge_multiplier": 1.0,
        }
        for index in range(1, len(path)):
            details = self._step_details(
                self._position(path[index - 1]),
                self._position(path[index]),
                known,
            )
            for key in ("base", "elevation", "weather", "danger"):
                totals[key] += details[key]
            totals["knowledge_multiplier"] = max(
                totals["knowledge_multiplier"], details["knowledge_multiplier"]
            )
        return {key: round(value, 6) for key, value in totals.items()}

    def _heuristic(self, current, goal):
        dx = abs(current[0] - goal[0])
        dy = abs(current[1] - goal[1])
        distance = max(dx, dy) if self.settings.get("allow_diagonal") is True else dx + dy
        minimum = min(1.0, max(0.001, float(self.settings.get("road_multiplier", 1.0))))
        return distance * max(0.001, float(self.settings.get("base_cost", 1.0))) * minimum

    def _sync_environment(self):
        stamp = self._environment_stamp()
        if stamp != self.state.get("stamp"):
            self.invalidate("environment_changed")

    def _environment_stamp(self):
        width = int(self.world.get("width", 0))
        road_checksum = 0
        for y, row in enumerate(self.world.get("road", ())):
            for x, value in enumerate(row):
                if value not in (None, "", "  "):
                    road_checksum += y * max(1, width) + x + 1
        influence = self.world.get("influence")
        fear_checksum = 0.0
        for y, row in enumerate(getattr(influence, "fear_grid", ())):
            fear_checksum += sum((x + 1 + y * max(1, width)) * float(value) for x, value in enumerate(row))
        climate = self.world.get("climate", {})
        territory = self.world.get("territory", {})
        return [
            road_checksum,
            round(fear_checksum, 6),
            int(climate.get("last_update_cycle", 0)),
            round(float(climate.get("drought_severity", 0.0)), 6),
            round(float(climate.get("flood_severity", 0.0)), 6),
            int(territory.get("revision", 0)) if isinstance(territory, dict) else 0,
        ]

    def _store(self, key, result):
        maximum = max(1, int(self.settings.get("max_cache_entries", 128)))
        cache = self.state["cache"]
        order = self.state["cache_order"]
        if key in cache:
            order.remove(key)
        cache[key] = deepcopy(result)
        order.append(key)
        while len(order) > maximum:
            expired = order.pop(0)
            cache.pop(expired, None)

    def _cache_key(self, start, goal, known):
        known_key = "*"
        if known is not None:
            known_key = ";".join(f"{x},{y}" for x, y in sorted(known))
        return f"{start[0]},{start[1]}>{goal[0]},{goal[1]}|{known_key}"

    def _legacy_path(self, start, goal):
        x, y = start
        path = [[x, y]]
        while x != goal[0]:
            x += 1 if x < goal[0] else -1
            path.append([x, y])
        while y != goal[1]:
            y += 1 if y < goal[1] else -1
            path.append([x, y])
        return {
            "reachable": self._in_bounds(*start) and self._in_bounds(*goal),
            "path": path,
            "cost": round(max(0, len(path) - 1) * float(self.settings.get("base_cost", 1.0)), 6),
            "cost_breakdown": {},
            "expanded_nodes": 0,
            "cache_hit": False,
        }

    def _unreachable(self, expanded=0):
        return {
            "reachable": False,
            "path": [],
            "cost": None,
            "cost_breakdown": {},
            "expanded_nodes": expanded,
            "cache_hit": False,
        }

    def _has_road(self, x, y):
        try:
            return self.world["road"][y][x] not in (None, "", "  ")
        except (KeyError, IndexError, TypeError):
            return False

    def _in_bounds(self, x, y):
        return 0 <= x < int(self.world.get("width", 0)) and 0 <= y < int(self.world.get("height", 0))

    @staticmethod
    def _position(value):
        return int(value[0]), int(value[1])

    @staticmethod
    def _known_set(known_tiles):
        if known_tiles is None:
            return None
        return {(int(tile[0]), int(tile[1])) for tile in known_tiles}



def known_tiles_for(entity):
    """Extract surveyed tile positions without creating knowledge state."""
    state = getattr(entity, "knowledge", None)
    if not isinstance(state, dict):
        return None
    tiles = {
        tuple(map(int, fact["position"]))
        for fact in state.get("facts", ())
        if isinstance(fact, dict)
        and fact.get("kind") == "map_tile"
        and isinstance(fact.get("position"), (list, tuple))
        and len(fact["position"]) == 2
    }
    return tiles or None

