"""Tests for imitation warm-start (roadmap #5).

Covers: recorder JSONL round-trip, best-effort semantics (missing file,
malformed lines, unwritable path), game splitting, board reconstruction,
ranking-loss effect on the V-network, settings/menu plumbing.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import torch

from tetris.ai.agent import DQNAgent
from tetris.ai.imitation import _apply_placement, _split_games, imitation_pretrain
from tetris.game.imitation import PlacementsLog, read_placements


def _write_game(path, moves, seed=7):
    log = PlacementsLog(path)
    log.start_game(seed=seed, handicap=0)
    for piece, rot, x, hold in moves:
        log.record(piece, rot, x, hold=hold)
    log.close()


def test_recorder_roundtrip(tmp_path):
    p = str(tmp_path / "pl.jsonl")
    _write_game(p, [("I", 0, 0, False), ("T", 1, 4, True)])
    recs = read_placements(p)
    assert recs[0]["type"] == "game" and recs[0]["seed"] == 7
    assert recs[1] == {"type": "move", "piece": "I", "rot": 0, "x": 0, "hold": False}
    assert recs[2]["hold"] is True


def test_read_missing_file_is_empty(tmp_path):
    assert read_placements(str(tmp_path / "nope.jsonl")) == []


def test_read_skips_malformed_lines(tmp_path):
    p = tmp_path / "pl.jsonl"
    p.write_text('{"type": "game"}\nnot-json\n{"type": "move", "piece": "I", "rot": 0, "x": 0, "hold": false}\n\n')
    recs = read_placements(str(p))
    assert len(recs) == 2


def test_write_failure_never_raises(tmp_path):
    """Recording must never crash gameplay, even on an unwritable path."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    log = PlacementsLog(str(blocker / "pl.jsonl"))  # parent is a file → OSError
    log.record("I", 0, 0, hold=False)  # must not raise
    log.close()


def test_split_games_groups_by_header():
    recs = [
        {"type": "game"},
        {"type": "move", "piece": "I"},
        {"type": "game"},
        {"type": "move", "piece": "T"},
        {"type": "move", "piece": "O"},
    ]
    games = _split_games(recs)
    assert [len(g) for g in games] == [1, 2]


def test_apply_placement_drops_and_clears():
    grid = np.zeros((22, 10), dtype=np.int8)
    for x in (0, 2, 4, 6, 8):
        _apply_placement(grid, "O", 0, x)
    assert (grid == 0).all()  # full row cleared
    _apply_placement(grid, "T", 1, 4)
    assert (grid != 0).sum() == 4


def test_pretrain_noop_on_missing_log(tmp_path):
    agent = DQNAgent(seed=1)
    before = {k: v.clone() for k, v in agent.online_net.state_dict().items()}
    assert imitation_pretrain(agent, str(tmp_path / "nope.jsonl")) == 0
    after = agent.online_net.state_dict()
    for k, v in before.items():
        assert torch.equal(v, after[k])


def test_pretrain_pushes_human_choice_up():
    agent = DQNAgent(seed=3)
    grid = np.zeros((22, 10), dtype=np.int8)
    from tetris.ai.candidates import get_candidate_states

    cands, _, _, placements = get_candidate_states(
        grid, "I", None, "I", [], can_hold=False, lookahead=False, lookahead_depth=1
    )
    chosen_idx = next(i for i, p in enumerate(placements) if p.rot == 0 and p.px == 3 and not p.hold)

    def rank() -> int:
        v = agent.online_net(torch.as_tensor(cands, dtype=torch.float32)).squeeze(-1)
        return int((v > v[chosen_idx]).sum())

    before = rank()
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "pl.jsonl")
        _write_game(p, [("I", 0, 3, False)] * 5)
        trained = imitation_pretrain(agent, p, epochs=4)
    assert trained > 0
    assert rank() < before


def test_pretrain_skips_impossible_moves():
    """Moves that cannot be reconstructed (illegal placement) are skipped,
    not fatal."""
    agent = DQNAgent(seed=2)
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "pl.jsonl")
        _write_game(p, [("I", 0, 99, False), ("X", 0, 0, False), ("I", 0, 0, False)])
        trained = imitation_pretrain(agent, p, epochs=1)
    assert trained >= 1  # the legal move trained; bogus ones skipped


def test_settings_and_aiconfig_plumbing():
    from tetris.states.ai import AIConfig

    def make(imitation: bool = False) -> AIConfig:
        return AIConfig(
            epsilon_decay=0.999,
            epsilon_end=0.1,
            lr=1e-3,
            gamma=0.97,
            batch_size=64,
            buffer_size=50_000,
            ai_mode="learning",
            curriculum=False,
            curriculum_freq=50,
            curriculum_epsilon="reset",
            warm_start=True,
            learn_per_action=2,
            lookahead=True,
            lookahead_depth=1,
            imitation=imitation,
        )

    assert make().imitation is False
    assert make(imitation=True).imitation is True
    from tetris.states.hyperparam_menu import HyperparamMenuState

    assert "ai_imitation" in HyperparamMenuState._DEFAULTS
    assert HyperparamMenuState._DEFAULTS["ai_imitation"] is False
    assert "Imitation" in HyperparamMenuState._OPTIONS
    assert HyperparamMenuState._OPTIONS.index("Imitation") in HyperparamMenuState._toggle_indices


def test_human_state_records_placements(tmp_path, monkeypatch):
    """HumanState gameplay must record game headers and locked pieces."""
    import pygame

    pygame.init()
    screen = pygame.Surface((800, 600))
    font = pygame.font.Font(None, 20)
    from tetris.audio import AudioManager
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.game import GameConfig
    from tetris.states.human import HumanState
    from tetris.states.menu import MenuState
    from tetris.visuals.particles import ParticleSystem

    log_path = str(tmp_path / "pl.jsonl")
    orig_init = PlacementsLog.__init__
    monkeypatch.setattr(PlacementsLog, "__init__", lambda self, path=log_path: orig_init(self, path))
    audio = AudioManager(sound_volume=0, music_volume=0)
    menu = MenuState(screen, font, audio)
    cfg = GameConfig(
        handicap=0,
        sound_volume=0,
        music_volume=0,
        music_song="korobeiniki",
        debug=False,
        ghost_piece=True,
        preview_count=1,
        speed_mode="normal",
    )
    state = HumanState(screen, font, audio, cfg, PieceProvider(generator="7bag", seed=42), menu)
    monkeypatch.setattr(PlacementsLog, "__init__", orig_init)
    particles = ParticleSystem()
    state.handle_event(pygame.event.Event(pygame.KEYDOWN, key=menu.keybinds["hard_drop"]))
    state.update(1 / 60, particles)
    state.update(1 / 60, particles)
    recs = read_placements(log_path)
    assert len([r for r in recs if r["type"] == "game"]) == 1
    moves = [r for r in recs if r["type"] == "move"]
    assert len(moves) >= 1
    assert moves[0]["piece"] in ("I", "J", "L", "O", "S", "T", "Z")
