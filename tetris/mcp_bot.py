"""Automated MCP Tetris player.

Drives the same primitives the MCP ``play`` / ``enumerate_drops`` tools use
(``tetris.states.simulator.enumerate_drops`` + ``GameState._execute_actions``)
with a hole-averse 1-ply heuristic, to clear >=20 lines in a single episode.

The game is headless (SDL dummy). One episode = play to game over.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

from tetris.audio import AudioManager
from tetris.states.game import GameConfig
from tetris.states.mcp import MCPConfig, MCPState
from tetris.game.piece_provider import PieceProvider
from tetris.settings import BOARD_HEIGHT, BOARD_WIDTH
from tetris.states.simulator import enumerate_drops


def _agg_height(board: list) -> int:
    total = 0
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            if board[y][x] == 1:
                total += BOARD_HEIGHT - y
                break
    return total


def _bumpiness(board: list) -> int:
    hs = []
    for x in range(BOARD_WIDTH):
        h = 0
        for y in range(BOARD_HEIGHT):
            if board[y][x] == 1:
                h = BOARD_HEIGHT - y
                break
        hs.append(h)
    return sum(abs(hs[i] - hs[i + 1]) for i in range(BOARD_WIDTH - 1))


def _score(b: dict) -> float:
    lines = b.get("lines_cleared") or 0
    holes = b.get("holes") or 0
    overhangs = b.get("overhangs") or 0
    board = b["board"]
    # Strongly prefer clears, avoid holes (unreachable) far more than overhangs
    # (reachable/fillable), keep the stack low and flat.
    return lines * 1000 - holes * 120 - overhangs * 10 - _agg_height(board) * 0.8 - _bumpiness(board) * 1.5


def make_state() -> MCPState:
    screen = pygame.Surface((640, 480))
    font = pygame.font.Font(None, 24)
    audio = AudioManager(sound_volume=0, music_volume=0)
    config = GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=3,
        speed_mode="normal",
    )
    return MCPState(
        screen,
        font,
        audio,
        config,
        MCPConfig(port=8765),
        piece_provider=PieceProvider(generator="7bag"),
        start_server=False,
    )


def play_episode(state: MCPState, max_pieces: int = 5000) -> tuple[int, int]:
    dt = 1.0 / 60.0
    pieces = 0
    while not state.game_over and pieces < max_pieces:
        res = enumerate_drops(state, dt)
        boards = res["boards"]
        if not boards:
            state._execute_actions(["hard_drop"])
            pieces += 1
            continue
        best = max(boards, key=_score)
        state._execute_actions(best["actions"])
        pieces += 1
    return state.stats.total_lines, pieces


def main() -> None:
    best = 0
    best_board = None
    best_pieces = 0
    for ep in range(10):
        st = make_state()
        st._reset_game()
        lines, pieces = play_episode(st)
        print(f"ep{ep}: lines={lines} pieces={pieces}")
        if lines > best:
            best = lines
            best_board = st.board
            best_pieces = pieces
        if lines >= 20:
            break
    print(f"BEST_LINES={best} pieces={best_pieces}")
    if best_board is not None:
        grid = best_board.grid
        print("FINAL_BOARD:")
        for row in grid:
            print("".join("#" if c is not None else "." for c in row))


if __name__ == "__main__":
    main()
