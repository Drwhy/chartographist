from entities.registry import register_civ, STRUCTURE_TYPES
from entities.constructs.ruins import Ruins
from core.logger import GameLogger
from core.translator import Translator
from core.random_service import RandomService
from .base import Human
import math

@register_civ
class Trader(Human):
    def __init__(self, x, y, culture, config, home_city):
        # Le marchand est rapide (1.2) car il utilise souvent des bêtes de somme
        super().__init__(x, y, culture, config, 1.2)
        self.home_city = home_city
        self.target_city = None
        self.inventory = 0
        self.max_capacity = 50
        self.char = culture.get("trader_emoji", "⚖️")

        self.fear_sensitivity = 5.0  # Très peureux, il transporte des richesses !
        self.perception_range = 15

    def think(self, world):
        """Décide de la prochaine destination commerciale."""
        if self.is_expired: return

        # Si pas de ville cible, on en cherche une autre que la nôtre
        if not self.target_city or self.target_city.is_expired:
            self._find_trading_partner(world)

    def perform_action(self, world):
        """Se déplace entre les cités ou effectue l'échange."""
        if not self.target_city:
            self._wander_on_roads(world)
            return

        dist = math.dist(self.pos, self.target_city.pos)

        if dist < 1.5: # Arrivé à destination
            self._trade_and_swap(world)
        else:
            self._move_smart_on_roads(world)

    def _find_trading_partner(self, world):
        """Cherche une ville partenaire avec un biais pour la proximité, mais autorise l'aventure."""
        cities = [
            e for e in world['entities']
            if type(e) in STRUCTURE_TYPES
            and e != self.home_city
            and not e.is_expired
            and not isinstance(e, Ruins)
            and getattr(e, 'population', 0) > 0
        ]

        if not cities:
            self.target_city = None
            return

        # 1. On calcule les scores de chaque ville (Inverse de la distance)
        scored_cities = []
        for city in cities:
            dist = math.dist(self.pos, city.pos)
            # On évite la division par zéro et on donne un poids (ex: 1/dist)
            # Plus dist est grand, plus score est petit
            score = 1.0 / (dist + 1.0)

            # Optionnel : On booste le score si la ville est très peuplée
            # score *= (city.population / 100.0)

            scored_cities.append((city, score))

        # 2. Sélection pondérée (weighted choice)
        # On utilise le RandomService pour choisir selon les poids
        total_score = sum(s for _, s in scored_cities)
        pick = RandomService.random() * total_score
        current = 0

        for city, score in scored_cities:
            current += score
            if current >= pick:
                self.target_city = city
                break

    def _move_smart_on_roads(self, world):
        """
        Déplacement privilégiant les routes (vitesse) et évitant le danger.
        """
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        best_move = self.pos
        max_score = -float('inf')

        for nx, ny in possible_moves:
            # 1. Calcul de la distance vers la cible
            dist_score = 1 - (math.dist((nx, ny), self.target_city.pos) / 100)

            # 2. Bonus de route (un marchand préfère rester sur le pavé)
            road_bonus = 0.5 if world['road'][ny][nx] != "  " else 0

            # 3. Facteur de peur (Heatmap)
            fear = world['influence'].get_fear(nx, ny)

            score = dist_score + road_bonus + (fear * self.fear_sensitivity)

            if score > max_score:
                max_score = score
                best_move = (nx, ny)

        self.pos = best_move

    def _trade_and_swap(self, world):
        """Simule un échange commercial et change de destination."""
        """Gère l'échange et la propagation de la peste."""
        # 1. TRANSMISSION : Ville -> Marchand
        # On vérifie si la cité actuelle est infectée (via un attribut ou une influence)
        city_is_plagued = getattr(self.target_city, 'is_infected', False)
        if city_is_plagued and not self.is_infected:
            if RandomService.random() < 0.3: # 30% de chance d'attraper la peste
                self.is_infected = True
        # 2. TRANSMISSION : Marchand -> Ville
        elif self.is_infected and not city_is_plagued:
            if RandomService.random() < 0.5: # 50% de chance d'infecter la ville
                self.target_city.has_plague = True
                GameLogger.log(
                    Translator.translate("events.epidemic_spread", merchant_name=self.name, city_name=self.target_city.name)
                )
        # On booste la population/richesse de la ville visitée
        self.target_city.population += 2
        GameLogger.log(
            Translator.translate(
                "events.trade_success",
                home_city=self.home_city.name,
                target_city=self.target_city.name,
                bonus=2
            )
        )
        # On inverse : l'ancienne cible devient le nouveau foyer et vice-versa
        old_home = self.home_city
        self.home_city = self.target_city
        self.target_city = old_home

    def _wander_on_roads(self, world):
        """Erre le long des routes si aucune ville n'est trouvée."""
        # Logique de wander classique avec bonus pour les cases road != "  "
        pass