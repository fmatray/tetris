"""Pytest configuration: initialize pygame in headless mode."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.mixer.init()

import shutil
import tempfile
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _backup_data_dir() -> Iterator[None]:
    """Back up data/ before the session, restore after.

    Tests destructively modify real data files (MODEL_PATH, LOG_PATH,
    SETTINGS_PATH, etc.). This fixture snapshots the entire data/ tree
    (including data/runs/) to a temp dir before tests run and restores
    it after, so real training/playing data is never corrupted.
    """
    from tetris.settings import DATA_DIR

    backup_dir = None
    had_data = os.path.isdir(DATA_DIR)

    if had_data:
        backup_dir = tempfile.mkdtemp(prefix="tetris_test_data_")
        shutil.copytree(DATA_DIR, backup_dir, dirs_exist_ok=True)

    yield

    if had_data:
        assert backup_dir is not None  # type narrowing
        shutil.rmtree(DATA_DIR, ignore_errors=True)
        shutil.copytree(backup_dir, DATA_DIR, dirs_exist_ok=True)
        shutil.rmtree(backup_dir, ignore_errors=True)
