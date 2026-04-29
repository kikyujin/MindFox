"""ページワンデモ — キャラクター定義"""
from dataclasses import dataclass


@dataclass
class Character:
    id: int
    name: str
    gender: str
    archetype: str
    pageone_price: int
    reinforce_factor: float
    is_player: bool = False

    @property
    def bit(self) -> int:
        return 1 << self.id


CHARACTERS = [
    Character(0, "マスター", "男性", "player",     0,   0.0,  is_player=True),
    Character(1, "エルマー", "女性", "analyst",   170,  0.4),
    Character(2, "ノクちん", "女性", "contrarian",  70,  0.1),
    Character(3, "スミレ",   "女性", "analyst",   220,  0.5),
    Character(4, "ティル",   "女性", "impulsive",   80,  0.1),
    Character(5, "ヴェリ",   "女性", "observer",  200,  0.5),
]

AI_CHARACTERS = [c for c in CHARACTERS if not c.is_player]
