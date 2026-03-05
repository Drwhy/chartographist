import math

class InfluenceSystem:
    def __init__(self, width, height, config):
        self.width = width
        self.height = height
        # On utilise une grille de zéros
        # Couche de PEUR (négative uniquement)
        self.fear_grid = [[0.0 for _ in range(width)] for _ in range(height)]
        # Couche d'ATTRACTION (positive uniquement)
        self.scent_grid = [[0.0 for _ in range(width)] for _ in range(height)]
        # Taux de dissipation (0.95 = 5% de perte par tour)
        self.decay = config.get('influence_decay', 0.95)

    def update(self):
        """Fait s'évaporer l'influence sur toute la carte."""
        for y in range(self.height):
            for x in range(self.width):
                self.fear_grid[y][x] *= 0.9
                self.scent_grid[y][x] *= 0.9

    def add_influence(self, x, y, value, radius=1):
        """
        Dépose une empreinte soit dans la grille de peur, soit dans celle d'attraction.
        L'atténuation est linéaire par rapport à la distance.
        """
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy

                if 0 <= nx < self.width and 0 <= ny < self.height:
                    dist = math.sqrt(dx**2 + dy**2)
                    if dist <= radius:
                        # Calcul de l'impact selon la distance (linéaire)
                        impact = value * (1 - (dist / (radius + 1)))

                        if value < 0:
                            # --- GESTION DE LA PEUR ---
                            # On utilise min() pour que le danger le plus extrême (le plus bas)
                            # soit TOUJOURS prioritaire et ne soit jamais dilué.
                            current_fear = self.fear_grid[ny][nx]
                            self.fear_grid[ny][nx] = min(current_fear, impact)
                        else:
                            # --- GESTION DE L'ATTRACTION ---
                            # On cumule les odeurs (plusieurs fleurs = plus d'odeur)
                            # mais on peut plafonner pour éviter l'infini.
                            current_scent = self.scent_grid[ny][nx]
                            self.scent_grid[ny][nx] = max(current_scent, current_scent + impact)

    def get_fear(self, x, y):
        """Récupère la valeur d'influence à une coordonnée donnée."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.fear_grid[y][x]
        return 0.0
    def get_scent(self, x, y):
        """Récupère la valeur d'influence à une coordonnée donnée."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.scent_grid[y][x]
        return 0.0