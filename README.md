📜 Chartographist

Chartographist is a procedural world simulation engine written in Python that runs entirely within your terminal. It simulates the evolution of a complex ecosystem where geography, climate, and lifeforms (humans and animals) interact through deterministic logic.

🌍 Core Features

🧬 Procedural Generation & Determinism

    Centralized Seeding System: Powered by a custom RandomService, a single seed will generate the exact same map, identical animal movements, and the same civilizational trajectory every time.

    Dynamic Biomes: Advanced terrain generation including temperature calculations based on altitude, latitude, and axial tilt.

    ASCII/Emoji Rendering: A rich visual interface delivered directly to your console, optimized for modern terminal emulators.

📚 Structured Chronicles & Inspection

    Persistent Causal History: Optional v2 chronicles connect typed events through bounded causes and consequences while preserving legacy messages and saves.

    Headless Queries: SimulationEngine can filter facts by event, actor, object or place, traverse causal chains, or inspect a live entity without starting the terminal UI.

🏛️ Persistent Sites

    Stable Place Identity: Optional battlefields, ruins, sanctuaries, mines and remarkable roads retain bounded ownership, occupation, resource and event history.

    Visible Evolution: Destruction, reconstruction, reoccupation and overgrowth change data-driven map symbols; physical ruins are synchronized instead of hiding the site’s state.

    Real Integrations: Battles create battlefields, ruins enter the registry, settlers can refound them, and headless/checkpoint/system views preserve the same identity.

    In-App Chronicle: Press H to browse events and causal-link counts; press Y to inspect the history system’s volume, types and effects.
🏺 Persistent Artifacts

    Conserved Promotion: High-quality produced items can become unique artifacts and leave the fungible stock without duplicating material.

    Durable Provenance: Creator, materials, inscription, holders, locations and bounded transfers survive checkpoints and remain inspectable.

    Emergent Influence: Renown affects holder prestige, territorial claims and pilgrimage attraction; battles can deterministically loot artifacts.

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

    Safe Opt-In: The calibrated `resources` section uses an isolated, checkpointed ecology random stream but remains disabled by default to preserve historical trajectories.

🧠 Emergent Characters

    Personal State: Optional bounded needs, practiced skills, stable traits, household inheritance, and structured memories distinguish people with the same profession.

    Explainable Utility: Characters rank three candidate actions from their current needs and past experiences; expensive decisions are deterministically staggered by stable entity ID.

    Lived History: Successful trades and witnessed raids create persistent memories. Role accessions promote citizens to notables without changing identity, and archived notables keep a defensive snapshot of their personal history.

    Safe Opt-In: `characters.enabled` remains `false`; ordinary cohorts use a slower configurable cadence while notables retain detailed decisions.

🧩 Scenarios & Declarative Mods

    Safe JSON Layers: Mods use deep `patch` merges and explicit `append` lists; no external Python code is executed.

    Persistent Objectives: Scenarios track approved world metrics, victory and defeat conditions, and survive save/resume checkpoints.

    Command Line Composition: Apply multiple mods in order with `--mod`, then a scenario with `--scenario`.

📦 Material Production & Multi-Good Markets

    Data-Driven Goods: Optional resources, items, recipes, targets, reserves, capacities, and decay rules are validated from the template and declarative mods.

    Conserved Stockpiles: Settlement storage prevents negative quantities and duplication, applies bounded decay, and transfers only goods that physically exist.

    Work Orders: Shortages create deterministic production orders that require inputs, tools, labor, time, and output capacity before completion.

    Scarcity Routes: Multi-good prices and market selection account for stock, distance, risk, transport cost and losses, capacity, and affordability.

    Productive Infrastructure: Granaries, roads, markets, workshops, and fortifications are built, maintained, damaged, repaired, and apply condition-scaled effects.

    Safe Opt-In: `materials.enabled` remains `false` to preserve the historical simulation unless the complete material economy is explicitly requested.

🗺️ Local Knowledge & Rumors

    Partial Worlds: Settlements and agents observe only nearby sites and visited tiles; maps can age and carry terrain, biome, river, and resource observations.

    Traveling Information: Trade and migration move bounded facts with explicit observed, reported, copied, sold, or stolen provenance.

    Explainable Belief: Reliability decays with time, distance, and retransmission, while personality affects belief and conflicting sources may coexist.

    Safe Opt-In: `knowledge.enabled` remains `false` to preserve omniscient historical behavior unless local information is explicitly requested.


🏛️ Factions, Institutions & Politics

    Competing Interests: Profession, faith, and household factions keep stable identities, bounded influence, satisfaction, grievances, and incompatible objectives.

    Person-Based Institutions: Data-driven offices use existing notable identities for eligibility, succession, vacancies, regencies, and legitimacy crises.

    Measurable Policies: Collective proposals record supporters, opponents, causes, winners, and losers; temporary policies affect production, trade, defense, taxation, and religious dissent.

������ Territories, Migration & Causal Warfare

    Dynamic Claims: Optional territorial influence propagates from population, roads, fortifications, distance, and strategic resources into owned tiles, contested borders, and diplomatic grievances.

    Measured Paths: A bounded deterministic A* service combines elevation, roads, weather, danger, and local map knowledge. Its cache invalidates when the world changes; traders and soldiers use it only when enabled.

    Migrating Cohorts: Hunger, war, climate, persecution, and opportunity move bounded groups of real citizens, including selected notables. Culture, faith, skills, diseases, stories, family networks, diasporas, integration, and returnees remain inspectable.

    Logistical War: Every campaign records a cause, objective, evidence, armies, supply cost, morale, command, casualties, prisoners, sieges, occupations, retreats, and an explicit end.

    Consequential Peace: Treaties can transfer contested territory, food tribute, hostages, and commercial rights while leaving debts, veterans, refugees, ruins, and postwar grievances.

    Safe Opt-In: `territory`, `pathfinding`, `migration`, `warfare`, and `peace` are disabled by default and persist through checkpoints when activated.

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

    The browser mode is optional:
    Bash

    pip install -r requirements-web.txt

🎮 How to Use

Launch the simulation with a specific seed to generate a unique world:

```bash
python main.py --seed atlas --lang en
```

Launch the local browser mode, then open `http://127.0.0.1:8765`:

```bash
python main.py --renderer web --seed atlas --host 127.0.0.1 --port 8765 --tick-speed 0.15
```

The server accepts only loopback addresses. Its versioned API exposes metadata,
snapshots, entity inspection, bounded commands, and snapshot deltas over WebSocket.

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

The bundled template enables the economy, diplomacy, and seasonal climate. The optional `resources`, `characters`, `materials`, `knowledge`, `politics`, `territory`, `pathfinding`, `migration`, `warfare`, `peace`, `sites`, `artifacts`, `legends`, and `explanations` sections remain disabled by default to preserve historical trajectories. They add renewable spatial stocks, people and production, local knowledge and politics, territory, migration and warfare, persistent places and objects, divergent public legends, and causal explanations. Removing an extension section preserves its legacy behavior.

Controls during simulation:

    W: Open the Why tab; 1/2/3/4 filter all, warfare, artifacts, or legends.
    Y: Open the Systems tab, including the visible legend state.
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
│   ├── sites.py             # Persistent indexed places and lifecycle
│   ├── climate.py           # Seasons, tile climate, biomes and ecology
│   ├── resources.py         # Renewable stocks, extraction and disturbances
│   ├── artifacts.py         # Unique objects, provenance and renown
│   ├── materials.py         # Validated resources, items, recipes and food-chain catalog
│   ├── legends.py           # Cultural public narratives and renown
│   ├── why.py               # Causal queries, explanations and JSON export
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
│   ├── system_visibility.py # Observable state/effects of influential systems
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
│   │   ├── base.py          # Construct base, families, species and religion
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
│   └── ui_bestiary.py       # Paged inspection, diplomacy, Systems and Chronicles overlay
└── main.py                  # Simulation entry point
```


The regression suite currently contains 437 `unittest` tests, including deterministic resume, conserved multi-good transactions, spatial resources and production, local knowledge, factions and succession, territorial claims, measured pathfinding, migrating cohorts, logistical warfare, cross-system causal chains, persistent sites, artifacts and legends, causal explanations and export, semantic presentation snapshots, bounded simulation hosting, the local HTTP/WebSocket protocol, system visibility, localization parity, and terminal navigation.
Developed with ❤️ by Drwhy
