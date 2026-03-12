📜 Chartographist

Chartographist is a procedural world simulation engine written in Python that runs entirely within your terminal. It simulates the evolution of a complex ecosystem where geography, climate, and lifeforms (humans and animals) interact through deterministic logic.

🌍 Core Features

🧬 Procedural Generation & Determinism

    Centralized Seeding System: Powered by a custom RandomService, a single seed will generate the exact same map, identical animal movements, and the same civilizational trajectory every time.

    Dynamic Biomes: Advanced terrain generation including temperature calculations based on altitude, latitude, and axial tilt.

    ASCII/Emoji Rendering: A rich visual interface delivered directly to your console, optimized for modern terminal emulators.

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
Bash

python main.py [your_seed]

If no seed is provided, a random one will be generated automatically.

Controls during simulation:

    Ctrl+C: Stop the simulation and display the Final Chronicles (world statistics).

🛠️ Project Structure

```
chartographist/
├── core/
│   ├── discovery_service.py # Shared world knowledge for entities
│   ├── entities.py          # Base Entity class & Z-Index constants
│   ├── logger.py            # Global event logging system
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
│   │   │   └── trader.py    # Inter-city economy & plague vector
│   │   └── animal/
│   │       ├── base.py      # Predator/Prey & Heatmap navigation
│   │       ├── bear.py      # Highland territorial predator
│   │       ├── deer.py      # Lowland herbivore (prey)
│   │       ├── eagle.py     # High-altitude flying predator
│   │       ├── fish.py      # Aquatic prey
│   │       ├── shark.py     # Deep-sea predator
│   │       └── wolf.py      # Pack-hunter (plains)
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
│   └── history_engine.py    # Road generation & world chronicles
├── locales/
│   ├── textes.en.json       # English localization
│   ├── textes.es.json       # Spanish localization
│   └── textes.fr.json       # French localization
├── render/
│   └── render_engine.py     # ASCII/Emoji UI & Biome visualization
└── main.py                  # Simulation entry point
```


Developed with ❤️ by Drwhy