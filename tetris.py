import random

from settings import BOARD_HEIGHT, BOARD_WIDTH, SHAPES, SHAPES_COLORS


class Tetromino:
    def __init__(self):
        self.type = random.choice(list(SHAPES.keys()))
        self.color = SHAPES_COLORS[self.type]
        self.rotation = 0
        self.x = BOARD_WIDTH // 2 - 2
        self.y = 0
        self.shape = self.get_current_shape()

    def get_current_shape(self):
        shapes = SHAPES[self.type]
        return shapes[self.rotation % len(shapes)]

    def rotate(self, direction=1):
        self.rotation += direction
        self.shape = self.get_current_shape()

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def get_blocks(self):
        return [(self.x + bx, self.y + by) for bx, by in self.shape]


class Board:
    def __init__(self):
        self.grid = [[None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]

    def is_valid_move(self, tetromino, dx=0, dy=0, rotation=None):
        # Temporary tetromino for rotation check
        temp_tetro = Tetromino()
        temp_tetro.type = tetromino.type
        temp_tetro.color = tetromino.color
        temp_tetro.x = tetromino.x + dx
        temp_tetro.y = tetromino.y + dy

        if rotation is not None:
            temp_tetro.rotation = rotation
            temp_tetro.shape = temp_tetro.get_current_shape()
        else:
            temp_tetro.shape = tetromino.shape

        for x, y in temp_tetro.get_blocks():
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def lock_tetromino(self, tetromino):
        for x, y in tetromino.get_blocks():
            if y >= 0:
                self.grid[y][x] = tetromino.color
        return self.clear_lines()

    def apply_handicap(self, level):
        if level == 0:
            return

        import random
        from settings import GRAY

        num_rows = level * 2
        # We apply handicap to the bottom rows
        for y in range(BOARD_HEIGHT - 1, max(0, BOARD_HEIGHT - 1 - num_rows), -1):
            # Fill some random cells (e.g., 3 to 7 blocks)
            # Ensure it's "incomplete" so it doesn't clear immediately
            fill_count = random.randint(3, 7)
            cells = random.sample(range(BOARD_WIDTH), fill_count)
            for x in cells:
                self.grid[y][x] = GRAY

    def clear_lines(self):
        cleared_rows_data = []
        for y in range(BOARD_HEIGHT):
            if all(self.grid[y][x] is not None for x in range(BOARD_WIDTH)):
                cleared_rows_data.append((y, list(self.grid[y])))

        lines_cleared = len(cleared_rows_data)
        if lines_cleared > 0:
            # Garder seulement les lignes qui ne sont pas complètes
            new_grid = [
                row for row in self.grid if not all(cell is not None for cell in row)
            ]
            # Ajouter des lignes vides en haut pour compenser
            for _ in range(lines_cleared):
                new_grid.insert(0, [None for _ in range(BOARD_WIDTH)])
            self.grid = new_grid

        return lines_cleared, cleared_rows_data
