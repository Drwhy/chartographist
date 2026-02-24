import random

PREFIXES = {
    "Empire": ["Val", "Pont", "Castel", "Mont", "Saint", "Aigue"],
    "Sultanat": ["Al", "Ouar", "Ben", "Zir", "Ab", "Kasr"],
    "Dynastie": ["Shan", "Bei", "Nan", "Lian", "Zhong", "Feng"],
    "Nord": ["Bjorn", "Heim", "Skog", "Thor", "Ulf", "Grim"],
}

SUFFIXES = {
    "Empire": ["bourg", "mont", "gard", "val", "ois", "ance"],
    "Sultanat": ["zane", "dhar", "bak", "stan", "ria", "oum"],
    "Dynastie": ["hai", "jing", "po", "du", "shan", "wa"],
    "Nord": ["dar", "run", "vik", "stod", "hall", "mir"],
}


def generate_city_name(culture_name):
    pre = random.choice(PREFIXES.get(culture_name, ["Lieu"]))
    suf = random.choice(SUFFIXES.get(culture_name, [""]))
    return f"{pre}{suf}"
