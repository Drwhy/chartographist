import random

class RandomService:
    _instance = None
    _rng = None

    @classmethod
    def initialize(cls, seed):
        """Initialise le générateur unique avec la seed."""
        cls._rng = random.Random(seed)
        cls._instance = cls

    @classmethod
    def get_rng(cls):
        """Récupère l'instance du générateur."""
        if cls._rng is None:
            # Fallback de sécurité si on oublie l'init
            cls.initialize(RandomService.randint(0, 999999))
        return cls._rng

    # Raccourcis pour les fonctions les plus utilisées
    @classmethod
    def random(cls): return cls._rng.random()

    @classmethod
    def randint(cls, a, b): return cls._rng.randint(a, b)

    @classmethod
    def choice(cls, seq): return cls._rng.choice(seq)

    @classmethod
    def uniform(cls, a, b): return cls._rng.uniform(a, b)

    @classmethod
    def sample(cls, a, b): return cls._rng.sample(a, b)