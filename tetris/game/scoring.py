"""Scoring rules — pure function, no side effects."""

from tetris.settings import LINE_BONUS


class ScoreEngine:
    """Computes score awarded for a line clear.

    Base score is ``lines * 100``; a bonus table rewards multi-line
    clears. Encapsulating the table keeps the rule in one place (DRY).
    """

    @staticmethod
    def score_for(lines_cleared: int) -> int:
        return lines_cleared * 100 + LINE_BONUS.get(lines_cleared, 0)