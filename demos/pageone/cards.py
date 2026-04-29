"""ページワンデモ — Card / Deck"""
import random
from dataclasses import dataclass

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = list(range(1, 14))  # 1=A, 2-10, 11=J, 12=Q, 13=K
SPECIAL_RANKS = {2, 8, 11, 12}  # ドロー2, ワイルド, スキップ, リバース

RANK_DISPLAY = {1: "A", 11: "J", 12: "Q", 13: "K"}


@dataclass
class Card:
    suit: str
    rank: int

    def display(self) -> str:
        r = RANK_DISPLAY.get(self.rank, str(self.rank))
        return f"{self.suit}{r}"

    def __repr__(self) -> str:
        return self.display()


class Deck:
    def __init__(self):
        self.cards: list[Card] = [Card(s, r) for s in SUITS for r in RANKS]

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self) -> Card | None:
        if not self.cards:
            return None
        return self.cards.pop()

    def draw_many(self, n: int) -> list[Card]:
        drawn = []
        for _ in range(n):
            c = self.draw()
            if c is None:
                break
            drawn.append(c)
        return drawn

    def __len__(self) -> int:
        return len(self.cards)
