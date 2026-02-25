import random

# Dictionnaires de sonorités par style culturel
NAMING_STYLES = {
    "imperial": {
        "prefixes": ["Aur", "Valer", "Octav", "Jul", "Septim", "Tiber", "Claud"],
        "suffixes": ["ia", "ius", "um", "ian", "is", "us"],
        "titles": ["Haut", "Grand", "Vénérable"]
    },
    "nordic": {
        "prefixes": ["Thorg", "Bjorn", "Sig", "Hrolf", "Egil", "Gunn", "Ivar"],
        "suffixes": ["gard", "felt", "mund", "sten", "heim", "rok"],
        "titles": ["Fief de", "Bastion", "Terres de"]
    },
    "nomad": {
        "prefixes": ["Kha", "Zul", "Qar", "Tog", "Mog", "Bak"],
        "suffixes": ["'Zul", " khan", " dur", " ghal"],
        "titles": ["Camp", "Halte", "Source"]
    }
}

def generate_name(style="imperial"):
    """Génère un nom unique basé sur un style culturel."""
    data = NAMING_STYLES.get(style, NAMING_STYLES["imperial"])

    pre = random.choice(data["prefixes"])
    suf = random.choice(data["suffixes"])
    name = pre + suf

    # 20% de chance d'ajouter un titre
    if random.random() < 0.2:
        title = random.choice(data["titles"])
        return f"{title} {name}"

    return name

def get_name_by_culture(culture_dict):
    """
    Récupère un nom en faisant le lien avec le dictionnaire
    de culture du template JSON.
    """
    # On essaye de mapper le nom de la culture du JSON aux styles ici
    cult_name = culture_dict.get("name", "imperial").lower()

    if "nord" in cult_name or "clan" in cult_name:
        return generate_name("nordic")
    elif "nomad" in cult_name or "steppe" in cult_name:
        return generate_name("nomad")
    else:
        return generate_name("imperial")