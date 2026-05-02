"""ページワンデモ — MxBS忘却定量テスト + MxMindFox temperature 揺らぎ (v0.4)"""
import argparse
import json
import math
import os
import random
import time

from characters import CHARACTERS, AI_CHARACTERS
from memory import init_mxbs, inject_pageone_rule, get_score_snapshot, THRESHOLD
from engine import run_game, GameResult


def print_game_summary(result: GameResult, game_num: int):
    print(f"\n{'='*50}")
    print(f"=== Game {game_num} Summary ({result.turns} turns) ===")
    print(f"勝者: {result.winner or '引き分け'} ({result.reason})")

    if result.pageone_events:
        print(f"\n📊 ページワン宣言イベント:")
        for ev in result.pageone_events:
            t_str = f", T={ev.temperature:.2f}, p={ev.probability:.2f}" if ev.temperature > 0 else ""
            if ev.action == "declared":
                miracle = " (miracle!)" if ev.is_miracle else ""
                print(f"  Turn {ev.turn:3d}: {ev.agent} → 残1 → score={ev.score:.2f}{t_str} → ✅ 宣言{miracle}")
            elif ev.action == "forgot_called":
                print(f"  Turn {ev.turn:3d}: {ev.agent} → 残1 → score={ev.score:.2f}{t_str} → ❌ 忘れ → {ev.checker}指摘(score={ev.checker_score:.2f}) → 5枚ドロー")
            elif ev.action == "forgot_safe":
                print(f"  Turn {ev.turn:3d}: {ev.agent} → 残1 → score={ev.score:.2f}{t_str} → ❌ 忘れ → {ev.checker}指摘失敗({ev.checker_score:.2f}) → セーフ！")

    if result.score_log:
        print(f"\n📈 忘却推移（ページワンルールセル effective_score）:")
        names = [c.name for c in AI_CHARACTERS]
        header = "  Turn | " + " | ".join(f"{n:>6s}" for n in names)
        print(header)
        print("  " + "-" * (len(header) - 2))
        for snap in result.score_log:
            turn_str = f"{snap['turn']:5d}"
            scores = " | ".join(f"{snap.get(n, 0.0):6.2f}" for n in names)
            print(f"  {turn_str} | {scores}")


def print_campaign_summary(all_results: list[GameResult], elapsed: float):
    total_turns = sum(r.turns for r in all_results)
    n_games = len(all_results)

    print(f"\n{'='*60}")
    print(f"=== Campaign Summary ({n_games} games, {total_turns} turns total, elapsed {elapsed:.0f}s) ===")

    stats: dict[str, dict] = {}
    for c in AI_CHARACTERS:
        stats[c.name] = {
            "price": c.pageone_price,
            "opportunities": 0,
            "forgot": 0,
            "called_out": 0,
            "safe": 0,
            "callout_opportunities": 0,
            "callout_success": 0,
            "callout_fail": 0,
            "first_forget_turns": [],
            "miracle_remembers": 0,
            "total_pageone_events": 0,
        }

    for result in all_results:
        declared_turns: dict[str, list[int]] = {c.name: [] for c in AI_CHARACTERS}
        for ev in result.pageone_events:
            if ev.agent == "マスター":
                continue
            s = stats[ev.agent]
            s["opportunities"] += 1
            s["total_pageone_events"] += 1

            if ev.action == "declared":
                declared_turns[ev.agent].append(ev.turn)
                if ev.is_miracle:
                    s["miracle_remembers"] += 1
            elif ev.action == "forgot_called":
                s["forgot"] += 1
                s["called_out"] += 1
                if not declared_turns[ev.agent]:
                    s["first_forget_turns"].append(ev.turn)
            elif ev.action == "forgot_safe":
                s["forgot"] += 1
                s["safe"] += 1
                if not declared_turns[ev.agent]:
                    s["first_forget_turns"].append(ev.turn)

            if ev.checker and ev.checker != "マスター":
                cs = stats[ev.checker]
                cs["callout_opportunities"] += 1
                if ev.action == "forgot_called":
                    cs["callout_success"] += 1
                elif ev.action == "forgot_safe":
                    cs["callout_fail"] += 1

    print(f"\n🎯 ページワン忘却率:")
    print(f"  {'キャラ':8s} | price | 宣言機会 | 忘れた | 忘却率  | miracle | 指摘された | 逃げた")
    print(f"  {'-'*8}-+-------+----------+--------+---------+---------+-----------+-------")
    for c in AI_CHARACTERS:
        s = stats[c.name]
        rate = (s["forgot"] / s["opportunities"] * 100) if s["opportunities"] > 0 else 0.0
        print(f"  {c.name:8s} | {s['price']:5d} | {s['opportunities']:8d} | {s['forgot']:6d} | {rate:5.1f}%  | {s['miracle_remembers']:7d} | {s['called_out']:9d} | {s['safe']:5d}")

    print(f"\n🔔 指摘成功率（指摘者として）:")
    print(f"  {'キャラ':8s} | 指摘機会 | 成功 | 失敗（自分も忘れてた）")
    print(f"  {'-'*8}-+----------+------+---------------------")
    for c in AI_CHARACTERS:
        s = stats[c.name]
        print(f"  {c.name:8s} | {s['callout_opportunities']:8d} | {s['callout_success']:4d} | {s['callout_fail']:4d}")

    print(f"\n📉 price vs 忘却ターン（初回忘却までのターン数）:")
    for c in AI_CHARACTERS:
        s = stats[c.name]
        turns = s["first_forget_turns"]
        if turns:
            avg = sum(turns) / len(turns)
            if len(turns) > 1:
                variance = sum((t - avg) ** 2 for t in turns) / len(turns)
                sigma = math.sqrt(variance)
            else:
                sigma = 0.0
            print(f"  price {s['price']:3d} ({c.name}): 平均 {avg:.1f} ターン (σ={sigma:.1f}, n={len(turns)})")
        else:
            print(f"  price {s['price']:3d} ({c.name}): 忘却なし (n={s['opportunities']})")

    miracle_events = []
    for result in all_results:
        for ev in result.pageone_events:
            if ev.is_miracle:
                miracle_events.append(ev)
    if miracle_events:
        print(f"\n🎲 揺らぎイベント（miracle_remembers）:")
        for ev in miracle_events:
            print(f"  Turn {ev.turn:3d}: {ev.agent} の奇跡的記憶（score={ev.score:.2f}, T={ev.temperature:.2f}, p={ev.probability:.2f}）")

    return stats


def build_json_summary(
    all_results, stats, condition, temperature_mode, seed, elapsed,
    temperature_value=None, reinject=False,
):
    total_turns = sum(r.turns for r in all_results)
    by_character = {}
    for c in AI_CHARACTERS:
        s = stats[c.name]
        opps = s["opportunities"]
        rate = s["forgot"] / opps if opps > 0 else 0.0
        temp = temperature_value if temperature_value is not None else None
        if temp is None:
            from memory import _init_mxmf
            mxmf, mood_preset = _init_mxmf()
            mood = mxmf.compute_mood(mood_preset, [], archetype=c.archetype)
            temp = mood["axes"].get("temperature", 0.0)
        by_character[c.name] = {
            "price": c.pageone_price,
            "archetype": c.archetype,
            "T": round(temp, 4),
            "forget_rate": round(rate, 4),
            "miracle_remembers": s["miracle_remembers"],
            "total_pageone_events": s["total_pageone_events"],
            "forgot": s["forgot"],
            "opportunities": opps,
        }

    callout_stats = {}
    for c in AI_CHARACTERS:
        s = stats[c.name]
        attempts = s["callout_opportunities"]
        successes = s["callout_success"]
        rate = successes / attempts if attempts > 0 else 0.0
        callout_stats[c.name] = {
            "successes": successes,
            "attempts": attempts,
            "rate": round(rate, 4),
        }

    return {
        "version": "0.4.0",
        "condition": condition,
        "temperature_mode": temperature_mode,
        "reinject": reinject,
        "seed": seed,
        "num_games": len(all_results),
        "total_turns": total_turns,
        "elapsed_seconds": round(elapsed, 2),
        "by_character": by_character,
        "callout_stats": callout_stats,
    }


def print_mxbs_stats(mxbs):
    stats = mxbs.stats()
    if stats:
        print(f"\nMxBS stats: total={stats.get('total', '?')} cells, "
              f"scored={stats.get('scored', '?')}, unscored={stats.get('unscored', '?')}")


def main():
    parser = argparse.ArgumentParser(description="ページワンデモ — MxBS忘却テスト + MxMindFox v0.4")
    parser.add_argument("--games", type=int, default=1, help="キャンペーンゲーム数")
    parser.add_argument("--half-life", type=int, default=8, help="MxBS half_life")
    parser.add_argument("--threshold", type=float, default=0.3, help="search hit 閾値")
    parser.add_argument("--seed", type=int, default=None, help="ランダムシード")
    parser.add_argument("--temperature-mode", choices=["zero", "archetype", "uniform"],
                        default="archetype", help="temperature 適用モード")
    parser.add_argument("--temperature", type=float, default=0.10,
                        help="uniform モードでの temperature 値")
    parser.add_argument("--reinject", action="store_true",
                        help="毎ゲーム開始時にルール再注入（v0.3.0 条件A 互換）")
    parser.add_argument("--output-json", action="store_true",
                        help="JSON サマリーをファイル出力")
    args = parser.parse_args()

    campaign_seed = args.seed if args.seed is not None else 42
    random.seed(campaign_seed)

    import memory
    memory.THRESHOLD = args.threshold

    if args.temperature_mode == "zero":
        temperature_override = 0.0
        condition = "A"
    elif args.temperature_mode == "uniform":
        temperature_override = args.temperature
        condition = "C"
    else:
        temperature_override = None
        condition = "B"

    db_path = os.path.join(os.path.dirname(__file__), "pageone.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    mxbs = init_mxbs(db_path, args.half_life)
    inject_pageone_rule(mxbs, CHARACTERS, turn=0)

    global_turn = 0
    prev_losers = None
    all_results = []
    start_time = time.time()

    for game_num in range(1, args.games + 1):
        print(f"\n{'='*50}")
        print(f"🃏 Game {game_num}")
        print(f"{'='*50}")

        if args.reinject and game_num > 1:
            inject_pageone_rule(mxbs, CHARACTERS, turn=global_turn)

        result, global_turn = run_game(
            mxbs, CHARACTERS, global_turn, prev_losers,
            campaign_seed=campaign_seed, game_idx=game_num,
            temperature_override=temperature_override,
        )
        all_results.append(result)

        if result.winner:
            prev_losers = [c for c in CHARACTERS if c.name != result.winner]
        else:
            prev_losers = None

        print_game_summary(result, game_num)

    elapsed = time.time() - start_time

    stats = None
    if args.games > 1:
        stats = print_campaign_summary(all_results, elapsed)

    print_mxbs_stats(mxbs)

    if args.output_json and stats:
        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)

        if args.temperature_mode == "zero":
            fname = f"v0.4_A_zero_seed{campaign_seed}.json"
        elif args.temperature_mode == "archetype":
            fname = f"v0.4_B_archetype_seed{campaign_seed}.json"
        else:
            fname = f"v0.4_C_uniform_t{args.temperature:.2f}_seed{campaign_seed}.json"

        summary = build_json_summary(
            all_results, stats, condition, args.temperature_mode,
            campaign_seed, elapsed,
            temperature_value=temperature_override if args.temperature_mode != "archetype" else None,
            reinject=args.reinject,
        )
        out_path = os.path.join(results_dir, fname)
        with open(out_path, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n📄 JSON サマリー出力: {out_path}")


if __name__ == "__main__":
    main()
