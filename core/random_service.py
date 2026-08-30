import hashlib
import random

class RandomService:
    """
    Centralized random number generator service.
    Ensures deterministic behavior across the simulation using a single seeded instance.
    """
    _instance = None
    _rng = None
    _seed = None
    _streams = {}

    @classmethod
    def initialize(cls, seed):
        """
        Initializes the unique generator with a specific seed.
        Essential for world persistence and reproducibility.
        """
        cls._seed = seed
        cls._rng = random.Random(seed)
        cls._streams = {}
        cls._instance = cls

    @classmethod
    def get_rng(cls, stream=None):
        """
        Retrieves the generator instance.
        Provides a safety fallback initialization if the service wasn't seeded.
        """
        if cls._rng is None:
            # Security fallback using the standard random module for the initial seed
            cls.initialize(random.randint(0, 999999))
        if stream is None:
            return cls._rng
        stream_name = str(stream)
        if stream_name not in cls._streams:
            seed_material = (
                f"{type(cls._seed).__name__}:{cls._seed}:{stream_name}"
            ).encode("utf-8")
            stream_seed = int.from_bytes(
                hashlib.sha256(seed_material).digest(), "big"
            )
            cls._streams[stream_name] = random.Random(stream_seed)
        return cls._streams[stream_name]

    @classmethod
    def get_state(cls):
        """Returns the serializable state of the deterministic generator."""
        return cls.get_rng().getstate()

    @classmethod
    def get_seed(cls):
        """Returns the seed used to derive deterministic named streams."""
        return cls._seed

    @classmethod
    def set_state(cls, state, seed=None):
        """Restores a previously captured deterministic generator state."""
        rng = random.Random()
        rng.setstate(state)
        cls._rng = rng
        if seed is not None:
            cls._seed = seed
        cls._instance = cls

    @classmethod
    def get_stream_states(cls):
        """Returns serializable states for all initialized named streams."""
        return {
            name: rng.getstate()
            for name, rng in sorted(cls._streams.items())
        }

    @classmethod
    def set_stream_states(cls, states):
        """Restores named streams, accepting missing state from legacy saves."""
        cls._streams = {}
        for name, state in (states or {}).items():
            rng = random.Random()
            rng.setstate(state)
            cls._streams[str(name)] = rng

    # Helper shortcuts for the most frequently used random operations
    @classmethod
    def random(cls, stream=None):
        """Returns a random float between 0.0 and 1.0."""
        return cls.get_rng(stream).random()

    @classmethod
    def randint(cls, a, b, stream=None):
        """Returns a random integer between a and b (inclusive)."""
        return cls.get_rng(stream).randint(a, b)

    @classmethod
    def choice(cls, seq, stream=None):
        """Returns a random element from a non-empty sequence."""
        return cls.get_rng(stream).choice(seq)

    @classmethod
    def uniform(cls, a, b, stream=None):
        """Returns a random float between a and b."""
        return cls.get_rng(stream).uniform(a, b)

    @classmethod
    def sample(cls, population, k, stream=None):
        """Returns a k-length list of unique elements chosen from the population."""
        return cls.get_rng(stream).sample(population, k)

    @classmethod
    def shuffle(cls, seq, stream=None):
        """Returns a random element from a non-empty sequence."""
        return cls.get_rng(stream).shuffle(seq)
