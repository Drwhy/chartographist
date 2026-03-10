from .base import Construct
from entities.registry import register_structure, STRUCTURE_TYPES
from entities.species.human.settler import Settler
from entities.species.human.trader import Trader
from core.logger import GameLogger
from core.random_service import RandomService
from core.translator import Translator
from entities.constructs.ruins import Ruins

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
        self.active_trader = None
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

        # 2. Logique d'Expansion (Modifiée)
        if self.population >= self.settler_threshold and self.settler_cooldown == 0:
            # On ne tente le spawn que si le monde a encore du potentiel
            if self._can_world_support_new_settler(world):
                if self._spawn_settler(world):
                    # Succès : On paie le coût et on lance le cooldown
                    self.population -= self.settler_cost
                    self.settler_cooldown = self.cooldown_duration
            else:
                # Optionnel : On peut ajouter un petit cooldown de "paix"
                # pour éviter de recalculer la saturation à chaque tick
                self.settler_cooldown = 100
        # --- LOGIQUE DE SPAWN DES MARCHANDS ---
        # Condition : Population > 50 et 1% de chance par tick
        if self.active_trader is None or self.active_trader.is_expired:
            if self.population > 1000 and RandomService.random() < 0.01:
                other_cities = [
                    e for e in world['entities']
                        if type(e) in STRUCTURE_TYPES and e != self and not e.is_expired and (not isinstance(e, Ruins))
                ]
                # Si le monde est trop vide, le marchand ne spawn pas
                if len(other_cities) > 0:
                    self._spawn_trader(world)
        self._check_cultural_drift(world)
    def _spawn_settler(self, world):
        """Crée un colon qui partira fonder un village relié par une route."""
        
        # On réduit la population de la ville mère
        self.population -= self.settler_cost
        
        # Création du colon à la position de la ville
        # On lui passe 'self' (la ville mère) pour qu'il sache où tracer la route
        new_settler = Settler(self.x, self.y, self.culture, self.config, home_city=self)
        
        # Ajout au gestionnaire d'entités
        world['entities'].add(new_settler)
        GameLogger.log(Translator.translate("entities.settler_spawn", name=self.name))

    def take_damage(self, amount):
        """La population peut baisser en cas de catastrophe ou d'attaque."""
        self.population -= amount
        if self.population <= 0:
            self.is_expired = True
            GameLogger.log(Translator.translate("entities.ruins_desc", name=self.name))

    def _spawn_trader(self, world):
        """Génère un marchand unique par cité."""
        from entities.species.human.trader import Trader

        # 1. Comptage ultra-strict des marchands vivants appartenant à CETTE cité
        # On vérifie aussi si l'entité n'est pas en train d'être supprimée
        my_traders = [
            e for e in world['entities']
            if isinstance(e, Trader)
            and getattr(e, 'home_city', None) == self
            and not getattr(e, 'is_expired', False)
        ]

        # 2. LIMITE STRICTE : 1 SEUL MARCHAND
        if len(my_traders) >= 1:
            return False # On stoppe immédiatement si un marchand existe déjà

        # 3. Création du marchand
        new_trader = Trader(self.x, self.y, self.culture, self.config, self)
        world['entities'].add(new_trader)
        self.active_trader = new_trader
        # 4. Log unique
        GameLogger.log(
            Translator.translate(
                "events.trader_spawn",
                city_name=self.name
            )
        )
        return True

    def _can_world_support_new_settler(self, world):
        """
        Analyse globale pour savoir si le monde est saturé.
        Empêche la création de colons inutiles.
        """
        # 1. Compter les structures vivantes
        from entities.registry import STRUCTURE_TYPES
        from entities.constructs.ruins import Ruins

        existing_cities = [
            e for e in world['entities']
            if type(e) in STRUCTURE_TYPES and not e.is_expired
        ]

        # 2. Calcul de la capacité de charge (Carrying Capacity)
        # On estime qu'une ville a besoin d'un carré de 15x15 cases pour respirer (225 cases)
        total_area = world['width'] * world['height']
        max_cities = total_area // 225

        # 3. Seuil de saturation (ex: à 90% de la carte pleine, on arrête)
        if len(existing_cities) >= max_cities * 0.9:
            return False

        # 4. Vérification des colons déjà en route (pas plus de 3 colons mondiaux simultanés)
        from entities.species.human.settler import Settler
        active_settlers = [e for e in world['entities'] if isinstance(e, Settler) and not e.is_expired]
        if len(active_settlers) > 3:
            return False

        return True
    # Dans settler.py

    def think(self, world):
        if self.is_expired: return
        self.distance_traveled += 1

        # Recherche d'une ruine dans le radar (perception_range)
        nearby_ruins = [
            e for e in world['entities']
            if isinstance(e, Ruins) and not e.is_expired and math.dist(self.pos, e.pos) < self.perception_range
        ]

        if nearby_ruins:
            # On cible la ruine la plus proche
            target_ruin = min(nearby_ruins, key=lambda r: math.dist(self.pos, r.pos))
            self._move_towards(target_ruin.pos, world)

            # Si on est sur la ruine, on la repopule
            if math.dist(self.pos, target_ruin.pos) < 1.0:
                self._restore_ruin(target_ruin, world)
        else:
            # Comportement normal si aucune ruine n'est proche
            super().think(world) # Ou ta logique de mouvement habituelle