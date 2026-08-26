import unittest

from types import SimpleNamespace


def knowledge_config(**overrides):
    values = {
        "enabled": True,
        "perception_radius": 5.0,
        "observation_interval": 1,
        "max_facts": 32,
        "reliability_decay": 0.01,
        "transmission_decay": 0.1,
        "distance_decay": 0.01,
        "minimum_reliability": 0.05,
    }
    values.update(overrides)
    return {"knowledge": values}


def settlement(entity_id, pos, *, population=10, config=None):
    return SimpleNamespace(
        entity_id=entity_id,
        name=f"City {entity_id}",
        pos=pos,
        population=population,
        food_stock=50,
        max_food=100,
        is_expired=False,
        known_cities=set(),
        config=config or knowledge_config(),
    )


class KnowledgeIntegrationTests(unittest.TestCase):
    def test_trader_selects_only_a_known_market_and_explains_its_source(self):
        from core.knowledge import KnowledgeService
        from core.random_service import RandomService
        from entities.species.human.trader import Trader

        RandomService.initialize(12)
        config = knowledge_config(perception_radius=0)
        home = settlement(1, (0, 0), config=config)
        known = settlement(2, (12, 0), config=config)
        unknown = settlement(3, (2, 0), config=config)
        KnowledgeService(home, config).learn(
            kind="settlement",
            subject_id=known.entity_id,
            claim="state",
            value={"exists": True, "population": known.population},
            cycle=1,
            source_id=44,
            source_type="reported",
            reliability=0.6,
            position=known.pos,
        )
        trader = Trader.__new__(Trader)
        trader.entity_id = 50
        trader.pos = home.pos
        trader.config = config
        trader.home_city = home
        trader.base_city = home
        trader.target_city = None
        trader.visited_cities = set()
        trader.trades_since_home = 0
        trader._returning_home = False
        world = {"cycle": 2, "entities": [home, known, unknown]}

        trader._find_new_target(world)

        self.assertIs(trader.target_city, known)
        self.assertEqual(trader.knowledge_decision["subject_id"], known.entity_id)
        self.assertEqual(trader.knowledge_decision["source_id"], 44)
        self.assertEqual(trader.knowledge_decision["reliability"], 0.6)

    def test_trade_connection_transmits_reports_in_both_directions(self):
        from unittest import mock

        from core.knowledge import KnowledgeService
        from entities.species.human.trader import Trader

        config = knowledge_config(perception_radius=0)
        home = settlement(1, (0, 0), config=config)
        target = settlement(2, (5, 0), config=config)
        KnowledgeService(home, config).learn(
            kind="threat",
            subject_id=77,
            claim="danger",
            value="high",
            cycle=3,
            source_id=77,
            source_type="observed",
            reliability=1,
        )
        trader = Trader.__new__(Trader)
        trader.home_city = home
        trader.target_city = target
        world = {
            "cycle": 4,
            "road": [["  "] * 6],
            "width": 6,
            "height": 1,
        }

        with mock.patch("entities.species.human.trader.connect_with_road"):
            trader._establish_connection(world)

        report = KnowledgeService(target, config).best_fact(
            "threat", 77, claim="danger"
        )
        self.assertIsNotNone(report)
        self.assertEqual(report["source_id"], home.entity_id)
        self.assertEqual(report["source_type"], "reported")
        self.assertIn(target.entity_id, home.known_cities)
        self.assertIn(home.entity_id, target.known_cities)

    def test_exploration_records_only_the_observed_map_tile(self):
        from core.knowledge import KnowledgeService

        config = knowledge_config()
        explorer = settlement(1, (1, 0), config=config)
        world = {
            "cycle": 6,
            "entities": [explorer],
            "width": 3,
            "height": 1,
            "terrain": [["plain", "forest", "mountain"]],
            "biome": [["grassland", "forest", "alpine"]],
        }
        service = KnowledgeService(explorer, config)

        service.observe_tile(world, explorer.pos)

        maps = service.query(kind="map_tile")
        self.assertEqual(len(maps), 1)
        self.assertEqual(maps[0]["subject_id"], 1)
        self.assertEqual(maps[0]["position"], [1, 0])
        self.assertEqual(
            maps[0]["value"],
            {"terrain": "forest", "biome": "forest"},
        )


    def test_reported_scarcity_changes_market_selection_without_world_omniscience(self):
        from unittest import mock

        from core.knowledge import KnowledgeService
        from core.random_service import RandomService
        from entities.species.human.trader import Trader

        RandomService.initialize(18)
        config = knowledge_config(perception_radius=0)
        home = settlement(1, (0, 0), config=config)
        abundant = settlement(2, (12, 0), config=config)
        scarce = settlement(3, (12, 0), config=config)
        book = KnowledgeService(home, config)
        for candidate, ratio in ((abundant, 0.9), (scarce, 0.1)):
            book.learn(
                kind="settlement",
                subject_id=candidate.entity_id,
                claim="state",
                value={"exists": True, "population": 10, "food_ratio": ratio},
                cycle=1,
                source_id=40 + candidate.entity_id,
                source_type="reported",
                reliability=0.8,
                position=candidate.pos,
            )
        trader = Trader.__new__(Trader)
        trader.entity_id = 50
        trader.pos = home.pos
        trader.config = config
        trader.home_city = home
        trader.base_city = home
        trader.target_city = None
        trader.visited_cities = set()
        trader.trades_since_home = 0
        trader._returning_home = False
        world = {"cycle": 2, "entities": [home, abundant, scarce]}

        with mock.patch.object(RandomService, "random", return_value=1.0):
            trader._find_new_target(world)

        self.assertIs(trader.target_city, scarce)
        self.assertEqual(trader.knowledge_decision["value"]["food_ratio"], 0.1)

    def test_settler_observation_maps_the_real_world_layers(self):
        from core.knowledge import KnowledgeService
        from entities.species.human.settler import Settler

        config = knowledge_config()
        explorer = Settler.__new__(Settler)
        explorer.entity_id = 7
        explorer.pos = (0, 0)
        explorer.config = config
        explorer.is_expired = False
        explorer.distance_traveled = 0
        explorer.max_travel_time = 120
        explorer.home_city = SimpleNamespace(name="Home")
        explorer.land_char = "L"
        explorer.boat_char = "B"
        world = {
            "cycle": 4,
            "width": 1,
            "height": 1,
            "elev": [[0.25]],
            "riv": [[1]],
            "entities": [explorer],
        }

        explorer.think(world)

        fact = KnowledgeService(explorer, config).query(kind="map_tile")[0]
        self.assertEqual(fact["position"], [0, 0])
        self.assertEqual(fact["value"]["elevation"], 0.25)
        self.assertTrue(fact["value"]["river"])
        self.assertIn("biome", fact["value"])

    def test_raid_creates_a_transmissible_threat_fact(self):
        from unittest import mock

        from core.knowledge import KnowledgeService
        from entities.species.human.soldier import Soldier

        config = knowledge_config()
        target = settlement(2, (1, 1), config=config)
        target.citizens = []
        target.food_stock = 0
        home = settlement(1, (0, 0), config=config)
        soldier = Soldier.__new__(Soldier)
        soldier.entity_id = 77
        soldier.name = "Raider"
        soldier.strength = 1.0
        soldier.target_city = target
        soldier.home_city = home
        soldier.config = config
        soldier.is_dead = False
        soldier.is_expired = False
        world = {"cycle": 9, "entities": [home, target, soldier]}

        with mock.patch("entities.species.human.soldier.GameLogger.log"):
            soldier._raid_city(world)

        threat = KnowledgeService(target, config).best_fact(
            "threat", soldier.entity_id, claim="raid"
        )
        self.assertIsNotNone(threat)
        self.assertEqual(threat["source_type"], "observed")
        self.assertEqual(threat["value"]["attacker_city_id"], home.entity_id)

    def test_settler_copies_carried_knowledge_to_founded_village(self):
        from unittest import mock

        from core.knowledge import KnowledgeService
        from entities.species.human.settler import Settler

        config = knowledge_config()
        home = settlement(1, (0, 0), config=config)
        settler = Settler.__new__(Settler)
        settler.entity_id = 7
        settler.pos = (4, 0)
        settler.config = config
        settler.culture = {}
        settler.faith = None
        settler.home_city = home
        settler.is_expired = False
        KnowledgeService(settler, config).learn(
            kind="map_tile",
            subject_id=3,
            claim="survey",
            value={"terrain": "forest"},
            cycle=3,
            source_id=settler.entity_id,
            source_type="observed",
            reliability=1.0,
            position=(3, 0),
        )
        village = settlement(9, (4, 0), config=config)
        manager = mock.Mock()
        village.char = "V"
        world = {
            "cycle": 4,
            "entities": manager,
            "road": [["  "] * 5],
            "width": 5,
            "height": 1,
        }

        with (
            mock.patch(
                "entities.species.human.settler.Village", return_value=village
            ),
            mock.patch("entities.species.human.settler.connect_with_road"),
            mock.patch("entities.species.human.settler.GameLogger.log"),
        ):
            settler._found_village(world)

        copied = KnowledgeService(village, config).query(kind="map_tile")[0]
        self.assertEqual(copied["source_type"], "copied")
        self.assertEqual(copied["source_id"], settler.entity_id)

if __name__ == "__main__":
    unittest.main()
