import sys
from core.species import get_species_templates
from core import bestiary_tracker
from core.translator import Translator

FAUNA_TAB = 'fauna'
SPECIES_TAB = 'species'
ENTRIES_PER_PAGE = 7


def render_bestiary(width, height, world_data, config, state):
    """Full-screen bestiary overlay replacing the normal simulation frame."""
    tab = state.get('tab', FAUNA_TAB)
    W = width * 2
    eol = "\033[K"

    entries = (
        _build_fauna_entries(world_data, config)
        if tab == FAUNA_TAB
        else _build_species_entries(world_data)
    )

    total_pages = max(1, (len(entries) + ENTRIES_PER_PAGE - 1) // ENTRIES_PER_PAGE)
    page = min(state.get('page', 0), total_pages - 1)
    state['page'] = page

    sys.stdout.write("\033[H")

    # ── Header bar ──
    tf = Translator.translate("ui.bestiary_tab_fauna_on" if tab == FAUNA_TAB else "ui.bestiary_tab_fauna_off")
    ts = Translator.translate("ui.bestiary_tab_species_on" if tab == SPECIES_TAB else "ui.bestiary_tab_species_off")
    nav = Translator.translate("ui.bestiary_nav", fauna=tf, species=ts, page=page + 1, total=total_pages)
    title = Translator.translate("ui.bestiary_title")
    print(("═" * W)[:W] + eol)
    print(f"{title}   {nav}"[:W] + eol)
    print(("═" * W)[:W] + eol)

    lines_written = 3
    start = page * ENTRIES_PER_PAGE
    visible = entries[start : start + ENTRIES_PER_PAGE]

    for i, entry_lines in enumerate(visible):
        for line in entry_lines:
            sys.stdout.write(line + eol + "\n")
            lines_written += 1
        if i < len(visible) - 1:
            sys.stdout.write(("─" * W)[:W] + eol + "\n")
            lines_written += 1

    # Pad remaining rows to avoid frame artifacts from previous render
    total_rows = height + 12
    while lines_written < total_rows:
        sys.stdout.write(eol + "\n")
        lines_written += 1

    sys.stdout.flush()


# ── Fauna tab ──────────────────────────────────────────────────────────────

def _build_fauna_entries(world_data, config):
    fauna_list = config.get('fauna', [])
    live_counts = _count_live_fauna(world_data)
    entries = []
    for sd in fauna_list:
        entries.append(_fauna_entry(sd, live_counts))
    return entries


def _count_live_fauna(world_data):
    from entities.species.animal.base import Animal
    counts = {}
    for e in world_data['entities']:
        if isinstance(e, Animal) and not e.is_expired:
            counts[e.species] = counts.get(e.species, 0) + 1
    return counts


def _danger_bar(danger, length=10):
    filled = round(danger * length)
    return "█" * filled + "░" * (length - filled)


def _fauna_entry(sd, live_counts):
    key = sd['species']
    name = sd.get('name', key)
    char = sd.get('char', '?')
    loco = sd.get('locomotion', 'land')
    diet = sd.get('diet', '?')
    weight = sd.get('weight', '?')
    speed = sd.get('speed', 0)
    perc = sd.get('perception_range', '?')
    fear = sd.get('fear_sensitivity', '?')
    food = sd.get('food_value', [0, 0])
    danger = sd.get('danger_level', 0)

    live = live_counts.get(key, 0)
    kills = bestiary_tracker.get_kills(key)
    starved = bestiary_tracker.get_starvations(key)

    bar = _danger_bar(danger)
    danger_label = Translator.translate("ui.bestiary_danger_label")
    live_label = Translator.translate("ui.bestiary_live_label")
    killed_label = Translator.translate("ui.bestiary_killed_label")
    starved_label = Translator.translate("ui.bestiary_starved_label")

    line1 = f"  {char} {name:<18} [{loco} · {diet}]   {danger_label}: {bar} {danger:.2f}"
    line2 = "     " + Translator.translate(
        "ui.bestiary_stats_fauna",
        speed=f"{speed:.2f}", perc=perc, wt=weight,
        fear=f"{fear:.1f}", food_min=food[0], food_max=food[1]
    )
    line3 = f"     {live_label}: {live:<4}  {killed_label}: {kills:<5}  {starved_label}: {starved}"
    return [line1, line2, line3]


# ── Species tab ────────────────────────────────────────────────────────────

def _build_species_entries(world_data):
    templates = get_species_templates()
    pop_by_culture = _count_humans_by_culture(world_data)
    entries = []
    for tmpl in templates:
        entries.append(_species_entry(tmpl, pop_by_culture))
    return entries


def _count_humans_by_culture(world_data):
    from entities.registry import CIV_UNITS
    counts = {}
    for e in world_data['entities']:
        if type(e) in CIV_UNITS and not e.is_expired:
            cname = e.culture.get('name', '') if isinstance(e.culture, dict) else ''
            if cname:
                counts[cname] = counts.get(cname, 0) + 1
    return counts


def _trait_bar(value, max_val=9.0, length=5):
    filled = round((value / max_val) * length)
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def _species_entry(tmpl, pop_by_culture):
    name = tmpl.get('name', '?')
    culture = tmpl.get('culture', '?')
    origin = tmpl.get('origin', '?')
    physiology = tmpl.get('physiology', '?')
    nature = tmpl.get('nature', '?')
    emojis = tmpl.get('emojis', ['🌍', '🧬', '🌀'])
    bonuses = tmpl.get('bonuses', {})
    speed_mod = tmpl.get('speed_mod', 0.0)

    pop = pop_by_culture.get(culture, 0)
    emoji_str = " ".join(emojis)
    b = bonuses
    spd_sign = "+" if speed_mod >= 0 else ""

    line1 = f"  {emoji_str}  {name:<18} [{origin} · {physiology} · {nature}]"
    line2 = "     " + Translator.translate("ui.bestiary_pop_line", culture=culture, pop=pop)
    line3 = "     " + Translator.translate(
        "ui.bestiary_stats_species",
        strength=f"{b.get('strength', 0):.1f}",
        perception=f"{b.get('perception', 0):.1f}",
        speed_sign=spd_sign,
        speed=f"{speed_mod:.2f}",
        fertility=f"{b.get('fertility', 0):.1f}",
        harvest=f"{b.get('harvest', 0):.1f}",
        trade=f"{b.get('trade', 0):.1f}",
        defense=f"{b.get('defense', 0):.1f}",
    )
    return [line1, line2, line3]


# ── Final Chronicles bestiary summary ──────────────────────────────────────

def print_bestiary_summary(config, world_data):
    """Called at end of simulation for a printed bestiary in Final Chronicles."""
    fauna_list = config.get('fauna', [])
    live_counts = _count_live_fauna(world_data)
    templates = get_species_templates()

    col_name = Translator.translate("ui.bestiary_col_name")
    col_type = Translator.translate("ui.bestiary_col_type")
    col_danger = Translator.translate("ui.bestiary_col_danger")
    col_live = Translator.translate("ui.bestiary_col_live")
    col_killed = Translator.translate("ui.bestiary_col_killed")
    col_starved = Translator.translate("ui.bestiary_col_starved")

    print("\n" + "─" * 50)
    print(Translator.translate("ui.bestiary_summary_fauna_title"))
    print("─" * 50)
    print(f"  {col_name:<20} {col_type:<18} {col_danger:>7}  {col_live:>5}  {col_killed:>7}  {col_starved:>8}")
    print("  " + "─" * 70)
    for sd in fauna_list:
        key = sd['species']
        loco = sd.get('locomotion', 'land')
        diet = sd.get('diet', '?')
        archetype = f"{loco}/{diet}"
        print(
            f"  {sd.get('char','')} {sd.get('name','?'):<18} "
            f"{archetype:<18} "
            f"{sd.get('danger_level', 0):>7.2f}  "
            f"{live_counts.get(key, 0):>5}  "
            f"{bestiary_tracker.get_kills(key):>7}  "
            f"{bestiary_tracker.get_starvations(key):>8}"
        )

    if templates:
        print("\n" + "─" * 50)
        print(Translator.translate("ui.bestiary_summary_species_title"))
        print("─" * 50)
        pop_by_culture = _count_humans_by_culture(world_data)
        for tmpl in templates:
            emojis = " ".join(tmpl.get('emojis', []))
            b = tmpl.get('bonuses', {})
            sm = tmpl.get('speed_mod', 0)
            sign = "+" if sm >= 0 else ""
            print(
                f"  {emojis} {tmpl.get('name','?'):<16}"
                f" [{tmpl.get('origin','?')} · {tmpl.get('physiology','?')} · {tmpl.get('nature','?')}]"
                f"  " + Translator.translate(
                    "ui.bestiary_pop_line",
                    culture=tmpl.get('culture', '?'),
                    pop=pop_by_culture.get(tmpl.get('culture', ''), 0)
                )
            )
            print(
                "     " + Translator.translate(
                    "ui.bestiary_stats_species",
                    strength=f"{b.get('strength', 0):.1f}",
                    perception=f"{b.get('perception', 0):.1f}",
                    speed_sign=sign,
                    speed=f"{sm:.2f}",
                    fertility=f"{b.get('fertility', 0):.1f}",
                    harvest=f"{b.get('harvest', 0):.1f}",
                    trade=f"{b.get('trade', 0):.1f}",
                    defense=f"{b.get('defense', 0):.1f}",
                )
            )
    print("─" * 50)
