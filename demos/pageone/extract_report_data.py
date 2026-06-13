"""Game 13 追加データ抽出 + 50ゲーム全体サマリー"""
import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_root, "mxbs", "python"))
sys.path.insert(0, os.path.join(_root, "mxmindfox", "python"))

from characters import CHARACTERS, AI_CHARACTERS
from memory import init_mxbs, inject_pageone_rule, get_score_snapshot, THRESHOLD, sigmoid_p
from engine import run_game, GameResult


def run_campaign(games, seed, temperature_override, reinject=True, half_life=8):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mxbs = init_mxbs(db_path, half_life)
        inject_pageone_rule(mxbs, CHARACTERS, turn=0)
        global_turn = 0
        prev_losers = None
        results = []
        random.seed(seed)
        for game_num in range(1, games + 1):
            if reinject and game_num > 1:
                inject_pageone_rule(mxbs, CHARACTERS, turn=global_turn)
            result, global_turn = run_game(
                mxbs, CHARACTERS, global_turn, prev_losers,
                campaign_seed=seed, game_idx=game_num,
                temperature_override=temperature_override,
            )
            results.append(result)
            if result.winner:
                prev_losers = [c for c in CHARACTERS if c.name != result.winner]
            else:
                prev_losers = None
        return results, mxbs
    except Exception:
        if os.path.exists(db_path):
            os.remove(db_path)
        raise


def extract_game13_scores(results, mxbs):
    """Game 13 の全ターンスコア推移を score_log から取得"""
    if len(results) < 13:
        return None
    r13 = results[12]
    return {
        "game": 13,
        "turns": r13.turns,
        "winner": r13.winner,
        "score_log": r13.score_log,
        "pageone_events": [
            {
                "turn": ev.turn,
                "agent": ev.agent,
                "action": ev.action,
                "score": round(ev.score, 4),
                "temperature": round(ev.temperature, 4),
                "probability": round(ev.probability, 4),
                "is_miracle": ev.is_miracle,
                "checker": ev.checker,
                "checker_score": round(ev.checker_score, 4) if ev.checker_score else None,
            }
            for ev in r13.pageone_events
        ],
    }


def extract_win_summary(results):
    """50ゲーム全体の勝率サマリー"""
    wins = {c.name: 0 for c in CHARACTERS}
    for r in results:
        if r.winner:
            wins[r.winner] = wins.get(r.winner, 0) + 1
    total = len(results)
    summary = []
    for c in CHARACTERS:
        w = wins[c.name]
        summary.append({
            "name": c.name,
            "wins": w,
            "win_rate": round(w / total, 4) if total > 0 else 0,
            "archetype": c.archetype if not c.is_player else "player",
            "price": c.pageone_price,
        })
    summary.sort(key=lambda x: x["wins"], reverse=True)
    return summary


def extract_miracle_events(results):
    """全miracle判定の詳細"""
    miracles = []
    for i, r in enumerate(results):
        for ev in r.pageone_events:
            if ev.is_miracle:
                miracles.append({
                    "game": i + 1,
                    "turn": ev.turn,
                    "agent": ev.agent,
                    "score": round(ev.score, 4),
                    "threshold": THRESHOLD,
                    "temperature": round(ev.temperature, 4),
                    "probability": round(ev.probability, 4),
                    "gap": round(ev.score - THRESHOLD, 4),
                })
    return miracles


def main():
    print("=" * 60)
    print("① Condition B (archetype-T): 50ゲーム実行中...")
    print("=" * 60)

    # suppress game output
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    results_b, mxbs_b = run_campaign(50, seed=42, temperature_override=None, reinject=True)

    sys.stdout = old_stdout

    print("② Condition A (T=0): 50ゲーム実行中...")
    sys.stdout = io.StringIO()

    results_a, mxbs_a = run_campaign(50, seed=42, temperature_override=0.0, reinject=True)

    sys.stdout = old_stdout

    # --- ① Game 13 スコア推移 ---
    g13_b = extract_game13_scores(results_b, mxbs_b)
    g13_a = extract_game13_scores(results_a, mxbs_a)

    # --- ② v0.3.0 vs v0.4 Game 13 比較 ---
    comparison = {
        "v0.4_archetype": {
            "winner": g13_b["winner"] if g13_b else None,
            "turns": g13_b["turns"] if g13_b else None,
            "pageone_events": g13_b["pageone_events"] if g13_b else [],
        },
        "v0.3_deterministic": {
            "winner": g13_a["winner"] if g13_a else None,
            "turns": g13_a["turns"] if g13_a else None,
            "pageone_events": g13_a["pageone_events"] if g13_a else [],
        },
    }

    # --- ③ 50ゲーム勝率 ---
    wins_b = extract_win_summary(results_b)
    wins_a = extract_win_summary(results_a)

    # --- ④ miracle 判定 ---
    miracles = extract_miracle_events(results_b)

    # --- 出力 ---
    output = {
        "game13_score_log": g13_b["score_log"] if g13_b else [],
        "game13_comparison": comparison,
        "win_summary_archetype": wins_b,
        "win_summary_deterministic": wins_a,
        "miracle_events": miracles,
        "miracle_total": len(miracles),
    }

    out_path = os.path.join(os.path.dirname(__file__), "results", "v0.4_report_extra.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # --- コンソール出力 ---
    print("\n" + "=" * 60)
    print("① Game 13 忘却推移（Condition B: archetype-T）")
    print("=" * 60)
    if g13_b:
        names = [c.name for c in AI_CHARACTERS]
        print(f"  {'Turn':>5s} | " + " | ".join(f"{n:>8s}" for n in names))
        print("  " + "-" * 65)
        for snap in g13_b["score_log"]:
            t = snap["turn"]
            vals = " | ".join(f"{snap.get(n, 0.0):8.4f}" for n in names)
            print(f"  {t:5d} | {vals}")
        print(f"\n  threshold = {THRESHOLD}")

    print("\n" + "=" * 60)
    print("② Game 13 比較: v0.4 (archetype-T) vs v0.3.0 (T=0)")
    print("=" * 60)
    for label, key in [("v0.4 archetype-T", "v0.4_archetype"), ("v0.3.0 T=0", "v0.3_deterministic")]:
        c = comparison[key]
        print(f"\n  [{label}]")
        print(f"  勝者: {c['winner']} ({c['turns']} turns)")
        for ev in c["pageone_events"]:
            miracle = " ★MIRACLE" if ev.get("is_miracle") else ""
            checker_str = f" → {ev['checker']}指摘(score={ev['checker_score']:.2f})" if ev.get("checker") else ""
            print(f"    Turn {ev['turn']}: {ev['agent']} score={ev['score']:.2f} T={ev['temperature']:.2f} p={ev['probability']:.2f} → {ev['action']}{miracle}{checker_str}")

    print("\n" + "=" * 60)
    print("③ 50ゲーム勝率サマリー")
    print("=" * 60)
    print("\n  [Condition B: archetype-T]")
    print(f"  {'キャラ':8s} | archetype  | price | 勝数 | 勝率")
    print(f"  {'-'*8}-+{'-'*11}+-------+------+------")
    for w in wins_b:
        print(f"  {w['name']:8s} | {w['archetype']:10s} | {w['price']:5d} | {w['wins']:4d} | {w['win_rate']*100:5.1f}%")

    print("\n  [Condition A: T=0 (v0.3.0 互換)]")
    print(f"  {'キャラ':8s} | archetype  | price | 勝数 | 勝率")
    print(f"  {'-'*8}-+{'-'*11}+-------+------+------")
    for w in wins_a:
        print(f"  {w['name']:8s} | {w['archetype']:10s} | {w['price']:5d} | {w['wins']:4d} | {w['win_rate']*100:5.1f}%")

    print("\n" + "=" * 60)
    print(f"④ miracle 判定 一覧（全{len(miracles)}件）")
    print("=" * 60)
    if miracles:
        print(f"  {'Game':>4s} | {'Turn':>4s} | {'キャラ':8s} | score  | T     | p     | gap")
        print(f"  {'-'*4}-+{'-'*5}+{'-'*9}+--------+-------+-------+-------")
        for m in miracles:
            print(f"  {m['game']:4d} | {m['turn']:4d} | {m['agent']:8s} | {m['score']:.4f} | {m['temperature']:.2f}  | {m['probability']:.4f} | {m['gap']:+.4f}")
    else:
        print("  なし")

    print(f"\n📄 JSON出力: {out_path}")


if __name__ == "__main__":
    main()
