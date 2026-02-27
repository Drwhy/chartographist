import sys
from .ui_header import render_header
from .ui_map import render_map, radial_reveal
from .ui_logs import render_logs

class RenderEngine:
    def __init__(self, width, height, config):
        self.width = width
        self.height = height
        self.config = config

    def draw_frame(self, world_data, stats, reveal=False):
        """Coordonne l'affichage complet de la frame."""
        if reveal:
            radial_reveal(self, world_data, stats)
            return

        # 1. Reset curseur et nettoyage écran
        sys.stdout.write("\033[H")

        # 2. Entête (Stats)
        render_header(self.width, world_data, stats, self.config)

        # 3. Carte (Le coeur du rendu)
        render_map(self.width, self.height, world_data, self.config)

        # 4. Logs (Les derniers messages)
        render_logs(self.width, stats)

        sys.stdout.flush()