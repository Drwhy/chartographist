"""Migrations causales par cohortes et diasporas persistantes."""

from copy import deepcopy
import math


class MigrationSystem:
    """Evalue les pressions de depart et deplace de vraies personnes."""

    def __init__(self, world, config):
        self.world = world
        self.config = config if isinstance(config, dict) else {}
        section = config.get("migration", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.enabled = self.settings.get("enabled") is True
        if self.enabled:
            state = world.get("migration")
            if not isinstance(state, dict):
                world["migration"] = {
                    "version": 1,
                    "next_cohort_id": 1,
                    "last_advanced_cycle": None,
                    "cohorts": [],
                    "diasporas": {},
                    "total_migrants": 0,
                    "returnees": 0,
                }

    @property
    def state(self):
        return self.world.get("migration")

    def advance(self):
        if not self.enabled:
            return False
        cycle = int(self.world.get("cycle", 0))
        interval = max(1, int(self.settings.get("advance_interval", 1)))
        if self.state.get("last_advanced_cycle") == cycle or cycle % interval:
            return False

        moved = False
        threshold = max(0.0, float(self.settings.get("departure_threshold", 1.0)))
        for source in self._settlements():
            causes = self.departure_causes(source)
            if sum(causes.values()) < threshold:
                continue
            ranked = self.rank_destinations(source)
            if not ranked:
                continue
            destination = self._by_id(ranked[0]["settlement_id"])
            if destination is None:
                continue
            cohort = self._select_cohort(source)
            if not cohort:
                continue
            self._move_cohort(source, destination, cohort, causes, ranked[0])
            moved = True

        self.state["last_advanced_cycle"] = cycle
        return moved

    def departure_causes(self, settlement):
        ratio = self._food_ratio(settlement)
        hunger_threshold = max(
            0.001, float(self.settings.get("hunger_food_ratio", 0.25))
        )
        hunger = (
            max(0.0, hunger_threshold - ratio)
            / hunger_threshold
            * max(0.0, float(self.settings.get("hunger_weight", 0.0)))
        )

        identifier = int(settlement.entity_id)
        at_war = any(
            relation.get("status") == "war"
            and identifier in (relation.get("first_id"), relation.get("second_id"))
            for relation in self.world.get("diplomacy", {}).values()
            if isinstance(relation, dict)
        )
        war = max(0.0, float(self.settings.get("war_weight", 0.0))) if at_war else 0.0

        climate = self.world.get("climate", {})
        hazard = max(
            0.0,
            float(climate.get("drought_severity", 0.0)),
            float(climate.get("flood_severity", 0.0)),
        )
        climate_pressure = hazard * max(
            0.0, float(self.settings.get("climate_weight", 0.0))
        )
        persecution = max(
            0.0, float(getattr(settlement, "migration_persecution", 0.0))
        ) * max(0.0, float(self.settings.get("persecution_weight", 0.0)))

        opportunity = max(
            (
                self._food_ratio(candidate) - ratio
                for candidate in self._settlements()
                if candidate is not settlement
            ),
            default=0.0,
        )
        opportunity = max(0.0, opportunity) * max(
            0.0,
            float(self.settings.get("opportunity_departure_weight", 0.0)),
        )
        return {
            "hunger": round(hunger, 6),
            "war": round(war, 6),
            "climate": round(climate_pressure, 6),
            "persecution": round(persecution, 6),
            "opportunity": round(opportunity, 6),
        }

    def rank_destinations(self, source):
        capacity = max(1, int(self.settings.get("settlement_capacity", 200)))
        source_families = {
            str(getattr(person, "family_name", "") or "")
            for person in getattr(source, "citizens", ())
        }
        ranked = []
        for destination in self._settlements():
            if destination is source:
                continue
            available = max(0, capacity - len(getattr(destination, "citizens", ())))
            if available <= 0:
                continue
            factors = {
                "food": self._food_ratio(destination)
                * max(0.0, float(self.settings.get("food_attractiveness", 0.0))),
                "capacity": (available / capacity)
                * max(
                    0.0,
                    float(self.settings.get("capacity_attractiveness", 0.0)),
                ),
            }
            from core.artifacts import ArtifactRegistry
            factors["artifacts"] = ArtifactRegistry(
                self.world, self.config
            ).prestige_bonus(destination.entity_id)
            known = int(destination.entity_id) in set(
                getattr(source, "known_cities", ())
            )
            if known:
                factors["knowledge"] = max(
                    0.0, float(self.settings.get("knowledge_bonus", 0.0))
                )
            destination_families = {
                str(getattr(person, "family_name", "") or "")
                for person in getattr(destination, "citizens", ())
            }
            if (source_families - {""}) & (destination_families - {""}):
                factors["family"] = max(
                    0.0, float(self.settings.get("family_bonus", 0.0))
                )
            distance = math.dist(tuple(source.pos), tuple(destination.pos))
            factors["distance"] = -distance * max(
                0.0, float(self.settings.get("distance_penalty", 0.0))
            )
            ranked.append(
                {
                    "settlement_id": int(destination.entity_id),
                    "score": round(sum(factors.values()), 6),
                    "factors": {
                        key: round(value, 6) for key, value in factors.items()
                    },
                    "available_capacity": available,
                }
            )
        return sorted(
            ranked,
            key=lambda candidate: (
                -candidate["score"],
                candidate["settlement_id"],
            ),
        )

    def summary(self):
        if not self.enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "total_migrants": int(self.state.get("total_migrants", 0)),
            "returnees": int(self.state.get("returnees", 0)),
            "active_diasporas": sum(
                len(cultures)
                for cultures in self.state.get("diasporas", {}).values()
            ),
            "diasporas": deepcopy(self.state.get("diasporas", {})),
            "recent_cohorts": deepcopy(self.state.get("cohorts", [])),
        }

    def _select_cohort(self, source):
        citizens = [
            person
            for person in getattr(source, "citizens", ())
            if not getattr(person, "is_dead", False)
        ]
        minimum = max(0, int(self.settings.get("minimum_population", 1)))
        size = min(
            max(1, int(self.settings.get("cohort_size", 1))),
            max(0, len(citizens) - minimum),
        )
        if size <= 0:
            return []
        return sorted(
            citizens,
            key=lambda person: (
                not self._is_notable(person),
                int(getattr(person, "entity_id", 0)),
            ),
        )[:size]

    def _move_cohort(self, source, destination, people, causes, destination_score):
        source_ids = {
            int(getattr(person, "entity_id", 0)) for person in people
        }
        source.citizens = [
            person for person in source.citizens
            if int(getattr(person, "entity_id", 0)) not in source_ids
        ]
        returnees = 0
        for person in people:
            origin = getattr(person, "migrant_origin_id", None)
            if origin is None:
                person.migrant_origin_id = int(source.entity_id)
            elif int(origin) == int(destination.entity_id):
                returnees += 1
            person.pos = list(destination.pos)
            if hasattr(person, "home_city"):
                person.home_city = destination
            destination.citizens.append(person)

        record = {
            "cohort_id": int(self.state["next_cohort_id"]),
            "cycle": int(self.world.get("cycle", 0)),
            "origin_id": int(source.entity_id),
            "destination_id": int(destination.entity_id),
            "count": len(people),
            "notable_ids": sorted(
                int(person.entity_id) for person in people if self._is_notable(person)
            ),
            "causes": deepcopy(causes),
            "destination_factors": deepcopy(destination_score["factors"]),
            "carried": self._carried_identity(people),
            "returnees": returnees,
        }
        self.state["next_cohort_id"] += 1
        self.state["cohorts"].append(record)
        limit = max(1, int(self.settings.get("max_history", 64)))
        if len(self.state["cohorts"]) > limit:
            del self.state["cohorts"][:-limit]
        self.state["total_migrants"] += len(people)
        self.state["returnees"] += returnees
        self._update_diasporas(destination, people)
        from core.logger import GameLogger
        from core.translator import Translator
        primary_cause = max(causes, key=lambda key: (causes[key], key))
        GameLogger.log(
            Translator.translate(
                "events.migration_cohort",
                count=len(people),
                origin=getattr(source, "name", source.entity_id),
                destination=getattr(destination, "name", destination.entity_id),
                cause=Translator.translate(f"events.migration_cause_{primary_cause}"),
            ),
            category="migration",
            entity_ids=[source.entity_id, destination.entity_id],
            position=destination.pos,
            event_type="migration_cohort",
            actors=[
                {"entity_id": source.entity_id, "role": "origin"},
                {"entity_id": destination.entity_id, "role": "destination"},
                {"entity_id": people[0].entity_id, "role": "migrant"},
            ],
            objects=[{
                "object_id": f"cohort:{record['cohort_id']}",
                "role": "cohort",
            }],
            locations=[
                {"location_id": f"tile:{source.pos[0]},{source.pos[1]}", "role": "origin"},
                {"location_id": f"tile:{destination.pos[0]},{destination.pos[1]}", "role": "destination"},
            ],
            causes=[
                {"kind": key, "weight": value}
                for key, value in causes.items()
                if value > 0
            ],
            consequences=[{
                "kind": "diaspora",
                "destination_id": destination.entity_id,
                "returnees": returnees,
            }],
            facts={
                "cohort_id": record["cohort_id"],
                "count": record["count"],
                "carried": deepcopy(record["carried"]),
            },
        )
        return record

    def _update_diasporas(self, destination, people):
        settlement_key = str(int(destination.entity_id))
        cultures = self.state["diasporas"].setdefault(settlement_key, {})
        destination_culture = self._culture_name(destination)
        rate = min(1.0, max(0.0, float(self.settings.get("integration_rate", 0.0))))
        penalty = min(
            1.0,
            max(0.0, float(self.settings.get("discrimination_penalty", 0.0))),
        )
        for culture_name in sorted({self._culture_name(person) for person in people}):
            count = sum(self._culture_name(person) == culture_name for person in people)
            entry = cultures.setdefault(
                culture_name,
                {"population": 0, "integration": 0.0},
            )
            entry["population"] += count
            effective_rate = rate * (
                1.0 if culture_name == destination_culture else 1.0 - penalty
            )
            entry["integration"] = round(
                min(1.0, float(entry.get("integration", 0.0)) + effective_rate),
                6,
            )

    def _carried_identity(self, people):
        cultures = sorted({self._culture_name(person) for person in people})
        faiths = sorted(
            {
                str(getattr(getattr(person, "faith", None), "primary", ""))
                for person in people
                if getattr(getattr(person, "faith", None), "primary", None)
            }
        )
        skills = sorted(
            {
                str(skill)
                for person in people
                for skill in (
                    getattr(person, "skills", {}).keys()
                    if isinstance(getattr(person, "skills", None), dict)
                    else ()
                )
            }
        )
        diseases = sorted(
            {
                str(getattr(person, "disease"))
                for person in people
                if getattr(person, "disease", None)
            }
        )
        stories = sorted(
            {
                str(memory.get("kind"))
                for person in people
                for memory in (
                    getattr(person, "memories", ())
                    if isinstance(getattr(person, "memories", None), list)
                    else ()
                )
                if isinstance(memory, dict) and memory.get("kind")
            }
        )
        return {
            "cultures": cultures,
            "faiths": faiths,
            "skills": skills,
            "diseases": diseases,
            "stories": stories,
        }

    def _settlements(self):
        return sorted(
            (
                entity
                for entity in self.world.get("entities", ())
                if hasattr(entity, "citizens")
                and hasattr(entity, "food_stock")
                and not getattr(entity, "is_expired", False)
            ),
            key=lambda entity: int(entity.entity_id),
        )

    def _by_id(self, entity_id):
        return next(
            (
                settlement
                for settlement in self._settlements()
                if int(settlement.entity_id) == int(entity_id)
            ),
            None,
        )

    @staticmethod
    def _food_ratio(settlement):
        capacity = max(1.0, float(getattr(settlement, "max_food", 1.0)))
        return min(
            1.0,
            max(0.0, float(getattr(settlement, "food_stock", 0.0)) / capacity),
        )

    @staticmethod
    def _culture_name(entity):
        culture = getattr(entity, "culture", None)
        if isinstance(culture, dict):
            return str(culture.get("name", ""))
        return str(culture or "")

    @staticmethod
    def _is_notable(person):
        character = getattr(person, "character", None)
        notability = (
            character.get("notability", {}) if isinstance(character, dict) else {}
        )
        return isinstance(notability, dict) and notability.get("is_notable") is True

