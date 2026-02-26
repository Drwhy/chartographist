# entities/registry.py

# Catalogues vides au démarrage
WILD_SPECIES = []
CIV_UNITS = []

def register_wild(cls):
    """Décorateur pour enregistrer une espèce sauvage."""
    WILD_SPECIES.append(cls)
    return cls

def register_civ(cls):
    """Décorateur pour enregistrer une unité de civilisation."""
    CIV_UNITS.append(cls)
    return cls