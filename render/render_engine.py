import sys, time, math, random

class RenderEngine:
    def __init__(self, width, height, config):
        self.width = width
        self.height = height
        self.config = config

    def _get_char(self, x, y, elevation, river_map, structures, road_map, cycle, fauna_list):
        h = elevation[y][x]
        r = river_map[y][x]
        rd = road_map[y][x]

        bio = self.config["biomes"]
        wat = self.config["water"]
        spec = self.config["special"]

        # 1. STRUCTURES & CIVILISATIONS
        if (x, y) in structures:
            s = structures[(x, y)]

            # Gestion des ruines
            if s.get("type") == "ruin":
                return spec.get("ruin", "🏚️")

            # Récupération sécurisée de la culture
            cult = s.get("culture")
            stype = s.get("type")

            # Cas spécifique du village côtier (Port)
            if stype == "village":
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < self.height and 0 <= nx < self.width:
                        if elevation[ny][nx] < 0:
                            return cult.get("port", spec.get("port", "⚓"))

            # Retourne l'émoji (city ou village) depuis le dictionnaire de culture
            # Si cult est un dictionnaire, on pioche dedans, sinon on met un fallback
            if isinstance(cult, dict):
                return cult.get(stype, "? ")
            return "? "

        # 2. FAUNE (Priorité après les villes)
        for animal in fauna_list:
            if animal.pos == (x, y):
                return animal.char

        # 3. RÉSEAUX
        if rd != "  " and h >= 0: return rd
        if r > 0 and h >= 0: return wat["river"]

        # 4. CLIMAT & BIOMES (Logique inchangée)
        dist_to_equator = abs(y - (self.height // 2)) / (self.height // 2)
        tilt = math.sin(cycle * 0.15)
        temp = (dist_to_equator * 0.6) + (tilt * (y / self.height - 0.5) * 0.5) + (h * 0.4)

        if h > 0.90: return bio["volcano"]
        if h > 0.85 or temp > 0.8: return bio["peak"]
        if h > 0.55: return bio["high_mountain"]
        if h > 0.35: return bio["mountain"]
        if h < -0.15: return wat["ocean"]
        if h < 0: return wat["shore"]
        if h < 0.05: return bio["sand"]

        if temp > 0.65: return bio["boreal_forest"] if h > 0.2 else bio["glaciated"]
        if temp > 0.45: return bio["autumn_forest"] if h > 0.2 and 0.48 < temp < 0.55 else bio["temperate_forest"]
        return bio["tropical_forest"] if temp < 0.25 and h > 0.12 else bio["grassland"]

    def draw_frame(self, world_data, stats, reveal=False):
        if reveal:
            self._radial_reveal(world_data, stats)
        else:
            sys.stdout.write("\033[H")
            # Calcul de population sécurisé
            pop = sum(15000 if s.get("type") == "city" else 1500 for s in world_data['civ'].values())

            print(f"--- 🗺️  {self.config.get('world_name', 'WORLD').upper()} | AN: {stats['year']} ---")
            print(f"👥 POP: {pop:,} | 🐾 FAUNE: {len(world_data['fauna'])} | SEED: {stats['seed']}")
            print("=" * self.width * 2)

            for y in range(self.height):
                line = "".join([self._get_char(x, y, world_data['elev'], world_data['riv'],
                                             world_data['civ'], world_data['road'],
                                             world_data['cycle'], world_data['fauna'])
                               for x in range(self.width)])
                print(line)

            print("=" * self.width * 2)
            for l in stats['logs'][-5:]:
                print(f" > {l}".ljust(self.width * 2))
            sys.stdout.flush()

    def _radial_reveal(self, world_data, stats):
        current_display = [["  " for _ in range(self.width)] for _ in range(self.height)]
        coords = [(x, y) for y in range(self.height) for x in range(self.width)]
        center = (self.width // 2, self.height // 2)
        coords.sort(key=lambda c: math.dist(c, center) + random.uniform(-1, 1))

        for i, (x, y) in enumerate(coords):
            current_display[y][x] = self._get_char(x, y, world_data['elev'], world_data['riv'],
                                                 world_data['civ'], world_data['road'],
                                                 world_data['cycle'], world_data['fauna'])
            if i % 12 == 0 or i == len(coords) - 1:
                sys.stdout.write("\033[H")
                print(f"--- 📜 GENÈSE : {stats['seed']} ---")
                print(" " * (self.width * 2))
                for row in current_display:
                    print("".join(row))
                sys.stdout.flush()
                time.sleep(0.008)