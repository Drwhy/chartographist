# chartographist
A small hobby project to create a map and simulate event on it
# 🌍 Chartographist: Procedural World & Fauna Simulator

**Chartographist** is a modular Python-based world generator and life simulator. It creates a procedurally generated map with shifting seasons, evolving civilizations, and a specialized fauna system driven by Object-Oriented Programming (OOP).

## ✨ Key Features
* **Procedural Geography**: Plate tectonics and hydrology simulations.
* **Dynamic Biomes**: Landscapes change based on elevation and seasonal temperature shifts.
* **Modular Fauna Engine**: Animals are individual objects with specific behaviors (Wolves hunt, Bears climb, Birds fly).
* **Civilization Growth**: Empires rise, build roads, and collapse over centuries.
* **Terminal Graphics**: High-fidelity ASCII/Emoji rendering with a "Genesis" radial reveal.

## 📂 Project Structure
The project is designed with a decoupled architecture to separate data, logic, and rendering:

```text
.
├── main.py               # Entry point and rendering loop
├── culture.py            # Data-driven theme & biome definitions
├── geo.py                # Geology & Hydrology engine
├── history.py            # Civilization & event logic
└── fauna/                # Specialized Fauna Package
    ├── __init__.py       # Package exposure
    ├── animal.py         # Base Animal class
    ├── fauna_engine.py   # Spawning & Lifecycle management
    ├── fauna_mapper.py   # Data-to-Class mapping registry
    └── species/          # Specialized behaviors
        ├── aquatic.py    # Water-bound entities
        ├── flyer.py      # Terrain-agnostic entities
        └── predator/     # Predators sub-package
            ├── __init__.py
            ├── base_predator.py
            ├── wolf.py   # Specialized Wolf logic (high mobility)
            └── bear.py   # Specialized Bear logic (high altitude)
````
🛠️ Requirements & Installation
1. Prerequisites

    Python 3.8+

    A terminal that supports UTF-8 and Emojis (VS Code Terminal, Windows Terminal, iTerm2, or any modern Linux shell).

2. Install Dependencies

This project uses numpy for terrain generation and colorama (optional, for terminal management).
Bash

pip install numpy

🚀 How to Run

Launch the simulation with the default settings:
Bash

python main.py

Advanced Usage

You can specify a Theme and a Seed:
Bash

# Syntax: python main.py [theme] [seed]
python main.py fantasy 4289
python main.py wasteland 666
python main.py arctic 90210

🧪 Development: Adding New Species

To add a new animal (e.g., a Lion):

    Create fauna/species/predator/lion.py inheriting from Predator.

    Register the class in fauna/species/predator/__init__.py.

    Add the mapping in fauna/fauna_mapper.py:
    ("predator", "lion"): (Lion, "🦁")