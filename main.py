import os
import random
import sys
import json
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

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


class AudioManager:
    """Handles procedural sound generation and playback."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self._init_sounds()

    def _init_sounds(self) -> None:
        # Line clears
        self.sounds["clear_1"] = self.generate_melody(
            [(261.63, 0.08), (392.00, 0.08), (523.25, 0.2)]
        )
        self.sounds["clear_2"] = self.generate_melody(
            [
                (261.63, 0.06),
                (392.00, 0.06),
                (261.63, 0.06),
                (392.00, 0.06),
                (523.25, 0.2),
            ]
        )
        self.sounds["clear_3"] = self.generate_melody(
            [
                (261.63, 0.06),
                (329.63, 0.06),
                (392.00, 0.06),
                (493.88, 0.06),
                (523.25, 0.3),
            ]
        )
        self.sounds["clear_4"] = self.generate_melody(
            [(261.63, 0.05), (523.25, 0.05), (783.99, 0.05), (1046.50, 0.4)]
        )
        # Rotations
        self.sounds["rotate_cw"] = self.generate_melody([(440.0, 0.05), (659.25, 0.05)])
        self.sounds["rotate_ccw"] = self.generate_melody(
            [(659.25, 0.05), (440.0, 0.05)]
        )
        # Game State
        self.sounds["game_over"] = self.generate_melody(
            [(261.63, 0.2), (196.00, 0.2), (130.81, 0.5)]
        )
        self.sounds["glitch"] = self.generate_melody([(880.0, 0.01), (1760.0, 0.01)])
        self.sounds["lock"] = self.generate_melody([(600.0, 0.05), (400.0, 0.05)])

    def generate_melody(self, notes: List[Tuple[float, float]]) -> pygame.mixer.Sound:
        sample_rate = 44100
        full_buf = []
        try:
            for freq, duration in notes:
                n_samples = int(sample_rate * duration)
                buf = np.zeros((n_samples, 2), dtype=np.int16)
                for i in range(n_samples):
                    envelope = 1.0
                    if i < 100:
                        envelope = i / 100
                    if i > n_samples - 100:
                        envelope = (n_samples - i) / 100
                    val = int(
                        32767 * np.sin(2 * np.pi * freq * i / sample_rate) * envelope
                    )
                    buf[i][0] = buf[i][1] = val
                full_buf.append(buf)
            combined_buf = np.concatenate(full_buf, axis=0)
            return pygame.sndarray.make_sound(combined_buf)
        except Exception as e:
            print(f"Audio error: {e}")
            return pygame.mixer.Sound(buffer=np.zeros((44100, 2), dtype=np.int16))

    def play(self, key: str) -> None:
        if self.enabled and key in self.sounds:
            self.sounds[key].play()


class Particle:
    def __init__(self, x: float, y: float, color: Tuple[int, int, int]) -> None:
        self.x, self.y, self.color = x, y, color
        self.vx = random.uniform(-8, 8)
        self.vy = random.uniform(-12, -4)
        self.life = random.uniform(0.6, 1.4)
        self.decay = random.uniform(0.01, 0.03)
        self.size = random.randint(2, 6)

    def update(self) -> None:
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1
        self.vx *= 0.95
        self.life -= self.decay

    def draw(self, screen: pygame.Surface) -> None:
        if self.life > 0:
            try:
                current_size = max(1, int(self.size * self.life))
                color_fade = [max(0, min(255, int(c * self.life))) for c in self.color]
                pygame.draw.rect(
                    screen, color_fade, (self.x, self.y, current_size, current_size)
                )
            except (ValueError, TypeError):
                pass


class ParticleSystem:
    def __init__(self) -> None:
        self.particles: List[Particle] = []

    def emit(
        self, x: float, y: float, color: Tuple[int, int, int], count: int = 1
    ) -> None:
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def update(self) -> None:
        for p in self.particles[:]:
            p.update()
            if p.life <= 0:
                self.particles.remove(p)

    def draw(self, screen: pygame.Surface) -> None:
        for p in self.particles:
            p.draw(screen)


class Renderer:
    def __init__(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        self.screen = screen
        self.font = font

    def render_frame(self, game: "GameState", particles: ParticleSystem) -> None:
        self.screen.fill(BLACK)
        self.draw_grid(game.board)
        self.draw_tetromino(game.current_piece)
        self._draw_text(f"SCORE: {game.score}", (20, 20))
        self._draw_text(f"LINES: {game.total_lines}", (20, 60))
        self._draw_text(f"LEVEL: {game.level}", (20, 100))
        self._draw_text("NEXT:", (550, 50))
        for x, y in game.next_piece.get_blocks():
            rect = pygame.Rect(
                x * BLOCK_SIZE + 550, y * BLOCK_SIZE + 100, BLOCK_SIZE, BLOCK_SIZE
            )
            pygame.draw.rect(self.screen, game.next_piece.color, rect)
        if game.paused:
            pause_text = self.font.render("PAUSE", True, WHITE)
            self.screen.blit(
                pause_text,
                (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, SCREEN_HEIGHT // 2),
            )
        particles.draw(self.screen)
        pygame.display.flip()

    def _draw_text(self, text: str, pos: Tuple[int, int]) -> None:
        surf = self.font.render(text, True, WHITE)
        self.screen.blit(surf, pos)

    def draw_grid(self, board: Board) -> None:
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                rect = pygame.Rect(
                    x * BLOCK_SIZE + 250, y * BLOCK_SIZE + 50, BLOCK_SIZE, BLOCK_SIZE
                )
                pygame.draw.rect(self.screen, GRAY, rect, 1)
                color = board.grid[y][x]
                if color:
                    pygame.draw.rect(self.screen, color, rect)

    def draw_tetromino(self, tetromino: Tetromino) -> None:
        for x, y in tetromino.get_blocks():
            if y >= 0:
                rect = pygame.Rect(
                    x * BLOCK_SIZE + 250, y * BLOCK_SIZE + 50, BLOCK_SIZE, BLOCK_SIZE
                )
                pygame.draw.rect(self.screen, tetromino.color, rect)

    def play_game_over_animation(self, game: "GameState", audio: AudioManager) -> None:
        duration, start_time = 4000, pygame.time.get_ticks()
        particles = []
        for _ in range(400):
            particles.append(
                Particle(
                    random.randint(250, 250 + BOARD_WIDTH * BLOCK_SIZE),
                    random.randint(50, 50 + BOARD_HEIGHT * BLOCK_SIZE),
                    random.choice(
                        [
                            WHITE,
                            GRAY,
                            (255, 0, 0),
                            (0, 255, 0),
                            (0, 0, 255),
                            (255, 255, 0),
                            (255, 0, 255),
                        ]
                    ),
                )
            )
        audio.play("game_over")
        while pygame.time.get_ticks() - start_time < duration:
            elapsed = pygame.time.get_ticks() - start_time
            if random.random() < 0.1:
                self.screen.fill((random.randint(50, 150), 0, 0))
                audio.play("glitch")
            else:
                self.screen.fill(BLACK)
            shake_x = (
                random.randint(-15, 15) if elapsed < 1500 else random.randint(-3, 3)
            )
            shake_y = (
                random.randint(-15, 15) if elapsed < 1500 else random.randint(-3, 3)
            )
            board_surf = pygame.Surface(
                (BOARD_WIDTH * BLOCK_SIZE, BOARD_HEIGHT * BLOCK_SIZE)
            )
            board_surf.set_colorkey(BLACK)
            glitch = random.random()
            for y in range(BOARD_HEIGHT):
                for x in range(BOARD_WIDTH):
                    rect = pygame.Rect(
                        x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE
                    )
                    pygame.draw.rect(board_surf, GRAY, rect, 1)
                    if game.board.grid[y][x]:
                        color = (
                            game.board.grid[y][x]
                            if glitch <= 0.95
                            else (
                                random.randint(0, 255),
                                random.randint(0, 255),
                                random.randint(0, 255),
                            )
                        )
                        if color:
                            pygame.draw.rect(board_surf, color, rect)
            for x, y in game.current_piece.get_blocks():
                if y >= 0:
                    pygame.draw.rect(
                        board_surf,
                        game.current_piece.color,
                        (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
                    )
            self.screen.blit(board_surf, (250 + shake_x, 50 + shake_y))
            if random.random() < 0.3:
                particles.append(
                    Particle(
                        random.randint(0, SCREEN_WIDTH),
                        random.randint(0, SCREEN_HEIGHT),
                        random.choice([WHITE, (255, 0, 0), (0, 255, 0)]),
                    )
                )
            for p in particles[:]:
                p.update()
                p.draw(self.screen)
                if p.life <= 0:
                    particles.remove(p)
            try:
                r = int(127 + 127 * np.sin(elapsed * 0.01))
                g = int(127 + 127 * np.sin(elapsed * 0.01 + 2 * np.pi / 3))
                b = int(127 + 127 * np.sin(elapsed * 0.01 + 4 * np.pi / 3))
            except Exception:
                r, g, b = 255, 0, 0
            txt = self.font.render("!!! GAME OVER !!!", True, (r, g, b))
            dx, dy = (
                (random.randint(-10, 10), random.randint(-10, 10))
                if elapsed < 2000
                else (0, 0)
            )
            self.screen.blit(
                txt,
                (
                    SCREEN_WIDTH // 2 - txt.get_width() // 2 + dx,
                    SCREEN_HEIGHT // 2 - txt.get_height() // 2 + dy,
                ),
            )
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
            pygame.time.delay(16)


class State:
    def handle_event(self, event: pygame.event.Event) -> Optional["State"]:
        pass

    def update(self, dt: float, particles: ParticleSystem) -> Optional["State"]:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass


class MenuState(State):
    def __init__(
        self, screen: pygame.Surface, font: pygame.font.Font, audio: AudioManager
    ) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.h, self.s = 0, True

    def handle_event(self, event: pygame.event.Event) -> Optional["State"]:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.h = max(0, self.h - 1)
            elif event.key == pygame.K_RIGHT:
                self.h = min(5, self.h + 1)
            elif event.key == pygame.K_s:
                self.s = not self.s
            elif event.key == pygame.K_RETURN:
                return GameState(self.screen, self.font, self.audio, self.h)
        return None

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)
        title = self.font.render("TETRIS", True, WHITE)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        instr = self.font.render("Select Handicap Level (0-5)", True, GRAY)
        screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, 200))
        lvl = self.font.render(f"Current Level: {self.h}", True, WHITE)
        screen.blit(lvl, (SCREEN_WIDTH // 2 - lvl.get_width() // 2, 250))
        snd = self.font.render(f"Sound: {'ON' if self.s else 'OFF'}", True, WHITE)
        screen.blit(snd, (SCREEN_WIDTH // 2 - snd.get_width() // 2, 300))
        ctrl = self.font.render(
            "LEFT/RIGHT: Level | S: Sound | ENTER: Start", True, GRAY
        )
        screen.blit(ctrl, (SCREEN_WIDTH // 2 - ctrl.get_width() // 2, 400))


class GameState(State):
    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        handicap: int,
    ) -> None:
        self.screen, self.font, self.audio = screen, font, audio
        self.renderer = Renderer(screen, font)
        self.board = Board()
        self.board.apply_handicap(handicap)
        self.current_piece = Tetromino()
        self.next_piece = Tetromino()
        self.score, self.total_lines, self.level, self.drop_time = 0, 0, 0, 0
        self.game_over, self.paused, self.down_pressed = False, False, False

        self.input_map = {
            pygame.K_LEFT: self._move_left,
            pygame.K_RIGHT: self._move_right,
            pygame.K_UP: self._rotate_cw,
            pygame.K_s: self._rotate_ccw,
            pygame.K_DOWN: self._toggle_down_true,
        }

    def _move_left(self) -> None:
        if not self.paused and self.board.is_valid_move(self.current_piece, dx=-1):
            self.current_piece.move(-1, 0)

    def _move_right(self) -> None:
        if not self.paused and self.board.is_valid_move(self.current_piece, dx=1):
            self.current_piece.move(1, 0)

    def _rotate_cw(self) -> None:
        if not self.paused and self.board.is_valid_move(
            self.current_piece, rotation=self.current_piece.rotation + 1
        ):
            self.current_piece.rotate(1)
            self.audio.play("rotate_cw")

    def _rotate_ccw(self) -> None:
        if not self.paused and self.board.is_valid_move(
            self.current_piece, rotation=self.current_piece.rotation - 1
        ):
            self.current_piece.rotate(-1)
            self.audio.play("rotate_ccw")

    def _toggle_down_true(self) -> None:
        self.down_pressed = True

    def handle_event(self, event: pygame.event.Event) -> Optional["State"]:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key in self.input_map:
                self.input_map[event.key]()
        elif event.type == pygame.KEYUP and event.key == pygame.K_DOWN:
            self.down_pressed = False
        return None

    def update(self, dt: float, particles: ParticleSystem) -> Optional["State"]:
        if self.paused or self.game_over:
            return None
        self.drop_time += dt
        speed = 0.05 if self.down_pressed else 0.5 * (0.98**self.level)
        if self.drop_time / 1000 >= speed:
            if self.board.is_valid_move(self.current_piece, dy=1):
                self.current_piece.move(0, 1)
            else:
                cleared, rows_data = self.board.lock_tetromino(self.current_piece)
                self.total_lines += cleared
                self.level = self.total_lines // 10
                self.score += (cleared * 100) + {1: 0, 2: 20, 3: 50, 4: 100}.get(
                    cleared, 0
                )
                if cleared > 0:
                    self.audio.play(f"clear_{cleared}")
                    for r_idx, colors in rows_data:
                        for c_idx, col in enumerate(colors):
                            particles.emit(
                                c_idx * BLOCK_SIZE + 250 + BLOCK_SIZE // 2,
                                r_idx * BLOCK_SIZE + 50 + BLOCK_SIZE // 2,
                                col,
                                80,
                            )
                else:
                    self.audio.play("lock")
                self.current_piece, self.next_piece = self.next_piece, Tetromino()
                self.down_pressed = False
                if not self.board.is_valid_move(self.current_piece):
                    self.game_over = True
            self.drop_time = 0
        if self.game_over:
            return GameOverState(self.screen, self.font, self.audio, self)
        return None

    def draw(self, screen: pygame.Surface) -> None:
        # Use the renderer we created in __init__ but pass in an external particles system
        # To keep state clean, we'll need to pass particles from main loop.
        # I'll update the render_frame call in the main loop.
        pass

    def render(self, particles: ParticleSystem) -> None:
        self.renderer.render_frame(self, particles)


class GameOverState(State):
    def __init__(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        audio: AudioManager,
        game: GameState,
    ) -> None:
        self.screen, self.font, self.audio, self.game = screen, font, audio, game
        self.renderer = Renderer(screen, font)
        self.name = ""
        self.step = "ANIMATION"  # ANIMATION -> NAME -> LEADERBOARD -> RESTART

    def update(self, dt: float, particles: ParticleSystem) -> Optional["State"]:
        if self.step == "ANIMATION":
            self.renderer.play_game_over_animation(self.game, self.audio)
            self.step = "NAME"
        return None

    def handle_event(self, event: pygame.event.Event) -> Optional["State"]:
        if self.step == "NAME":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and self.name.strip():
                    save_score(
                        self.name,
                        self.game.score,
                        self.game.level,
                        self.game.total_lines,
                    )
                    self.step = "LEADERBOARD"
                elif event.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif len(self.name) < 15:
                    self.name += event.unicode
        elif self.step == "LEADERBOARD":
            if event.type == pygame.KEYDOWN:
                self.step = "RESTART"
        elif self.step == "RESTART":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return MenuState(self.screen, self.font, self.audio)
                if event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
        return None

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(BLACK)
        if self.step == "NAME":
            prompt = self.font.render("GAME OVER!", True, WHITE)
            screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 150))
            instr = self.font.render("Enter your name and press ENTER:", True, GRAY)
            screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, 200))
            rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, 250, 300, 50)
            pygame.draw.rect(screen, GRAY, rect, 2)
            txt = self.font.render(self.name, True, WHITE)
            screen.blit(txt, (rect.x + 10, rect.y + 10))
        elif self.step == "LEADERBOARD":
            scores = load_leaderboard()
            title = self.font.render("TOP 10 LEADERBOARD", True, WHITE)
            screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))

            # Table Header
            header = self.font.render(
                "Name       Score    Lvl   Lines   Date", True, GRAY
            )
            screen.blit(header, (SCREEN_WIDTH // 2 - header.get_width() // 2, 80))

            for i, entry in enumerate(scores[:10], 1):
                # Formatted row: "1. Fred     37120   12    85    2024-05-20"
                row_str = (
                    f"{i:<2} {entry['name']:<10} {entry['score']:<8} "
                    f"{entry['level']:<5} {entry['lines']:<7} {entry['date']}"
                )
                row = self.font.render(row_str, True, WHITE)
                screen.blit(
                    row, (SCREEN_WIDTH // 2 - row.get_width() // 2, 120 + i * 30)
                )

            instr = self.font.render("Press any key to continue", True, GRAY)
            screen.blit(instr, (SCREEN_WIDTH // 2 - instr.get_width() // 2, 600))
        elif self.step == "RESTART":
            title = self.font.render("GAME OVER", True, WHITE)
            screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))
            r_txt = self.font.render("Press 'R' to Restart", True, GRAY)
            screen.blit(r_txt, (SCREEN_WIDTH // 2 - r_txt.get_width() // 2, 220))
            q_txt = self.font.render("Press 'Q' to Quit", True, GRAY)
            screen.blit(q_txt, (SCREEN_WIDTH // 2 - q_txt.get_width() // 2, 280))


def load_leaderboard() -> List[Dict[str, Any]]:
    if not os.path.exists("leaderboard.json"):
        return []
    try:
        with open("leaderboard.json", "r") as f:
            data = json.load(f)
            # Ensure data is a list of dicts
            return [
                d
                if isinstance(d, dict)
                else {
                    "name": d[0],
                    "score": d[1],
                    "level": 0,
                    "lines": 0,
                    "date": "Unknown",
                }
                for d in data
            ]
    except (OSError, json.JSONDecodeError):
        return []


def save_score(name: str, score: int, level: int, lines: int) -> None:
    scores = load_leaderboard()
    scores.append(
        {
            "name": name,
            "score": score,
            "level": level,
            "lines": lines,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    # Sort by score descending
    scores.sort(key=lambda x: x["score"], reverse=True)
    try:
        with open("leaderboard.json", "w") as f:
            json.dump(scores[:10], f, indent=4)
    except OSError as e:
        print(f"Save error: {e}")


def main() -> None:
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Tetris Python")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 32)

    # Initial Menu to get settings
    h_lvl, s_en = 0, True
    # Temporarily use MenuState just to get settings if we wanted to be pure,
    # but for simplicity, let's just instantiate a MenuState as the start.

    audio = AudioManager(True)  # Default True, updated by menu
    particles = ParticleSystem()
    state: State = MenuState(screen, font, audio)

    while True:
        dt = clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            new_state = state.handle_event(event)
            if new_state:
                # If we transition to GameState, we can pass the handicap from MenuState
                if isinstance(new_state, GameState):
                    # we need to pass the handicap from the previous state
                    if isinstance(state, MenuState):
                        new_state.board.apply_handicap(state.h)
                        audio.enabled = state.s
                state = new_state

        new_state = state.update(dt, particles) if hasattr(state, "update") else None
        if new_state:
            state = new_state

        if isinstance(state, GameState):
            state.render(particles)
        else:
            state.draw(screen)
            pygame.display.flip()

        particles.update()


if __name__ == "__main__":
    main()
