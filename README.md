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

If no seed is provided, a random one will be generated. Checkpoints use Python's binary object format to preserve the full simulation graph; only load files you trust.

The bundled template enables the economy, diplomacy, and seasonal climate. The `economy` section controls treasury, scarcity prices, reserves, trader capacity, and settler cost. The `diplomacy` section controls relation gains, treaty thresholds, war/truce duration, trade-pact capacity, and allied food aid. The `climate` section controls seasons, humidity, anomaly decay and hazard probability. Removing any extension section preserves its corresponding legacy behavior.

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


The regression suite currently contains 143 `unittest` tests, including deterministic resume, conserved market transactions, persistent diplomacy, structured chronicles, stable-ID inspection, localization parity, and terminal navigation.
Developed with ❤️ by Drwhy
