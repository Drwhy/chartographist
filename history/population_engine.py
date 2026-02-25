import random
from fauna.species.human.hunter import Hunter

def update_population(world, stats):
    """
    Gère le cycle de vie des colons et des chasseurs.
    """

    # --- 1. GESTION DES COLONS (SETTLERS) ---
    for s in world['settlers'][:]:
        s.update()

        # Si le colon est arrivé, il fonde un village
        if hasattr(s, 'reached') and s.reached:
            pos = s.current_pos
            if pos not in world['civ']:
                # PROTECTION : On récupère le nom s'il existe, sinon fallback
                v_name = getattr(s, 'target_name', "Nouveau Village")

                world['civ'][pos] = {
                    "name": v_name,
                    "type": "village",
                    "culture": s.culture,
                    "age": 0
                }
                stats['logs'].append(f"🏠 {v_name} a été fondé par des colons.")

            # On retire le colon après fondation
            if s in world['settlers']:
                world['settlers'].remove(s)

    # --- 2. GESTION DES CHASSEURS (HUNTERS) ---
    active_hunter_homes = []

    for h in world['hunters'][:]:
        # A. Vérification de combat/capture AVANT l'update
        if h.target_prey and h.current_pos == tuple(getattr(h.target_prey, 'pos', (None, None))):
            combat_log = h.catch_prey(world['fauna'])
            if combat_log:
                stats['logs'].append(combat_log)

        # B. Mise à jour (IA, mouvement, repos, évitement eau)
        h.update(world['fauna'], world['elev'])

        # C. Enregistrement pour le quota de spawn
        active_hunter_homes.append(h.home_pos)

        # D. Vieillesse : On augmente un peu la limite si tu veux qu'ils durent
        if h.age > 150:
            if h in world['hunters']:
                world['hunters'].remove(h)

    # --- 3. LOGIQUE DE SPAWN (1 par VILLAGE uniquement) ---
    for pos, data in world['civ'].items():
        # Restriction : type == "village" uniquement
        if data.get('type') == "village":
            if pos not in active_hunter_homes:
                new_hunter = Hunter(pos, data['culture'])
                world['hunters'].append(new_hunter)

    # Note: On ne retourne rien car 'world' et 'stats' sont modifiés en place (mutabilité)