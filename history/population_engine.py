import random
from fauna.species.human.hunter import Hunter

def update_population(world, stats):
    """
    Gère le cycle de vie des colons et des chasseurs.
    """

    # --- 1. GESTION DES COLONS (SETTLERS) ---
    for s in world['settlers'][:]:
        s.update()

        if hasattr(s, 'reached') and s.reached:
            pos = s.current_pos
            if pos not in world['civ']:
                v_name = getattr(s, 'target_name', "Nouveau Village")
                world['civ'][pos] = {
                    "name": v_name,
                    "type": "village",
                    "culture": s.culture,
                    "age": 0
                }
                stats['logs'].append(f"🏠 {v_name} a été fondé par des colons.")

            if s in world['settlers']:
                world['settlers'].remove(s)

    # --- 2. GESTION DES CHASSEURS (HUNTERS) ---
    active_hunter_homes = []

    for h in world['hunters'][:]:
        # A. Vérification de combat/capture AVANT l'update
        if h.target_prey and h.current_pos == tuple(getattr(h.target_prey, 'pos', (None, None))):
            # On récupère le dictionnaire {'event': ..., 'log': ...}
            result = h.catch_prey(world['fauna'])

            if result:
                # On extrait uniquement la chaîne de caractères pour les logs
                stats['logs'].append(result['log'])

                # Si l'événement est un décès, on supprime le chasseur et on passe au suivant
                if result['event'] == 'hunter_died':
                    if h in world['hunters']:
                        world['hunters'].remove(h)
                    continue

        # B. Mise à jour de l'IA (IA, mouvement, repos, évitement eau)
        h.update(world['fauna'], world['elev'])

        # C. Enregistrement pour le quota de spawn
        active_hunter_homes.append(h.home_pos)

        # D. Retraite naturelle (Vieillesse)
        if h.age > 150:
            if h in world['hunters']:
                world['hunters'].remove(h)

    # --- 3. LOGIQUE DE SPAWN (1 VILLAGE = 1 CHASSEUR) ---
    for pos, data in world['civ'].items():
        if data.get('type') == "village":
            if pos not in active_hunter_homes:
                new_hunter = Hunter(pos, data['culture'])
                world['hunters'].append(new_hunter)