from __future__ import annotations

import random
from typing import Any


class LearningSession:
    """Keeps a randomized queue of cards for one learn session."""

    def __init__(self, cards: list[dict[str, Any]]) -> None:
        self._cards = cards[:]
        random.shuffle(self._cards)
        self._index = -1

    def next_card(self) -> dict[str, Any] | None:
        self._index += 1
        if self._index >= len(self._cards):
            return None
        return self._cards[self._index]

    @property
    def total(self) -> int:
        return len(self._cards)

    @property
    def current_position(self) -> int:
        return max(0, self._index + 1)
