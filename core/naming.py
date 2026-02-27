from core.random_service import RandomService

class NameGenerator:
    @staticmethod
    def generate_person_name(culture_data):
        pre = RandomService.choice(culture_data["naming"]["prefixes"])
        suf = RandomService.choice(culture_data["naming"]["suffixes_person"])
        return f"{pre}{suf}"

    @staticmethod
    def generate_place_name(culture_data):
        pre = RandomService.choice(culture_data["naming"]["prefixes"])
        suf = RandomService.choice(culture_data["naming"]["suffixes_place"])
        # On peut ajouter une petite variation pour les grandes villes
        return f"{pre}{suf}".capitalize()