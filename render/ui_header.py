from entities.registry import WILD_SPECIES, STRUCTURE_TYPES, CIV_UNITS
from core.translator import Translator

def render_header(width, world_data, stats, config):
    """Affiche les statistiques globales basées sur les registres d'entités."""

    # 1. COMPTAGE TECHNIQUE
    # On compte les instances des classes enregistrées dans les différents registres
    hunters = sum(1 for e in world_data['entities'] if type(e) in CIV_UNITS and not e.is_expired)
    fauna = sum(1 for e in world_data['entities'] if type(e) in WILD_SPECIES and not e.is_expired)

    # Pour les villes, si on veut spécifiquement les villes (pas les villages)
    # On peut soit filtrer par classe spécifique, soit garder le z_index
    # Ici, on compte toutes les structures (Villes + Villages)
    structures = sum(1 for e in world_data['entities'] if type(e) in STRUCTURE_TYPES and not e.is_expired)

    world_name = config.get("world_name", "WORLD").upper()
    erase_to_end = "\033[K"

    # 2. AFFICHAGE VIA TRANSLATOR
    # Ligne 1 : Nom, Année, Structures
    line1 = Translator.translate("ui.header_line_1",
              name=world_name,
              year=stats['year'],
              structs=structures)
    print(f"{line1}{erase_to_end}")

    # Ligne 2 : Humains, Faune, Seed
    line2 = Translator.translate("ui.header_line_2",
              humans=hunters,
              fauna=fauna,
              seed=stats['seed'])
    print(f"{line2}{erase_to_end}")

    # Ligne de séparation proportionnelle à la largeur de la map
    print("=" * (width * 2))