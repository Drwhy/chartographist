import sys
from core.species import get_species_templates
from core.religion import get_religion_templates
from core import bestiary_tracker
from core.translator import Translator

FAUNA_TAB = 'fauna'
SPECIES_TAB = 'species'
RELIGION_TAB = 'religion'
GUIDE_TAB = 'guide'
SETTLEMENTS_TAB = 'cities'
CHRONICLES_TAB = 'chronicles'
DIPLOMACY_TAB = 'diplomacy'
SYSTEMS_TAB = "systems"
WHY_TAB = "why"
ENTRIES_PER_PAGE = 7

_GUIDE_KEYS = [
    ('bestiary_guide.section_fauna',           None),
    ('bestiary_guide.speed_name',              'bestiary_guide.speed_desc'),
    ('bestiary_guide.perception_name',         'bestiary_guide.perception_desc'),
    ('bestiary_guide.weight_name',             'bestiary_guide.weight_desc'),
    ('bestiary_guide.fear_name',               'bestiary_guide.fear_desc'),
    ('bestiary_guide.food_name',               'bestiary_guide.food_desc'),
    ('bestiary_guide.danger_name',             'bestiary_guide.danger_desc'),
    ('bestiary_guide.section_species',         None),
    ('bestiary_guide.strength_name',           'bestiary_guide.strength_desc'),
    ('bestiary_guide.species_perception_name', 'bestiary_guide.species_perception_desc'),
    ('bestiary_guide.speed_mod_name',          'bestiary_guide.speed_mod_desc'),
    ('bestiary_guide.fertility_name',          'bestiary_guide.fertility_desc'),
    ('bestiary_guide.harvest_name',            'bestiary_guide.harvest_desc'),
    ('bestiary_guide.trade_name',              'bestiary_guide.trade_desc'),
    ('bestiary_guide.defense_name',            'bestiary_guide.defense_desc'),
    ('bestiary_guide.section_religion',        None),
    ('bestiary_guide.growth_name',             'bestiary_guide.growth_desc'),
    ('bestiary_guide.religion_perception_name','bestiary_guide.religion_perception_desc'),
    ('bestiary_guide.religion_harvest_name',   'bestiary_guide.religion_harvest_desc'),
    ('bestiary_guide.religion_trade_name',     'bestiary_guide.religion_trade_desc'),
    ('bestiary_guide.religion_defense_name',   'bestiary_guide.religion_defense_desc'),
]


def render_bestiary(width, height, world_data, config, state):
    """Full-screen bestiary overlay replacing the normal simulation frame."""
    tab = state.get('tab', FAUNA_TAB)
    W = width * 2
    eol = "\033[K"

    if tab == FAUNA_TAB:
        entries = _build_fauna_entries(world_data, config)
    elif tab == SPECIES_TAB:
        entries = _build_species_entries(world_data)
    elif tab == RELIGION_TAB:
        entries = _build_religion_entries()
    elif tab == SETTLEMENTS_TAB:
        entries = _build_settlements_entries(world_data)
    elif tab == CHRONICLES_TAB:
        entries = _build_chronicle_entries(world_data)
    elif tab == DIPLOMACY_TAB:
        entries = _build_diplomacy_entries(world_data)
    elif tab == SYSTEMS_TAB:
        entries = _build_system_entries(world_data, config)
    elif tab == WHY_TAB:
        entries = _build_why_entries(world_data, config, state)
    else:
        entries = _build_guide_entries()

    total_pages = max(1, (len(entries) + ENTRIES_PER_PAGE - 1) // ENTRIES_PER_PAGE)
    page = min(state.get('page', 0), total_pages - 1)
    state['page'] = page

    sys.stdout.write("\033[H")

    # ── Header bar ──
    tf = Translator.translate("ui.bestiary_tab_fauna_on" if tab == FAUNA_TAB else "ui.bestiary_tab_fauna_off")
    ts = Translator.translate("ui.bestiary_tab_species_on" if tab == SPECIES_TAB else "ui.bestiary_tab_species_off")
    tr = Translator.translate("ui.bestiary_tab_religion_on" if tab == RELIGION_TAB else "ui.bestiary_tab_religion_off")
    tg = Translator.translate("ui.bestiary_tab_guide_on" if tab == GUIDE_TAB else "ui.bestiary_tab_guide_off")
    tc = Translator.translate("ui.bestiary_tab_cities_on" if tab == SETTLEMENTS_TAB else "ui.bestiary_tab_cities_off")
    th = Translator.translate("ui.bestiary_tab_chronicles_on" if tab == CHRONICLES_TAB else "ui.bestiary_tab_chronicles_off")
    ty = Translator.translate("ui.bestiary_tab_systems_on" if tab == SYSTEMS_TAB else "ui.bestiary_tab_systems_off")
    tw = Translator.translate("ui.bestiary_tab_why_on" if tab == WHY_TAB else "ui.bestiary_tab_why_off")
    td = Translator.translate("ui.bestiary_tab_diplomacy_on" if tab == DIPLOMACY_TAB else "ui.bestiary_tab_diplomacy_off")
    nav = Translator.translate(
        "ui.bestiary_nav",
        fauna=tf,
        species=ts,
        religion=tr,
        guide=tg,
        cities=tc,
        chronicles=th,
        systems=ty,
        why=tw,
        diplomacy=td,
        page=page + 1,
        total=total_pages,
    )
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
    origin_key = tmpl.get('origin', '?')
    physiology_key = tmpl.get('physiology', '?')
    nature_key = tmpl.get('nature', '?')
    emojis = tmpl.get('emojis', ['🌍', '🧬', '🌀'])
    bonuses = tmpl.get('bonuses', {})
    speed_mod = tmpl.get('speed_mod', 0.0)

    origin = Translator.translate(f"species.origins.{origin_key}")
    physiology = Translator.translate(f"species.physiologies.{physiology_key}")
    nature = Translator.translate(f"species.natures.{nature_key}")

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


# ── Religion tab ───────────────────────────────────────────────────────────

def _build_religion_entries():
    templates = get_religion_templates()
    entries = []
    for tmpl in templates:
        entries.append(_religion_entry(tmpl))
    return entries


def _religion_entry(tmpl):
    name = tmpl.get('name', '?')
    god = tmpl.get('god', '?')
    culture = tmpl.get('culture', '?')
    domain_key = tmpl.get('domain', '')
    emoji = tmpl.get('emoji', '🙏')
    bonuses = tmpl.get('bonuses', {})
    parents = tmpl.get('parents', [])

    domain_label = Translator.translate(f"domains.{domain_key}.name")

    line1 = f"  {emoji} {name:<28} [{domain_label}]"
    line2 = "     " + Translator.translate("ui.bestiary_religion_culture_line", culture=culture, god=god)
    line3 = "     " + Translator.translate(
        "ui.bestiary_stats_religion",
        growth=f"{bonuses.get('growth', 0)}",
        perception=f"{bonuses.get('perception', 0)}",
        harvest=f"{bonuses.get('harvest', 0)}",
        trade=f"{bonuses.get('trade', 0)}",
        defense=f"{bonuses.get('defense', 0)}",
    )
    lines = [line1, line2, line3]
    if parents:
        lines.append("     " + Translator.translate("ui.bestiary_religion_parents", p1=parents[0], p2=parents[1] if len(parents) > 1 else "?"))
    return lines


# ── Settlements tab ────────────────────────────────────────────────────────

def _build_settlements_entries(world_data):
    from entities.constructs.city import City
    from entities.constructs.village import Village
    settlements = [
        e for e in world_data['entities']
        if isinstance(e, (City, Village)) and not e.is_expired
    ]
    settlements.sort(key=lambda s: (0 if isinstance(s, City) else 1, s.name))
    return [_settlement_entry(s) for s in settlements]


def _settlement_economy_line(settlement):
    from core.economy import economy_snapshot

    economy = economy_snapshot(settlement)
    return Translator.translate(
        "ui.bestiary_settlements_economy_line",
        treasury=f"{economy['treasury']:.2f}",
        price=f"{economy['food_price']:.2f}",
        imported=economy["food_imported"],
        exported=economy["food_exported"],
    )


def _settlement_entry(settlement):
    from entities.constructs.city import City
    from entities.species.human.base import Human
    from entities.species.human.farmer import Farmer

    name = settlement.name
    char = settlement.char
    culture_name = settlement.culture.get('name', '?') if isinstance(settlement.culture, dict) else '?'
    citizens = settlement.citizens
    pop = len(citizens)

    type_key = "ui.bestiary_settlements_type_city" if isinstance(settlement, City) else "ui.bestiary_settlements_type_village"
    type_label = Translator.translate(type_key)

    civilians = sum(1 for c in citizens if type(c) is Human)
    farmers   = sum(1 for c in citizens if isinstance(c, Farmer))
    males     = sum(1 for c in citizens if getattr(c, 'sex', '?') == 'M')
    females   = sum(1 for c in citizens if getattr(c, 'sex', '?') == 'F')

    couple_pairs = set()
    for c in citizens:
        if c.partner is not None and not c.partner.is_dead:
            couple_pairs.add(frozenset({c.entity_id, c.partner.entity_id}))
    couples = len(couple_pairs)

    families  = sum(1 for c in citizens if any(not ch.is_dead for ch in c.children))
    dynasties = len({c.family_name for c in citizens if c.family_name})
    in_love   = sum(1 for c in citizens
                    if getattr(c, 'love_interest', None) is not None
                    and getattr(c, 'love_score', 0) > 0.3)

    food     = int(getattr(settlement, 'food_stock', 0))
    max_food = int(getattr(settlement, 'max_food', 0))

    faith_label = '—'
    if settlement.religion and settlement.religion.dominant:
        faith_label = settlement.religion.dominant

    line1 = f"  {char} {name:<22} [{culture_name}]   {type_label}"
    line2 = "     " + Translator.translate(
        "ui.bestiary_settlements_pop_line",
        pop=pop, couples=couples, families=families, dynasties=dynasties
    )
    line3 = "     " + Translator.translate(
        "ui.bestiary_settlements_roles_line",
        civilians=civilians, farmers=farmers, males=males, females=females, in_love=in_love
    )
    line4 = "     " + Translator.translate(
        "ui.bestiary_settlements_food_line",
        food=food, max_food=max_food, faith=faith_label
    )
    lines = [line1, line2, line3, line4]
    from core.economy import economy_enabled
    if economy_enabled(settlement):
        lines.append("     " + _settlement_economy_line(settlement))
    return lines


# ── Diplomacy tab ──────────────────────────────────────────────────────────

def _build_diplomacy_entries(world_data):
    from core.diplomacy import DiplomacyRegistry

    entities = {
        entity.entity_id: entity
        for entity in world_data.get("entities", [])
        if hasattr(entity, "entity_id")
    }
    entries = []
    for relation in DiplomacyRegistry(world_data).query():
        first = entities.get(relation["first_id"])
        second = entities.get(relation["second_id"])
        first_name = getattr(first, "name", relation["first_id"])
        second_name = getattr(second, "name", relation["second_id"])
        status = Translator.translate(
            f"ui.diplomacy_status_{relation['status']}"
        )
        line1 = "  " + Translator.translate(
            "ui.diplomacy_relation_line",
            first=first_name,
            second=second_name,
            status=status,
        )
        line2 = "     " + Translator.translate(
            "ui.diplomacy_metrics_line",
            trust=f"{relation['trust']:.1f}",
            tension=f"{relation['tension']:.1f}",
            interdependence=f"{relation['interdependence']:.1f}",
        )
        entries.append([line1, line2])
    if not entries:
        entries.append(["  " + Translator.translate("ui.diplomacy_empty")])
    return entries


# ── Guide tab ──────────────────────────────────────────────────────────────

def _build_guide_entries():
    entries = []
    for name_key, desc_key in _GUIDE_KEYS:
        name = Translator.translate(f"ui.{name_key}")
        if desc_key is None:
            entries.append([name])
        else:
            desc = Translator.translate(f"ui.{desc_key}")
            entries.append([f"  {name}", f"     {desc}"])
    return entries


# ── Chronicles tab ────────────────────────────────────────────────────────

def _build_chronicle_entries(world_data):
    from core.chronicles import ChronicleBook

    entries = []
    for entry in reversed(ChronicleBook(world_data).query()):
        date = Translator.translate(
            "ui.chronicle_date",
            year=entry["year"],
            month=entry["month"],
            cycle=entry["cycle"],
        )
        category = Translator.translate(
            f"ui.chronicle_category_{entry['category']}"
        )
        if category.startswith("[MISSING_TEXT:"):
            category = Translator.translate(
                "ui.chronicle_category",
                category=entry["category"],
            )
        lines = [f"  {date}  {category}", f"     {entry['message']}"]
        if entry.get("caused_by") or entry.get("resulted_in"):
            lines.append(
                "     " + Translator.translate(
                    "ui.chronicle_causality",
                    causes=len(entry.get("caused_by", ())),
                    results=len(entry.get("resulted_in", ())),
                )
            )
        entries.append(lines)
    return entries

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
            origin = Translator.translate(f"species.origins.{tmpl.get('origin','?')}")
            physiology = Translator.translate(f"species.physiologies.{tmpl.get('physiology','?')}")
            nature = Translator.translate(f"species.natures.{tmpl.get('nature','?')}")
            print(
                f"  {emojis} {tmpl.get('name','?'):<16}"
                f" [{origin} · {physiology} · {nature}]"
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

    religion_templates = get_religion_templates()
    if religion_templates:
        print("\n" + "─" * 50)
        print(Translator.translate("ui.bestiary_summary_religion_title"))
        print("─" * 50)
        for tmpl in religion_templates:
            domain_key = tmpl.get('domain', '')
            domain_label = Translator.translate(f"domains.{domain_key}.name")
            b = tmpl.get('bonuses', {})
            parents = tmpl.get('parents', [])
            print(
                f"  {tmpl.get('emoji','🙏')} {tmpl.get('name','?'):<28} [{domain_label}]  "
                + Translator.translate("ui.bestiary_religion_culture_line", culture=tmpl.get('culture', '?'), god=tmpl.get('god', '?'))
            )
            print(
                "     " + Translator.translate(
                    "ui.bestiary_stats_religion",
                    growth=f"{b.get('growth', 0)}",
                    perception=f"{b.get('perception', 0)}",
                    harvest=f"{b.get('harvest', 0)}",
                    trade=f"{b.get('trade', 0)}",
                    defense=f"{b.get('defense', 0)}",
                )
            )
            if parents:
                print("     " + Translator.translate("ui.bestiary_religion_parents", p1=parents[0], p2=parents[1] if len(parents) > 1 else "?"))
    print("─" * 50)

# Systems tab

def _build_system_entries(world_data, config):
    from core.system_visibility import systems_snapshot

    entries = []
    for system in systems_snapshot(world_data, config):
        identifier = system["id"]
        state = system["state"]
        effects = system["effects"]
        name = Translator.translate(f"ui.system_name_{identifier}")
        status = Translator.translate(
            "ui.system_status_enabled"
            if system["enabled"]
            else "ui.system_status_disabled"
        )
        header = Translator.translate(
            "ui.system_entry_header",
            name=name,
            status=status,
        )
        values = _system_line_values(identifier, state, effects)
        detail = Translator.translate(f"ui.system_{identifier}_line", **values)
        entries.append([f"  {header}", f"     {detail}"])
    return entries


def _system_line_values(identifier, state, effects):
    if identifier == "climate":
        return {
            "season": Translator.translate(f"ui.season_{state.get('season', 'spring')}"),
            "drought": round(float(state.get("drought_severity", 0.0)) * 100),
            "flood": round(float(state.get("flood_severity", 0.0)) * 100),
            "events": int(effects.get("events", 0)),
        }
    if identifier == "resources":
        return {
            "biomass": round(float(state["biomass_ratio"]) * 100),
            "fish": round(float(state["fish_ratio"]) * 100),
            "soil": round(float(state["soil_ratio"]) * 100),
            "forest": round(float(state["forest_ratio"]) * 100),
        }
    if identifier == "ecology":
        return {"fauna": state["fauna"], **effects}
    if identifier == "food":
        return {**state, **effects}
    if identifier == "economy":
        return state
    if identifier == "diplomacy":
        statuses = state.get("statuses", {})
        return {
            "relations": state.get("relations", 0),
            "wars": statuses.get("war", 0),
            "alliances": statuses.get("alliance", 0),
            "pacts": statuses.get("trade_pact", 0),
        }
    if identifier == "characters":
        return {**state, **effects}
    if identifier == "materials":
        return state
    if identifier == "artifacts":
        return {
            "artifacts": int(state.get("artifacts", 0)),
            "active": int(state.get("active", 0)),
            "lost": int(state.get("lost", 0)),
            "holders": int(state.get("holders", 0)),
            "renown": round(float(state.get("total_renown", 0.0)), 1),
            "events": int(state.get("provenance_events", 0)),
        }
    if identifier == "legends":
        motives = state.get("motivations", {})
        return {
            "legends": int(state.get("legends", 0)),
            "versions": int(state.get("versions", 0)),
            "renown": round(float(state.get("total_renown", 0.0)), 1),
            "propagations": int(state.get("propagations", 0)),
            "exploration": int(motives.get("exploration", 0)),
            "war": int(motives.get("war", 0)),
            "cult": int(motives.get("cult", 0)),
        }
    if identifier == "knowledge":
        return {**state, **effects}
    if identifier == "politics":
        return {
            "settlements": int(state.get("settlements", 0)),
            "factions": int(state.get("factions", 0)),
            "legitimacy": round(float(state.get("average_legitimacy", 0.0))),
            "policies": int(state.get("active_policies", 0)),
            "conflicts": int(state.get("conflicts", 0)),
            "proposals": int(effects.get("proposals", 0)),
        }
    if identifier == "pathfinding":
        return {
            "queries": int(state.get("queries", 0)),
            "cache_hits": int(state.get("cache_hits", 0)),
            "cache_entries": int(state.get("cache_entries", 0)),
            "invalidations": int(state.get("invalidations", 0)),
            "expanded": int(state.get("expanded_nodes", 0)),
        }
    if identifier == "territory":
        return {
            "claimed": int(state.get("claimed_tiles", 0)),
            "owned": sum(int(value) for value in state.get("owned_tiles", {}).values()),
            "contested": int(state.get("contested_tiles", 0)),
            "borders": len(state.get("borders", ())),
        }
    if identifier == "migration":
        return {
            "migrants": int(state.get("total_migrants", 0)),
            "diasporas": int(state.get("active_diasporas", 0)),
            "returnees": int(state.get("returnees", 0)),
            "cohorts": len(state.get("recent_cohorts", ())),
        }
    if identifier == "warfare":
        return {
            "active": len(state.get("active_campaigns", ())),
            "ended": len(state.get("ended_campaigns", ())),
            "casualties": int(state.get("total_casualties", 0)),
            "prisoners": int(state.get("total_prisoners", 0)),
            "supply": round(float(state.get("total_supply_consumed", 0.0)), 1),
            "occupations": len(state.get("occupations", ())),
        }
    if identifier == "sites":
        return {
            "sites": int(state.get("sites", 0)),
            "kinds": len(state.get("kinds", {})),
            "statuses": len(state.get("statuses", {})),
            "discoveries": int(state.get("discoveries", 0)),
            "dropped_sites": int(state.get("dropped_sites", 0)),
        }
    if identifier == "peace":
        return {
            "treaties": int(state.get("treaties", 0)),
            "debts": len(state.get("debts", ())),
            "veterans": sum(int(value) for value in state.get("veterans", {}).values()),
            "refugees": int(state.get("refugees", 0)),
            "ruins": int(state.get("ruins", 0)),
        }
    if identifier == "history":
        return state
    if identifier == "influence":
        return state
    if identifier == "events":
        return state
    objectives = state.get("objectives", ())
    status = (
        Translator.translate(
            f"ui.scenario_status_{state.get('status', 'active')}"
        )
        if state.get("configured")
        else Translator.translate("ui.system_status_disabled")
    )
    return {
        "status": status,
        "complete": effects.get("completed_objectives", 0),
        "total": len(objectives),
    }

def _build_why_entries(world_data, config, state=None):
    """Rend les situations explicables selon le filtre terminal courant."""
    from core.why import ExplanationService

    current = state if isinstance(state, dict) else {}
    selected_filter = current.get("why_filter", "all")
    category = None if selected_filter == "all" else selected_filter
    service = ExplanationService(world_data, config)
    explanations = service.overview(category=category)
    entries = []
    for explanation in explanations:
        subject = explanation.get("subject", {})
        header = Translator.translate(
            "ui.why_entry_header",
            kind=subject.get("kind", "?"),
            subject_id=subject.get("id", "?"),
        )
        summary = explanation.get("summary") or Translator.translate(
            "ui.why_no_summary"
        )
        lines = [
            "  " + Translator.translate("ui.why_heading"),
            f"     {header}",
            f"     {summary}",
        ]
        for cause in explanation.get("causes", ())[:3]:
            lines.append(
                "     " + Translator.translate(
                    "ui.why_cause",
                    cause=cause.get("kind", "unknown"),
                )
            )
        entries.append(lines)
    if not entries:
        entries.append([
            "  " + Translator.translate("ui.why_heading"),
            "     " + Translator.translate("ui.why_empty"),
        ])
    return entries
