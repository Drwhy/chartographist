"""Moteur de simulation indépendant du terminal et du rendu."""

import os
import traceback

import entities.spawn_system as entities_spawn
from core.chronicles import ChronicleBook
from core.entity_ids import EntityIdService
from core.fauna_gen import generate_fauna
from core.grid_service import SpatialGrid
from core.logger import GameLogger
from core.random_service import RandomService
from core.religion import init_religion_data
from core.species import init_species_data
from core.translator import Translator
from core.inspection import inspect_entity
from core.world_factory import assemble_world
from events.event_manager import EventManager


class SimulationEngine:
    """Possède l'état de simulation et exécute ses cycles sans interface utilisateur."""

    def __init__(self, world, stats, config):
        self.world = world
        self.stats = stats
        self.config = config
        ChronicleBook(self.world)
        from core.characters import ensure_notable_storage
        ensure_notable_storage(self.world)
        from core.simulation_metrics import SimulationMetrics
        SimulationMetrics(self.world)
        from core.resources import ResourceSystem
        ResourceSystem(self.world, self.config)
        from core.diplomacy import DiplomacyRegistry
        from core.climate import ClimateSystem
        DiplomacyRegistry(self.world)
        ClimateSystem(self.world, self.config)
        from core.scenarios import ScenarioService
        ScenarioService(self.world, self.config)

    @classmethod
    def create(cls, config, seed, width, height):
        """Initialise tous les services et construit un nouveau monde simulable."""
        EntityIdService.reset()
        RandomService.initialize(seed)
        init_religion_data(config)
        init_species_data(config)

        generated_fauna = generate_fauna(config)
        if generated_fauna:
            config["fauna"] = config.get("fauna", []) + generated_fauna

        world, stats = assemble_world(width, height, config, seed)
        world["grid"] = SpatialGrid(width, height, cell_size=10)
        entities_spawn.seed_initial_cities(world, config)
        return cls(world, stats, config)

    def step(self):
        """Exécute exactement un cycle mensuel et renvoie son numéro."""
        world = self.world
        stats = self.stats

        world["cycle"] += 1
        total_months = world["cycle"]
        stats["year"] = total_months // 12
        stats["month"] = (total_months % 12) + 1

        from core.climate import ClimateSystem
        from core.diplomacy import advance_diplomacy
        ClimateSystem(world, self.config).advance()
        from core.resources import ResourceSystem
        ResourceSystem(world, self.config).advance()
        advance_diplomacy(world, self.config)
        self._refresh_grid()
        entities_spawn.spawn_system(world, self.config)

        if world["cycle"] % 10 == 0:
            world["influence"].update()

        for entity in list(world["entities"]):
            if getattr(entity, "is_expired", False):
                continue
            try:
                self._update_entity(entity)
            except Exception as error:
                self._log_entity_error(entity, error)

        EventManager.update(world, stats, self.config)
        from core.scenarios import ScenarioService
        ScenarioService(world, self.config).advance()
        new_logs = GameLogger.get_new_logs()
        stats["logs"].extend(new_logs)
        ChronicleBook(world).record_many(
            new_logs,
            cycle=world["cycle"],
            year=stats["year"],
            month=stats["month"],
            metadata=GameLogger.get_last_metadata(len(new_logs)),
        )
        from core.characters import (
            NotabilityService,
            characters_enabled,
        )
        if characters_enabled(self.config):
            NotabilityService(world, self.config).archive_inactive()
        world["entities"].remove_dead()
        return world["cycle"]

    def run(self, cycles):
        """Exécute plusieurs cycles sans temporisation, entrée clavier ni rendu."""
        for _ in range(cycles):
            self.step()
        return self.world, self.stats

    def run_observed(self, cycles, sample_every=1):
        """Run cycles and sample state without random draws."""
        if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 0:
            raise ValueError("cycles must be a non-negative integer")
        if not isinstance(sample_every, int) or isinstance(sample_every, bool) or sample_every <= 0:
            raise ValueError("sample_every must be a positive integer")

        samples = []
        for index in range(cycles):
            self.step()
            if (index + 1) % sample_every == 0:
                samples.append(self.get_metrics_snapshot())
        if cycles and cycles % sample_every:
            samples.append(self.get_metrics_snapshot())
        return samples

    def get_metrics_snapshot(self):
        """Return a defensive snapshot of observable state and flows."""
        from core.simulation_metrics import SimulationMetrics
        return SimulationMetrics(self.world).snapshot()

    def save(self, path):
        """Crée un checkpoint versionné de cette simulation."""
        from core.persistence import save_engine
        return save_engine(self, path)

    @classmethod
    def load(cls, path):
        """Restaure un moteur depuis un checkpoint local de confiance."""
        from core.persistence import load_engine
        return load_engine(path)

    def record_chronicle(self, message, *, category="event", entity_ids=None, position=None):
        """Ajoute une trace structurée à la date courante de la simulation."""
        return ChronicleBook(self.world).record(
            message,
            cycle=self.world["cycle"],
            year=self.stats["year"],
            month=self.stats.get("month", 1),
            category=category,
            entity_ids=entity_ids,
            position=position,
        )

    def get_chronicles(self, **filters):
        """Interroge les chroniques sans exposer leur stockage mutable."""
        return ChronicleBook(self.world).query(**filters)

    def get_economic_summary(self):
        """Agrège les marchés actifs sans dépendance envers le rendu."""
        from core.economy import world_economic_summary
        return world_economic_summary(self.world)

    def inspect_entity(self, entity_id):
        """Renvoie l'instantané courant d'une entité et son historique lié."""
        return inspect_entity(self.world, entity_id)

    def get_scenario_summary(self):
        """Renvoie une copie de l'état et des objectifs du scénario."""
        from core.scenarios import ScenarioService
        return ScenarioService(self.world, self.config).summary()
    def get_tile_resources(self, x, y):
        """Return a defensive resource snapshot for one tile."""
        from core.resources import ResourceSystem
        return ResourceSystem(self.world, self.config).tile_snapshot(x, y)

    def get_resource_summary(self):
        """Return a defensive aggregate of renewable resources."""
        from core.resources import ResourceSystem
        return ResourceSystem(self.world, self.config).summary()

    def get_climate_snapshot(self):
        """Renvoie une copie de l'état climatique mondial."""
        from core.climate import ClimateSystem
        return ClimateSystem(self.world, self.config).snapshot()

    def get_tile_climate(self, x, y):
        """Inspecte le climat et le biome logique d'une tuile."""
        from core.climate import ClimateSystem, biome_at
        climate = ClimateSystem(self.world, self.config)
        elevation = float(self.world["elev"][y][x])
        return {
            "position": [int(x), int(y)],
            "temperature": climate.temperature_at(x, y),
            "moisture": climate.moisture_at(x, y),
            "biome": biome_at(x, y, elevation, self.world, self.config),
        }

    def get_relationship(self, first_id, second_id):
        """Renvoie une copie de la relation entre deux identifiants stables."""
        from core.diplomacy import DiplomacyRegistry
        return DiplomacyRegistry(self.world).get(first_id, second_id)

    def get_relationships(self, **filters):
        """Interroge les relations diplomatiques sans exposer leur stockage."""
        from core.diplomacy import DiplomacyRegistry
        return DiplomacyRegistry(self.world).query(**filters)

    def get_diplomatic_summary(self):
        """Agrège les relations diplomatiques courantes."""
        from core.diplomacy import world_diplomatic_summary
        return world_diplomatic_summary(self.world)

    def _refresh_grid(self):
        grid = self.world["grid"]
        grid.clear()
        for entity in self.world["entities"]:
            if not getattr(entity, "is_expired", False):
                grid.add_entity(entity)

    def _update_entity(self, entity):
        world = self.world
        stats = self.stats
        cycle = world["cycle"]

        entity.process_turn(world, stats)
        if cycle % 10 == 0:
            entity.update_influence(world)
            if hasattr(entity, "check_vital_signs"):
                entity.check_vital_signs(world)
        if cycle % 100 == 0 and hasattr(entity, "process_long_term_logic"):
            entity.process_long_term_logic(world)

    def _log_entity_error(self, entity, error):
        frame = traceback.extract_tb(error.__traceback__)[-1]
        message = Translator.translate(
            "system.entity_bug",
            entity_type=type(entity).__name__,
            pos=getattr(entity, "pos", "?"),
            error=str(error),
            file=os.path.basename(frame.filename),
            line=frame.lineno,
        )
        self.stats["logs"].append(message)
        self.record_chronicle(
            message,
            category="system",
            entity_ids=[getattr(entity, "entity_id", None)],
            position=getattr(entity, "pos", None),
        )
