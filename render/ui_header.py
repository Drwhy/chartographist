from entities.registry import STRUCTURE_TYPES, CIV_UNITS
from entities.species.animal.base import Animal
from core.translator import Translator
from core.religion import _find_template

def render_header(width, world_data, stats, config):
    """Displays global statistics based on entity registries."""

    # 1. ENTITY COUNTING
    # Counts instances of classes registered in the different global registries
    humans = sum(1 for e in world_data['entities'] if type(e) in CIV_UNITS and not e.is_expired)
    fauna = sum(1 for e in world_data['entities'] if isinstance(e, Animal) and not e.is_expired)

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

    # Line 3: Dominant religion across all settlements
    faiths_str = _get_religion_summary(world_data)
    if faiths_str:
        line3 = Translator.translate("ui.header_faiths", faiths=faiths_str)
        print(f"{line3}{erase_to_end}")

    # Proportional separation line based on map width (character width is 2 per tile)
    print("=" * (width * 2))


def _get_religion_summary(world_data):
    """Build a compact summary of world religions from active settlements."""
    global_fractions = {}

    for e in world_data['entities']:
        if e.is_expired:
            continue
        religion = getattr(e, 'religion', None)
        if religion and hasattr(religion, 'fractions') and religion.fractions:
            pop = getattr(e, 'population', 1)
            for rname, frac in religion.fractions.items():
                global_fractions[rname] = global_fractions.get(rname, 0) + frac * pop

    if not global_fractions:
        return None

    total = sum(global_fractions.values())
    if total == 0:
        return None

    # Top 3 religions by population weight
    sorted_religions = sorted(global_fractions.items(), key=lambda x: -x[1])
    top = sorted_religions[:3]

    parts = []
    for rname, weight in top:
        pct = int((weight / total) * 100)
        tmpl = _find_template(rname)
        emoji = tmpl.get("emoji", "🙏") if tmpl else "🙏"
        domain_key = tmpl.get("domain", "") if tmpl else ""
        domain = Translator.translate(f"domains.{domain_key}.name") if domain_key else ""
        god = tmpl.get("god", "") if tmpl else ""
        # Short display: emoji + god name + domain + %
        parts.append(f"{emoji} {god}({domain}) {pct}%")

    return " | ".join(parts)