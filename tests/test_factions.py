import unittest
from types import SimpleNamespace

from core.random_service import RandomService


def politics_config(enabled=True):
    return {
        "politics": {
            "enabled": enabled,
            "faction_types": [
                {
                    "id": "profession",
                    "source": "profession",
                    "objectives": {
                        "Trader": "open_trade",
                        "Soldier": "military_readiness",
                        "default": "food_security",
                    },
                    "opposes": {
                        "open_trade": ["military_readiness"],
                        "military_readiness": ["open_trade"],
                    },
                    "base_influence": 20,
                },
                {
                    "id": "faith",
                    "source": "faith",
                    "objective": "religious_privilege",
                    "base_influence": 10,
                },
                {
                    "id": "household",
                    "source": "household",
                    "objective": "family_security",
                    "base_influence": 5,
                },
            ],
        }
    }


def citizen(entity_id, profession, *, faith="Sun", household="Vale"):
    return SimpleNamespace(
        entity_id=entity_id,
        name=f"Person {entity_id}",
        pos=(2, 3),
        profession=profession,
        family_name=household,
        faith=SimpleNamespace(religion_name=faith),
        character={"household_id": household},
        is_dead=False,
        is_expired=False,
    )


def settlement(config=None):
    people = [
        citizen(11, "Trader", household="Vale"),
        citizen(12, "Soldier", household="Vale"),
        citizen(13, "Farmer", faith="Moon", household="Reed"),
    ]
    return SimpleNamespace(
        entity_id=7,
        name="Harbor",
        pos=(2, 3),
        citizens=people,
        population=len(people),
        food_stock=30,
        max_food=100,
        config=config or politics_config(),
        economy={"treasury": 100.0},
        is_expired=False,
    )


def politics_world(city):
    return {
        "cycle": 0,
        "entities": [city],
        "diplomacy": {},
        "chronicles": [],
    }


class FactionRegistryTests(unittest.TestCase):
    def test_disabled_registry_is_a_noop_for_legacy_settlements(self):
        from core.factions import FactionRegistry

        city = settlement(politics_config(enabled=False))
        world = politics_world(city)

        registry = FactionRegistry(world, city.config)

        self.assertEqual(registry.sync(city), [])
        self.assertEqual(registry.query(), [])
        self.assertFalse(hasattr(city, "politics"))

    def test_membership_is_derived_from_profession_faith_and_household_with_stable_ids(self):
        from core.factions import FactionRegistry

        city = settlement()
        world = politics_world(city)
        RandomService.initialize(1301)
        before = RandomService.get_state()
        registry = FactionRegistry(world, city.config)

        first = registry.sync(city)
        second = registry.sync(city)

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 7)
        self.assertEqual(
            {(faction["kind"], faction["key"]) for faction in first},
            {
                ("profession", "Farmer"),
                ("profession", "Soldier"),
                ("profession", "Trader"),
                ("faith", "Moon"),
                ("faith", "Sun"),
                ("household", "Reed"),
                ("household", "Vale"),
            },
        )
        trader = next(
            faction for faction in first
            if faction["kind"] == "profession" and faction["key"] == "Trader"
        )
        soldier = next(
            faction for faction in first
            if faction["kind"] == "profession" and faction["key"] == "Soldier"
        )
        self.assertEqual(trader["member_ids"], [11])
        self.assertEqual(trader["objective"], "open_trade")
        self.assertIn(soldier["objective"], trader["opposed_objectives"])
        self.assertEqual(
            [faction["faction_id"] for faction in first],
            [faction["faction_id"] for faction in second],
        )

    def test_satisfaction_and_influence_are_bounded_and_queries_are_defensive(self):
        from core.factions import FactionRegistry

        city = settlement()
        registry = FactionRegistry(politics_world(city), city.config)
    def test_high_cardinality_households_are_bounded_for_modest_hardware(self):
        from core.factions import FactionRegistry

        config = politics_config()
        config["politics"]["max_factions_per_type"] = 4
        city = settlement(config)
        city.citizens = [
            citizen(index, "Farmer", household=f"Family-{index}")
            for index in range(1, 21)
        ]
        registry = FactionRegistry(politics_world(city), config)

        factions = registry.sync(city)
        households = [
            faction for faction in factions
            if faction["kind"] == "household"
        ]

        self.assertEqual(len(households), 4)
        self.assertEqual(
            [faction["key"] for faction in households],
            ["Family-1", "Family-10", "Family-11", "Family-12"],
        )

        faction = registry.sync(city)[0]

        registry.adjust_satisfaction(faction["faction_id"], -500, reason="famine")
        registry.set_influence(faction["faction_id"], 500)
        snapshot = registry.query(faction_id=faction["faction_id"])[0]

        self.assertEqual(snapshot["satisfaction"], 0.0)
        self.assertEqual(snapshot["influence"], 100.0)
        self.assertEqual(snapshot["grievances"][-1]["reason"], "famine")
        snapshot["member_ids"].append(999)
        self.assertNotIn(
            999,
            registry.query(faction_id=faction["faction_id"])[0]["member_ids"],
        )

    def test_inspection_exposes_settlement_factions_and_citizen_memberships(self):
        from core.factions import FactionRegistry
        from core.inspection import inspect_entity

        city = settlement()
        world = politics_world(city)
        registry = FactionRegistry(world, city.config)
        factions = registry.sync(city)

        city_view = inspect_entity(world, city.entity_id)
        citizen_view = inspect_entity(world, city.citizens[0].entity_id)

        self.assertEqual(city_view["politics"]["factions"], factions)
        self.assertEqual(citizen_view["owner_entity_id"], city.entity_id)
        self.assertGreaterEqual(len(citizen_view["politics"]["memberships"]), 3)


if __name__ == "__main__":
    unittest.main()

def institutional_config():
    config = politics_config()
    config["politics"].update({
        "default_government": "council",
        "governments": [
            {
                "id": "council",
                "head_office": "steward",
                "offices": [
                    {
                        "id": "steward",
                        "skill": "leadership",
                        "minimum_notability": 20,
                        "term_cycles": 12,
                    },
                    {
                        "id": "marshal",
                        "skill": "combat",
                        "minimum_notability": 20,
                        "term_cycles": 24,
                    },
                ],
            }
        ],
        "initial_legitimacy": 55,
    })
    return config


def make_notable(person, *, score, leadership=0, combat=0):
    person.character.update({
        "notability": {
            "is_notable": True,
            "score": score,
            "reasons": [],
        },
        "skills": {
            "leadership": leadership,
            "combat": combat,
        },
    })
    return person


class InstitutionTests(unittest.TestCase):
    def test_government_and_vacant_offices_are_created_from_configuration(self):
        from core.institutions import InstitutionService

        config = institutional_config()
        city = settlement(config)
        service = InstitutionService(politics_world(city), config, city)

        snapshot = service.snapshot()

        self.assertEqual(snapshot["government_id"], "council")
        self.assertEqual(snapshot["legitimacy"], 55.0)
        self.assertEqual(set(snapshot["offices"]), {"steward", "marshal"})
        self.assertTrue(all(
            office["status"] == "vacant"
            and office["holder_id"] is None
            for office in snapshot["offices"].values()
        ))

    def test_only_eligible_notables_are_appointed_without_duplicate_identity(self):
        from core.institutions import InstitutionService

        config = institutional_config()
        city = settlement(config)
        eligible = make_notable(city.citizens[0], score=30, leadership=40)
        service = InstitutionService(politics_world(city), config, city)

        appointed = service.appoint("steward", eligible, cycle=2)

        self.assertEqual(appointed["holder_id"], eligible.entity_id)
        self.assertIs(city.citizens[0], eligible)
        with self.assertRaises(ValueError):
            service.appoint("marshal", eligible, cycle=2)
        with self.assertRaises(ValueError):
            service.appoint("marshal", city.citizens[1], cycle=2)

    def test_expired_term_uses_deterministic_person_based_succession(self):
        from core.institutions import InstitutionService

        config = institutional_config()
        city = settlement(config)
        outgoing = make_notable(city.citizens[2], score=25, leadership=10)
        leader = make_notable(city.citizens[0], score=30, leadership=50)
        rival = make_notable(city.citizens[1], score=70, leadership=20)
        world = politics_world(city)
        service = InstitutionService(world, config, city)
        service.appoint("steward", outgoing, cycle=0)
        outgoing.is_dead = True

        result = service.advance(cycle=12)

        self.assertEqual(result["offices"]["steward"]["holder_id"], leader.entity_id)
        self.assertNotEqual(result["offices"]["steward"]["holder_id"], rival.entity_id)
        self.assertEqual(result["offices"]["steward"]["succession_count"], 1)
        self.assertEqual(world["metrics"]["flows"]["politics"]["successions"], 2)
        self.assertEqual(result["regent_id"], None)

    def test_vacant_head_uses_an_existing_officer_as_regent_and_records_crisis(self):
        from core.institutions import InstitutionService

        config = institutional_config()
        city = settlement(config)
        marshal = make_notable(city.citizens[0], score=30, combat=60)
        world = politics_world(city)
        service = InstitutionService(world, config, city)
        service.appoint("marshal", marshal, cycle=0)

        result = service.advance(cycle=12)

        self.assertEqual(result["offices"]["steward"]["status"], "vacant")
        self.assertEqual(result["regent_id"], marshal.entity_id)
        self.assertEqual(result["succession_crises"], 1)
        self.assertEqual(world["metrics"]["flows"]["politics"]["crises"], 1)
        self.assertLess(result["legitimacy"], 55.0)

def policy_config():
    config = institutional_config()
    config["politics"].update({
        "proposal_threshold": 5,
        "policies": [
            {
                "id": "market_charter",
                "duration_cycles": 24,
                "supports": ["open_trade"],
                "opposes": ["military_readiness"],
                "modifiers": {
                    "trade_capacity_multiplier": 1.5,
                    "labor_efficiency_multiplier": 0.9,
                    "religious_tolerance_multiplier": 1.1,
                    "defense_multiplier": 0.8,
                    "tax_rate": 0.05,
                },
            },
            {
                "id": "military_levy",
                "duration_cycles": 12,
                "supports": ["military_readiness"],
                "opposes": ["open_trade"],
                "modifiers": {
                    "trade_capacity_multiplier": 0.7,
                    "labor_efficiency_multiplier": 0.8,
                    "defense_multiplier": 1.4,
                    "tax_rate": 0.1,
                },
            },
        ],
    })
    return config


class PolicyTests(unittest.TestCase):
    def _services(self):
        from core.factions import FactionRegistry
        from core.institutions import PolicyService

        config = policy_config()
        city = settlement(config)
        world = politics_world(city)
        registry = FactionRegistry(world, config)
        factions = registry.sync(city)
        trader = next(
            faction for faction in factions
            if faction["kind"] == "profession" and faction["key"] == "Trader"
        )
        soldier = next(
            faction for faction in factions
            if faction["kind"] == "profession" and faction["key"] == "Soldier"
        )
        registry.set_influence(trader["faction_id"], 90)
        registry.set_influence(soldier["faction_id"], 10)
        return world, city, registry, trader, soldier, PolicyService(world, config, city)

    def test_proposal_records_support_opposition_causes_and_affected_groups(self):
        from core.logger import GameLogger
        from core.translator import Translator
        Translator.load("fr")
        GameLogger.get_new_logs()
        world, city, registry, trader, soldier, service = self._services()
        RandomService.initialize(1303)
        before = RandomService.get_state()

        proposal = service.propose(
            "market_charter",
            trader["faction_id"],
            cycle=3,
        )
        resolved = service.resolve(proposal["proposal_id"], cycle=3)

        self.assertEqual(RandomService.get_state(), before)
        self.assertEqual(resolved["status"], "enacted")
        self.assertIn(trader["faction_id"], resolved["supporter_ids"])
        self.assertIn(soldier["faction_id"], resolved["opponent_ids"])
        self.assertGreater(resolved["support_score"], resolved["opposition_score"])
        self.assertEqual(
            resolved["causes"],
            ["faction_interests", "satisfaction", "relationships", "legitimacy", "information"],
        )
        logs = GameLogger.get_new_logs()
        self.assertGreater(resolved["relationship_score"], 0)
        metadata = GameLogger.get_last_metadata(len(logs))
        self.assertTrue(logs)
        self.assertEqual(metadata[-1]["category"], "politics")
        self.assertEqual(resolved["winners"], resolved["supporter_ids"])
        self.assertEqual(resolved["losers"], resolved["opponent_ids"])
        flows = world["metrics"]["flows"]["politics"]
        self.assertEqual(flows["proposals"], 1)
        self.assertEqual(flows["enacted"], 1)

    def test_enacted_modifiers_are_explicit_composable_and_expire(self):
        from core.institutions import policy_modifier, settlement_policy_modifier

        world, city, registry, trader, soldier, service = self._services()
        proposal = service.propose("market_charter", trader["faction_id"], cycle=3)
        service.resolve(proposal["proposal_id"], cycle=3)

        self.assertEqual(
            policy_modifier(
                world,
                city,
                "trade_capacity_multiplier",
                default=1.0,
            ),
            1.5,
        )
        self.assertEqual(policy_modifier(world, city, "tax_rate", default=0.0), 0.05)
        self.assertEqual(settlement_policy_modifier(city, "trade_capacity_multiplier", default=1.0), 1.5)
        service.advance(cycle=27)
        self.assertEqual(
            policy_modifier(
                world,
                city,
                "trade_capacity_multiplier",
                default=1.0,
            ),
            1.0,
        )
        self.assertEqual(service.snapshot()["active_policies"], [])
        self.assertEqual(settlement_policy_modifier(city, "trade_capacity_multiplier", default=1.0), 1.0)

    def test_rejected_proposal_has_no_modifier(self):
        from core.institutions import policy_modifier

        world, city, registry, trader, soldier, service = self._services()
        registry.set_influence(trader["faction_id"], 5)
        registry.set_influence(soldier["faction_id"], 100)

        proposal = service.propose("market_charter", trader["faction_id"], cycle=1)
        resolved = service.resolve(proposal["proposal_id"], cycle=1)

        self.assertEqual(resolved["status"], "rejected")
        self.assertEqual(
            policy_modifier(
                world,
                city,
                "trade_capacity_multiplier",
                default=1.0,
            ),
            1.0,
        )

def conflict_config():
    config = policy_config()
    config["politics"].update({
        "advance_interval": 1,
        "famine_ratio": 0.25,
        "famine_penalty": 25,
        "tax_dissent_scale": 100,
        "war_dissent": 10,
        "protest_threshold": 50,
        "sabotage_threshold": 75,
        "revolt_threshold": 90,
        "sabotage_min_influence": 30,
        "coup_min_influence": 60,
        "reform_min_legitimacy": 50,
        "conflict_cooldown": 1,
        "sabotage_food_loss": 10,
        "policies": policy_config()["politics"]["policies"] + [
            {
                "id": "food_relief",
                "duration_cycles": 12,
                "supports": ["food_security", "family_security"],
                "opposes": ["open_trade"],
                "modifiers": {
                    "tax_rate": -0.05,
                    "labor_efficiency_multiplier": 1.1,
                },
            }
        ],
    })
    return config


class InternalConflictTests(unittest.TestCase):
    def _service(self):
        from core.politics import PoliticsService

        config = conflict_config()
        city = settlement(config)
        world = politics_world(city)
        world["cycle"] = 1
        service = PoliticsService(world, config)
        service.sync(city)
        return world, city, service

    def _faction(self, service, *, kind, key):
        return next(
            faction for faction in service.registry.query(active=True)
            if faction["kind"] == kind and faction["key"] == key
        )

    def test_hunger_tax_and_war_create_measurable_dissent_and_protest(self):
        world, city, service = self._service()
        city.food_stock = 100
        city.max_food = 100
        world["diplomacy"] = {
            "7:8": {
                "first_id": city.entity_id,
                "second_id": 8,
                "status": "war",
            }
        }
        trader = self._faction(service, kind="profession", key="Trader")
        service.registry.adjust_satisfaction(
            trader["faction_id"],
            -15,
            reason="existing_grievance",
        )
        service.institution.state["active_policies"].append({
            "policy_id": "tax",
            "expires_cycle": 20,
            "modifiers": {"tax_rate": 0.1},
        })

        result = service.advance(cycle=1)

        updated = service.registry.query(faction_id=trader["faction_id"])[0]
        self.assertLess(updated["satisfaction"], 45)
        self.assertEqual(result["new_conflicts"][0]["kind"], "protest")
        self.assertLess(result["institution"]["legitimacy"], 55)

    def test_capable_military_faction_turns_severe_crisis_into_coup(self):
        from core.logger import GameLogger
        GameLogger.get_new_logs()
        world, city, service = self._service()
        soldier = self._faction(service, kind="profession", key="Soldier")
        service.registry.set_influence(soldier["faction_id"], 100)
        service.registry.adjust_satisfaction(
            soldier["faction_id"],
            -100,
            reason="defeat",
        )
        service.institution.state["legitimacy"] = 20

        result = service.advance(cycle=1)

        conflict = result["new_conflicts"][0]
        self.assertEqual(conflict["kind"], "coup")
        self.assertEqual(conflict["faction_id"], soldier["faction_id"])
        self.assertLess(result["institution"]["legitimacy"], 20)
        logs = GameLogger.get_new_logs()
        metadata = GameLogger.get_last_metadata(len(logs))
        self.assertTrue(logs)
        self.assertEqual(metadata[-1]["category"], "politics")
        self.assertEqual(world["metrics"]["flows"]["politics"]["coups"], 1)

    def test_legitimate_government_reforms_during_famine(self):
        world, city, service = self._service()
        farmer = self._faction(service, kind="profession", key="Farmer")
        service.registry.set_influence(farmer["faction_id"], 80)
        service.registry.adjust_satisfaction(
            farmer["faction_id"],
            -100,
            reason="famine",
        )
        service.institution.state["legitimacy"] = 80
        city.food_stock = 0

        result = service.advance(cycle=1)

        self.assertEqual(result["new_conflicts"][0]["kind"], "reform")
        self.assertIn(
            "food_relief",
            {
                policy["policy_id"]
                for policy in result["institution"]["active_policies"]
            },
        )

    def test_weak_faction_creates_exodus_pressure_and_can_be_negotiated_with(self):
        world, city, service = self._service()
        household = self._faction(service, kind="household", key="Vale")
        service.registry.set_influence(household["faction_id"], 5)
        service.registry.adjust_satisfaction(
            household["faction_id"],
            -100,
            reason="discrimination",
        )
        service.institution.state["legitimacy"] = 10

        result = service.advance(cycle=1)
        conflict = result["new_conflicts"][0]

        self.assertEqual(conflict["kind"], "exodus")
        self.assertGreater(result["migration_pressure"], 0)
        before = service.registry.query(
            faction_id=household["faction_id"]
        )[0]["satisfaction"]
        response = service.respond(
            conflict["conflict_id"],
            "negotiate",
            cycle=2,
        )
        self.assertEqual(world["metrics"]["flows"]["politics"]["exodus"], 1)
        self.assertEqual(world["metrics"]["flows"]["politics"]["responses"], 1)
        after = service.registry.query(
            faction_id=household["faction_id"]

        )[0]["satisfaction"]
        self.assertEqual(response["response"], "negotiate")
        self.assertGreater(after, before)

    def test_conflict_history_is_bounded_while_ids_remain_monotonic(self):
        world, city, service = self._service()
        service.settings["conflict_limit"] = 3
        service.settings["protest_threshold"] = 0

        service.advance(cycle=1)

        state = service.registry.storage["settlements"][str(city.entity_id)]
        conflicts = state["conflicts"]
        self.assertEqual(len(conflicts), 3)
        self.assertEqual(
            [item["conflict_id"] for item in conflicts],
            sorted(item["conflict_id"] for item in conflicts),
        )
        self.assertGreater(state["next_conflict_id"], conflicts[-1]["conflict_id"])


    def test_sabotage_consumes_real_food_and_repression_has_costs(self):
        world, city, service = self._service()
        trader = self._faction(service, kind="profession", key="Trader")
        service.registry.set_influence(trader["faction_id"], 50)
        service.registry.adjust_satisfaction(
            trader["faction_id"],
            -40,
            reason="taxes",
        )
        city.food_stock = 50
        service.institution.state["legitimacy"] = 20

        result = service.advance(cycle=1)
        conflict = result["new_conflicts"][0]

        self.assertEqual(conflict["kind"], "sabotage")
        self.assertEqual(city.food_stock, 40)
        legitimacy = service.institution.state["legitimacy"]
        service.respond(conflict["conflict_id"], "repress", cycle=2)
        self.assertLess(service.institution.state["legitimacy"], legitimacy)
