"""
Package History : Gestion de l'évolution des civilisations et des événements mondiaux.
Expose le moteur principal via la fonction evolve_world.
"""

from .history_engine import evolve_world

# On peut aussi exposer les registres d'événements si besoin de debug
from .events import RANDOM_EVENTS
from .civilizations import seed_civilization