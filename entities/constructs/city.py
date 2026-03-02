from .base import Construct
from entities.registry import register_structure
from entities.species.human.settler import Settler
from core.logger import GameLogger
from core.random_service import RandomService

@register_structure
class City(Construct):
    def __init__(self, x, y, culture, config):
        super().__init__(x, y, culture, config)
        # Identité
        self.char = culture.get("city", "🏛️ ")
        # Économie et Population
        self.population = RandomService.randint(500, 1000)
        self.growth_rate = config.get("city_growth", 1.005) # +2% par tour
        self.settler_threshold = 5000 # Population nécessaire pour envoyer des colons
        self.settler_cost = 1500       # Population "consommée" par l'envoi d'un groupe

    def update(self, world, stats):
        """Évolution de la cité à chaque cycle."""
        
        # 1. Croissance démographique
        # On applique un facteur de croissance basé sur l'accès à l'eau
        near_water = world['riv'][self.y][self.x] > 0
        current_growth = self.growth_rate if near_water else (self.growth_rate * 0.98)
        
        self.population = int(self.population * current_growth)

        # 2. Logique d'Expansion (Génération de Colons)
        if self.population >= self.settler_threshold:
            self._spawn_settler(world)

    def _spawn_settler(self, world):
        """Crée un colon qui partira fonder un village relié par une route."""
        
        # On réduit la population de la ville mère
        self.population -= self.settler_cost
        
        # Création du colon à la position de la ville
        # On lui passe 'self' (la ville mère) pour qu'il sache où tracer la route
        new_settler = Settler(self.x, self.y, self.culture, self.config, home_city=self)
        
        # Ajout au gestionnaire d'entités
        world['entities'].add(new_settler)
        
        GameLogger.log(f"🚶Trop peuplée ! Un groupe de colons part de {self.name} vers l'inconnu.")

    def take_damage(self, amount):
        """La population peut baisser en cas de catastrophe ou d'attaque."""
        self.population -= amount
        if self.population <= 0:
            self.is_expired = True
            GameLogger.log(f"🏚️  La cité de {self.name} a été abandonnée.")