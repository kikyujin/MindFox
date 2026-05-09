"""AI学園どきどきメモリー — Phase 0 CLI"""

import argparse
import json
import random
import time

import yaml

from characters import (
    CHARACTER_DATA, LOCATIONS, LOCATION_NAMES,
    SLOTS, SLOT_NAMES, PLAYER_ID, ALL_NPC_BITS, TIL_ID,
)
from dialogue import generate_dialogue
from mood import compute_mood
from mxbs_bridge import MxBSBridge

TOTAL_DAYS = 5
SLOTS_PER_DAY = 3
TOTAL_TURNS = TOTAL_DAYS * SLOTS_PER_DAY


def load_reactions() -> dict:
    with open("reactions.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["reactions"]


REACTIONS = load_reactions()

# 訪問セル: 会いに来た事実を記録（fondness にプラス寄与）
VISIT_SCORES = [100, 0, 40, 80, 0, 60, 0, 40, 0, 0, 80, 0, 40, 0, 0, 80]


# --- NPC 配置 ---

def place_npcs() -> dict[str, list[str]]:
    placement = {loc: [] for loc in LOCATIONS}
    for key, char in CHARACTER_DATA.items():
        if char["home_location"] is None:
            loc = random.choice(LOCATIONS)
        elif random.random() < 0.6:
            loc = char["home_location"]
        else:
            loc = random.choice(LOCATIONS)
        placement[loc].append(key)
    return placement


# --- ルールベース反応選択 (Phase 0) ---

def select_reaction_rule_based(mood: dict, npc_key: str, witnesses: list) -> str:
    fondness = mood.get("fondness", 0.3)
    jealousy = mood.get("jealousy_mood", 0.2)
    tension = mood.get("tension", 0.3)
    openness = mood.get("openness", 0.3)

    if jealousy >= 0.5:
        return "jealous_sulk" if fondness >= 0.3 else "jealous_attack"
    if fondness < 0.25:
        return "cold_wall"
    if fondness < 0.35:
        return "indifferent_polite"
    if fondness >= 0.6:
        if openness >= 0.5:
            return "clingy_sweet"
        if tension >= 0.5:
            return "tsundere_blush"
        return "delighted"
    if tension >= 0.5:
        return "tsundere_deny"
    if openness >= 0.5:
        return "vulnerable_honest"
    return "curious_approach"


# --- 公開/非公開判定 ---

def determine_visibility(npcs_at_location: list[str], target_npc: str) -> tuple[bool, list[str]]:
    witnesses = [n for n in npcs_at_location if n != target_npc]
    return len(witnesses) > 0, witnesses


def til_photo_check(witnesses: list[str]) -> bool:
    if "til" not in witnesses:
        return False
    return random.random() < 0.7


# --- mood 変化通知（嫉妬連鎖等） ---

def notify_mood_changes(bs: MxBSBridge, target_key: str, is_public: bool,
                        photo: bool, turn: int):
    if not is_public and not photo:
        return
    for key, char in CHARACTER_DATA.items():
        if key == target_key or key == "til":
            continue
        if not char["attackable"]:
            continue
        cells = get_npc_cells(bs, char["id"], turn)
        m = compute_mood(cells, npc_id=char["id"], personality=char["personality_vector"])
        if m.get("jealousy_mood", 0) > 0.3:
            delta = 0.05 if photo else 0.03
            src = "写真で知った" if photo else "目撃した"
            print(f"  {char['name']}: jealousy_mood +{delta:.2f}（{src}）")


# --- NPC セル取得ヘルパー ---

def get_npc_cells(bs: MxBSBridge, npc_id: int, current_turn: int) -> list[dict]:
    pv = [128] * 16
    npc_groups = 1 << npc_id
    results = bs.search(pv, viewer_id=npc_id, viewer_groups=npc_groups,
                        current_turn=current_turn, limit=20)
    return results


# --- エンカウント ---

def encounter(bs: MxBSBridge, npc_key: str, npcs_at_location: list[str],
              location: str, slot: str, turn: int):
    char = CHARACTER_DATA[npc_key]
    is_public, witnesses = determine_visibility(npcs_at_location, npc_key)
    witness_names = [CHARACTER_DATA[w]["name"] for w in witnesses]

    witness_str = f"（目撃者: {', '.join(witness_names)}）" if witnesses else ""
    print(f"[{char['name']}] が{LOCATION_NAMES[location]}にいます。{witness_str}")
    print()

    cells = get_npc_cells(bs, char["id"], turn)
    m = compute_mood(cells, npc_id=char["id"], personality=char["personality_vector"])
    print(f"  気分: fondness={m['fondness']:.2f} tension={m['tension']:.2f} "
          f"jealousy={m['jealousy_mood']:.2f} openness={m['openness']:.2f}")

    reaction_key = select_reaction_rule_based(m, npc_key, witnesses)
    reaction = REACTIONS.get(reaction_key, REACTIONS["curious_approach"])
    print(f"  反応: {reaction_key}（{reaction['hint']}）")
    print(f"  生成中...")

    line = generate_dialogue(
        char, LOCATION_NAMES[location], SLOT_NAMES[slot],
        reaction["hint"], reaction["context"],
    )
    print()
    print(f"  {char['name']}「{line}」")
    print()

    # MxBS セル保存（反応セル）
    group_bits = ALL_NPC_BITS if is_public else (1 << char["id"]) | (1 << PLAYER_ID)
    mode = 0o744 if is_public else 0o700
    meta = json.dumps({"reaction": reaction_key, "location": location, "slot": slot},
                       ensure_ascii=False)
    cell_id = bs.store(
        owner=char["id"], text=line,
        from_id=PLAYER_ID, turn=turn,
        group_bits=group_bits, mode=mode,
        price=100, features=reaction["scores"],
        meta=meta,
    )

    # 訪問セル（会いに来た事実を記録）
    visit_text = f"[訪問] マスターが{LOCATION_NAMES[location]}に来た"
    bs.store(
        owner=char["id"], text=visit_text,
        from_id=PLAYER_ID, turn=turn,
        group_bits=group_bits,
        mode=0o744 if is_public else 0o740,
        price=40, features=VISIT_SCORES,
        meta='{"type":"visit"}',
    )

    vis_label = "公開" if is_public else "非公開"
    wit_detail = f" — 目撃者: {', '.join(witness_names)}" if witnesses else ""
    print(f"  → MxBS セル保存（{vis_label}{wit_detail}）+ 訪問セル")

    # ティル写真
    photo = til_photo_check(witnesses)
    if photo:
        print(f"  → 📷 ティルが写真を撮った！（公開セル化）")
        bs.update_group_bits(cell_id, ALL_NPC_BITS, requester=TIL_ID, req_groups=ALL_NPC_BITS)

    # reinforce
    if cells:
        latest = cells[-1]
        latest_id = latest.get("id", latest.get("cell_id"))
        if latest_id:
            imp = latest.get("importance", 1.0)
            bs.reinforce(latest_id, imp * 1.5)

    # mood 変化通知
    print()
    print("  [mood変化]")
    notify_mood_changes(bs, npc_key, is_public, photo, turn)


# --- 告白フェーズ ---

def confession_phase(bs: MxBSBridge, turn: int, auto_target: str = ""):
    print()
    print("━" * 40)
    print(" 告白フェーズ")
    print("━" * 40)
    print()

    attackable = [(k, v) for k, v in CHARACTER_DATA.items() if v["attackable"]]
    for i, (key, char) in enumerate(attackable, 1):
        cells = get_npc_cells(bs, char["id"], turn)
        m = compute_mood(cells, npc_id=char["id"], personality=char["personality_vector"])
        print(f"  {i}. {char['name']}（{char['role']}）— fondness={m['fondness']:.2f}")

    print()
    if auto_target:
        choice = next((i for i, (k, _) in enumerate(attackable) if k == auto_target), 0)
        print(f"  → auto: {attackable[choice][1]['name']}に告白")
    else:
        try:
            choice = int(input("誰に告白する？ (1-5): ")) - 1
        except (ValueError, EOFError):
            choice = 0
    choice = max(0, min(choice, len(attackable) - 1))

    target_key, target_char = attackable[choice]
    cells = get_npc_cells(bs, target_char["id"], turn)
    m = compute_mood(cells, npc_id=target_char["id"], personality=target_char["personality_vector"])
    fondness = m.get("fondness", 0.3)

    print()
    print(f"─── {target_char['name']}に告白 ───")
    print()

    success = fondness >= 0.5
    if success:
        print(f"  💕 告白成功！（fondness={fondness:.2f} >= 0.5）")
        reaction_hint = "告白を受け入れる"
        reaction_context = "好感度が高く、嬉しい"
    else:
        print(f"  💔 告白失敗…（fondness={fondness:.2f} < 0.5）")
        reaction_hint = "告白を断る"
        reaction_context = "まだ心を開いていない"

    print(f"  生成中...")
    line = generate_dialogue(
        target_char, "教室", "放課後",
        reaction_hint, reaction_context,
        situation_detail="マスターから告白された",
    )
    print()
    print(f"  {target_char['name']}「{line}」")

    # ティル救済
    if not success:
        print()
        print("  ...")
        print()
        til = CHARACTER_DATA["til"]
        rescue_line = generate_dialogue(
            til, "教室", "放課後",
            "落ち込んだマスターを励ます",
            "告白に失敗して落ち込んでいる",
            situation_detail="にーにが告白に失敗して落ち込んでいる",
        )
        print(f"  ティル「{rescue_line}」")
        print()
        print(f"  → ティルがそばにいてくれた")

    return success, target_key


# --- メインループ ---

def main():
    parser = argparse.ArgumentParser(description="AI学園どきどきメモリー Phase 0")
    parser.add_argument("--auto-target", type=str, default="",
                        help="自動プレイ対象 NPC キー (例: elmar)")
    parser.add_argument("--seed", type=int, default=0,
                        help="乱数シード (0=time)")
    args = parser.parse_args()

    auto_target = args.auto_target
    seed = args.seed or int(time.time())
    random.seed(seed)

    db_name = f"dokidoki_{int(time.time())}.db"
    print(f"[system] DB: {db_name} / seed: {seed} / auto: {auto_target or 'off'}")
    print()

    bs = MxBSBridge(db_name)

    try:
        turn = 0
        for day in range(1, TOTAL_DAYS + 1):
            for slot_idx, slot in enumerate(SLOTS):
                turn += 1
                print("━" * 40)
                print(f" AI学園どきどきメモリー — Day {day} / {SLOT_NAMES[slot]}")
                print("━" * 40)
                print()

                placement = place_npcs()

                for i, loc in enumerate(LOCATIONS, 1):
                    npcs = placement[loc]
                    names = ", ".join(CHARACTER_DATA[k]["name"] for k in npcs) if npcs else "（誰もいない）"
                    print(f"  {i}. {LOCATION_NAMES[loc]:6s} … {names}")
                print()

                if auto_target:
                    # auto_target がいる場所を選ぶ
                    choice = next(
                        (i for i, loc in enumerate(LOCATIONS) if auto_target in placement[loc]),
                        0,
                    )
                    print(f"  → auto: {LOCATION_NAMES[LOCATIONS[choice]]}")
                else:
                    try:
                        choice = int(input("どこに行く？ (1-5): ")) - 1
                    except (ValueError, EOFError):
                        choice = 0
                choice = max(0, min(choice, len(LOCATIONS) - 1))
                chosen_loc = LOCATIONS[choice]
                npcs_here = placement[chosen_loc]

                print()
                print(f"─── {LOCATION_NAMES[chosen_loc]} ───")
                print()

                if not npcs_here:
                    print("  誰もいなかった…")
                else:
                    for npc_key in npcs_here:
                        encounter(bs, npc_key, npcs_here, chosen_loc, slot, turn)
                        print()

                print()

        # 告白フェーズ
        success, target = confession_phase(bs, turn, auto_target=auto_target)

        # 結果表示
        print()
        print("━" * 40)
        print(" ゲーム終了")
        print("━" * 40)
        st = bs.stats()
        print(f"  MxBS セル数: {st.get('total', 0)}")
        print(f"  告白相手: {CHARACTER_DATA[target]['name']}")
        print(f"  結果: {'💕 成功' if success else '💔 失敗（ティル救済）'}")
        print()

    finally:
        bs.close()


if __name__ == "__main__":
    main()
