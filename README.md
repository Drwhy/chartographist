📜 Chartographist

Chartographist is a procedural world simulation engine written in Python that runs entirely within your terminal. It simulates the evolution of a complex ecosystem where geography, climate, and lifeforms (humans and animals) interact through deterministic logic.

🌍 Core Features

🧬 Procedural Generation & Determinism

    Centralized Seeding System: Powered by a custom RandomService, a single seed will generate the exact same map, identical animal movements, and the same civilizational trajectory every time.

    Dynamic Biomes: Advanced terrain generation including temperature calculations based on altitude, latitude, and axial tilt.

    ASCII/Emoji Rendering: A rich visual interface delivered directly to your console, optimized for modern terminal emulators.

📚 Structured Chronicles & Inspection

    Persistent History: Every simulation keeps a versioned, structured chronology with cycle, date, category, related entity IDs, and location.

    Headless Queries: SimulationEngine can filter chronicles or inspect a live entity by its stable ID without starting the terminal UI.

    In-App Chronicle: Open the bestiary overlay and press H to browse the newest world events first.

💰 Conserved Market Economy

    Scarcity Pricing: Food prices rise and fall with each destination's stock level, within configurable bounds.

    Real Transfers: Economic trade moves existing food and wealth between settlements without creating either resource.

    Funded Expansion: With the economy enabled, cities must finance settler expeditions from their treasury.

    Backward Compatibility: Templates without economy.enabled keep the historical trader food bonus.

🤝 Persistent Diplomacy

    Stable Relations: Settlements share symmetric relationships keyed by stable entity IDs, with trust, tension, interdependence, status, truces, and structured reasons.

    Economic Consequences: Successful trade builds trust, trade pacts increase caravan capacity, alliances can transfer limited food aid, and war blocks direct trade.

    War Lifecycle: Alliances and active truces prevent declarations, war exhaustion creates timed truces, and soldiers retreat once peace is restored.

    Headless & Terminal Inspection: SimulationEngine exposes relation queries and summaries, while the bestiary overlay provides a localized Diplomacy tab.

🌦️ Seasonal Climate & Ecology

    Headless Climate: A twelve-month seasonal model combines latitude, hemisphere, altitude, river humidity, and persistent anomalies for every tile.

    Ecological Consequences: Climate productivity affects farming and herbivore grazing, while fauna can define optional temperature and moisture habitat bounds.

    Replayable Hazards: Droughts, floods, heatwaves, and cold snaps use the centralized deterministic random service and are recorded in structured chronicles.

    Backward Compatibility: Templates without climate.enabled retain the exact historical biome, farming, grazing, and spawning behavior.

Spatial Renewable Resources

    Causal Terrain: Optional tile stocks model biomass, soil fertility, surface water, fish, and forest cover with bounded seasonal regeneration.

    Conserved Harvests: Farming, fishing, and herbivore grazing cannot gain more than they remove locally; full granaries no longer waste biomass.

    Persistent Disturbances: Droughts, floods, fires, and volcanoes alter spatial stocks, while deterministic fire spread follows vegetation and humidity.

    Safe Opt-In: The calibrated `resources` section is bundled but disabled by default until ecological random streams can be isolated without changing historical demographic trajectories.

🧠 Emergent Characters

    Personal State: Optional bounded needs, practiced skills, stable traits, household inheritance, and structured memories distinguish people with the same profession.

    Explainable Utility: Characters rank three candidate actions from their current needs and past experiences; expensive decisions are deterministically staggered by stable entity ID.

    Lived History: Successful trades and witnessed raids create persistent memories. Role accessions promote citizens to notables without changing identity, and archived notables keep a defensive snapshot of their personal history.

    Safe Opt-In: `characters.enabled` remains `false` in the reference template while long-run demographic impact and CPU cost continue to be calibrated.

🧩 Scenarios & Declarative Mods

    Safe JSON Layers: Mods use deep `patch` merges and explicit `append` lists; no external Python code is executed.

    Persistent Objectives: Scenarios track approved world metrics, victory and defeat conditions, and survive save/resume checkpoints.

    Command Line Composition: Apply multiple mods in order with `--mod`, then a scenario with `--scenario`.

📦 Material Production & Multi-Good Markets

    Data-Driven Goods: Optional resources, items, recipes, targets, reserves, capacities, and decay rules are validated from the template and declarative mods.

    Conserved Stockpiles: Settlement storage prevents negative quantities and duplication, applies bounded decay, and transfers only goods that physically exist.

    Work Orders: Shortages create deterministic production orders that require inputs, tools, labor, time, and output capacity before completion.

    Scarcity Routes: Multi-good prices and market selection account for target stock, distance, risk, reserves, capacity, and buyer affordability.

    Safe Opt-In: `materials.enabled` remains `false` while infrastructure, timber sourcing, regional specialization, and performance calibration are completed.

👥 Civilization & Actors

    Intelligent Expansion: Settlers seek ideal locations to found villages, which dynamically evolve into massive Cities as their population grows.

    Specialized Roles:

        🏹 Hunters: Protect settlements from terrestrial predators and bring back food to boost population.

        🎣 Fishermen: Operate in coastal villages, utilizing boats (🛶) to track aquatic prey in open waters.

    Survival Logic: All actors must gather resources and navigate environmental hazards to ensure the survival of their home culture.

🦁 Fauna & Hazards

    Terrestrial Ecosystem: Features high-speed Wolves and powerful, territorial Bears.

    Marine Ecosystem:

        🐟 Fish: Dwell in shallow waters and serve as a primary food source for coastal cultures.

        🦈 Sharks: Fearsome predators that hunt both fish and fishermen.

    Combat System: A probability-based resolution system influenced by species-specific danger levels, resulting in various outcomes (Victory, Fleeing, or Death).

🚀 Installation

    Clone the repository:
    Bash

    git clone https://github.com/Drwhy/chartographist.git
    cd chartographist

    Install dependencies:
    Bash

    pip install -r requirements.txt

🎮 How to Use

Launch the simulation with a specific seed to generate a unique world:

```bash
python main.py --seed atlas --lang en
```

Save automatically when the simulation exits, then resume that trusted local checkpoint:

```bash
python main.py --seed atlas --lang en --save world.chart
python main.py --lang en --load world.chart --save world.chart
```

Run the bundled scenario with its example fauna mod:

```bash
python main.py --seed atlas --mod mods/highland_bison.json --scenario scenarios/fragile_frontier.json --lang en
```
If no seed is provided, a random one will be generated. Checkpoints use Python's binary object format to preserve the full simulation graph; only load files you trust.

The bundled template enables the economy, diplomacy, and seasonal climate. The `economy` section controls treasury, scarcity prices, reserves, trader capacity, settler cost, and optional material-route costs. The `diplomacy` section controls relation gains, treaty thresholds, war/truce duration, trade-pact capacity, and allied food aid. The `climate` section controls seasons, humidity, anomaly decay and hazard probability. The calibrated `resources` section controls renewable stocks and disturbances but remains disabled by default; set `resources.enabled` to `true` to opt in. The `characters` section likewise remains disabled by default and controls memory bounds, notability, personal needs, and the staggered decision interval. The opt-in `materials` section defines goods, recipes, stockpiles, food conversion, trade reserves, spatial timber sourcing, and infrastructure kits. Its first granary increases settlement storage capacity, but the system remains disabled until long-run calibration and regional specialization are complete. Removing any extension section preserves its corresponding legacy behavior.

Controls during simulation:

    B: Open or close the inspection/bestiary overlay.
    H: Open the structured Chronicles tab while the overlay is active.
    D: Open the Diplomacy tab while the overlay is active.
    F / S / R / C / I: Browse fauna, species, religions, settlements, and guide tabs.
    N / P: Move to the next or previous page.
    Ctrl+C: Stop the simulation and display the Final Chronicles (world statistics).

🛠️ Project Structure

```
chartographist/
├── core/
│   ├── chronicles.py        # Structured persistent world history
│   ├── climate.py           # Seasons, tile climate, biomes and ecology
│   ├── resources.py         # Renewable stocks, extraction and disturbances
│   ├── materials.py         # Validated resources, items, recipes and food-chain catalog
│   ├── stockpiles.py        # Capacity, decay and conserved settlement inventories
│   ├── production.py        # Shortage planning and deterministic work orders
│   ├── infrastructure.py    # Persistent infrastructure levels and capacity bonuses
│   ├── characters.py        # Personal state, utility choices, cohorts and notables
│   ├── needs.py             # Bounded personal needs and monthly evolution
│   ├── skills.py            # Practice with bounded diminishing returns
│   ├── memory.py            # Structured memories, decay and derived opinions
│   ├── scenarios.py         # Safe JSON mods, objectives and scenario state
│   ├── inspection.py        # Stable-ID entity snapshots and linked history
│   ├── discovery_service.py # Shared world knowledge for entities
│   ├── entities.py          # Base Entity class, stable IDs & Z-Index
│   ├── entity_ids.py        # Deterministic persistent ID sequence
│   ├── economy.py           # Scarcity prices, treasury, conserved trade
│   ├── diplomacy.py         # Persistent relations, treaties, war and allied aid
│   ├── persistence.py       # Versioned save/load checkpoints
│   ├── simulation_engine.py # Headless initialization and cycle runner
│   ├── logger.py            # Legacy strings plus optional chronicle metadata
│   ├── naming.py            # Procedural name generator
│   ├── random_service.py    # Centralized deterministic PRNG
│   └── translator.py        # I18n engine (Supporting EN, FR, ES)
├── entities/
│   ├── species/
│   │   ├── human/
│   │   │   ├── base.py      # Human base class & shared AI logic
│   │   │   ├── fisherman.py # Coastal resource gathering
│   │   │   ├── hunter.py    # Predator control & food supply
│   │   │   ├── settler.py   # Expansion & village foundation
│   │   │   ├── soldier.py   # War missions and retreat after peace
│   │   │   └── trader.py    # Inter-city economy, diplomacy & plague vector
│   │   └── animal/
│   │       └── base.py      # Data-driven predator/prey & heatmap navigation
│   ├── constructs/
│   │   ├── base.py          # Construct base & Cultural Drift logic
│   │   ├── city.py          # Expansion hubs & growth logic
│   │   ├── ruins.py         # Abandoned settlement markers
│   │   └── village.py       # Early-stage settlements
│   ├── special/
│   │   └── ufo.py           # Special event actor (Abductions)
│   ├── registry.py          # Global entity categorization decorators
│   └── spawn_system.py      # Fauna regulation & initial seeding
├── events/
│   ├── abduction.py         # UFO spawning logic
│   ├── base_event.py        # Abstract event interface
│   ├── epidemic.py          # Disease spread & mortality logic
│   ├── event_manager.py     # Global event orchestrator
│   └── volcano.py           # Tectonic disaster logic
├── history/
│   └── history_engine.py    # Road generation between settlements
├── locales/
│   ├── textes.en.json       # English localization
│   ├── textes.es.json       # Spanish localization
│   └── textes.fr.json       # French localization
├── render/
│   ├── render_engine.py     # ASCII/Emoji UI orchestration
│   └── ui_bestiary.py       # Paged inspection, economy, diplomacy and Chronicles overlay
└── main.py                  # Simulation entry point
```


The regression suite currently contains 265 `unittest` tests, including deterministic resume, conserved multi-good transactions, spatial material sourcing, production preconditions, infrastructure capacity, stockpile conservation and decay, persistent diplomacy, structured chronicles, stable-ID inspection, localization parity, and terminal navigation.
Developed with ❤️ by Drwhy
