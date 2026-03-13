from entities.registry import WILD_SPECIES, STRUCTURE_TYPES, CIV_UNITS
from core.translator import Translator

def render_header(width, world_data, stats, config):
    """Displays global statistics based on entity registries."""

    # 1. ENTITY COUNTING
    # Counts instances of classes registered in the different global registries
    humans = sum(1 for e in world_data['entities'] if type(e) in CIV_UNITS and not e.is_expired)
    fauna = sum(1 for e in world_data['entities'] if type(e) in WILD_SPECIES and not e.is_expired)

    # Counts all inhabited structures (Cities, Villages, etc.)
    structures = sum(1 for e in world_data['entities'] if type(e) in STRUCTURE_TYPES and not e.is_expired)

    world_name = config.get("world_name", "WORLD").upper()

    # ANSI Escape code to erase the line to the end, preventing artifacts when stats shrink
    erase_to_end = "\033[K"

    # 2. RENDERING VIA TRANSLATOR
    # Line 1: World Name, Current Year, Structure Count
    line1 = Translator.translate(
        "ui.header_line_1",
        name=world_name,
        year=stats['year'],
        month=stats['month'],
        structs=structures
    )
    print(f"{line1}{erase_to_end}")

    # Line 2: Human Count, Wild Fauna Count, World Seed
    line2 = Translator.translate("ui.header_line_2",
              humans=humans,
              fauna=fauna,
              seed=stats['seed'])
    print(f"{line2}{erase_to_end}")

    # Proportional separation line based on map width (character width is 2 per tile)
    print("=" * (width * 2))