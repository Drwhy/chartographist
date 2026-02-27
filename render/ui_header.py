from core.random_service import RandomService

def render_header(width, world_data, stats, config):
    """Affiche les statistiques globales en haut de l'écran avec nettoyage de ligne."""
    hunters = sum(1 for e in world_data['entities'] if getattr(e, 'char', '') == "🏹")
    fauna = sum(1 for e in world_data['entities'] if getattr(e, 'type', '') == "animal")
    cities = sum(1 for e in world_data['entities'] if getattr(e, 'subtype', '') == "city")

    world_name = config.get("world_name", "WORLD").upper()

    # Le code \033[K (EL - Erase in Line) efface tout ce qui se trouve à droite
    # du curseur. On l'ajoute à la fin de chaque ligne de print.
    erase_to_end = "\033[K"

    print(f"--- 🗺️  {world_name} | AN: {stats['year']} | 🏛️  VILLES: {cities} ---{erase_to_end}")
    print(f"🏹 CHASSEURS: {hunters} | 🐾 FAUNE: {fauna} | 🌱 SEED: {stats['seed']}{erase_to_end}")

    # La ligne de séparation
    print("=" * (width * 2))