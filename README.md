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
Plaintext

chartographist/
├── core/
│   ├── random_service.py   # Centralized determinism service
│   ├── translator.py       # Multi-language support (EN, FR, ES)
│   └── logger.py           # Global world event tracking
├── entities/
│   ├── species/
│   │   ├── human/          # Settlers, Hunters, Fishermen, Traders
│   │   └── animal/         # Wolves, Bears, Fish, Sharks
│   └── constructs/         # Cities, Villages, Ruins, Roads
├── events/
│   ├── event_manager.py    # Global orchestrator (Plagues, UFOs, Volcanoes)
│   └── base_event.py       # Abstract event interface
├── render/
│   └── render_engine.py    # UI/UX, Map rendering, and Biome logic
└── main.py                 # Simulation entry point

⚖️ Combat Balancing

The combat resolution follows a specific formula based on the entity's danger_level:
Victory:roll>(0.6+2danger​)
Flee:roll>danger
Defeat:roll≤danger
Animal	Danger	Type
🐺 Wolf	0.3	Terrestrial
🐻 Bear	0.8	Terrestrial
🦈 Shark	0.7	Aquatic

Developed with ❤️ by Drwhy