class Human:
    def __init__(self, start_pos, culture_dict):
        self.pos = list(start_pos)
        self.culture = culture_dict
        self.dead = False

    def move_towards(self, target):
        tx, ty = target
        cx, cy = self.pos

        dx = 1 if tx > cx else -1 if tx < cx else 0
        dy = 1 if ty > cy else -1 if ty < cy else 0

        self.pos[0] += dx
        self.pos[1] += dy

    @property
    def current_pos(self):
        return tuple(self.pos)