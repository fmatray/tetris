"""Score-over-episode graph rendered with matplotlib (Agg backend).

Renders the episode-vs-score learning curve to a ``pygame.Surface`` so
it can be blitted inside the game window. The matplotlib figure uses a
dark theme to match the game's palette.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless renderer — no GUI window

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pygame

from tetris.i18n import tr

# Matplotlib colors (normalized 0-1 floats) and matching pygame color.
_BG = (0.0, 0.0, 0.0)
_FG = (1.0, 1.0, 1.0)
_GRID = (0.235, 0.235, 0.235)

# Figure size in inches (rendered at 100 dpi → pixels).
_FIG_W, _FIG_H = 11.0, 6.0
_DPI = 100


def _moving_average(values: list[int], window: int) -> list[float]:
    """Simple trailing moving average; returns one value per input."""
    if not values:
        return []
    out: list[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def render_score_graph(
    episodes: list[int], scores: list[int], figsize: tuple[float, float] = (_FIG_W, _FIG_H)
) -> pygame.Surface:
    """Render the episode-vs-score graph to a ``pygame.Surface``.

    A raw-score line (cyan) is overlaid with a 20-episode moving average
    (yellow) to make the learning trend visible through the noise.

    ``figsize`` overrides the figure size in inches (at ``_DPI``); narrow
    figures (e.g. ``(8, 6)``) leave room for side-panel text.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=_DPI)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    if episodes:
        ax.plot(episodes, scores, color="cyan", linewidth=0.8, alpha=0.6, label=tr("Score"))
        ma_window = min(20, len(scores))
        avg = _moving_average(scores, ma_window)
        ax.plot(episodes, avg, color="yellow", linewidth=1.8, label=tr("Avg. {}").format(ma_window))
        ax.legend(facecolor=_BG, edgecolor=_FG, labelcolor=_FG)

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(tr("Episode"), color=_FG, fontsize=12)
    ax.set_ylabel(tr("Score"), color=_FG, fontsize=12)
    ax.set_title(tr("Score per episode"), color=_FG, fontsize=16)
    ax.tick_params(colors=_FG)
    ax.grid(True, color=_GRID, alpha=0.5)
    for spine in ax.spines.values():
        spine.set_color(_FG)

    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    buf = fig.canvas.buffer_rgba()  # type: ignore[attr-defined]
    plt.close(fig)

    surf = pygame.image.frombuffer(bytes(buf), (w, h), "RGBA")
    if pygame.display.get_surface() is not None:
        surf = surf.convert()
    return surf
