from .base import Construct
from entities.registry import register_structure
from core.logger import GameLogger
from entities.species.human.hunter import Hunter
from entities.species.human.fisherman import Fisherman
from core.random_service import RandomService

@register_structure
class Village(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        self.type = "construct"
        self.subtype = "village"
        self.population = RandomService.randint(50, 150)
        self.city_threshold = 1000 # Population requise pour devenir une ville
        self.char = culture.get("village", "🏛️ ")

        # Logique de gestion du chasseur
        self.check_interval = 15   # Fréquence de vérification du chasseur
        self.timer = 0

    def update(self, world, stats):
        """Mise à jour cyclique du village."""
        # 1. Croissance démographique (1% par tour)
        self.population = int(self.population * 1.01)

        # 2. Gestion du chasseur unique
        self.timer += 1
        if self.timer >= self.check_interval:
            self._verify_and_spawn_hunter(world)
            self.timer = 0

        # 3. TRANSFORMATION EN CITÉ
        if self.population >= self.city_threshold:
            self._evolve_to_city(world)

    def _verify_and_spawn_hunter(self, world):
        # On cherche n'importe quel travailleur (chasseur ou pêcheur) lié au village
        my_worker = next((e for e in world['entities']
                         if getattr(e, 'subtype', '') in ['hunter', 'fisherman']
                         and getattr(e, 'home_pos', None) == self.pos), None)

        if not my_worker and self.population > 50:
            # Est-ce un village côtier ?
            is_coastal = False
            for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                ny, nx = self.y + dy, self.x + dx
                if 0 <= ny < world['height'] and 0 <= nx < world['width']:
                    if world['elev'][ny][nx] < 0:
                        is_coastal = True
                        break

            if is_coastal:
                self._spawn_fisherman(world)
            else:
                self._spawn_village_hunter(world)

    def _spawn_village_hunter(self, world):
        """Crée un unique chasseur attaché à ce village."""

        # On passe self.pos comme home_pos
        new_hunter = Hunter(self.x, self.y, self.culture, self.config, self.pos)

        # IMPORTANT : On s'assure que le subtype est mis AVANT l'ajout au monde
        new_hunter.subtype = "hunter"
        new_hunter.home_pos = self.pos

        world['entities'].add(new_hunter)

        # Log optionnel pour vérifier en console si ça boucle encore
        # print(f"DEBUG: Village à {self.pos} a spawn un chasseur.")

    def _evolve_to_city(self, world):
        """Transforme le village en ville et nettoie les unités associées."""
        from entities.constructs.city import City

        # --- DISPARITION DU HUNTER ASSOCIÉ ---
        # On cherche le chasseur lié à ce village avant de muter
        my_hunter = next((e for e in world['entities']
                         if getattr(e, 'subtype', '') == 'hunter'
                         and getattr(e, 'home_pos', None) == self.pos), None)

        if my_hunter:
            my_hunter.is_expired = True # Le chasseur disparaît avec le village
            # Optionnel : GameLogger.log("🏹 Le chasseur local rejoint la nouvelle cité.")

        # --- CRÉATION DE LA CITÉ ---
        # On crée la cité au même endroit
        new_city = City(self.x, self.y, self.culture, self.config)
        new_city.population = self.population # Transfert de population

        # On ajoute la cité au monde
        world['entities'].add(new_city)

        # On marque le village comme expiré pour qu'il soit retiré au prochain tour
        self.is_expired = True

        GameLogger.log(f"🏛️  Le village de {self.x}, {self.y} est devenu une cité florissante !")

    def _spawn_fisherman(self, world):
        new_fisher = Fisherman(self.x, self.y, self.culture, self.config, self.pos)
        world['entities'].add(new_fisher)