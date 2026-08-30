"""Revendications territoriales deterministes et inspectables."""

from copy import deepcopy

from core.diplomacy import DiplomacyRegistry


class TerritorySystem:
    """Projette le controle des etablissements sur la carte."""

    def __init__(self, world, config):
        self.config = config if isinstance(config, dict) else {}
        self.world = world
        section = config.get("territory", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if self.enabled:
            state = world.get("territory")
            if not isinstance(state, dict):
                world["territory"] = {
                    "version": 1,
                    "revision": 0,
                    "last_advanced_cycle": None,
                    "tiles": {},
                    "borders": [],
                    "contested_tiles": 0,
                }

    @property
    def state(self):
        return self.world.get("territory")

    def advance(self):
        if not self.enabled:
            return False
        cycle = int(self.world.get("cycle", 0))
        interval = max(1, int(self.settings.get("advance_interval", 1)))
        last_cycle = self.state.get("last_advanced_cycle")
        if last_cycle == cycle or cycle % interval:
            return False

        claims = self._collect_claims()
        tiles = {}
        disputed_pairs = set()
        contest_margin = max(0.0, float(self.settings.get("contest_margin", 2.0)))
        for (x, y), candidates in sorted(claims.items()):
            ranked = sorted(
                candidates,
                key=lambda claim: (-claim["score"], claim["settlement_id"]),
            )
            contested = (
                len(ranked) > 1
                and ranked[0]["score"] - ranked[1]["score"] < contest_margin
            )
            resources = self._strategic_resources_at(x, y)
            tiles[f"{x},{y}"] = {
                "x": x,
                "y": y,
                "owner_id": None if contested else ranked[0]["settlement_id"],
                "contested": contested,
                "claimants": ranked,
                "strategic_resources": resources,
            }
            if contested:
                disputed_pairs.add(
                    tuple(sorted((ranked[0]["settlement_id"], ranked[1]["settlement_id"])))
                )

        overrides = self.state.get("treaty_overrides", {})
        for key, owner_id in sorted(overrides.items()):
            tile = tiles.get(key)
            if tile is None:
                continue
            tile["owner_id"] = int(owner_id)
            tile["contested"] = False
            previous = self.state.get("tiles", {}).get(key, {})
            if "treaty_id" in previous:
                tile["treaty_id"] = previous["treaty_id"]
        borders = self._build_borders(tiles, disputed_pairs)
        self._record_grievances(borders)
        self.state.update(
            {
                "revision": int(self.state.get("revision", 0)) + 1,
                "last_advanced_cycle": cycle,
                "tiles": tiles,
                "borders": borders,
                "contested_tiles": sum(
                    1 for tile in tiles.values() if tile["contested"]
                ),
            }
        )
        return True

    def tile_snapshot(self, x, y):
        if not self.enabled:
            return None
        tile = self.state["tiles"].get(f"{int(x)},{int(y)}")
        return deepcopy(tile)

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        owned = {}
        for tile in self.state["tiles"].values():
            owner_id = tile["owner_id"]
            if owner_id is not None:
                owned[str(owner_id)] = owned.get(str(owner_id), 0) + 1
        return {
            "enabled": True,
            "revision": self.state["revision"],
            "claimed_tiles": len(self.state["tiles"]),
            "contested_tiles": self.state["contested_tiles"],
            "owned_tiles": owned,
            "borders": deepcopy(self.state["borders"]),
        }

    def _collect_claims(self):
        claims = {}
        radius = max(0, int(self.settings.get("max_radius", 5)))
        width = int(self.world.get("width", 0))
        height = int(self.world.get("height", 0))
        for settlement in self._settlements():
            source_x, source_y = map(int, settlement.pos)
            power = self._source_power(settlement)
            for y in range(max(0, source_y - radius), min(height, source_y + radius + 1)):
                for x in range(max(0, source_x - radius), min(width, source_x + radius + 1)):
                    distance = abs(x - source_x) + abs(y - source_y)
                    if distance > radius:
                        continue
                    decay = max(0.0, float(self.settings.get("distance_decay", 0.5)))
                    score = power / (1.0 + distance * decay)
                    if self._has_road(x, y):
                        score *= max(0.0, float(self.settings.get("road_multiplier", 1.0)))
                    if self._strategic_resources_at(x, y):
                        score += max(
                            0.0,
                            float(self.settings.get("strategic_resource_bonus", 0.0)),
                        )
                    claims.setdefault((x, y), []).append(
                        {
                            "settlement_id": int(settlement.entity_id),
                            "score": round(score, 6),
                            "distance": distance,
                        }
                    )
        return claims

    def _settlements(self):
        entities = self.world.get("entities", ())
        return sorted(
            (
                entity
                for entity in entities
                if hasattr(entity, "citizens")
                and hasattr(entity, "pos")
                and not getattr(entity, "is_expired", False)
            ),
            key=lambda entity: int(entity.entity_id),
        )

    def _source_power(self, settlement):
        population = len(getattr(settlement, "citizens", ()))
        fortification = max(
            0.0,
            float(getattr(settlement, "fortification_strength", 0.0)),
        )
        from core.artifacts import ArtifactRegistry
        artifact_power = ArtifactRegistry(
            self.world, self.config
        ).prestige_bonus(settlement.entity_id)
        return (
            max(0.0, float(self.settings.get("base_power", 1.0)))
            + population * max(0.0, float(self.settings.get("population_scale", 1.0)))
            + fortification
            * max(0.0, float(self.settings.get("fortification_scale", 1.0)))
            + artifact_power
        )

    def _has_road(self, x, y):
        road = self.world.get("road", ())
        try:
            return road[y][x] not in (None, "", "  ")
        except (IndexError, TypeError):
            return False

    def _strategic_resources_at(self, x, y):
        resource_names = self.settings.get("strategic_resources", ())
        grids = self.world.get("resources", {}).get("grids", {})
        found = []
        for name in resource_names if isinstance(resource_names, list) else ():
            stock = grids.get(name, {}).get("stock")
            try:
                if float(stock[y][x]) > 0:
                    found.append(str(name))
            except (IndexError, TypeError, ValueError):
                continue
        return found

    def _build_borders(self, tiles, disputed_pairs):
        pairs = {pair: 0 for pair in disputed_pairs}
        for tile in tiles.values():
            owner_id = tile["owner_id"]
            if owner_id is None:
                continue
            x, y = tile["x"], tile["y"]
            for neighbour in ((x + 1, y), (x, y + 1)):
                other = tiles.get(f"{neighbour[0]},{neighbour[1]}")
                if other is None or other["owner_id"] in (None, owner_id):
                    continue
                pair = tuple(sorted((owner_id, other["owner_id"])))
                pairs[pair] = pairs.get(pair, 0) + 1
        for tile in tiles.values():
            if not tile["contested"] or len(tile["claimants"]) < 2:
                continue
            pair = tuple(
                sorted(
                    (
                        tile["claimants"][0]["settlement_id"],
                        tile["claimants"][1]["settlement_id"],
                    )
                )
            )
            pairs[pair] = pairs.get(pair, 0) + 1
        return [
            {
                "first_id": first_id,
                "second_id": second_id,
                "tiles": tile_count,
            }
            for (first_id, second_id), tile_count in sorted(pairs.items())
        ]

    def _record_grievances(self, borders):
        tension = max(0.0, float(self.settings.get("territorial_tension", 0.0)))
        if tension <= 0:
            return
        registry = DiplomacyRegistry(self.world)
        for border in borders:
            if border["tiles"] <= 0:
                continue
            registry.adjust(
                border["first_id"],
                border["second_id"],
                tension=tension,
                reason="territorial_dispute",
            )

