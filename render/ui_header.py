def render_header(width, world_data, stats, config):
    """Affiche les statistiques globales en haut de l'écran."""
    hunters = sum(1 for e in world_data['entities'] if getattr(e, 'char', '') == "🏹")
    fauna = sum(1 for e in world_data['entities'] if getattr(e, 'type', '') == "animal")
    cities = sum(1 for e in world_data['entities'] if getattr(e, 'subtype', '') == "city")

    world_name = config.get("world_name", "WORLD").upper()

    print(f"--- 🗺️  {world_name} | AN: {stats['year']} | 🏛️  VILLES: {cities} ---")
    print(f"🏹 CHASSEURS: {hunters} | 🐾 FAUNE: {fauna} | 🌱 SEED: {stats['seed']}")
    print("=" * (width * 2))