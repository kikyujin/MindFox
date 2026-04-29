"""AI館おやつデモ — MxBS記憶管理"""
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxbs" / "python"))
from mxbs_bridge import MxBSBridge

from characters import Character, GROUP_ALL, SYSTEM_OWNER


# ========== プリセット読み込み ==========

def load_preset() -> dict:
    preset_path = Path(__file__).parent / "preset.json"
    with open(preset_path) as f:
        return json.load(f)

PRESET = load_preset()
EVENT_FEATURES = PRESET["event_features"]
MOOD_MAPPING = PRESET["mood_mapping"]


# ========== Mood 算出 ==========

class Mood:
    def __init__(self, suspicion=0.5, anxiety=0.5, confidence=0.5, cooperation=0.5):
        self.suspicion = suspicion
        self.anxiety = anxiety
        self.confidence = confidence
        self.cooperation = cooperation

    def __repr__(self):
        return (f"Mood(sus={self.suspicion:.2f}, anx={self.anxiety:.2f}, "
                f"conf={self.confidence:.2f}, coop={self.cooperation:.2f})")


def compute_mood(recent_features: list[list[int]]) -> Mood:
    if not recent_features:
        return Mood()

    n = len(recent_features)
    mood = {}
    for mood_name, mapping in MOOD_MAPPING.items():
        pos_indices = mapping["positive"]
        neg_indices = mapping["negative"]
        total = 0.0
        for feat in recent_features:
            for i in pos_indices:
                total += feat[i] / 255.0
            for i in neg_indices:
                total += (1.0 - feat[i] / 255.0)
        count = n * (len(pos_indices) + len(neg_indices))
        mood[mood_name] = total / count if count > 0 else 0.5

    return Mood(**mood)


def get_agent_mood(mxbs: MxBSBridge, char: Character, turn: int) -> Mood:
    query = [128] * 16
    results = mxbs.search(
        query_features=query,
        viewer_id=char.id, viewer_groups=char.bit,
        current_turn=turn, limit=8,
    )
    features_list = []
    for r in results:
        feat = r.get("features")
        if feat and any(v != 0 for v in feat):
            features_list.append(feat)
    return compute_mood(features_list)


# ========== 信頼度 (diplomacy_toward) ==========

def compute_diplomacy_toward(
    mxbs: MxBSBridge,
    agent: Character,
    counterpart: Character,
    turn: int,
) -> float:
    query = [0] * 16
    query[2] = 200   # trust
    query[9] = 200   # empathy
    query[10] = 200  # cooperation

    results = mxbs.search(
        query_features=query,
        viewer_id=agent.id, viewer_groups=agent.bit,
        current_turn=turn, limit=10,
    )

    relevant = []
    for r in results:
        if r.get("from") == counterpart.id or r.get("owner") == counterpart.id:
            feat = r.get("features")
            if feat and any(v != 0 for v in feat):
                relevant.append(feat)

    if not relevant:
        return 0.5

    pos_indices = [2, 9, 10]
    neg_indices = [7, 8]
    total = 0.0
    count = 0
    for feat in relevant:
        for i in pos_indices:
            total += feat[i] / 255.0
            count += 1
        for i in neg_indices:
            total += (1.0 - feat[i] / 255.0)
            count += 1

    return total / count if count > 0 else 0.5


# ========== セル格納ヘルパー ==========

def store_testimony(mxbs: MxBSBridge, char: Character, text: str,
                    event_type: str, turn: int, meta_extra: dict = None):
    meta = {"type": event_type}
    if meta_extra:
        meta.update(meta_extra)
    mxbs.store(
        owner=char.id, text=text,
        from_id=char.id, turn=turn,
        group_bits=GROUP_ALL, mode=0o744,
        price=80,
        features=EVENT_FEATURES.get(event_type, [128]*16),
        meta=json.dumps(meta),
    )


def store_night_plot(mxbs: MxBSBridge, text: str,
                     culprit_a: Character, culprit_b: Character,
                     turn: int, target_name: str) -> int:
    meta = {"type": "night_plot", "target": target_name}
    cell_id = mxbs.store(
        owner=culprit_a.id, text=text,
        from_id=culprit_a.id, turn=turn,
        group_bits=culprit_a.bit | culprit_b.bit,
        mode=0o770, price=120,
        features=EVENT_FEATURES["night_plot"],
        meta=json.dumps(meta),
    )
    return cell_id


def store_event(mxbs: MxBSBridge, text: str, event_type: str,
                turn: int, meta_extra: dict = None):
    meta = {"type": event_type}
    if meta_extra:
        meta.update(meta_extra)
    price_map = {
        "accusation_hit": 200,
        "accusation_miss": 150,
        "elimination": 200,
        "game_summary": 250,
    }
    mxbs.store(
        owner=SYSTEM_OWNER, text=text,
        from_id=SYSTEM_OWNER, turn=turn,
        group_bits=GROUP_ALL, mode=0o744,
        price=price_map.get(event_type, 100),
        features=EVENT_FEATURES.get(event_type, [128]*16),
        meta=json.dumps(meta),
    )


def store_personal_memory(mxbs: MxBSBridge, char: Character,
                          text: str, turn: int, price: int = 150,
                          meta_type: str = "personal_game_memory",
                          game_id: int = 1):
    meta = {"type": meta_type, "game_id": game_id}
    mxbs.store(
        owner=char.id, text=text,
        from_id=char.id, turn=turn,
        group_bits=char.bit, mode=0o700,
        price=price,
        features=[128]*16,
        meta=json.dumps(meta),
    )


def get_night_plots(mxbs: MxBSBridge, game_turn_start: int, game_turn_end: int) -> list:
    query = EVENT_FEATURES["night_plot"]
    results = mxbs.search(
        query_features=query,
        viewer_id=SYSTEM_OWNER,
        viewer_groups=0xFFFFFFFFFFFFFFFF,
        current_turn=game_turn_end,
        limit=20,
    )
    plots = []
    for r in results:
        meta = json.loads(r.get("meta", "{}"))
        if meta.get("type") == "night_plot":
            t = r.get("turn", 0)
            if game_turn_start <= t <= game_turn_end:
                plots.append(r)
    plots.sort(key=lambda x: x.get("turn", 0))
    return plots


def get_memories_for_prompt(mxbs: MxBSBridge, char: Character,
                            turn: int, limit: int = 5) -> str:
    query = [128] * 16
    results = mxbs.search(
        query_features=query,
        viewer_id=char.id, viewer_groups=char.bit,
        current_turn=turn, limit=limit,
    )
    if not results:
        return "（記憶なし）"
    lines = []
    for r in results:
        lines.append(f"- {r['text']}")
    return "\n".join(lines)
