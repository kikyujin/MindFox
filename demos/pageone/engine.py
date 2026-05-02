"""ページワンデモ — ゲームエンジン"""
import random
from dataclasses import dataclass, field

from cards import Card, Deck, SPECIAL_RANKS
from characters import Character, AI_CHARACTERS
from lines import pick_start_line, pick_line
from memory import (
    check_pageone, do_reinforce, check_callout, get_score_snapshot,
    THRESHOLD, sigmoid_p,
)


@dataclass
class PageoneEvent:
    turn: int
    agent: str
    action: str  # "declared" | "forgot_called" | "forgot_safe"
    score: float
    temperature: float = 0.0
    probability: float = 0.0
    checker: str | None = None
    checker_score: float | None = None
    checker_temperature: float = 0.0
    checker_probability: float = 0.0
    is_miracle: bool = False


@dataclass
class PlayerState:
    char: Character
    hand: list[Card] = field(default_factory=list)


@dataclass
class GameResult:
    winner: str | None
    reason: str  # "empty_hand" | "all_pass"
    turns: int
    pageone_events: list[PageoneEvent] = field(default_factory=list)
    score_log: list[dict] = field(default_factory=list)


class GameState:
    def __init__(self, characters: list[Character]):
        self.deck = Deck()
        self.deck.shuffle()
        self.discard: list[Card] = []
        self.players = [PlayerState(c) for c in characters]
        self.direction = 1
        self.current_idx = 0
        self.pass_counter = 0
        self.draw2_pending = 0

        # 7枚ずつ配る
        for ps in self.players:
            ps.hand = self.deck.draw_many(7)

        # 台札を1枚めくる（特殊カードなら一般カードが出るまで）
        while True:
            top = self.deck.draw()
            if top is None:
                break
            if top.rank not in SPECIAL_RANKS:
                self.discard.append(top)
                break
            self.discard.insert(0, top)

        self.top_card: Card = self.discard[-1] if self.discard else Card("♠", 1)
        self.current_suit: str = self.top_card.suit


def can_play(card: Card, top_card: Card, current_suit: str) -> bool:
    if card.rank == 8:
        return True
    return card.suit == current_suit or card.rank == top_card.rank


def choose_card(hand: list[Card], top_card: Card, current_suit: str) -> Card | None:
    playable = [c for c in hand if can_play(c, top_card, current_suit)]
    if not playable:
        return None
    normal = [c for c in playable if c.rank not in SPECIAL_RANKS]
    if normal:
        return random.choice(normal)
    return random.choice(playable)


def choose_wild_suit(hand: list[Card]) -> str:
    from collections import Counter
    suits = Counter(c.suit for c in hand if c.rank != 8)
    if not suits:
        return random.choice(["♠", "♥", "♦", "♣"])
    return suits.most_common(1)[0][0]


def advance_player(gs: GameState, skip: int = 1):
    for _ in range(skip):
        gs.current_idx = (gs.current_idx + gs.direction) % len(gs.players)


def run_game(mxbs, characters: list[Character], global_turn: int,
             prev_losers: list[Character] | None = None,
             campaign_seed: int = 42, game_idx: int = 0,
             temperature_override: float | None = None) -> tuple[GameResult, int]:
    gs = GameState(characters)
    result = GameResult(winner=None, reason="", turns=0)

    # 開始セリフ
    for ps in gs.players:
        line = pick_start_line(ps.char.name, ps.hand)
        print(f"  {ps.char.name}: {line}")

    # heated セリフ（前ゲーム敗者）
    if prev_losers:
        for char in prev_losers:
            if not char.is_player:
                heated = pick_line(char.name, "heated")
                if heated:
                    print(f"  {char.name}: {heated}")

    # 初期スコア記録
    snapshot = get_score_snapshot(mxbs, characters, global_turn)
    result.score_log.append({"turn": global_turn, **snapshot})

    round_num = 0
    max_rounds = 200

    while round_num < max_rounds:
        round_num += 1
        global_turn += 1

        print(f"\n--- Turn {round_num} (global={global_turn}) ---")

        all_passed_this_round = True

        for _ in range(len(gs.players)):
            ps = gs.players[gs.current_idx]
            player_name = ps.char.name

            # ドロー2 ペナルティ処理
            if gs.draw2_pending > 0:
                # 2で返せるか
                twos = [c for c in ps.hand if c.rank == 2]
                if twos:
                    card = twos[0]
                    ps.hand.remove(card)
                    gs.discard.append(card)
                    gs.top_card = card
                    gs.current_suit = card.suit
                    gs.draw2_pending += 2
                    gs.pass_counter = 0
                    all_passed_this_round = False
                    print(f"  {player_name}: {card.display()} 出し（ドロー2返し！累積{gs.draw2_pending}枚）")
                    advance_player(gs)
                    continue
                else:
                    drawn = gs.deck.draw_many(gs.draw2_pending)
                    ps.hand.extend(drawn)
                    print(f"  {player_name}: ドロー2ペナルティ {len(drawn)}枚引き（残り{len(ps.hand)}枚）")
                    gs.draw2_pending = 0
                    gs.pass_counter = 0
                    all_passed_this_round = False
                    advance_player(gs)
                    continue

            # 通常プレイ
            card = choose_card(ps.hand, gs.top_card, gs.current_suit)

            if card:
                ps.hand.remove(card)
                gs.discard.append(card)
                gs.top_card = card
                gs.pass_counter = 0
                all_passed_this_round = False

                # ワイルド(8)でスート変更
                if card.rank == 8:
                    gs.current_suit = choose_wild_suit(ps.hand) if ps.hand else card.suit
                    print(f"  {player_name}: {card.display()} 出し（ワイルド→{gs.current_suit}）")
                elif card.rank == 12:  # Q: リバース
                    gs.current_suit = card.suit
                    gs.direction *= -1
                    print(f"  {player_name}: {card.display()} 出し（リバース）")
                elif card.rank == 11:  # J: スキップ
                    gs.current_suit = card.suit
                    print(f"  {player_name}: {card.display()} 出し（スキップ）")
                elif card.rank == 2:  # ドロー2
                    gs.current_suit = card.suit
                    gs.draw2_pending += 2
                    print(f"  {player_name}: {card.display()} 出し（ドロー2！）")
                else:
                    gs.current_suit = card.suit
                    print(f"  {player_name}: {card.display()} 出し")

                # 手札0 → 勝利
                if len(ps.hand) == 0:
                    win_line = pick_line(player_name, "win")
                    if win_line:
                        print(f"    🏆 {player_name}: {win_line}")
                    result.winner = player_name
                    result.reason = "empty_hand"
                    result.turns = round_num
                    snapshot = get_score_snapshot(mxbs, characters, global_turn)
                    result.score_log.append({"turn": global_turn, **snapshot})
                    return result, global_turn

                # ページワンチェック（残り1枚）
                if len(ps.hand) == 1:
                    _handle_pageone(mxbs, gs, ps, characters, global_turn, round_num, result,
                                    campaign_seed, game_idx, temperature_override)

                # スキップ処理
                if card.rank == 11:
                    advance_player(gs)  # 追加で1人飛ばす
                    skipped = gs.players[gs.current_idx]
                    print(f"    ⏭ {skipped.char.name} スキップ")

            elif len(gs.deck) > 0:
                drawn = gs.deck.draw()
                if drawn and can_play(drawn, gs.top_card, gs.current_suit):
                    gs.discard.append(drawn)
                    gs.top_card = drawn
                    gs.pass_counter = 0
                    all_passed_this_round = False

                    if drawn.rank == 8:
                        gs.current_suit = choose_wild_suit(ps.hand) if ps.hand else drawn.suit
                        print(f"  {player_name}: 引き → {drawn.display()} → 出し（ワイルド→{gs.current_suit}）")
                    elif drawn.rank == 12:
                        gs.current_suit = drawn.suit
                        gs.direction *= -1
                        print(f"  {player_name}: 引き → {drawn.display()} → 出し（リバース）")
                    elif drawn.rank == 11:
                        gs.current_suit = drawn.suit
                        print(f"  {player_name}: 引き → {drawn.display()} → 出し（スキップ）")
                    elif drawn.rank == 2:
                        gs.current_suit = drawn.suit
                        gs.draw2_pending += 2
                        print(f"  {player_name}: 引き → {drawn.display()} → 出し（ドロー2！）")
                    else:
                        gs.current_suit = drawn.suit
                        print(f"  {player_name}: 引き → {drawn.display()} → 出し")

                    if len(ps.hand) == 1:
                        _handle_pageone(mxbs, gs, ps, characters, global_turn, round_num, result,
                                        campaign_seed, game_idx, temperature_override)

                    if drawn.rank == 11:
                        advance_player(gs)
                        skipped = gs.players[gs.current_idx]
                        print(f"    ⏭ {skipped.char.name} スキップ")
                else:
                    if drawn:
                        ps.hand.append(drawn)
                    gs.pass_counter += 1
                    print(f"  {player_name}: 引き → 出せず（残り{len(ps.hand)}枚）")
            else:
                gs.pass_counter += 1
                print(f"  {player_name}: パス（山札なし、残り{len(ps.hand)}枚）")

            # 全員パス判定
            if gs.pass_counter >= len(gs.players):
                winner_ps = min(gs.players, key=lambda p: len(p.hand))
                result.winner = winner_ps.char.name
                result.reason = "all_pass"
                result.turns = round_num
                snapshot = get_score_snapshot(mxbs, characters, global_turn)
                result.score_log.append({"turn": global_turn, **snapshot})
                print(f"\n  ⚠ 全員パス — 手札最少: {winner_ps.char.name}（{len(winner_ps.hand)}枚）")
                return result, global_turn

            advance_player(gs)

        # 5ターンごとのスコアスナップショット + losing/comeback
        if round_num % 5 == 0:
            snapshot = get_score_snapshot(mxbs, characters, global_turn)
            result.score_log.append({"turn": global_turn, **snapshot})
            _check_losing_comeback(gs)

    result.winner = None
    result.reason = "max_rounds"
    result.turns = round_num
    return result, global_turn


def _handle_pageone(mxbs, gs: GameState, ps: PlayerState,
                    characters: list[Character], global_turn: int,
                    round_num: int, result: GameResult,
                    campaign_seed: int = 42, game_idx: int = 0,
                    temperature_override: float | None = None):
    player_name = ps.char.name
    print(f"    📋 残り1枚！")

    if ps.char.is_player:
        line = pick_line(player_name, "pageone")
        if line:
            print(f"    ✅ {player_name}: {line}")
        event = PageoneEvent(round_num, player_name, "declared", 1.0)
        result.pageone_events.append(event)
        return

    turn_seed = campaign_seed * 100000 + game_idx * 1000 + global_turn * 10 + ps.char.id
    remembered, score, temperature, prob = check_pageone(
        mxbs, ps.char, global_turn, turn_seed, temperature_override,
    )

    deterministic_hit = score >= THRESHOLD
    is_miracle = remembered and not deterministic_hit

    if remembered:
        line = pick_line(player_name, "pageone")
        miracle_tag = " (miracle!)" if is_miracle else ""
        print(f"    📋 ページワン検索: score={score:.2f}, T={temperature:.2f} → p={prob:.2f} → ✅ 宣言！{miracle_tag}")
        print(f"    {player_name}: {line}")
        event = PageoneEvent(round_num, player_name, "declared", score,
                             temperature, prob, is_miracle=is_miracle)
        result.pageone_events.append(event)
        do_reinforce(mxbs, characters, ps.char.id, global_turn)
    else:
        forgot_line = pick_line(player_name, "forgot")
        print(f"    📋 ページワン検索: score={score:.2f}, T={temperature:.2f} → p={prob:.2f} → ❌ 忘れた！")
        print(f"    {player_name}: {forgot_line}")

        callout_seed = turn_seed + 100
        checker_name, called, checker_score, checker_temp, checker_prob = check_callout(
            mxbs, ps.char.id, characters, global_turn, callout_seed, temperature_override,
        )

        if called:
            callout_line = pick_line(checker_name, "callout", target=player_name)
            called_out_line = pick_line(player_name, "called_out")
            print(f"    👀 指摘チェック: {checker_name} → score={checker_score:.2f}, T={checker_temp:.2f} → p={checker_prob:.2f} → 指摘！")
            print(f"    {checker_name}: {callout_line}")
            print(f"    {player_name}: {called_out_line}")

            drawn = gs.deck.draw_many(5)
            ps.hand.extend(drawn)
            print(f"    💀 ペナルティ: {player_name} {len(drawn)}枚ドロー（残り{len(ps.hand)}枚）")

            event = PageoneEvent(round_num, player_name, "forgot_called", score,
                                 temperature, prob,
                                 checker_name, checker_score,
                                 checker_temp, checker_prob)
        else:
            safe_line = pick_line(player_name, "safe")
            print(f"    👀 指摘チェック: {checker_name} → score={checker_score:.2f}, T={checker_temp:.2f} → p={checker_prob:.2f} → 指摘失敗")
            print(f"    {player_name}: {safe_line}")
            event = PageoneEvent(round_num, player_name, "forgot_safe", score,
                                 temperature, prob,
                                 checker_name, checker_score,
                                 checker_temp, checker_prob)

        result.pageone_events.append(event)


def _check_losing_comeback(gs: GameState):
    if not gs.players:
        return
    max_hand = max(len(ps.hand) for ps in gs.players)
    for ps in gs.players:
        if ps.char.is_player:
            continue
        if len(ps.hand) == max_hand and max_hand > 5:
            line = pick_line(ps.char.name, "losing")
            if line:
                print(f"    😰 {ps.char.name}: {line}")
        elif len(ps.hand) <= 3 and max_hand > 5:
            line = pick_line(ps.char.name, "comeback")
            if line:
                print(f"    💪 {ps.char.name}: {line}")
