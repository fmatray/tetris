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
from tetris.ai.imitation import (
    _apply_placement,
    _rank_games,
    _split_games,
    bot_imitation_pretrain,
    imitation_pretrain,
)
from tetris.game.imitation import PlacementsLog, next_game_path, read_placements, read_placements_dir


def _write_game(path, moves, seed=7):
    log = PlacementsLog(path)
    log.start_game(seed=seed, handicap=0)
    for piece, rot, x, hold in moves:
        log.record(piece, rot, x, hold=hold)
    log.close()


def _write_game_with_result(path, moves, result, seed=7):
    """Write a game header, moves, and a game-end summary record."""
    log = PlacementsLog(path)
    log.start_game(seed=seed, handicap=0)
    for piece, rot, x, hold in moves:
        log.record(piece, rot, x, hold=hold)
    log.end_game(**result)
    log.close()


def _write_game_dir(dir_path, moves, seed=7, result=None):
    """Write one game into a per-game directory (dir= mode)."""
    log = PlacementsLog(dir=dir_path)
    log.start_game(seed=seed, handicap=0)
    for piece, rot, x, hold in moves:
        log.record(piece, rot, x, hold=hold)
    if result is not None:
        log.end_game(**result)
    log.close()


def test_recorder_roundtrip(tmp_path):
    p = str(tmp_path / "pl.jsonl")
    _write_game(p, [("I", 0, 0, False), ("T", 1, 4, True)])
    recs = read_placements(p)
    assert recs[0]["type"] == "game" and recs[0]["seed"] == 7
    assert recs[1] == {"type": "move", "piece": "I", "rot": 0, "x": 0, "hold": False}
    assert recs[2]["hold"] is True


def test_placements_log_per_game_mode(tmp_path):
    """dir= mode writes one file per game, in game order."""
    d = str(tmp_path / "games")
    _write_game_dir(
        d, [("I", 0, 0, False)], seed=7, result={"score": 100, "tetris": 0, "triple": 0, "lines": 0, "pieces": 10}
    )
    _write_game_dir(d, [("T", 1, 4, True)], seed=8)
    files = sorted(os.listdir(d))
    assert files == ["game_000001.jsonl", "game_000002.jsonl"]
    recs = read_placements_dir(d)
    assert [r["type"] for r in recs] == ["game", "move", "game_end", "game", "move"]
    assert recs[0]["seed"] == 7 and recs[3]["seed"] == 8
    assert recs[4]["hold"] is True


def test_placements_log_no_start_game_is_noop(tmp_path):
    """record/end_game before start_game in dir mode must not create files."""
    d = str(tmp_path / "games")
    log = PlacementsLog(dir=d)
    log.record("I", 0, 0, hold=False)
    log.end_game(score=1, tetris=0, triple=0, lines=0, pieces=1)
    log.close()
    assert not os.path.exists(d)


def test_next_game_path_collision_suffix(tmp_path):
    """next_game_path skips existing names, never overwriting."""
    d = str(tmp_path / "games")
    os.makedirs(d)
    # Gap: game_000002.jsonl missing but game_000003.jsonl present — the
    # len+1 index collides and must increment past it.
    for name in ("game_000001.jsonl", "game_000003.jsonl"):
        (tmp_path / "games" / name).write_text("{}\n")
    assert os.path.basename(next_game_path(d)) == "game_000004.jsonl"


def test_end_game_record_roundtrip(tmp_path):
    p = str(tmp_path / "pl.jsonl")
    _write_game_with_result(
        p, [("I", 0, 0, False)], {"score": 5000, "tetris": 2, "triple": 1, "lines": 12, "pieces": 80}
    )
    recs = read_placements(p)
    assert recs[-1] == {
        "type": "game_end",
        "score": 5000,
        "tetris": 2,
        "triple": 1,
        "lines": 12,
        "pieces": 80,
    }


def test_rank_games_keeps_top_n_by_tetris_triple_score(tmp_path):
    """Ranking key is (tetris, triple, score); result-less games are excluded."""
    p = str(tmp_path / "pl.jsonl")
    keys = [
        {"score": 3000, "tetris": 0, "triple": 3, "lines": 3, "pieces": 60},  # triples beat high score alone
        {"score": 5000, "tetris": 2, "triple": 1, "lines": 12, "pieces": 80},
        {"score": 4000, "tetris": 2, "triple": 1, "lines": 12, "pieces": 80},  # fewer points than game 2
        {"score": 9000, "tetris": 3, "triple": 2, "lines": 20, "pieces": 110},
    ]
    for key in keys:
        _write_game_with_result(p, [("I", 0, 0, False)], key)
    _write_game(p, [("I", 0, 0, False)])  # abandoned: no game_end record
    recs = read_placements(p)
    games = _rank_games(_split_games(recs), top_n=2)
    assert len(games) == 2
    got = []
    for moves in games:
        end = next(m for m in moves if m.get("type") == "game_end")
        got.append(end["score"])
    assert got == [9000, 5000]  # sorted by (tetris, triple, score) desc
    for moves in games:
        assert len([m for m in moves if m.get("type") == "move"]) == 1


def test_bot_pretrain_trains_only_top_n(tmp_path):
    """Only the top-N best games are used for warm-start."""
    p = str(tmp_path / "pl.jsonl")
    _write_game_with_result(p, [("I", 0, 0, False)], {"score": 100, "tetris": 0, "triple": 0, "lines": 0, "pieces": 30})
    _write_game_with_result(p, [("I", 0, 0, False)], {"score": 200, "tetris": 1, "triple": 0, "lines": 4, "pieces": 40})
    _write_game_with_result(
        p, [("I", 0, 0, False)], {"score": 300, "tetris": 2, "triple": 1, "lines": 11, "pieces": 50}
    )
    agent = DQNAgent(seed=1)
    # top_n=1: only the best game (tetris=2) trains — its single move,
    # repeated over the 3 warm-start epochs. All three games would give 9.
    assert bot_imitation_pretrain(agent, p, top_n=1) == 3


def test_bot_pretrain_missing_file_is_silent_noop(tmp_path):
    agent = DQNAgent(seed=1)
    before = {k: v.clone() for k, v in agent.online_net.state_dict().items()}
    assert bot_imitation_pretrain(agent, str(tmp_path / "nope.jsonl")) == 0
    after = agent.online_net.state_dict()
    for k, v in before.items():
        assert torch.equal(v, after[k])


def test_god_bot_records_placements(tmp_path, monkeypatch):
    """God-level El-Tetris games write header, move, and game_end records."""
    import pygame

    from tetris.audio import AudioManager
    from tetris.game.imitation import read_placements_dir
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.eltetris import BotConfig, ElTetrisState
    from tetris.states.game import GameConfig
    from tetris.visuals.particles import ParticleSystem

    pygame.init()
    log_dir = str(tmp_path / "bot")
    monkeypatch.setattr("tetris.states.eltetris.BOT_PLACEMENTS_DIR", log_dir)
    bot = ElTetrisState(
        screen=pygame.Surface((800, 600)),
        font=pygame.font.Font(None, 20),
        audio=AudioManager(sound_volume=0, music_volume=0),
        config=GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=1,
            speed_mode="normal",
        ),
        piece_provider=PieceProvider(generator="7bag", seed=42),
        bot_config=BotConfig(lookahead=False, lookahead_depth=1, level="god"),
    )
    assert bot._placement_recorder is not None
    # Play a few pieces, then force a game-over flow.
    parts = ParticleSystem()
    for _ in range(200):
        if bot.update(16, parts) is not None:
            break
    bot.game_over = True
    bot.update(16, parts)  # routes into _do_game_over
    recs = read_placements_dir(log_dir)
    assert sum(r["type"] == "game" for r in recs) == 1
    moves = [r for r in recs if r["type"] == "move"]
    assert len(moves) >= 1
    assert moves[0]["piece"] in ("I", "J", "L", "O", "S", "T", "Z")
    ends = [r for r in recs if r["type"] == "game_end"]
    assert len(ends) == 1
    assert ends[0]["score"] == bot.stats.score
    assert ends[0]["tetris"] == bot.stats.clear_counts.tetris
    assert ends[0]["pieces"] == bot.stats.piece_count
    assert bot._placement_recorder is None


def test_non_god_bot_does_not_record(tmp_path, monkeypatch):
    """Below-god levels do not record placements (imitation data is god-pure)."""
    import pygame

    from tetris.audio import AudioManager
    from tetris.game.piece_provider import PieceProvider
    from tetris.states.eltetris import BotConfig, ElTetrisState
    from tetris.states.game import GameConfig
    from tetris.visuals.particles import ParticleSystem

    pygame.init()
    log_dir = str(tmp_path / "bot")
    monkeypatch.setattr("tetris.states.eltetris.BOT_PLACEMENTS_DIR", log_dir)
    bot = ElTetrisState(
        screen=pygame.Surface((800, 600)),
        font=pygame.font.Font(None, 20),
        audio=AudioManager(sound_volume=0, music_volume=0),
        config=GameConfig(
            handicap=0,
            sound_volume=0,
            music_volume=0,
            music_song="korobeiniki",
            debug=False,
            ghost_piece=True,
            preview_count=1,
            speed_mode="normal",
        ),
        piece_provider=PieceProvider(generator="7bag", seed=42),
        bot_config=BotConfig(lookahead=False, lookahead_depth=1, level="noob"),
    )
    assert bot._placement_recorder is None
    parts = ParticleSystem()
    for _ in range(200):
        if bot.update(16, parts) is not None:
            break
    bot.game_over = True
    bot.update(16, parts)
    assert not os.path.exists(log_dir)


def test_read_missing_file_is_empty(tmp_path):
    assert read_placements(str(tmp_path / "nope.jsonl")) == []


def test_read_placements_dir_missing_and_malformed(tmp_path):
    """Missing dir → []; malformed lines skipped; non-game files ignored."""
    assert read_placements_dir(str(tmp_path / "nope")) == []
    d = tmp_path / "games"
    d.mkdir()
    (d / "game_000001.jsonl").write_text('{"type": "game"}\nnot-json\n')
    (d / "game_000002.jsonl").write_text('{"type": "move", "piece": "I", "rot": 0, "x": 0, "hold": false}\n')
    (d / "notes.txt").write_text('{"type": "game"}\n')
    recs = read_placements_dir(str(d))
    assert [r["type"] for r in recs] == ["game", "move"]


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


def test_pretrain_reads_dir_default(tmp_path, monkeypatch):
    """imitation_pretrain() with no path reads the human per-game dir."""
    d = str(tmp_path / "human")
    monkeypatch.setattr("tetris.ai.imitation.HUMAN_PLACEMENTS_DIR", d)
    _write_game_dir(d, [("I", 0, 0, False)], seed=7)
    agent = DQNAgent(seed=1)
    assert imitation_pretrain(agent) == 3  # one move × 3 warm-start epochs


def test_bot_pretrain_accepts_dir(tmp_path):
    """bot_imitation_pretrain() reads a per-game dir or a flat file."""
    d = str(tmp_path / "bot")
    _write_game_dir(
        d, [("I", 0, 0, False)], seed=7, result={"score": 100, "tetris": 0, "triple": 0, "lines": 0, "pieces": 10}
    )
    agent = DQNAgent(seed=1)
    assert bot_imitation_pretrain(agent, d, top_n=1) == 3  # one move × 3 epochs
    # Flat-file path still works (explicit override).
    p = str(tmp_path / "flat.jsonl")
    _write_game_with_result(p, [("I", 0, 0, False)], {"score": 100, "tetris": 0, "triple": 0, "lines": 0, "pieces": 10})
    agent2 = DQNAgent(seed=1)
    assert bot_imitation_pretrain(agent2, p, top_n=1) == 3


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
    monkeypatch.setattr(PlacementsLog, "__init__", lambda self, path=None, dir=None: orig_init(self, path=log_path))
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
