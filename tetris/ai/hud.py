"""AI training HUD rendering — training params, stats table, last-5-moves.

Pure presentation: reads AI state, draws text. No game logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.states.ai import AIState

from tetris.settings import HUD_POSITIONS, RED, SCREEN_WIDTH
from tetris.visuals.fonts import LINE_HEIGHT_SMALL


def draw_ai_hud(ai_state: AIState) -> None:
    """Overlay training parameters and a statistics table on the game screen."""
    x0 = HUD_POSITIONS["ai_stats"][0]
    y = HUD_POSITIONS["ai_stats"][1]
    lh = LINE_HEIGHT_SMALL  # line height

    # --- Training section (3 columns) ---
    mode_label = "Apprentissage" if ai_state.ai_mode == "learning" else "Jeu"
    training_items = [
        f"Mode: {mode_label}",
        f"Vitesse: {'Rapide' if ai_state.speed == 'fast' else 'Normal'}",
        f"Episode: {ai_state.episode}",
        f"Epsilon: {ai_state.agent.epsilon:.5f}",
        f"Epsilon decay: {ai_state.agent.epsilon_decay:.4f}",
        f"Epsilon end: {ai_state.agent.epsilon_end:.2f}",
        f"LR: {ai_state.agent.optimizer.param_groups[0]['lr']:.1e}",
        f"Gamma: {ai_state.agent.gamma:.3f}",
        f"Batch: {ai_state.agent.batch_size}",
        f"Loss: {ai_state.agent.last_loss:.4f}",
        f"Curriculum: {'ON' if ai_state.curriculum else 'OFF'}",
        f"Pieces: {''.join(ai_state._curriculum_types) if ai_state._curriculum_types else 'ALL'}",
        f"Warm-start: {'ON' if ai_state.warm_start else 'OFF'}",
        f"Maj/pièce: {ai_state.learn_per_action}",
    ]
    col_w = (SCREEN_WIDTH - x0) // 3
    for i, item in enumerate(training_items):
        col = i % 3
        row = i // 3
        surf = ai_state.font.render(item, True, RED)
        ai_state.screen.blit(surf, (x0 + col * col_w, y + row * lh))
    y += (len(training_items) // 3 + (1 if len(training_items) % 3 else 0)) * lh

    y += 10  # gap between sections

    # --- Statistics table ---
    # Columns: [Tetromino, Lines, Score, Level] — right-aligned
    # Rows: [Current, Total, Best, Average, Last 100]
    label_w = 130
    margin = 20
    col_w = (SCREEN_WIDTH - x0 - label_w - margin) // 4
    col_x = [x0 + label_w + i * col_w for i in range(5)]

    headers = ["", "Tetromino", "Lines", "Score", "Level"]
    for i in range(1, 5):
        surf = ai_state.font.render(headers[i], True, RED)
        ai_state.screen.blit(surf, (col_x[i] - surf.get_width(), y))
    y += lh

    rows = _hud_table_rows(ai_state.log, ai_state.stats, ai_state.episode_steps)
    for row in rows:
        label = row[0]
        surf = ai_state.font.render(label, True, RED)
        ai_state.screen.blit(surf, (x0, y))
        for i in range(1, 5):
            surf = ai_state.font.render(str(row[i]), True, RED)
            ai_state.screen.blit(surf, (col_x[i] - surf.get_width(), y))
        y += lh

    # --- Last 5 moves (compact, below board) ---
    parts = [
        f"{ptype} r{rot} c{col} {'H' if hold else ' '}"
        for _i, (ptype, rot, col, hold) in enumerate(ai_state._last_moves)
    ]
    moves_text = "Derniers coups: " + " | ".join(parts) if parts else "Derniers coups: —"
    surf = ai_state.font.render(moves_text, True, RED)
    ai_state.screen.blit(surf, HUD_POSITIONS["ai_moves"])


def _hud_table_rows(log, stats, episode_steps: int) -> list[list]:
    """Build the 6 statistics rows: Current, Total, Best, Average, Last 100, Trend."""
    cur_steps = episode_steps
    cur_lines = stats.total_lines
    cur_score = stats.score
    cur_level = stats.level

    total_steps = log.total_steps + cur_steps
    total_lines = log.total_lines + cur_lines
    total_score = log.total_score + cur_score

    return [
        ["Current", cur_steps, cur_lines, cur_score, cur_level],
        ["Total", total_steps, total_lines, total_score, "—"],
        ["Best", log.best_steps, log.best_lines, log.best_score, log.best_level],
        ["Average", f"{log.avg_steps:.1f}", f"{log.avg_lines:.1f}", f"{log.avg_score:.1f}", f"{log.avg_level:.1f}"],
        [
            "Last 100",
            f"{log.last_100_avg_steps:.1f}",
            f"{log.last_100_avg_lines:.1f}",
            f"{log.last_100_avg:.1f}",
            f"{log.last_100_avg_level:.1f}",
        ],
        [
            "Trend",
            _trend_arrow(log._trend("steps")),
            _trend_arrow(log._trend("lines")),
            _trend_arrow(log._trend("score")),
            _trend_arrow(log._trend("level")),
        ],
    ]


def _trend_arrow(trend: str) -> str:
    """Convert a trend string to an arrow symbol."""
    return {"up": "↑", "down": "↓", "stable": "→"}.get(trend, "→")
