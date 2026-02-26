import random
from entities.actor import Actor
from entities.registry import register_civ

@register_civ
class Settler(Actor):
    def __init__(self, x, y, culture, config, home_pos):
        super().__init__(x, y, culture, config)
        self.char = culture.get("settler_emoji", "🚶")
        self.home_pos = home_pos
        self.type = "human"
        self.travel_distance = 0
        self.min_travel = random.randint(12, 25)
        self.type = "hunter"
    @staticmethod
    def try_spawn(city_pos, city_data, world, config, active_homes):
        """
        RÈGLE MISE À JOUR :
        Uniquement une VILLE peut envoyer des colons.
        """
        # Vérification du type de structure
        if city_data.get('type') != "city": # On ignore les "village"
            return None

        # Un seul colon par ville à la fois
        if city_pos in active_homes:
            return None

        # Probabilité de spawn
        if random.random() < 0.02:
            return Settler(city_pos[0], city_pos[1], city_data['culture'], config, city_pos)

        return None

    def think(self, world):
        """Logique de décision : marcher loin de la ville mère avant de fonder."""
        self.travel_distance += 1

        # Distance de sécurité pour ne pas étouffer la ville mère
        if self.travel_distance >= self.min_travel:
            # On cherche un bon terrain (plaine et bord de rivière)
            h = world['elev'][self.y][self.x]
            is_near_river = world['riv'][self.y][self.x] > 0

            # Condition de fondation : Bon terrain + Rivière OU grande distance
            if (0 <= h < 0.3 and is_near_river) or self.travel_distance > 40:
                self._found_village(world)

    def perform_action(self, world):
        """Mouvement exploratoire."""
        dx, dy = random.randint(-1, 1), random.randint(-1, 1)
        nx, ny = self.x + dx, self.y + dy

        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0:
                self.pos = (nx, ny)

    def _found_village(self, world):
        """Transforme l'unité en village."""
        if self.pos not in world['civ']:
            world['civ'][self.pos] = {
                'type': 'village', # Le colon fonde toujours un village, pas une ville directe
                'culture': self.culture,
                'name': f"Nouv. {self.culture['name'][:3]}.",
                'founded': world['cycle']
            }
            self.is_expired = True
            if 'stats' in world:
                world['stats']['logs'].append(f"🏠 {self.culture['name']} a étendu son territoire !")