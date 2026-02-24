# Définition des peuples et de leurs styles architecturaux
CULTURES = [
    {"name": "Empire",   "city": "🏰", "village": "🏡", "port": "⚓", "road": ". "},
    {"name": "Sultanat", "city": "🕌", "village": "🧱", "port": "🛶", "road": "° "},
    {"name": "Dynastie", "city": "🏯", "village": "🏮", "port": "⛵", "road": "+ "},
    {"name": "Clans",    "city": "🛖", "village": "⛺", "port": "⛵", "road": "  "},
]

# Configuration visuelle et comportementale des mondes
THEMES = {
    "fantasy": {
        "water": {"ocean": "🌊", "shore": "💧", "river": "🔹", "deep": "🐬"},
        "biomes": {
            "volcano": "🌋", "peak": "❄️", "high_mountain": "🏔️", "mountain": "⛰️",
            "sand": "🏖️", "glaciated": "❄️", "boreal_forest": "🌲", "temperate_forest": "🌳",
            "autumn_forest": "🍂", "tropical_forest": "🌴", "grassland": "🌿", "tundra": "❄️",
            "desert": "🏜️", "cactus": "🌵"
        },
        "fauna": [
            {"char": "🐺", "type": "predator", "species": "wolf"}, # Deviendra 🐺 via Mapper
            {"char": "🐻", "type": "predator", "species": "bear"}, # Deviendra 🐻 via Mapper
            {"char": "🐎", "type": "standard", "species": None},
            {"char": "🦅", "type": "flyer", "species": None},
            {"char": "🐬", "type": "aquatic", "species": None}
        ],
        "special": {"ruin": "🏚️", "port": "⚓", "lava": "🔥"}
    },
    "wasteland": {
        "water": {"ocean": "☣️", "shore": "🧪", "river": "☢️", "deep": "💀"},
        "biomes": {
            "volcano": "🌋", "peak": "🌫️", "high_mountain": "🌋", "mountain": "⛰️",
            "sand": "💀", "glaciated": "🤢", "boreal_forest": "🌫️", "temperate_forest": "🪵",
            "autumn_forest": "🔥", "tropical_forest": "🤢", "grassland": "🏚️", "tundra": "💨",
            "desert": "🪨", "cactus": "🔥"
        },
        "fauna": [
            {"char": "🦂", "type": "predator", "species": None},
            {"char": "🐀", "type": "standard", "species": None},
            {"char": "🧟", "type": "predator", "species": None},
            {"char": "🦇", "type": "flyer", "species": None}
        ],
        "special": {"ruin": "💀", "port": "☣️", "lava": "💥"}
    },
    "arctic": {
        "water": {"ocean": "🧊", "shore": "💧", "river": "🧊", "deep": "🐋"},
        "biomes": {
            "volcano": "🏔️", "peak": "🧊", "high_mountain": "🏔️", "mountain": "🏔️",
            "sand": "🧊", "glaciated": "🥶", "boreal_forest": "🌲", "temperate_forest": "🌲",
            "autumn_forest": "❄️", "tropical_forest": "🥶", "grassland": "❄️", "tundra": "❄️",
            "desert": "🧊", "cactus": "❄️"
        },
        "fauna": [
            {"char": "🐾", "type": "predator", "species": "bear"}, # L'ours blanc !
            {"char": "🐾", "type": "predator", "species": "wolf"},
            {"char": "🦌", "type": "standard", "species": None},
            {"char": "🦉", "type": "flyer", "species": None},
            {"char": "🐋", "type": "aquatic", "species": None}
        ],
        "special": {"ruin": "🏚️", "port": "🐋", "lava": "🔥"}
    }
}