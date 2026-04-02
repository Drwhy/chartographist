from core.random_service import RandomService

class NameGenerator:
    """
    Service responsible for procedural generation of names based on cultural data.
    Handles both character and settlement naming conventions.
    """

    @staticmethod
    def generate_person_name(culture_data):
        """
        Generates a character name by combining a cultural prefix and personal suffix.
        Example: 'Valer' + 'ius' -> 'Valerius'
        """
        prefixes = culture_data["naming"]["prefixes"]
        suffixes = culture_data["naming"]["suffixes_person"]

        prefix = RandomService.choice(prefixes)
        suffix = RandomService.choice(suffixes)

        # Handle cases where suffixes might start with a space or hyphen
        return f"{prefix}{suffix}".strip()

    @staticmethod
    def generate_first_name(culture_data):
        """
        Generates a character name by combining a cultural prefix and personal suffix.
        Example: 'Valer' + 'ius' -> 'Valerius'
        """
        prefixes = culture_data["naming"]["prefixes"]
        prefix = RandomService.choice(prefixes)

        # Handle cases where suffixes might start with a space or hyphen
        return f"{prefix}".strip()

    @staticmethod
    def generate_place_name(culture_data):
        """
        Generates a settlement or geographic name.
        Uses cultural prefixes and place-specific suffixes.
        Example: 'August' + 'ia' -> 'Augustia'
        """
        prefixes = culture_data["naming"]["prefixes"]
        suffixes = culture_data["naming"]["suffixes_place"]

        prefix = RandomService.choice(prefixes)
        suffix = RandomService.choice(suffixes)

        # Concatenate and ensure proper capitalization (e.g., 'al-Din' remains correct)
        full_name = f"{prefix}{suffix}"

        # If the suffix starts with a space, we don't want to capitalize the middle
        if suffix.startswith(" "):
            return full_name.strip()

        return full_name.capitalize().strip()