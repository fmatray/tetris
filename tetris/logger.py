"""Central logging: replaces print() with Python logging to a file.

``configure_logging(debug)`` sets the root ``tetris`` logger level.
When debug is off (default), DEBUG messages are no-ops — only warnings
and errors reach the file.
"""

import logging

from tetris.settings import DEBUG_LOG_PATH

_LOGGER_NAME = "tetris"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the ``tetris`` namespace."""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)


def configure_logging(debug: bool = False) -> None:
    """Configure the ``tetris`` logger: FileHandler at DEBUG or WARNING level."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.FileHandler(DEBUG_LOG_PATH)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(handler)