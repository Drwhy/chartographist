import math
from .base import Human
from core.logger import GameLogger
from entities.constructs.village import Village
from history.history_engine import connect_with_road
from entities.registry import register_civ
from core.random_service import RandomService
from entities.registry import STRUCTURE_TYPES
from core.translator import Translator

@register_civ
class Settler(Human):
    def __init__(self, x, y, culture, config, home_city=None):
        # Respect de l'ordre strict des paramètres de Actor
        super().__init__(x, y, culture, config,1)
        self.char = culture.get("settler_emoji", "🚶")
        self.home_city = home_city
        self.distance_traveled = 0
        self.min_distance_from_home = 20
        self.max_travel_time = 120
        # Paramètres de survie
        self.fear_sensitivity = 4.0  # Très prudent : porte l'avenir de sa cité
        self.perception_range = 10
    def think(self, world):
            """Phase de réflexion : le colon cherche-t-il un spot ou fuit-il ?"""
            if self.is_expired: return

            # Le colon n'a pas de "target" fixe, son but est le meilleur score local
            self.distance_traveled += 1

            # Si trop vieux ou perdu dans une zone stérile
            if self.distance_traveled > self.max_travel_time:
                self.is_expired = True
                GameLogger.log(Translator.translate("events.settler_lost", settler_city_name=self.home_city.name))

    def perform_action(self, world):
        """Phase de mouvement et de fondation."""
        # 1. Tentative de fondation si on est assez loin
        if self.distance_traveled > self.min_distance_from_home:
            if self._is_ideal_spot(world):
                self._found_village(world)
                return

        # 2. Déplacement intelligent (Heatmap)
        self._move_smart(world)

    def _move_smart(self, world):
        """Se déplace en maximisant la sécurité, le potentiel et l'éloignement social."""
        possible_moves = self._get_accessible_neighbors(world)
        if not possible_moves: return

        scored_moves = []
        for nx, ny in possible_moves:
            # 1. Facteurs classiques (Fear, Scent, Géo)
            fear = world['influence'].get_fear(nx, ny)
            scent = world['influence'].get_scent(nx, ny)
            h = world['elev'][ny][nx]
            is_river = world['riv'][ny][nx] > 0
            geo_score = (0.5 if is_river else 0) + (0.3 if 0.2 < h < 0.6 else 0)

            # 2. REPULSION SOCIALE (La "Communication")
            # On calcule la gêne causée par les structures existantes
            social_repulsion = 0
            for e in world['entities']:
                if type(e) in STRUCTURE_TYPES and not e.is_expired:
                    dist = math.dist((nx, ny), e.pos)
                    # Si on est trop près d'une ville (moins de 15 cases),
                    # on génère une pénalité forte pour pousser le colon à partir
                    if dist < 15:
                        social_repulsion += (15 - dist) * 0.5
                if isinstance(e, Settler) and e != self:
                    if math.dist((nx, ny), e.pos) < 5:
                        social_repulsion += 2.0

            # 3. SCORE FINAL
            # Le social_repulsion est soustrait pour que le colon fuit les zones encombrées
            score = (fear * self.fear_sensitivity) + (scent * 1.5) + geo_score - social_repulsion

            # Biais d'exploration : plus il voyage, plus il est poussé à s'éloigner de sa source
            dist_to_home = math.dist((nx, ny), self.home_city.pos) if self.home_city else 0
            exploration_push = (dist_to_home / 50) # On augmente l'influence de l'éloignement

            scored_moves.append(((nx, ny), score + exploration_push + RandomService.random() * 0.1))

        self.pos = max(scored_moves, key=lambda m: m[1])[0]

    def _is_ideal_spot(self, world):
        """Critères de fondation utilisant les données du monde."""
        h = world['elev'][self.y][self.x]

        # Trop près d'un danger immédiat ?
        if world['influence'].get_fear(self.x, self.y) < -1.0:
            return False

        # Trop près d'une autre ville ?
        for e in world['entities']:
            if type(e) in STRUCTURE_TYPES and not e.is_expired:
                if math.dist(self.pos, e.pos) < 10: # Distance de voisinage
                    return False

        # Bonus rivière
        is_near_river = world['riv'][self.y][self.x] > 0
        chance = 0.35 if is_near_river else 0.10

        return RandomService.random() < chance

    def _is_ideal_spot(self, world):
        """
        Détermine si la case est valide pour fonder un village.
        Critères : Pas d'eau, pas de sommets, pas de voisinage urbain trop proche.
        """
        h = world['elev'][self.y][self.x]

        # 1. RÈGLES GÉOGRAPHIQUES (0 = Plage, 0.85 = Haute montagne)
        if not (0 <= h <= 0.85):
            return False

        # 2. VÉRIFICATION DU VOISINAGE (Registry & Proximité)
        for e in world['entities']:
            if e.is_expired: continue

            # Empêche de spawner deux entités exactement au même endroit
            if e.pos == self.pos and e != self:
                return False

            # RÈGLE DE DISTANCE : Pas d'autre structure dans un rayon de 8
            if type(e) in STRUCTURE_TYPES:
                if math.dist(self.pos, e.pos) < 8:
                    return False

        # 3. PROBABILITÉ DE FONDATION
        # Une rivière (riv > 0) rend le terrain beaucoup plus attractif
        is_near_river = world['riv'][self.y][self.x] > 0
        chance = 0.25 if is_near_river else 0.08

        return RandomService.random() < chance

    def _found_village(self, world):
        """Crée le village et trace la route vers la cité mère."""
        new_village = Village(self.x, self.y, self.culture, self.config)
        world['entities'].add(new_village)

        if self.home_city:
            connect_with_road(
                world['road'],
                self.home_city.pos,
                self.pos,
                world['width'],
                world['height']
            )
            GameLogger.log(Translator.translate("events.settler_found_village", new_village_char=new_village.char, new_village_name=new_village.name, home_city_name=self.home_city.name))
        else:
            GameLogger.log(Translator.translate("events.settler_found_village_independant", new_village_char=new_village.char, new_village_name=new_village.name))

        self.is_expired = True