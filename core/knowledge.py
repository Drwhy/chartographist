"""Local, bounded and explainable knowledge carried by world entities."""

from copy import deepcopy
import math


_KNOWLEDGE_VERSION = 1


def knowledge_settings(config):
    if not isinstance(config, dict):
        return {}
    settings = config.get("knowledge", {})
    return settings if isinstance(settings, dict) else {}


def knowledge_enabled(config):
    return knowledge_settings(config).get("enabled", False) is True


def _empty_state():
    return {
        "version": _KNOWLEDGE_VERSION,
        "next_fact_id": 1,
        "facts": [],
        "last_observation_cycle": None,
        "last_decay_cycle": None,
        "legacy_known_cities_migrated": False,
    }


def _bounded_reliability(value):
    return round(min(1.0, max(0.0, float(value))), 6)


def ensure_knowledge_state(owner):
    state = getattr(owner, "knowledge", None)
    if not isinstance(state, dict):
        state = _empty_state()
        owner.knowledge = state
    state["version"] = _KNOWLEDGE_VERSION
    state["next_fact_id"] = max(1, int(state.get("next_fact_id", 1)))
    if not isinstance(state.get("facts"), list):
        state["facts"] = []
    state.setdefault("last_observation_cycle", None)
    state.setdefault("last_decay_cycle", None)
    state.setdefault("legacy_known_cities_migrated", False)

    known_cities = getattr(owner, "known_cities", ())
    existing = {
        int(fact.get("subject_id"))
        for fact in state["facts"]
        if isinstance(fact, dict)
        and fact.get("kind") == "settlement"
        and isinstance(fact.get("subject_id"), int)
    }
    legacy_values = (
        known_cities
        if not state["legacy_known_cities_migrated"]
        and isinstance(known_cities, (set, list, tuple))
        else ()
    )
    state["legacy_known_cities_migrated"] = True
    for subject_id in sorted(legacy_values):
        identifier = int(subject_id)
        if identifier in existing:
            continue
        state["facts"].append({
            "fact_id": state["next_fact_id"],
            "kind": "settlement",
            "subject_id": identifier,
            "claim": "exists",
            "value": {"exists": True},
            "position": None,
            "observed_cycle": 0,
            "received_cycle": 0,
            "source_id": int(getattr(owner, "entity_id", 0)),
            "origin_source_id": int(getattr(owner, "entity_id", 0)),
            "source_type": "legacy",
            "reliability": 0.5,
            "transmissions": 0,
        })
        state["next_fact_id"] += 1
    return state


class KnowledgeService:
    """Manage one entity's partial view of the world."""

    def __init__(self, owner, config):
        self.owner = owner
        self.config = config if isinstance(config, dict) else {}
        self.settings = knowledge_settings(self.config)
        self.enabled = knowledge_enabled(self.config)
        existing = getattr(owner, "knowledge", None)
        self.state = (
            ensure_knowledge_state(owner)
            if self.enabled or isinstance(existing, dict)
            else _empty_state()
        )
        if self.enabled:
            self._prune()

    def snapshot(self):
        return deepcopy(self.state)

    def query(self, *, kind=None, subject_id=None, claim=None):
        facts = [
            fact for fact in self.state["facts"]
            if (kind is None or fact.get("kind") == str(kind))
            and (subject_id is None or fact.get("subject_id") == int(subject_id))
            and (claim is None or fact.get("claim") == str(claim))
        ]
        return deepcopy(sorted(
            facts,
            key=lambda fact: (
                str(fact.get("kind", "")),
                int(fact.get("subject_id", 0)),
                str(fact.get("claim", "")),
                -float(fact.get("reliability", 0.0)),
                -int(fact.get("observed_cycle", 0)),
                int(fact.get("fact_id", 0)),
            ),
        ))

    def best_fact(self, kind, subject_id, *, claim=None):
        facts = self.query(kind=kind, subject_id=subject_id, claim=claim)
        if not facts:
            return None
        return max(
            facts,
            key=lambda fact: (
                float(fact.get("reliability", 0.0)),
                int(fact.get("observed_cycle", 0)),
                -int(fact.get("transmissions", 0)),
                -int(fact.get("fact_id", 0)),
            ),
        )

    def known_subject_ids(self, kind):
        return sorted({
            int(fact["subject_id"])
            for fact in self.state["facts"]
            if fact.get("kind") == str(kind)
            and float(fact.get("reliability", 0.0))
            >= float(self.settings.get("minimum_reliability", 0.05))
        })

    def learn(
        self,
        *,
        kind,
        subject_id,
        claim,
        value,
        cycle,
        source_id,
        source_type,
        reliability,
        position=None,
        origin_source_id=None,
        transmissions=0,
        belief_modifier=1.0,
    ):
        if not self.enabled:
            return None
        identifier = int(subject_id)
        normalized_position = (
            [int(position[0]), int(position[1])] if position is not None else None
        )
        normalized_value = deepcopy(value)
        matching = next(
            (
                fact for fact in self.state["facts"]
                if fact.get("kind") == str(kind)
                and fact.get("subject_id") == identifier
                and fact.get("claim") == str(claim)
                and fact.get("origin_source_id")
                == int(source_id if origin_source_id is None else origin_source_id)
            ),
            None,
        )
        payload = {
            "kind": str(kind),
            "subject_id": identifier,
            "claim": str(claim),
            "value": normalized_value,
            "position": normalized_position,
            "observed_cycle": int(cycle),
            "received_cycle": int(cycle),
            "source_id": int(source_id),
            "origin_source_id": int(
                source_id if origin_source_id is None else origin_source_id
            ),
            "source_type": str(source_type),
            "reliability": _bounded_reliability(reliability),
            "transmissions": max(0, int(transmissions)),
            "belief_modifier": round(float(belief_modifier), 6),
        }
        if matching is None:
            payload["fact_id"] = int(self.state["next_fact_id"])
            self.state["next_fact_id"] += 1
            self.state["facts"].append(payload)
            learned = payload
        else:
            matching.update(payload)
            learned = matching
        self._prune()
        return deepcopy(learned)

    def observe(self, world):
        if not self.enabled:
            return []
        cycle = int(world.get("cycle", 0))
        radius = max(0.0, float(self.settings.get("perception_radius", 8.0)))
        observed = []
        origin = getattr(self.owner, "pos", (0, 0))
        owner_id = int(getattr(self.owner, "entity_id", 0))
        entities = sorted(
            world.get("entities", ()),
            key=lambda entity: int(getattr(entity, "entity_id", 0)),
        )
        for entity in entities:
            entity_id = getattr(entity, "entity_id", None)
            if entity_id is None or int(entity_id) == owner_id:
                continue
            if getattr(entity, "is_expired", False):
                continue
            if not hasattr(entity, "population") or getattr(entity, "population", 0) <= 0:
                continue
            position = getattr(entity, "pos", None)
            if position is None or math.dist(origin, position) > radius:
                continue
            maximum_food = max(1.0, float(getattr(entity, "max_food", 1.0)))
            fact = self.learn(
                kind="settlement",
                subject_id=int(entity_id),
                claim="state",
                value={
                    "exists": True,
                    "name": str(getattr(entity, "name", "")),
                    "population": int(getattr(entity, "population", 0)),
                    "food_ratio": round(
                        max(0.0, float(getattr(entity, "food_stock", 0.0)))
                        / maximum_food,
                        6,
                    ),
                },
                cycle=cycle,
                source_id=owner_id,
                source_type="observed",
                reliability=1.0,
                position=position,
            )
            observed.append(fact)
        self.state["last_observation_cycle"] = cycle
        return observed

    def observe_tile(self, world, position):
        if not self.enabled:
            return None
        x, y = int(position[0]), int(position[1])
        width = int(world.get("width", 0))
        height = int(world.get("height", 0))
        if x < 0 or y < 0 or x >= width or y >= height:
            return None
        value = {}
        for key in ("terrain", "biome"):
            grid = world.get(key)
            try:
                value[key] = deepcopy(grid[y][x])
            except (IndexError, KeyError, TypeError):
                continue
        elevation_grid = world.get("elev")
        try:
            elevation = float(elevation_grid[y][x])
        except (IndexError, KeyError, TypeError):
            elevation = None
        if elevation is not None:
            value["elevation"] = round(elevation, 6)
            try:
                value["river"] = bool(world.get("riv")[y][x] > 0)
            except (IndexError, KeyError, TypeError):
                value["river"] = False
            if "biome" not in value:
                from core.climate import biome_at
                value["biome"] = biome_at(
                    x, y, elevation, world, self.config
                )
        from core.resources import ResourceSystem, resources_enabled
        if resources_enabled(self.config):
            resources = ResourceSystem(world, self.config).tile_snapshot(x, y)
            if resources:
                value["resources"] = resources
        if not value:
            return None
        return self.learn(
            kind="map_tile",
            subject_id=y * width + x,
            claim="survey",
            value=value,
            cycle=int(world.get("cycle", 0)),
            source_id=int(getattr(self.owner, "entity_id", 0)),
            source_type="observed",
            reliability=1.0,
            position=(x, y),
        )

    def known_settlements(self, world):
        identifiers = set(self.known_subject_ids("settlement"))
        return sorted(
            (
                entity for entity in world.get("entities", ())
                if getattr(entity, "entity_id", None) in identifiers
                and not getattr(entity, "is_expired", False)
                and getattr(entity, "population", 0) > 0
            ),
            key=lambda entity: int(entity.entity_id),
        )

    def transmit_to(
        self, target, *, cycle, distance, facts=None, transfer_type="reported"
    ):
        if not self.enabled:
            return 0
        target_config = getattr(target, "config", self.config)
        target_service = KnowledgeService(target, target_config)
        if not target_service.enabled:
            return 0
        transmission_decay = max(
            0.0, float(self.settings.get("transmission_decay", 0.1))
        )
        distance_decay = max(0.0, float(self.settings.get("distance_decay", 0.005)))
        minimum = float(self.settings.get("minimum_reliability", 0.05))
        allowed_types = {"reported", "copied", "sold", "stolen"}
        source_type = (
            str(transfer_type) if str(transfer_type) in allowed_types else "reported"
        )
        character = getattr(target, "character", {})
        traits = character.get("traits", {}) if isinstance(character, dict) else {}
        empathy = min(1.0, max(0.0, float(traits.get("empathy", 0.0))))
        prudence = min(1.0, max(0.0, float(traits.get("prudence", 0.0))))
        belief_modifier = round(1.0 + empathy * 0.1 - prudence * 0.1, 6)
        transferred = 0
        for fact in self.query() if facts is None else deepcopy(facts):
            reliability = _bounded_reliability(
                (
                    float(fact["reliability"])
                    - transmission_decay
                    - max(0.0, float(distance)) * distance_decay
                ) * belief_modifier
            )
            if reliability < minimum:
                continue
            target_service.learn(
                kind=fact["kind"],
                subject_id=fact["subject_id"],
                claim=fact["claim"],
                value=fact["value"],
                cycle=int(cycle),
                source_id=int(getattr(self.owner, "entity_id", 0)),
                source_type=source_type,
                reliability=reliability,
                belief_modifier=belief_modifier,
                position=fact.get("position"),
                origin_source_id=fact.get("origin_source_id", fact.get("source_id", 0)),
                transmissions=int(fact.get("transmissions", 0)) + 1,
            )
            transferred += 1
        return transferred

    def advance(self, world):
        if not self.enabled:
            return self.snapshot()
        cycle = int(world.get("cycle", 0))
        last_decay = self.state.get("last_decay_cycle")
        elapsed = max(0, cycle - int(last_decay or 0))
        rate = min(1.0, max(0.0, float(
            self.settings.get("reliability_decay", 0.002)
        )))
        if elapsed > 0 and rate > 0:
            factor = (1.0 - rate) ** elapsed
            for fact in self.state["facts"]:
                fact["reliability"] = _bounded_reliability(
                    float(fact.get("reliability", 0.0)) * factor
                )
        self.state["last_decay_cycle"] = cycle
        interval = max(1, int(self.settings.get("observation_interval", 3)))
        last_observation = self.state.get("last_observation_cycle")
        if last_observation is None or cycle - int(last_observation) >= interval:
            self.observe(world)
        self._prune()
        return self.snapshot()

    def _prune(self):
        minimum = float(self.settings.get("minimum_reliability", 0.05))
        facts = [
            fact for fact in self.state["facts"]
            if isinstance(fact, dict)
            and float(fact.get("reliability", 0.0)) >= minimum
        ]
        maximum = max(1, int(self.settings.get("max_facts", 128)))
        facts.sort(key=lambda fact: (
            -float(fact.get("reliability", 0.0)),
            -int(fact.get("observed_cycle", 0)),
            int(fact.get("fact_id", 0)),
        ))
        self.state["facts"] = facts[:maximum]
