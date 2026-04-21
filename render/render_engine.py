import sys
from .ui_header import render_header
from .ui_map import render_map, radial_reveal
from .ui_logs import render_logs
from .ui_bestiary import render_bestiary

class RenderEngine:
    """
    Coordinates the terminal-based visual output of the simulation.
    Manages the sequence of rendering the header, the map, and the event logs.
    """
    def __init__(self, width, height, config):
        self.width = width
        self.height = height
        self.config = config

    def draw_frame(self, world_data, stats, reveal=False):
        """
        Coordinates the complete display of a single simulation frame.

        Args:
            world_data (dict): The current state of the world (elevation, entities, etc.)
            stats (dict): Global simulation statistics and logs.
            reveal (bool): If True, triggers the radial discovery animation.
        """
        if reveal:
            radial_reveal(self, world_data, stats)
            return

        # 1. Reset cursor to home position
        # Using ANSI escape code \033[H to avoid flickering by overwriting the frame
        sys.stdout.write("\033[H")

        # 2. Header (Statistics and world info)
        render_header(self.width, world_data, stats, self.config)

        # 3. Map (The core visual representation)
        render_map(self.width, self.height, world_data, self.config)

        # 4. Logs (The latest event messages)
        render_logs(self.width, stats)

        # Finalize the frame output
        sys.stdout.flush()

    def draw_bestiary(self, world_data, bestiary_state):
        render_bestiary(self.width, self.height, world_data, self.config, bestiary_state)