"""Game 13 全ターンスコア推移抽出（グラフ用）"""
import json
import os
import random
import sys
import tempfile
import io

sys.path.insert(0, os.path.dirname(__file__))
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_root, "mxbs", "python"))
sys.path.insert(0, os.path.join(_root, "mxmindfox", "python"))

from characters import CHARACTERS, AI_CHARACTERS
from memory import init_mxbs, inject_pageone_rule, get_score_snapshot, THRESHOLD

# Monkey-patch engine to record every-turn scores
import engine as eng

_original_run_game = eng.run_game

def _patched_run_game(mxbs, characters, global_turn, prev_losers=None,
                      campaign_seed=42, game_idx=0, temperature_override=None):
    # We need to inject per-turn scoring. Patch get_score_snapshot calls
    # Instead, we'll record scores before and after each turn by wrapping advance
    result, new_gt = _original_run_game(
        mxbs, characters, global_turn, prev_losers,
        campaign_seed=campaign_seed, game_idx=game_idx,
        temperature_override=temperature_override,
    )
    return result, new_gt


def run_campaign_to_game13(seed, temperature_override, reinject=True, half_life=8):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mxbs = init_mxbs(db_path, half_life)
        inject_pageone_rule(mxbs, CHARACTERS, turn=0)
        global_turn = 0
        prev_losers = None
        random.seed(seed)
        for game_num in range(1, 51):
            if reinject and game_num > 1:
                inject_pageone_rule(mxbs, CHARACTERS, turn=global_turn)
            result, global_turn = eng.run_game(
                mxbs, CHARACTERS, global_turn, prev_losers,
                campaign_seed=seed, game_idx=game_num,
                temperature_override=temperature_override,
            )
            if result.winner:
                prev_losers = [c for c in CHARACTERS if c.name != result.winner]
            else:
                prev_losers = None
            if game_num == 13:
                return result, mxbs, global_turn
        return None, mxbs, global_turn
    except Exception:
        if os.path.exists(db_path):
            os.remove(db_path)
        raise


def run_with_per_turn_scores(seed, temperature_override, reinject=True, half_life=8):
    """Run 12 games normally, then run Game 13 with per-turn score tracking"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mxbs = init_mxbs(db_path, half_life)
        inject_pageone_rule(mxbs, CHARACTERS, turn=0)
        global_turn = 0
        prev_losers = None
        random.seed(seed)

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        # Run games 1-12 normally
        for game_num in range(1, 13):
            if reinject and game_num > 1:
                inject_pageone_rule(mxbs, CHARACTERS, turn=global_turn)
            result, global_turn = eng.run_game(
                mxbs, CHARACTERS, global_turn, prev_losers,
                campaign_seed=seed, game_idx=game_num,
                temperature_override=temperature_override,
            )
            if result.winner:
                prev_losers = [c for c in CHARACTERS if c.name != result.winner]
            else:
                prev_losers = None

        sys.stdout = old_stdout

        # Now for Game 13, record score at every global_turn
        if reinject:
            inject_pageone_rule(mxbs, CHARACTERS, turn=global_turn)

        game13_start_turn = global_turn
        # Record initial scores
        per_turn_scores = []
        snap = get_score_snapshot(mxbs, CHARACTERS, global_turn)
        per_turn_scores.append({"global_turn": global_turn, "local_turn": 0, **snap})

        sys.stdout = io.StringIO()

        # We need to manually advance turns and record.
        # Simpler: run the game, but poll mxbs scores at each global turn after
        # Since MxBS decay is time-based, we can query retroactively for each turn
        result13, new_gt = eng.run_game(
            mxbs, CHARACTERS, global_turn, prev_losers,
            campaign_seed=seed, game_idx=13,
            temperature_override=temperature_override,
        )

        sys.stdout = old_stdout

        # Record scores for each turn in the game
        game_turns = result13.turns
        for local_t in range(1, game_turns + 1):
            gt = game13_start_turn + local_t
            snap = get_score_snapshot(mxbs, CHARACTERS, gt)
            per_turn_scores.append({"global_turn": gt, "local_turn": local_t, **snap})

        return result13, per_turn_scores, game13_start_turn
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def main():
    print("Game 13 per-turn score 抽出中 (archetype-T)...")
    result_b, scores_b, start_b = run_with_per_turn_scores(42, temperature_override=None)

    print("Game 13 per-turn score 抽出中 (T=0)...")
    result_a, scores_a, start_a = run_with_per_turn_scores(42, temperature_override=0.0)

    names = [c.name for c in AI_CHARACTERS]

    print("\n" + "=" * 70)
    print("Game 13 全ターンスコア推移 [Condition B: archetype-T]")
    print(f"  勝者: {result_b.winner} ({result_b.turns} turns)")
    print("=" * 70)
    print(f"  {'G.Turn':>6s} | {'Local':>5s} | " + " | ".join(f"{n:>8s}" for n in names))
    print("  " + "-" * 70)
    for s in scores_b:
        gt = s["global_turn"]
        lt = s["local_turn"]
        vals = " | ".join(f"{s.get(n, 0.0):8.4f}" for n in names)
        marker = ""
        if lt == 8:
            marker = "  ← ティル miracle + ノクちん忘却"
        print(f"  {gt:6d} | {lt:5d} | {vals}{marker}")

    print(f"\n  threshold = {THRESHOLD}")

    print("\n" + "=" * 70)
    print("Game 13 全ターンスコア推移 [Condition A: T=0]")
    print(f"  勝者: {result_a.winner} ({result_a.turns} turns)")
    print("=" * 70)
    print(f"  {'G.Turn':>6s} | {'Local':>5s} | " + " | ".join(f"{n:>8s}" for n in names))
    print("  " + "-" * 70)
    for s in scores_a:
        gt = s["global_turn"]
        lt = s["local_turn"]
        vals = " | ".join(f"{s.get(n, 0.0):8.4f}" for n in names)
        print(f"  {gt:6d} | {lt:5d} | {vals}")

    # CSV for graphing
    csv_path = os.path.join(os.path.dirname(__file__), "results", "game13_scores_archetype.csv")
    with open(csv_path, "w") as f:
        f.write("global_turn,local_turn," + ",".join(names) + ",threshold\n")
        for s in scores_b:
            vals = ",".join(f"{s.get(n, 0.0):.6f}" for n in names)
            f.write(f"{s['global_turn']},{s['local_turn']},{vals},{THRESHOLD}\n")
    print(f"\n📄 CSV出力: {csv_path}")

    csv_path2 = os.path.join(os.path.dirname(__file__), "results", "game13_scores_deterministic.csv")
    with open(csv_path2, "w") as f:
        f.write("global_turn,local_turn," + ",".join(names) + ",threshold\n")
        for s in scores_a:
            vals = ",".join(f"{s.get(n, 0.0):.6f}" for n in names)
            f.write(f"{s['global_turn']},{s['local_turn']},{vals},{THRESHOLD}\n")
    print(f"📄 CSV出力: {csv_path2}")

    # Update JSON
    json_path = os.path.join(os.path.dirname(__file__), "results", "v0.4_report_extra.json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)
    else:
        data = {}

    data["game13_per_turn_scores_archetype"] = scores_b
    data["game13_per_turn_scores_deterministic"] = scores_a
    data["game13_start_global_turn"] = start_b

    with open(json_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"📄 JSON更新: {json_path}")


if __name__ == "__main__":
    main()
