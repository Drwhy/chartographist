def render_logs(width, stats):
    """Affiche les derniers messages sous la carte."""
    print("=" * (width * 2))
    logs = stats.get('logs', [])
    for l in logs[-5:]:
        # Nettoyage et formatage pour éviter les décalages de ligne
        clean_log = str(l)[:width*2-4]
        print(f" > {clean_log}".ljust(width * 2))