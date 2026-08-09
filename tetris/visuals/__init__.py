"""Visual effects and rendering (particles, renderer, shared views, fonts)."""

from tetris.visuals.fonts import get_large_font, get_small_font
from tetris.visuals.graph_view import render_score_graph
from tetris.visuals.leaderboard_view import draw_leaderboard
from tetris.visuals.particles import Particle, ParticleSystem
from tetris.visuals.renderer import Renderer

__all__ = [
    "Particle",
    "ParticleSystem",
    "Renderer",
    "draw_leaderboard",
    "get_large_font",
    "get_small_font",
    "render_score_graph",
]
