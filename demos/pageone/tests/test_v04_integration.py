"""ページワン v0.4 統合テスト"""
import json
import os
import random
import sys
import tempfile

_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_root = os.path.abspath(os.path.join(_base, "..", ".."))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_root, "mxbs", "python"))
sys.path.insert(0, os.path.join(_root, "mxmindfox", "python"))

from characters import CHARACTERS, AI_CHARACTERS
from memory import init_mxbs, inject_pageone_rule, check_pageone, check_callout, sigmoid_p, THRESHOLD
from engine import run_game, GameResult


def _run_campaign(games, seed, temperature_override, reinject=True, half_life=8):
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
        return results
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def _forget_rate(results, char_name):
    total = 0
    forgot = 0
    for r in results:
        for ev in r.pageone_events:
            if ev.agent == char_name:
                total += 1
                if ev.action in ("forgot_called", "forgot_safe"):
                    forgot += 1
    return forgot / total if total > 0 else 0.0


def _miracle_count(results, char_name):
    count = 0
    for r in results:
        for ev in r.pageone_events:
            if ev.agent == char_name and ev.is_miracle:
                count += 1
    return count


def test_t_zero_matches_v03_behavior():
    results = _run_campaign(50, seed=42, temperature_override=0.0, reinject=True)

    assert abs(_forget_rate(results, "スミレ") - 0.0) < 0.001
    assert abs(_forget_rate(results, "ヴェリ") - 0.0) < 0.001
    assert abs(_forget_rate(results, "エルマー") - 0.05) < 0.001
    assert abs(_forget_rate(results, "ティル") - 1.0) < 0.001
    assert abs(_forget_rate(results, "ノクちん") - 1.0) < 0.001

    total_turns = sum(r.turns for r in results)
    assert total_turns == 419


def test_seed_reproducibility():
    r1 = _run_campaign(10, seed=123, temperature_override=None, reinject=True)
    r2 = _run_campaign(10, seed=123, temperature_override=None, reinject=True)

    for i in range(len(r1)):
        assert r1[i].winner == r2[i].winner
        assert r1[i].turns == r2[i].turns
        assert len(r1[i].pageone_events) == len(r2[i].pageone_events)
        for e1, e2 in zip(r1[i].pageone_events, r2[i].pageone_events):
            assert e1.agent == e2.agent
            assert e1.action == e2.action
            assert abs(e1.score - e2.score) < 0.001


def test_archetype_t_creates_miracle_remembers():
    results = _run_campaign(50, seed=42, temperature_override=None, reinject=True)
    assert _miracle_count(results, "ティル") > 0
    assert _miracle_count(results, "ノクちん") > 0


def test_high_uniform_t_blurs_archetype_difference():
    results_b = _run_campaign(50, seed=42, temperature_override=None, reinject=True)
    results_c = _run_campaign(50, seed=42, temperature_override=0.10, reinject=True)

    b_sumire = _forget_rate(results_b, "スミレ")
    b_tiru = _forget_rate(results_b, "ティル")
    b_diff = b_tiru - b_sumire

    c_sumire = _forget_rate(results_c, "スミレ")
    c_tiru = _forget_rate(results_c, "ティル")
    c_diff = c_tiru - c_sumire

    assert c_diff < b_diff


def test_sigmoid_p_deterministic_at_zero():
    assert sigmoid_p(0.5, 0.3, 0.0) == 1.0
    assert sigmoid_p(0.2, 0.3, 0.0) == 0.0
    assert sigmoid_p(0.3, 0.3, 0.0) == 1.0


def test_sigmoid_p_probabilistic():
    p = sigmoid_p(0.2, 0.3, 0.20)
    assert 0.0 < p < 1.0
    assert abs(p - 0.378) < 0.01
