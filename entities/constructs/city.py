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
        self.settler_cooldown = 0
        self.cooldown_duration = 100
        self.infected_count = 0
        self.is_infected = False
    def update(self, world, stats):
        # Capacité max théorique de la case (ex: 8000)
        max_pop = 10000

        # Facteur de freinage : plus on est proche de max_pop, plus growth_rate tend vers 1.0
        # Si pop = 10000, saturation = 0, donc croissance = 0.
        saturation = max(0, (max_pop - self.population) / max_pop)

        near_water = world['riv'][self.y][self.x] > 0
        base_growth = 0.01 if near_water else 0.005 # +1% ou +0.5%

        # Nouvelle population avec freinage logistique
        self.population += int(self.population * base_growth * saturation)
        # Gestion du timer de colonisation
        if self.settler_cooldown > 0:
            self.settler_cooldown -= 1

        # 2. Logique d'Expansion
        if self.population >= self.settler_threshold and self.settler_cooldown == 0:
            if self._spawn_settler(world):
                # On ne déclenche le cooldown et le coût que si le spawn réussit
                self.population -= self.settler_cost
                self.settler_cooldown = self.cooldown_duration

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