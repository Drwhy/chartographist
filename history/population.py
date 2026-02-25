import random

def grow_population(structures):
    logs = []
    for pos, s in structures.items():
        if s["type"] == "village" and random.random() < 0.01:
            s["type"] = "city"
            logs.append(f"La colonie de {s['name']} est devenue une cité.")
    return logs