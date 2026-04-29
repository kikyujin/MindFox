"""ページワンデモ — MxBS連携"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxbs" / "python"))
from mxbs_bridge import MxBSBridge

from characters import Character, AI_CHARACTERS

THRESHOLD = 0.3

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


def check_pageone(mxbs: MxBSBridge, char_id: int, char_bit: int, current_turn: int) -> tuple[bool, float]:
    results = mxbs.search(
        query_features=QUERY_FEATURES,
        viewer_id=char_id,
        viewer_groups=char_bit,
        current_turn=current_turn,
        limit=1,
    )
    if not results:
        return False, 0.0
    score = results[0].get("effective_score", 0.0)
    return score >= THRESHOLD, score


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


def check_callout(mxbs: MxBSBridge, forgetter_id: int, characters: list[Character], current_turn: int) -> tuple[str, bool, float]:
    candidates = [c for c in characters if not c.is_player and c.id != forgetter_id]
    if not candidates:
        return "", False, 0.0
    checker = random.choice(candidates)
    results = mxbs.search(
        query_features=QUERY_FEATURES,
        viewer_id=checker.id,
        viewer_groups=checker.bit,
        current_turn=current_turn,
        limit=1,
    )
    if not results:
        return checker.name, False, 0.0
    score = results[0].get("effective_score", 0.0)
    return checker.name, score >= THRESHOLD, score


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
