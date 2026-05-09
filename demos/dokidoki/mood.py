"""Mood 算出 — 三者積 (personality × mood × input) ベース"""

import os

MOOD_AXES = {
    "fondness": {
        "positive": [0, 5, 10],   # affection, excitement, comfort
        "negative": [6, 11],      # irritation, distance
        "default": 0.3,
    },
    "tension": {
        "positive": [2, 5, 8],    # shyness, excitement, rivalry
        "negative": [10, 3],      # comfort, trust
        "default": 0.3,
    },
    "jealousy_mood": {
        "positive": [1, 8, 14],   # jealousy, rivalry, possessiveness
        "negative": [3, 10],      # trust, comfort
        "default": 0.2,
    },
    "openness": {
        "positive": [3, 7, 13],   # trust, curiosity, vulnerability
        "negative": [4, 11],      # loneliness, distance
        "default": 0.3,
    },
}

FACTOR_NAMES = [
    "affection", "jealousy", "shyness", "trust",
    "loneliness", "excitement", "irritation", "curiosity",
    "rivalry", "protectiveness", "comfort", "distance",
    "admiration", "vulnerability", "possessiveness", "warmth",
]

LOG_TRIAD = os.environ.get("DOKIDOKI_LOG_TRIAD", "0") == "1"


def compute_mood(cells: list[dict], npc_id: int, personality: list[int]) -> dict:
    p = [v / 255.0 for v in personality]

    if not cells:
        return _baseline_from_personality(p)

    mood_vector = [p[i] * 0.3 for i in range(16)]

    scored_cells = [c for c in cells if any(f != 0 for f in c.get("features", [0] * 16))]
    recent = scored_cells[-8:]

    for cell in recent:
        features = cell.get("features", [0] * 16)
        f = [v / 255.0 for v in features]
        is_own = (cell.get("owner") == npc_id)

        if is_own:
            for i in range(16):
                mood_vector[i] += p[i] * f[i] * 0.1
        else:
            if LOG_TRIAD:
                _log_triad(npc_id, cell, p, mood_vector, f)
            for i in range(16):
                mood_vector[i] += p[i] * mood_vector[i] * f[i] * 0.1

    mood_vector = [max(0.0, min(1.0, v)) for v in mood_vector]

    return _aggregate_to_axes(mood_vector)


def _baseline_from_personality(p: list[float]) -> dict:
    mood = {}
    for axis_name, axis_def in MOOD_AXES.items():
        pos = sum(p[i] for i in axis_def["positive"])
        neg = sum(p[i] for i in axis_def["negative"])
        n = max(len(axis_def["positive"]) + len(axis_def["negative"]), 1)
        mood[axis_name] = max(0.0, min(1.0, axis_def["default"] + (pos - neg) / n * 0.3))
    return mood


def _aggregate_to_axes(mood_vector: list[float]) -> dict:
    mood = {}
    for axis_name, axis_def in MOOD_AXES.items():
        pos = sum(mood_vector[i] for i in axis_def["positive"])
        neg = sum(mood_vector[i] for i in axis_def["negative"])
        n = max(len(axis_def["positive"]) + len(axis_def["negative"]), 1)
        mood[axis_name] = max(0.0, min(1.0, (pos - neg) / n + 0.3))
    return mood


def _log_triad(npc_id: int, cell: dict, p: list[float],
               mood_vector: list[float], f: list[float]):
    owner = cell.get("owner", "?")
    print(f"  [三者積] npc={npc_id} が owner={owner} の公開セルを見た:")
    for i in range(16):
        product = p[i] * mood_vector[i] * f[i]
        if product > 0.01:
            print(f"    {FACTOR_NAMES[i]:16s}: p={p[i]:.2f} × mood={mood_vector[i]:.2f} × f={f[i]:.2f} = {product:.3f}")
