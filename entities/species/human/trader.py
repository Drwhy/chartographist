from core.discovery_service import DiscoveryService
from core.logger import GameLogger
from core.translator import Translator
from core.random_service import RandomService
from entities.registry import register_civ, STRUCTURE_TYPES
from entities.constructs.ruins import Ruins
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
        self.visited_cities = [] # Mémoire à court terme
        self.max_memory = 3
        self.fear_sensitivity = 5.0  # Très peureux, il transporte des richesses !
        self.perception_range = 15

    def think(self, world):
        """Décide de la prochaine destination commerciale."""
        if self.is_expired: return

        # Si pas de ville cible, on en cherche une autre que la nôtre
        if not self.target_city or self.target_city.is_expired:
            self._select_next_destination(world)

    def perform_action(self, world):
        """Se déplace entre les cités ou effectue l'échange."""
        if not self.target_city:
            self._wander_on_roads(world)
            return

        dist = math.dist(self.pos, self.target_city.pos)

        if dist < 1: # Arrivé à destination
            self._trade_and_swap(world)
        else:
            self._move_smart_on_roads(world)

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
        """Appelé quand le marchand arrive à destination."""
        # 1. Logique de commerce (gain de pop, etc.)
        # ... ton code existant ...

        # 2. Mise à jour de la mémoire
        self.visited_cities.append(self.target_city)
        if len(self.visited_cities) > self.max_memory:
            self.visited_cities.pop(0) # On oublie la plus ancienne

        # 3. On choisit la suite de la tournée
        self._select_next_destination(world)
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
        """
        Erre le long des routes si aucune ville n'est trouvée.
        Privilégie les cases avec des routes pour rester sur les axes commerciaux.
        """
        # 1. Récupération des voisins accessibles via la classe parente (Human/Entity)
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves:
            return

        scored_moves = []
        for nx, ny in possible_moves:
            # Score de base aléatoire pour éviter les mouvements de va-et-vient parfaits
            score = RandomService.random() * 0.2

            # 2. Bonus de Route : Si la case contient une route, on booste massivement le score
            # On suppose que world['road'] contient "  " pour le vide et un symbole sinon
            is_road = world['road'][ny][nx] != "  "
            if is_road:
                score += 2.0  # Poids fort pour rester sur le pavé

            # 3. Évitement du danger (Heatmap de peur)
            fear = world['influence'].get_fear(nx, ny)
            score += (fear * self.fear_sensitivity)

            scored_moves.append(((nx, ny), score))

        # 4. On choisit le mouvement avec le meilleur score
        if scored_moves:
            self.pos = max(scored_moves, key=lambda m: m[1])[0]
    def _select_next_destination(self, world):
        """Le marchand consulte le registre des cités pour planifier sa tournée."""

        # 1. Accès au savoir partagé via le service
        all_cities = DiscoveryService.get_known_settlements(world)

        # 2. Filtrage par mémoire (ne pas revenir sur ses pas immédiatement)
        # On exclut la ville actuelle et les X dernières villes visitées
        possible_targets = [
            c for c in all_cities
            if c != self.target_city and c not in self.visited_cities
        ]

        if not possible_targets:
            # Si tout a été visité ou si le monde est vide, on rentre à la maison
            self.visited_cities.clear()
            self.target_city = self.home_city
            return
        # Pondération par distance et opportunité (Population)
        scored_targets = []
        for city in possible_targets:
            dist = math.dist(self.pos, city.pos)
            # Plus c'est proche, mieux c'est, mais on favorise les grandes villes
            score = (city.population / 100) / (dist + 1)
            scored_targets.append((city, score))

        # Sélection par roulette pour garder de l'imprévisibilité
        total = sum(s for _, s in scored_targets)
        pick = RandomService.random() * total
        current = 0
        for city, score in scored_targets:
            current += score
            if current >= pick:
                self.target_city = city
                break