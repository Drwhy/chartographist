import random

class RandomService:
    """
    Centralized random number generator service.
    Ensures deterministic behavior across the simulation using a single seeded instance.
    """
    _instance = None
    _rng = None

    @classmethod
    def initialize(cls, seed):
        """
        Initializes the unique generator with a specific seed.
        Essential for world persistence and reproducibility.
        """
        cls._rng = random.Random(seed)
        cls._instance = cls

    @classmethod
    def get_rng(cls):
        """
        Retrieves the generator instance.
        Provides a safety fallback initialization if the service wasn't seeded.
        """
        if cls._rng is None:
            # Security fallback using the standard random module for the initial seed
            cls.initialize(random.randint(0, 999999))
        return cls._rng

    # Helper shortcuts for the most frequently used random operations
    @classmethod
    def random(cls):
        """Returns a random float between 0.0 and 1.0."""
        return cls.get_rng().random()

    @classmethod
    def randint(cls, a, b):
        """Returns a random integer between a and b (inclusive)."""
        return cls.get_rng().randint(a, b)

    @classmethod
    def choice(cls, seq):
        """Returns a random element from a non-empty sequence."""
        return cls.get_rng().choice(seq)

    @classmethod
    def uniform(cls, a, b):
        """Returns a random float between a and b."""
        return cls.get_rng().uniform(a, b)

    @classmethod
    def sample(cls, population, k):
        """Returns a k-length list of unique elements chosen from the population."""
        return cls.get_rng().sample(population, k)

    @classmethod
    def shuffle(cls, seq):
        """Returns a random element from a non-empty sequence."""
        return cls.get_rng().shuffle(seq)