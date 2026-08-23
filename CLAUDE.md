# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Simulation

```bash
pip install -r requirements.txt
python main.py [--seed SEED] [--template PATH] [--lang LANG]
```

- `--seed` accepts integers or strings (strings are hashed internally)
- `--lang` supports `en`, `fr`, `es` (default: `fr`)
- `Ctrl+C` stops the simulation and prints Final Chronicles (world stats)

There are no build, lint, or test commands — this is a pure Python project with no test suite.

## Architecture

**Entry point:** `main.py` initializes all systems and runs the main loop (up to 2000 cycles).

**Initialization order matters:**
1. `RandomService` (seeded PRNG — must come first)
2. World geometry (geo, hydrology, spatial grid)
3. Entity manager + influence system
4. City seeding on habitable land near rivers
5. Renderer

**Main loop per cycle:**
1. Spatial grid rebuild
2. Dynamic fauna spawn (`spawn_system`)
3. Influence heatmap decay (every 10 cycles)
4. Entity ticks — three frequencies:
   - Every cycle: `process_turn()` — movement, AI, combat
   - Every 10 cycles: `check_vital_signs()` — hunger, starvation
   - Every 100 cycles: `process_long_term_logic()` — births, plagues, cultural drift
5. Global events (`EventManager`)
6. Dead entity cleanup
7. Render frame

## Key Systems

**RandomService** (`core/`) — single seeded PRNG instance. All randomness in the codebase must go through it. Never use Python's `random` module directly; doing so breaks determinism (same seed must produce identical runs).

**InfluenceSystem** (`core/`) — fear and scent heatmaps used for AI navigation. Decays each cycle, recalculated every 10.

**SpatialGrid** (`core/`) — broadphase neighbor detection, `cell_size=10`.

**Template + locale config** — `template.json` drives fauna species, culture pools, event parameters, and world constants. `locales/textes.{lang}.json` contains all UI strings. New languages only need a new JSON file.

**ReligionSystem / CultureSystem** — procedurally generated per culture at city founding; religion domains (War, Trade, Fertility, etc.) modify entity behavior.

**EventSystem** (`events/`) — `BaseEvent` subclasses registered in `event_registry`. Volcano, Epidemic, and Abduction (UFO) are the current events.

## Entity Hierarchy

```
Entity (base: position, energy, Z-index)
├── Actor (culture, aging, lifespan)
│   ├── Animal  ← data-driven via template.json
│   └── Human roles: Settler, Hunter, Fisherman, Farmer, Trader, Soldier
└── Construct (static: cities, villages, ruins)
```

Human roles live in `entities/species/human/`, animal species in `entities/species/animal/`. Constructs are in `entities/constructs/`.
