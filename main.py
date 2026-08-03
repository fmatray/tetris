import os
import sys
import random
import numpy as np

import pygame
from settings import (
    BLACK,
    BLOCK_SIZE,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    GRAY,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
)
from tetris import Board, Tetromino


def generate_melody(notes):
    sample_rate = 44100
    full_buf = []

    for freq, duration in notes:
        n_samples = int(sample_rate * duration)
        # Generate sine wave
        buf = np.zeros((n_samples, 2), dtype=np.int16)
        for i in range(n_samples):
            # Simple envelope to avoid clicking (linear fade in/out)
            envelope = 1.0
            if i < 100:
                envelope = i / 100
            if i > n_samples - 100:
                envelope = (n_samples - i) / 100

            val = int(32767 * np.sin(2 * np.pi * freq * i / sample_rate) * envelope)
            buf[i][0] = val
            buf[i][1] = val
        full_buf.append(buf)

    combined_buf = np.concatenate(full_buf, axis=0)
    return pygame.sndarray.make_sound(combined_buf)


def draw_grid(screen, board):
    # Draw the board background and grid lines
    for y in range(BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            rect = pygame.Rect(
                x * BLOCK_SIZE + 250, y * BLOCK_SIZE + 50, BLOCK_SIZE, BLOCK_SIZE
            )
            pygame.draw.rect(screen, GRAY, rect, 1)

    # Draw locked blocks
    for y in range(BOARD_HEIGHT):
        for x in range(BOARD_WIDTH):
            if board.grid[y][x]:
                rect = pygame.Rect(
                    x * BLOCK_SIZE + 250, y * BLOCK_SIZE + 50, BLOCK_SIZE, BLOCK_SIZE
                )
                pygame.draw.rect(screen, board.grid[y][x], rect)


def draw_tetromino(screen, tetromino):
    for x, y in tetromino.get_blocks():
        if y >= 0:
            rect = pygame.Rect(
                x * BLOCK_SIZE + 250, y * BLOCK_SIZE + 50, BLOCK_SIZE, BLOCK_SIZE
            )
            pygame.draw.rect(screen, tetromino.color, rect)


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        # Spread wider and go higher
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-7, -2)
        self.life = random.uniform(1.0, 2.0)
        self.decay = random.uniform(0.003, 0.01)
        self.size = random.randint(2, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.05  # Even lighter gravity for a floating effect
        self.vx *= 0.97  # Friction
        self.life -= self.decay

    def draw(self, screen):
        if self.life > 0:
            # Dynamic size and fading color (approaching black)
            current_size = max(1, int(self.size * self.life))
            color_fade = [max(0, min(255, int(c * self.life))) for c in self.color]
            rect = pygame.Rect(self.x, self.y, current_size, current_size)
            pygame.draw.rect(screen, color_fade, rect)


def load_leaderboard():
    if not os.path.exists("leaderboard.txt"):
        return []
    with open("leaderboard.txt", "r") as f:
        scores = []
        for line in f:
            if ":" in line:
                name, score = line.strip().split(":")
                scores.append((name, int(score)))
        return scores


def save_score(name, score):
    scores = load_leaderboard()
    scores.append((name, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    with open("leaderboard.txt", "w") as f:
        for n, s in scores[:10]:
            f.write(f"{n}:{s}\n")


def show_leaderboard_screen(screen, font):
    leaderboard_active = True
    scores = load_leaderboard()

    while leaderboard_active:
        screen.fill(BLACK)

        title_text = font.render("TOP 10 LEADERBOARD", True, WHITE)
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 50))

        for i, (name, score) in enumerate(scores[:10], 1):
            row_text = font.render(f"{i}. {name} : {score}", True, WHITE)
            screen.blit(
                row_text, (SCREEN_WIDTH // 2 - row_text.get_width() // 2, 120 + i * 40)
            )

        instr_text = font.render("Press any key to continue", True, GRAY)
        screen.blit(instr_text, (SCREEN_WIDTH // 2 - instr_text.get_width() // 2, 600))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                leaderboard_active = False

    return True


def show_start_menu(screen, font):
    handicap_level = 0
    sound_enabled = True
    menu_active = True

    while menu_active:
        screen.fill(BLACK)

        title_text = font.render("TETRIS", True, WHITE)
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 100))

        instr_text = font.render("Select Handicap Level (0-5)", True, GRAY)
        screen.blit(instr_text, (SCREEN_WIDTH // 2 - instr_text.get_width() // 2, 200))

        level_text = font.render(f"Current Level: {handicap_level}", True, WHITE)
        screen.blit(level_text, (SCREEN_WIDTH // 2 - level_text.get_width() // 2, 250))

        sound_text = font.render(
            f"Sound: {'ON' if sound_enabled else 'OFF'}", True, WHITE
        )
        screen.blit(sound_text, (SCREEN_WIDTH // 2 - sound_text.get_width() // 2, 300))

        ctrl_text = font.render(
            "LEFT/RIGHT: Level | S: Sound | ENTER: Start", True, GRAY
        )
        screen.blit(ctrl_text, (SCREEN_WIDTH // 2 - ctrl_text.get_width() // 2, 400))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    handicap_level = max(0, handicap_level - 1)
                elif event.key == pygame.K_RIGHT:
                    handicap_level = min(5, handicap_level + 1)
                elif event.key == pygame.K_s:
                    sound_enabled = not sound_enabled
                elif event.key == pygame.K_RETURN:
                    return handicap_level, sound_enabled
    return 0, True


def get_user_name(screen, font):
    name = ""
    input_active = True

    while input_active:
        screen.fill(BLACK)

        # Title and Prompt
        prompt_text = font.render("GAME OVER!", True, WHITE)
        screen.blit(
            prompt_text, (SCREEN_WIDTH // 2 - prompt_text.get_width() // 2, 150)
        )

        instr_text = font.render("Enter your name and press ENTER:", True, GRAY)
        screen.blit(instr_text, (SCREEN_WIDTH // 2 - instr_text.get_width() // 2, 200))

        # Input box
        input_rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, 250, 300, 50)
        pygame.draw.rect(screen, GRAY, input_rect, 2)

        # Current name text
        name_text = font.render(name, True, WHITE)
        screen.blit(name_text, (input_rect.x + 10, input_rect.y + 10))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if name.strip():
                        input_active = False
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                else:
                    if len(name) < 15:
                        name += event.unicode

    return name if name.strip() else "Anonyme"


def show_restart_menu(screen, font):
    menu_active = True
    while menu_active:
        screen.fill(BLACK)

        title_text = font.render("GAME OVER", True, WHITE)
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 150))

        restart_text = font.render("Press 'R' to Restart", True, GRAY)
        screen.blit(
            restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, 220)
        )

        quit_text = font.render("Press 'Q' to Quit", True, GRAY)
        screen.blit(quit_text, (SCREEN_WIDTH // 2 - quit_text.get_width() // 2, 280))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return True
                if event.key == pygame.K_q:
                    return False
    return False


def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Tetris Python")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 32)

    # Generate epic melodic sounds for line clear
    line_sounds = {
        1: generate_melody(
            [
                (261.63, 0.08),  # C4
                (392.00, 0.08),  # G4
                (523.25, 0.2),  # C5
            ]
        ),
        2: generate_melody(
            [
                (261.63, 0.06),  # C4
                (392.00, 0.06),  # G4
                (261.63, 0.06),  # C4
                (392.00, 0.06),  # G4
                (523.25, 0.2),  # C5
            ]
        ),
        3: generate_melody(
            [
                (261.63, 0.06),  # C4
                (329.63, 0.06),  # E4
                (392.00, 0.06),  # G4
                (493.88, 0.06),  # B4
                (523.25, 0.3),  # C5
            ]
        ),
        4: generate_melody(
            [
                (261.63, 0.05),  # C4
                (523.25, 0.05),  # C5
                (783.99, 0.05),  # G5
                (1046.50, 0.4),  # C6 (The Climax!)
            ]
        ),
    }

    # Rotation sounds
    rotate_cw_sound = generate_melody([(440.0, 0.05), (659.25, 0.05)])  # Quick rising
    rotate_ccw_sound = generate_melody([(659.25, 0.05), (440.0, 0.05)])  # Quick falling

    handicap_level, sound_enabled = show_start_menu(screen, font)

    while True:
        board = Board()
        board.apply_handicap(handicap_level)
        current_piece = Tetromino()
        next_piece = Tetromino()

        game_over = False
        score = 0
        total_lines = 0
        level = 0
        drop_time = 0
        base_drop_speed = 0.5  # Seconds
        soft_drop_speed = 0.05  # Faster fall when holding DOWN
        particles = []
        down_pressed_for_current_piece = False
        paused = False

        while not game_over:
            drop_time += clock.get_rawtime()
            clock.tick()

            # Calculate current drop speed based on level (2% faster per level)
            current_base_speed = base_drop_speed * (0.98**level)
            current_drop_speed = (
                soft_drop_speed
                if down_pressed_for_current_piece
                else current_base_speed
            )

            # Piece falling logic
            if not paused and drop_time / 1000 >= current_drop_speed:
                if board.is_valid_move(current_piece, dy=1):
                    current_piece.move(0, 1)
                else:
                    cleared_count, cleared_rows_data = board.lock_tetromino(
                        current_piece
                    )
                    total_lines += cleared_count
                    level = total_lines // 10

                    # Basic score: 100 points per line
                    # Bonus: 2 lines -> +20, 3 lines -> +50, 4 lines -> +100
                    bonuses = {1: 0, 2: 20, 3: 50, 4: 100}
                    bonus = bonuses.get(cleared_count, 0)
                    score += (cleared_count * 100) + bonus

                    # Play sound based on number of lines cleared
                    if sound_enabled and cleared_count in line_sounds:
                        line_sounds[cleared_count].play()

                    # Spectacular particles explosion
                    for row_idx, row_colors in cleared_rows_data:
                        for col_idx, color in enumerate(row_colors):
                            # Spawn massive amounts of particles for a spectacular effect
                            for _ in range(80):
                                particles.append(
                                    Particle(
                                        col_idx * BLOCK_SIZE + 250 + BLOCK_SIZE // 2,
                                        row_idx * BLOCK_SIZE + 50 + BLOCK_SIZE // 2,
                                        color,
                                    )
                                )

                    current_piece = next_piece
                    next_piece = Tetromino()
                    down_pressed_for_current_piece = (
                        False  # Reset soft drop for the new piece
                    )
                    if not board.is_valid_move(current_piece):
                        game_over = True
                drop_time = 0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_DOWN:
                        down_pressed_for_current_piece = True
                    elif event.key == pygame.K_LEFT and board.is_valid_move(
                        current_piece, dx=-1
                    ):
                        current_piece.move(-1, 0)
                    elif event.key == pygame.K_RIGHT and board.is_valid_move(
                        current_piece, dx=1
                    ):
                        current_piece.move(1, 0)
                    elif event.key == pygame.K_UP:
                        # Rotation logic (Clockwise)
                        new_rot = current_piece.rotation + 1
                        if board.is_valid_move(current_piece, rotation=new_rot):
                            current_piece.rotate(1)
                            if sound_enabled:
                                rotate_cw_sound.play()
                    elif event.key == pygame.K_s:
                        # Rotation logic (Counter-Clockwise)
                        new_rot = current_piece.rotation - 1
                        if board.is_valid_move(current_piece, rotation=new_rot):
                            current_piece.rotate(-1)
                            if sound_enabled:
                                rotate_ccw_sound.play()
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_DOWN:
                        down_pressed_for_current_piece = False

            screen.fill(BLACK)
            draw_grid(screen, board)
            draw_tetromino(screen, current_piece)

            # Update and draw particles
            for p in particles[:]:
                p.update()
                p.draw(screen)
                if p.life <= 0:
                    particles.remove(p)

            # Draw score
            score_text = font.render(f"SCORE: {score}", True, WHITE)
            screen.blit(score_text, (20, 20))

            # Draw lines cleared
            lines_text = font.render(f"LINES: {total_lines}", True, WHITE)
            screen.blit(lines_text, (20, 60))

            # Draw level
            level_text = font.render(f"LEVEL: {level}", True, WHITE)
            screen.blit(level_text, (20, 100))

            # Draw "Next Piece"
            next_text = font.render("NEXT:", True, WHITE)
            screen.blit(next_text, (550, 50))

            if paused:
                pause_text = font.render("PAUSE", True, WHITE)
                screen.blit(
                    pause_text,
                    (
                        SCREEN_WIDTH // 2 - pause_text.get_width() // 2,
                        SCREEN_HEIGHT // 2,
                    ),
                )

            # Draw next piece offset to the side
            for x, y in next_piece.get_blocks():
                rect = pygame.Rect(
                    x * BLOCK_SIZE + 550, y * BLOCK_SIZE + 100, BLOCK_SIZE, BLOCK_SIZE
                )
                pygame.draw.rect(screen, next_piece.color, rect)

            pygame.display.flip()

        print(f"Game Over! Final Score: {score}")

        # Gestion du leaderboard via popup
        name = get_user_name(screen, font)
        save_score(name, score)
        show_leaderboard_screen(screen, font)

        if not show_restart_menu(screen, font):
            pygame.quit()
            return


if __name__ == "__main__":
    main()
