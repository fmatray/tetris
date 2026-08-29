"""AI training HUD rendering — training params, stats table, last-5-moves.

Pure presentation: reads AI state, draws text. No game logic.
"""

from __future__ import annotations

import pygame

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tetris.states.ai import AIState

from tetris.settings import HUD_POSITIONS, RED, GREEN, SCREEN_WIDTH
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

    # --- Cooking indicator (training mode only) ---
    if ai_state.ai_mode == "learning":
        status, color, level = _cooking_status(ai_state)
        _draw_thermometer(ai_state.screen, x0, y, level, color)
        label_x = x0 + 30
        surf = ai_state.font.render(f"Cuisson: {status}", True, color)
        ai_state.screen.blit(surf, (label_x, y))
        y += max(lh, 20) + 5

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


def _cooking_status(ai_state: AIState) -> tuple[str, tuple[int, int, int], float]:
    """Classify training health using 4 signals: score trend, TD error trend,
    V-margin discrimination, and epsilon decay.

    Returns (label, color, level) where level is 0..1 training progress.
    """
    log = ai_state.log
    agent = ai_state.agent
    n = log.total_episodes
    eps = agent.epsilon
    v_margin = agent.last_v_margin
    score_trend = log._trend("score")

    eps_range = 1.0 - agent.epsilon_end
    eps_progress = 1.0 - (eps - agent.epsilon_end) / eps_range if eps_range > 0 else 1.0
    ep_maturity = min(n / 500.0, 1.0)
    level = max(0.0, min(1.0, max(eps_progress, ep_maturity)))
    # ponytail: n<100 → undercooked by definition; TD window unavailable and early
    # score dips are normal learning churn, not divergence.
    if n < 100:
        return "Pas assez cuit", (100, 180, 255), level
    health = 0
    # Signal 1: score trend
    if score_trend == "up":
        health += 1
    elif score_trend == "down":
        health -= 1
    # Signal 2: TD error trend (50-ep window)
    if n >= 100:
        recent_td = [e.get("avg_td_error", 0) for e in log.episodes[-50:]]
        prev_td = [e.get("avg_td_error", 0) for e in log.episodes[-100:-50]]
        recent_avg = sum(recent_td) / len(recent_td) if recent_td else 0
        prev_avg = sum(prev_td) / len(prev_td) if prev_td else 0
        if prev_avg > 0:
            td_ratio = recent_avg / prev_avg
            if td_ratio < 0.9:
                health += 1
            elif td_ratio > 1.5:
                health -= 1
    # Signal 3: V-margin (network discriminates top-2 candidates)
    if v_margin > 0.01:
        health += 1
    # Signal 4: epsilon winding down
    if eps < 0.2:
        health += 1

    if health <= 0:
        return "Trop cuit", RED, level
    if health <= 1:
        return "Pas assez cuit", (100, 180, 255), level
    return "Bien cuit", GREEN, level


def _draw_thermometer(screen, x: int, y: int, level: float, color: tuple[int, int, int]) -> None:
    """Draw a vertical thermometer bar: outline + filled portion proportional to level.

    Height 20px, width 12px. Fill rises from bottom to top.
    Color reflects cooking state (blue/green/red).
    """
    h, w = 20, 12
    # Outline
    pygame.draw.rect(screen, (80, 80, 80), (x, y, w, h), 1)
    # Fill
    fill_h = int(h * level)
    if fill_h > 0:
        fill_y = y + h - fill_h
        pygame.draw.rect(screen, color, (x + 1, fill_y, w - 2, fill_h))
    # Bulb at bottom
    pygame.draw.circle(screen, color, (x + w // 2, y + h + 4), 5)
