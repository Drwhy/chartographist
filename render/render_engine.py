import sys, time, math, random

class RenderEngine:
    def __init__(self, width, height, config):
        self.width = width
        self.height = height
        self.config = config

    def _get_char(self, x, y, world_data):
        """Détermine le caractère unique pour une coordonnée (x, y) avec logique climatique."""
        # 1. EXTRACTION DES DONNÉES
        h = world_data['elev'][y][x]
        r = world_data['riv'][y][x]
        rd = world_data['road'][y][x]
        cycle = world_data['cycle']

        # Accès aux dictionnaires de config (template.json)
        bio = self.config.get("biomes", {})
        wat = self.config.get("water", {})
        spec = self.config.get("special", {})

        # 2. PRIORITÉ : ENTITÉS (EntityManager remplace les listes séparées)
        animal_char = None
        entities_at_pos = [e for e in world_data['entities'] if e.pos == (x, y)]

        for entity in entities_at_pos:
            # Si c'est un humain ou un construct (ville), on gère la priorité
            if getattr(entity, 'type', '') == 'actor': # Humains (Hunters/Settlers)
                return entity.char
            if getattr(entity, 'type', '') == 'animal':
                animal_char = entity.char

            # Si c'est un construct (Village/City)
            if getattr(entity, 'type', '') == 'construct':
                # Logique spécifique aux ports (si au bord de l'eau)
                if getattr(entity, 'subtype', '') == "village":
                    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < self.height and 0 <= nx < self.width:
                            if world_data['elev'][ny][nx] < 0:
                                return entity.culture.get("port", spec.get("port", "⚓"))
                return entity.char
        # 3. RETOUR DE L'ANIMAL (S'il n'y avait pas d'humain ou de construct dessus)
        if animal_char:
            return animal_char

        # 4. RÉSEAUX (Routes et Rivières)
        if rd and rd != "  " and h >= 0: return rd
        if r > 0 and h >= 0: return wat.get("river", "~~")

        # 5. TERRAIN ET BIOMES (Logique climatique procédurale)
        # Calcul de la température selon la latitude, l'inclinaison (tilt) et l'altitude
        dist_to_equator = abs(y - (self.height // 2)) / (self.height // 2)
        tilt = math.sin(cycle * 0.15)
        temp = (dist_to_equator * 0.6) + (tilt * (y / self.height - 0.5) * 0.5) + (h * 0.4)

        # --- Seuils d'élévation ---
        if h > 0.90: return bio.get("volcano", "🌋")
        if h > 0.85 or temp > 0.8: return bio.get("peak", "❄️")
        if h > 0.55: return bio.get("high_mountain", "🏔️")
        if h > 0.35: return bio.get("mountain", "⛰️")

        # --- Seuils d'eau ---
        if h < -0.15: return wat.get("ocean", "🌊")
        if h < 0: return wat.get("shore", "💧")
        if h < 0.05: return bio.get("sand", "🏖️")

        # --- Distribution par température ---
        if temp > 0.65:
            return bio.get("boreal_forest", "🌲") if h > 0.2 else bio.get("glaciated", "❄️")
        if temp > 0.45:
            if h > 0.2 and 0.48 < temp < 0.55:
                return bio.get("autumn_forest", "🍂")
            return bio.get("temperate_forest", "🌳")
        if temp < 0.25 and h > 0.12:
            return bio.get("tropical_forest", "🌴")

        # FALLBACK : Sécurité ultime
        return bio.get("grassland", "🌿")

    def draw_frame(self, world_data, stats, reveal=False):
        """Affiche le monde dans le terminal."""
        if reveal:
            self._radial_reveal(world_data, stats)
            return

        sys.stdout.write("\033[H") # Reset position curseur

        # Calcul des compteurs pour l'interface
        hunters = sum(1 for e in world_data['entities'] if getattr(e, 'char', '') == "🏹")
        fauna = sum(1 for e in world_data['entities'] if getattr(e, 'type', '') == "animal")

        print(f"--- 🗺️  {self.config.get('world_name', 'WORLD').upper()} | AN: {stats['year']} ---")
        print(f"🏹 CHASSEURS: {hunters} | 🐾 FAUNE: {fauna} | SEED: {stats['seed']}")
        print("=" * (self.width * 2))

        for y in range(self.height):
            line = "".join([self._get_char(x, y, world_data) for x in range(self.width)])
            print(line)

        print("=" * (self.width * 2))
        for l in stats['logs'][-5:]:
            print(f" > {l}".ljust(self.width * 2))
        sys.stdout.flush()

    def _radial_reveal(self, world_data, stats):
        """Animation de démarrage."""
        current_display = [["  " for _ in range(self.width)] for _ in range(self.height)]
        coords = [(x, y) for y in range(self.height) for x in range(self.width)]
        center = (self.width // 2, self.height // 2)
        coords.sort(key=lambda c: math.dist(c, center) + random.uniform(-1, 1))

        for i, (x, y) in enumerate(coords):
            current_display[y][x] = self._get_char(x, y, world_data)
            if i % 15 == 0 or i == len(coords) - 1:
                sys.stdout.write("\033[H")
                print(f"--- 📜 GENÈSE : {stats['seed']} ---")
                for row in current_display:
                    print("".join(row))
                sys.stdout.flush()
                time.sleep(0.005)