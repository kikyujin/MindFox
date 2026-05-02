import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from mxmindfox_bridge import MxMindFox


PRESET_DICT = {
    "name": "test",
    "version": "1.0",
    "axes": [
        {
            "name": "temperature",
            "positive_factors": [0],
            "negative_factors": [],
            "default_value": 0.05,
            "clamp_min": 0.0,
            "clamp_max": 1.0,
        }
    ],
    "archetype_baselines": {"impulsive": {"temperature": 0.20}},
}


def test_version():
    mxmf = MxMindFox()
    v = mxmf.version()
    assert v.startswith("0.1"), f"version = {v}"
    print(f"  version: {v}")


def test_preset_roundtrip():
    mxmf = MxMindFox()
    preset = mxmf.load_preset(PRESET_DICT)
    mood = mxmf.compute_mood(preset, [], archetype="impulsive")
    temp = mood["axes"]["temperature"]
    assert abs(temp - 0.20) < 1e-6, f"temperature = {temp}"
    print(f"  impulsive temperature: {temp}")


def test_compute_mood_no_archetype():
    mxmf = MxMindFox()
    preset = mxmf.load_preset(PRESET_DICT)
    mood = mxmf.compute_mood(preset, [], archetype=None)
    temp = mood["axes"]["temperature"]
    assert abs(temp - 0.05) < 1e-6, f"temperature = {temp}"
    print(f"  default temperature: {temp}")


def test_decision_remember_t0():
    mxmf = MxMindFox()
    assert mxmf.decision_remember(0.5, 0.3, 0.0, seed=42) == True
    assert mxmf.decision_remember(0.2, 0.3, 0.0, seed=42) == False
    print("  T=0 deterministic: OK")


def test_decision_remember_reproducible():
    mxmf = MxMindFox()
    r1 = [mxmf.decision_remember(0.3, 0.3, 0.1, seed=i) for i in range(100)]
    r2 = [mxmf.decision_remember(0.3, 0.3, 0.1, seed=i) for i in range(100)]
    assert r1 == r2
    print("  reproducible: OK")


def test_decision_sample_t0_argmax():
    mxmf = MxMindFox()
    cands = [
        {"index": 0, "score": 0.1},
        {"index": 1, "score": 0.9},
        {"index": 2, "score": 0.5},
    ]
    chosen = mxmf.decision_sample(cands, temperature=0.0, seed=42)
    assert chosen == 1, f"chosen = {chosen}"
    print(f"  argmax: index={chosen}")


def test_adjust_threshold():
    mxmf = MxMindFox()
    mood = {"axes": {"aggression": 0.8}}
    rules = [{"mood_axis": "aggression", "coefficient": -0.3}]
    adjusted = mxmf.adjust_threshold(0.6, mood, rules)
    expected = 0.6 + 0.8 * (-0.3)
    assert abs(adjusted - expected) < 1e-5, f"adjusted = {adjusted}"
    print(f"  threshold: {adjusted:.4f}")


if __name__ == "__main__":
    tests = [
        test_version,
        test_preset_roundtrip,
        test_compute_mood_no_archetype,
        test_decision_remember_t0,
        test_decision_remember_reproducible,
        test_decision_sample_t0_argmax,
        test_adjust_threshold,
    ]
    passed = 0
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {name} — {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
    if failed:
        sys.exit(1)
