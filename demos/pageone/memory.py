"""ページワンデモ — MxBS連携 + MxMindFox 統合 (v0.4)"""
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxbs" / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxmindfox" / "python"))
from mxbs_bridge import MxBSBridge
from mxmindfox_bridge import MxMindFox

from characters import Character, AI_CHARACTERS

THRESHOLD = 0.3

_mxmf = None
_mood_preset = None

def _init_mxmf():
    global _mxmf, _mood_preset
    if _mxmf is None:
        _mxmf = MxMindFox()
        preset_path = Path(__file__).parent / "pageone_mood.json"
        with open(preset_path) as f:
            preset_dict = json.load(f)
        _mood_preset = _mxmf.load_preset(preset_dict)
    return _mxmf, _mood_preset


def sigmoid_p(score: float, threshold: float, temperature: float) -> float:
    if temperature <= 0.0:
        return 1.0 if score >= threshold else 0.0
    logit = (score - threshold) / temperature
    logit = max(-500.0, min(500.0, logit))
    return 1.0 / (1.0 + math.exp(-logit))

RULE_FEATURES = [230, 240, 250, 200, 180, 160, 250, 250, 180, 120, 200, 200, 220, 128, 140, 160]
QUERY_FEATURES = [200, 220, 230, 150, 128, 128, 250, 230, 150, 128, 150, 180, 200, 128, 128, 128]

PAGEONE_RULE_TEXT = "手札が残り1枚になったら「ページワン！」と宣言しなければならない"


def init_mxbs(db_path: str, half_life: int = 8) -> MxBSBridge:
    return MxBSBridge(db_path, half_life=half_life)


def inject_pageone_rule(mxbs: MxBSBridge, characters: list[Character], turn: int = 0) -> dict[int, int]:
    cell_ids = {}
    for char in characters:
        if char.is_player:
            continue
        cell_id = mxbs.store(
            owner=char.id,
            from_id=0,
            turn=turn,
            text=PAGEONE_RULE_TEXT,
            group_bits=char.bit,
            mode=0o700,
            price=char.pageone_price,
            features=RULE_FEATURES,
            meta=json.dumps({"type": "rule", "rule_id": "pageone_declare"}),
        )
        cell_ids[char.id] = cell_id
    return cell_ids


def check_pageone(
    mxbs: MxBSBridge, char: Character, current_turn: int,
    rng_seed: int, temperature_override: float | None = None,
) -> tuple[bool, float, float, float]:
    """Returns (remembered, score, temperature, probability)."""
    results = mxbs.search(
        query_features=QUERY_FEATURES,
        viewer_id=char.id,
        viewer_groups=char.bit,
        current_turn=current_turn,
        limit=1,
    )
    if not results:
        return False, 0.0, 0.0, 0.0
    score = results[0].get("effective_score", 0.0)

    mxmf, mood_preset = _init_mxmf()
    if temperature_override is not None:
        temperature = temperature_override
    else:
        mood = mxmf.compute_mood(mood_preset, [], archetype=char.archetype)
        temperature = mood["axes"].get("temperature", 0.0)

    prob = sigmoid_p(score, THRESHOLD, temperature)
    remembered = mxmf.decision_remember(
        score=score, threshold=THRESHOLD,
        temperature=temperature, seed=rng_seed,
    )
    return remembered, score, temperature, prob


def do_reinforce(mxbs: MxBSBridge, characters: list[Character], declaring_char_id: int, current_turn: int):
    for char in characters:
        if char.is_player or char.id == declaring_char_id:
            continue
        results = mxbs.search(
            query_features=QUERY_FEATURES,
            viewer_id=char.id,
            viewer_groups=char.bit,
            current_turn=current_turn,
            limit=1,
        )
        if results:
            cell_id = results[0].get("id")
            if cell_id is not None:
                new_importance = 1.0 + char.reinforce_factor
                mxbs.reinforce(cell_id, new_importance)


def check_callout(
    mxbs: MxBSBridge, forgetter_id: int, characters: list[Character],
    current_turn: int, rng_seed: int, temperature_override: float | None = None,
) -> tuple[str, bool, float, float, float]:
    """Returns (checker_name, success, score, temperature, probability)."""
    candidates = [c for c in characters if not c.is_player and c.id != forgetter_id]
    if not candidates:
        return "", False, 0.0, 0.0, 0.0
    checker = random.choice(candidates)
    results = mxbs.search(
        query_features=QUERY_FEATURES,
        viewer_id=checker.id,
        viewer_groups=checker.bit,
        current_turn=current_turn,
        limit=1,
    )
    if not results:
        return checker.name, False, 0.0, 0.0, 0.0
    score = results[0].get("effective_score", 0.0)

    mxmf, mood_preset = _init_mxmf()
    if temperature_override is not None:
        temperature = temperature_override
    else:
        mood = mxmf.compute_mood(mood_preset, [], archetype=checker.archetype)
        temperature = mood["axes"].get("temperature", 0.0)

    prob = sigmoid_p(score, THRESHOLD, temperature)
    success = mxmf.decision_remember(
        score=score, threshold=THRESHOLD,
        temperature=temperature, seed=rng_seed,
    )
    return checker.name, success, score, temperature, prob


def get_score_snapshot(mxbs: MxBSBridge, characters: list[Character], current_turn: int) -> dict[str, float]:
    snapshot = {}
    for char in characters:
        if char.is_player:
            continue
        results = mxbs.search(
            query_features=QUERY_FEATURES,
            viewer_id=char.id,
            viewer_groups=char.bit,
            current_turn=current_turn,
            limit=1,
        )
        if results:
            snapshot[char.name] = results[0].get("effective_score", 0.0)
        else:
            snapshot[char.name] = 0.0
    return snapshot
