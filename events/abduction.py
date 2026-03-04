from .event_registry import register_event
from .base_event import BaseEvent
from core.random_service import RandomService
from core.logger import GameLogger
from core.translator import Translator
from core.entities import Z_EFFECT
import math
from entities.registry import CIV_UNITS
from entities.special.ufo import UFO

@register_event
class Abduction(BaseEvent):
    name = "Abduction"
    chance = 0.5

    def condition(self, world, stats):
        """Vérifie les cibles valides ET l'absence d'autre UFO."""
        # 1. Y a-t-il des humains à enlever ?
        has_targets = any(type(e) in CIV_UNITS for e in world['entities'] if not e.is_expired)

        # 2. Y a-t-il déjà un UFO actif sur la carte ?
        # On utilise isinstance pour être robuste
        no_ufo_present = not any(isinstance(e, UFO) for e in world['entities'] if not e.is_expired)

        return has_targets and no_ufo_present

    def trigger(self, world, stats, config):
        """Lance l'apparition de l'UFO si la chance sourit (ou pas)."""
        # --- LE FIX : On vérifie la probabilité ici ---
        if RandomService.random() > self.chance:
            return

        # 1. Détermination du point d'entrée (Bord haut de la carte)
        spawn_x = RandomService.randint(0, world['width'] - 1)
        spawn_y = 0

        # 2. Création de l'entité UFO
        # On passe un dictionnaire minimal pour species_data
        ufo = UFO(
            spawn_x,
            spawn_y,
            config['special']['ufo'],
            Z_EFFECT
        )

        # 3. Ajout au monde
        world['entities'].add(ufo)

        # Optionnel : Un petit log mystérieux pour le joueur attentif
        # GameLogger.log("✨ Des lumières étranges ont été aperçues dans le ciel...")
