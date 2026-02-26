import random
from entities.actor import Actor
from entities.registry import register_civ
import math

@register_civ
class Hunter(Actor):
    def __init__(self, x, y, culture, config, home_pos):
        super().__init__(x, y, culture, config)
        # On récupère l'emoji dynamiquement depuis la culture
        self.char = culture.get("hunter_emoji", "🏹")
        self.home_pos = home_pos
        self.target_prey = None

    def think(self, world):
        """Logique de décision du chasseur."""
        # Si pas de cible, on en cherche une dans world['entities']
        self._check_surroundings(world)

    def _check_surroundings(self, world):
        # Rayon de tir à l'arc (ex: 3 cases)
        range_shot = 1

        for entity in world['entities']:
            if getattr(entity, 'type', '') == 'animal' and not entity.is_expired:
                dist = math.dist(self.pos, entity.pos)

                # 1. TIR À DISTANCE (Avantage du Chasseur)
                if dist <= range_shot:
                    if random.random() < 0.3: # 30% de chance de tuer l'animal à distance
                        entity.is_expired = True
                        msg = f"🏹 {self.char} a abattu un {entity.species} à distance !"
                        world['stats']['logs'].append(msg)
                        self.target_prey = None
                        return # On s'arrête là pour ce tour

        # 2. Si aucun prédateur n'est abattu, on cherche une proie normale
        if not self.target_prey:
            self._find_prey(world)
    def perform_action(self, world):
        """Exécution du mouvement ou de la chasse."""
        if self.target_prey:
            self._move_towards_prey(world)
        else:
            self._wander(world)

    def _find_prey(self, world):
        # On cherche dans le nouveau manager d'entités
        # (Pour l'instant on simule, on affinera la logique de détection après)
        pass

    def _wander(self, world):
        """Déplacement aléatoire sécurisé."""
        dx, dy = random.randint(-1, 1), random.randint(-1, 1)
        nx, ny = self.x + dx, self.y + dy

        # Utilisation de la logique de world['elev'] pour éviter l'eau
        if 0 <= nx < world['width'] and 0 <= ny < world['height']:
            if world['elev'][ny][nx] >= 0:
                self.pos = (nx, ny) # Utilise le setter de Entity
    @staticmethod
    def try_spawn(city_pos, city_data, world, config, active_homes):
        """Décide si un chasseur doit apparaître."""
        # Règle : seulement dans les villages et si pas déjà un chasseur dehors
        if city_data.get('type') == "village" and city_pos not in active_homes:
            if random.random() < 0.1: # 10% de chance
                return Hunter(city_pos[0], city_pos[1], city_data['culture'], config, city_pos)
        return None