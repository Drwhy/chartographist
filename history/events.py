import random

def event_war(civ, city_coords):
    name = civ[city_coords]["name"]
    return f"La cité de {name} est entrée en conflit avec ses voisins."

def event_famine(civ, city_coords):
    name = civ[city_coords]["name"]
    return f"Une grande famine frappe {name}, la population décline."

def event_discovery(civ, city_coords):
    name = civ[city_coords]["name"]
    return f"Les érudits de {name} ont découvert de nouvelles techniques d'irrigation."

# Registre des événements
RANDOM_EVENTS = [
    (0.02, event_war),
    (0.03, event_famine),
    (0.05, event_discovery)
]