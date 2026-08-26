"""Requêtes transversales et explications causales de l'état du monde."""

from copy import deepcopy
import json

from core.chronicles import ChronicleBook
from core.translator import Translator


class ExplanationService:
    """Construit des lectures chronologiques, causales et situationnelles."""

    def __init__(self, world, config):
        self.world = world
        section = config.get("explanations", {}) if isinstance(config, dict) else {}
        self.settings = section if isinstance(section, dict) else {}
        self.config = config if isinstance(config, dict) else {}
        self.enabled = self.settings.get("enabled") is True

    def query(
        self,
        *,
        entity_id=None,
        location_id=None,
        object_id=None,
        family=None,
        event_type=None,
        category=None,
        limit=None,
    ):
        if not self.enabled:
            return {
                "enabled": False,
                "chronicles": [],
                "sites": [],
                "artifacts": [],
                "legends": [],
            }
        maximum = self._limit(limit)
        filters = {
            key: value for key, value in {
                "entity_id": entity_id,
                "location_id": location_id,
                "object_id": object_id,
                "event_type": event_type,
                "category": category,
            }.items() if value is not None
        }
        chronicles = ChronicleBook(self.world, self.config).query(**filters)
        if family is not None:
            expected = str(family)
            chronicles = [
                entry for entry in chronicles
                if str(entry.get("facts", {}).get("family", "")) == expected
                or expected in json.dumps(
                    entry.get("facts", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            ]
        chronicles = chronicles[-maximum:]
        chronicle_ids = {
            int(entry["chronicle_id"]) for entry in chronicles
        }

        from core.sites import SiteRegistry
        sites = SiteRegistry(self.world, self.config).query()
        if location_id is not None:
            sites = [
                site for site in sites
                if self._site_location_id(site) == str(location_id)
                or f"site:{site['site_id']}" == str(location_id)
            ]
        if entity_id is not None:
            identifier = int(entity_id)
            sites = [
                site for site in sites
                if identifier in (
                    site.get("owner_ids", [])
                    + site.get("founder_ids", [])
                    + site.get("occupant_ids", [])
                )
            ]

        from core.artifacts import ArtifactRegistry
        artifacts = ArtifactRegistry(self.world, self.config).query()
        if object_id is not None:
            artifacts = [
                artifact for artifact in artifacts
                if f"artifact:{artifact['artifact_id']}" == str(object_id)
            ]
        if entity_id is not None:
            identifier = int(entity_id)
            artifacts = [
                artifact for artifact in artifacts
                if identifier in (
                    artifact.get("creator_id"),
                    artifact.get("holder", {}).get("id"),
                )
            ]

        from core.legends import LegendRegistry
        legends = LegendRegistry(self.world, self.config).query()
        if chronicle_ids:
            legends = [
                legend for legend in legends
                if int(legend["origin_chronicle_id"]) in chronicle_ids
                or (
                    object_id is not None
                    and self._legend_matches_object(legend, object_id)
                )
            ]
        elif any(
            value is not None
            for value in (
                entity_id, location_id, object_id, family, event_type, category
            )
        ):
            legends = [
                legend for legend in legends
                if self._legend_matches_filters(
                    legend,
                    entity_id=entity_id,
                    location_id=location_id,
                    object_id=object_id,
                    family=family,
                    event_type=event_type,
                    category=category,
                )
            ]
        return {
            "enabled": True,
            "chronicles": deepcopy(chronicles),
            "sites": deepcopy(sites[-maximum:]),
            "artifacts": deepcopy(artifacts[-maximum:]),
            "legends": deepcopy(legends[-maximum:]),
        }

    def timeline(self, **filters):
        result = self.query(**filters)
        return sorted(
            result["chronicles"],
            key=lambda entry: (
                int(entry.get("cycle", 0)),
                int(entry.get("chronicle_id", 0)),
            ),
        )

    def causal_view(self, chronicle_id, *, max_depth=32):
        event = ChronicleBook(self.world, self.config).get(chronicle_id)
        if event is None:
            return None
        book = ChronicleBook(self.world, self.config)
        causes = [
            entry for entry in book.causal_chain(
                chronicle_id, direction="causes", max_depth=max_depth
            )
            if entry["chronicle_id"] != int(chronicle_id)
        ]
        consequences = [
            entry for entry in book.causal_chain(
                chronicle_id, direction="results", max_depth=max_depth
            )
            if entry["chronicle_id"] != int(chronicle_id)
        ]
        return {
            "event": event,
            "causes": causes,
            "consequences": consequences,
        }

    def why(self, subject_kind, subject_id, *, question=None):
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}
        kind = str(subject_kind)
        if kind == "entity":
            return self._why_entity(subject_id, question)
        if kind == "war":
            return self._why_war(subject_id)
        if kind == "artifact":
            return self._why_artifact(subject_id)
        if kind == "site":
            return self._why_site(subject_id)
        if kind == "event":
            view = self.causal_view(subject_id)
            return {
                "enabled": True,
                "status": "explained" if view is not None else "unknown",
                "subject": {"kind": kind, "id": subject_id},
                "causes": [] if view is None else deepcopy(view["causes"]),
                "timeline": [] if view is None else [view["event"]],
            }
        return {
            "enabled": True,
            "status": "unknown",
            "subject": {"kind": kind, "id": subject_id},
            "causes": [],
            "timeline": [],
        }

    def overview(self, category=None):
        if not self.enabled:
            return []
        entries = []
        if category in (None, "warfare"):
            for campaign in self.world.get("warfare", {}).get("campaigns", ()):
                if campaign.get("status") == "active":
                    entries.append(self._why_war(campaign["campaign_id"]))
        if category in (None, "hunger"):
            for entity in self.world.get("entities", ()):
                if not hasattr(entity, "food_stock") or not hasattr(entity, "max_food"):
                    continue
                ratio = float(entity.food_stock) / max(1.0, float(entity.max_food))
                if ratio < self._number("hunger_ratio", 0.25):
                    entries.append(
                        self._why_entity(entity.entity_id, "hunger")
                    )
        if category in (None, "artifacts"):
            from core.artifacts import ArtifactRegistry
            for artifact in ArtifactRegistry(
                self.world, self.config
            ).query(status="lost"):
                entries.append(
                    self._why_artifact(artifact["artifact_id"])
                )
        if category in (None, "legends"):
            from core.legends import LegendRegistry
            for motive in LegendRegistry(
                self.world, self.config
            ).motivations():
                entries.append({
                    "enabled": True,
                    "status": "explained",
                    "subject": {
                        "kind": "legend",
                        "id": motive["legend_id"],
                    },
                    "summary": Translator.translate(
                        "explanations.legend_motive",
                        motive=motive["kind"],
                        legend_id=motive["legend_id"],
                    ),
                    "causes": [{
                        "kind": "legend_renown",
                        "value": motive["renown"],
                    }],
                    "timeline": [],
                })
        if category is not None and not entries:
            queried = self.timeline(category=category)
            for event in queried:
                entries.append({
                    "enabled": True,
                    "status": "explained",
                    "subject": {
                        "kind": "event",
                        "id": event["chronicle_id"],
                    },
                    "summary": event["message"],
                    "causes": deepcopy(event.get("causes", [])),
                    "timeline": [event],
                })
        return entries[-self._limit(None):]

    def export(self):
        from core.legends import LegendRegistry
        return {
            "version": 1,
            "cycle": int(self.world.get("cycle", 0)),
            "timeline": self.timeline(),
            "legends": LegendRegistry(
                self.world, self.config
            ).query(),
            "situations": self.overview(),
        }

    def export_json(self, *, indent=2):
        return json.dumps(
            self.export(),
            ensure_ascii=False,
            sort_keys=True,
            indent=indent,
        )

    def _why_entity(self, entity_id, question):
        entity = self._entity(entity_id)
        if entity is None:
            return self._unknown("entity", entity_id)
        causes = []
        if question in (None, "hunger") and hasattr(entity, "food_stock"):
            stock = max(0.0, float(entity.food_stock))
            capacity = max(1.0, float(getattr(entity, "max_food", 1.0)))
            ratio = stock / capacity
            if ratio < self._number("hunger_ratio", 0.25):
                causes.append({
                    "kind": "low_food_stock",
                    "stock": round(stock, 6),
                    "capacity": round(capacity, 6),
                    "ratio": round(ratio, 6),
                })
        for campaign in self.world.get("warfare", {}).get("campaigns", ()):
            if int(entity_id) in (
                campaign.get("attacker_id"),
                campaign.get("defender_id"),
            ) and campaign.get("status") == "active":
                causes.append({
                    "kind": "active_war",
                    "campaign_id": campaign["campaign_id"],
                    "cause": campaign.get("cause"),
                })
        timeline = self.timeline(entity_id=int(entity_id))
        return {
            "enabled": True,
            "status": "explained" if causes or timeline else "observed",
            "subject": {"kind": "entity", "id": int(entity_id)},
            "summary": Translator.translate(
                "explanations.entity_summary",
                entity_id=int(entity_id),
                causes=len(causes),
            ),
            "causes": causes,
            "timeline": timeline,
        }

    def _why_war(self, campaign_id):
        identifier = int(campaign_id)
        campaign = next(
            (
                value for value in self.world.get(
                    "warfare", {}
                ).get("campaigns", ())
                if int(value.get("campaign_id", -1)) == identifier
            ),
            None,
        )
        if campaign is None:
            return self._unknown("war", identifier)
        causes = [{
            "kind": str(campaign.get("cause", "unknown")),
            "objective": campaign.get("objective"),
            "evidence": deepcopy(campaign.get("evidence", [])),
        }]
        timeline = self.timeline(
            object_id=f"campaign:{identifier}"
        )
        return {
            "enabled": True,
            "status": "explained",
            "subject": {"kind": "war", "id": identifier},
            "summary": Translator.translate(
                "explanations.war_summary",
                campaign_id=identifier,
                cause=causes[0]["kind"],
            ),
            "causes": causes,
            "timeline": timeline,
        }

    def _why_artifact(self, artifact_id):
        from core.artifacts import ArtifactRegistry
        artifact = ArtifactRegistry(
            self.world, self.config
        ).get(artifact_id)
        if artifact is None:
            return self._unknown("artifact", artifact_id)
        return {
            "enabled": True,
            "status": "explained",
            "subject": {
                "kind": "artifact",
                "id": int(artifact_id),
            },
            "summary": Translator.translate(
                "explanations.artifact_summary",
                artifact=artifact["name"],
                events=len(artifact["provenance"]),
            ),
            "causes": [{
                "kind": "created_by",
                "creator_id": artifact.get("creator_id"),
                "materials": deepcopy(artifact.get("material_ids", [])),
                "quality": artifact.get("quality"),
            }],
            "timeline": deepcopy(artifact["provenance"]),
        }

    def _why_site(self, site_id):
        from core.sites import SiteRegistry
        site = SiteRegistry(self.world, self.config).get(site_id)
        if site is None:
            return self._unknown("site", site_id)
        return {
            "enabled": True,
            "status": "explained",
            "subject": {"kind": "site", "id": int(site_id)},
            "summary": Translator.translate(
                "explanations.site_summary",
                site_id=int(site_id),
                events=len(site["history"]),
            ),
            "causes": deepcopy(site.get("facts", {})),
            "timeline": deepcopy(site["history"]),
        }

    def _unknown(self, kind, identifier):
        return {
            "enabled": True,
            "status": "unknown",
            "subject": {"kind": kind, "id": identifier},
            "summary": Translator.translate(
                "explanations.unknown",
                kind=kind,
                subject_id=identifier,
            ),
            "causes": [],
            "timeline": [],
        }

    def _entity(self, entity_id):
        identifier = int(entity_id)
        for entity in self.world.get("entities", ()):
            if int(getattr(entity, "entity_id", -1)) == identifier:
                return entity
            for citizen in getattr(entity, "citizens", ()):
                if int(getattr(citizen, "entity_id", -1)) == identifier:
                    return citizen
        return None

    @staticmethod
    def _site_location_id(site):
        position = site.get("position", [0, 0])
        return f"tile:{position[0]},{position[1]}"

    @staticmethod
    def _legend_matches_object(legend, object_id):
        return any(
            str(value.get("object_id")) == str(object_id)
            for value in legend["fact"].get("objects", ())
        )

    def _legend_matches_filters(self, legend, **filters):
        fact = legend["fact"]
        if filters["entity_id"] is not None and not any(
            actor.get("entity_id") == int(filters["entity_id"])
            for actor in fact.get("actors", ())
        ):
            return False
        if filters["location_id"] is not None and not any(
            location.get("location_id") == str(filters["location_id"])
            for location in fact.get("locations", ())
        ):
            return False
        if filters["object_id"] is not None and not self._legend_matches_object(
            legend, filters["object_id"]
        ):
            return False
        if filters["family"] is not None and str(
            fact.get("facts", {}).get("family", "")
        ) != str(filters["family"]):
            return False
        if filters["event_type"] is not None and fact.get(
            "event_type"
        ) != str(filters["event_type"]):
            return False
        if filters["category"] is not None and fact.get(
            "category"
        ) != str(filters["category"]):
            return False
        return True

    @staticmethod
    def _normalize_pair(values):
        return tuple(values) if isinstance(values, (list, tuple)) else ()

    def _limit(self, value):
        candidate = self.settings.get("max_results", 64) if value is None else value
        if (
            isinstance(candidate, bool)
            or not isinstance(candidate, int)
            or candidate <= 0
        ):
            return 64
        return candidate

    def _number(self, key, default):
        value = self.settings.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return float(default)
        return max(0.0, float(value))
