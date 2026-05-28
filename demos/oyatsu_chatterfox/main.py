#!/usr/bin/env python3
"""
MxChatterFox oyatsu demo — YamAMVA + MxYamAMVA + MxChatterFox CLI

Usage:
    python main.py                           # Python cascade_search
    python main.py --rust                    # Rust cascade_search via libmxbs
    python main.py --threshold 0.35 --debug
    python main.py --standalone              # standalone mode (no YamAMVA)
"""
import math
import random
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxbs" / "python"))

from data import NPC_DEFS, NPC_ID_MAP, ALL_LINES, WORDS_INITIAL, FALLBACKS, PLAYER_ID

# ─── Command IDs for YamAMVA ───

CMD_SPEAKER = 1
CMD_HEARING = 2
CMD_ACCUSE = 3
CMD_CHATTERFOX = 4

PLAYER_GROUPS = 0xFF
THRESHOLD_DEFAULT = 0.35


# ─── Python cascade search (reference impl) ───

def cosine_similarity(a: list[int], b: list[int]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cascade_search_py(
    words: list[dict],
    npc_lines: list[dict],
    recent_used: set[str],
    threshold: float = 0.35,
) -> tuple[Optional[dict], int]:
    for depth in range(len(words), 0, -1):
        query_words = words[:depth]

        scored = []
        for line in npc_lines:
            sim = cosine_similarity(query_words[0]["features"], line["features"])
            scored.append((line, sim))

        candidates = [(l, s) for l, s in scored if s >= threshold]
        candidates.sort(key=lambda x: x[1], reverse=True)
        candidates = [c[0] for c in candidates[:20]]

        for word in query_words[1:]:
            candidates = [
                c for c in candidates
                if cosine_similarity(c["features"], word["features"]) >= threshold
            ]

        if candidates:
            fresh = [c for c in candidates if c["id"] not in recent_used]
            pick = random.choice(fresh if fresh else candidates)
            return pick, depth

    return None, 0


# ─── Word resolution helper ───

def resolve_words(input_texts: list[str], available_words: dict) -> list[dict]:
    resolved = []
    for text in input_texts:
        if text in available_words:
            resolved.append(available_words[text])
        else:
            matches = [w for key, w in available_words.items()
                       if text in key or key in text]
            if matches:
                resolved.append(matches[0])
                print(f"    -> \"{text}\" -> \"{matches[0]['text']}\"")
            else:
                print(f"    x \"{text}\" not in inventory")
    return resolved


def show_words(available_words: dict, flags: set):
    by_slot = {}
    for w in available_words.values():
        slot = w["slot"]
        by_slot.setdefault(slot, []).append(w["text"])
    print("\n  Word cards:")
    for slot in ["WHO", "ACTION", "WHAT", "WHERE"]:
        if slot in by_slot:
            print(f"    [{slot:6s}] {' / '.join(by_slot[slot])}")
    if flags:
        print(f"\n  Keywords({len(flags)}): {', '.join(sorted(flags))}")


def gen_player_text(words):
    texts = [w["text"] for w in words]
    if len(texts) == 1:
        return f"\"{texts[0]}\" について教えてくれ"
    elif len(texts) == 2:
        return f"\"{texts[0]}\" のことで、\"{texts[1]}\"？"
    else:
        return f"\"{texts[0]}\" について、{'、'.join(texts[1:-1])}——\"{texts[-1]}\"？"


def npc_name_by_owner(owner_id: int) -> str:
    for key, oid in NPC_ID_MAP.items():
        if oid == owner_id:
            return NPC_DEFS[key]["name"]
    return "???"


def npc_key_by_owner(owner_id: int) -> str:
    for key, oid in NPC_ID_MAP.items():
        if oid == owner_id:
            return key
    return ""


# ═══════════════════════════════════════════════════════════
#  YamAMVA-driven mode
# ═══════════════════════════════════════════════════════════

def run_yamamva_mode(args):
    from mxbs_bridge import MxBSBridge, MxYamAMVAState
    from yamamva_bridge import YamamvaBridge

    yaml_path = Path(__file__).parent / "scenario" / "oyatsu.yaml"
    yaml_str = yaml_path.read_text(encoding="utf-8")

    db_path = str(Path(__file__).parent / "oyatsu_chatterfox.db")
    db = MxBSBridge(db_path, half_life=80)
    mxstate = MxYamAMVAState(db._lib)
    mxstate.load_keywords(db._handle, PLAYER_ID, PLAYER_GROUPS, 0)

    yamva = YamamvaBridge(yaml_str)
    yamva.register("speaker", CMD_SPEAKER)
    yamva.register("hearingmenu", CMD_HEARING, blocking=True)
    yamva.register("accusemenu", CMD_ACCUSE, blocking=True)
    yamva.register("chatterfox", CMD_CHATTERFOX, blocking=True)

    available_words = {w["text"]: w for w in WORDS_INITIAL}
    recent_used: dict[str, set] = {k: set() for k in NPC_DEFS}
    conversation_log = []
    threshold = args.threshold
    debug = args.debug

    mode_label = "Rust" if args.rust else "Python"
    print("=" * 56)
    print(f"  MxChatterFox oyatsu demo [YamAMVA + {mode_label}]")
    print("=" * 56)

    while True:
        cmd, info = yamva.exec()

        if cmd == yamva.END:
            total = len(conversation_log)
            flags = mxstate.flag_count()
            print(f"\n  -- {total} turns, {flags} keywords --")
            break

        node_type = info.get("node_type", "")
        node_json = info.get("node_json", {})
        elements = info.get("elements", [])

        if cmd == CMD_SPEAKER:
            speaker = node_json.get("speaker", "")
            text = node_json.get("text", "")
            if speaker == "narrator":
                print(f"\n  {text}")
            else:
                name = speaker
                for npc in NPC_DEFS.values():
                    if any(speaker == k for k in NPC_DEFS):
                        name = NPC_DEFS.get(speaker, {}).get("name", speaker)
                        break
                print(f"  {name}: {text}")

        elif cmd == CMD_HEARING:
            print()
            for i, el in enumerate(elements):
                print(f"    [{i+1}] {el['label']}")
            while True:
                try:
                    raw = input("\n  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    yamva.set_result("quit")
                    break
                if raw.lower() == "words":
                    flags_set = {f for f in
                                 [k for k in available_words.keys()]
                                 if mxstate.has_flag(f)}
                    show_words(available_words, flags_set)
                    continue
                try:
                    idx = int(raw) - 1
                    if 0 <= idx < len(elements):
                        yamva.set_result(elements[idx]["key"])
                        break
                except ValueError:
                    for el in elements:
                        if raw.lower() == el["key"]:
                            yamva.set_result(el["key"])
                            break
                    else:
                        print("  ? enter number or key")
                        continue
                    break

        elif cmd == CMD_ACCUSE:
            print()
            for i, el in enumerate(elements):
                print(f"    [{i+1}] {el['label']}")
            while True:
                try:
                    raw = input("\n  Who did it? > ").strip()
                except (EOFError, KeyboardInterrupt):
                    yamva.set_result(elements[0]["key"])
                    break
                try:
                    idx = int(raw) - 1
                    if 0 <= idx < len(elements):
                        yamva.set_result(elements[idx]["key"])
                        break
                except ValueError:
                    for el in elements:
                        if raw.lower() == el["key"]:
                            yamva.set_result(el["key"])
                            break
                    else:
                        print("  ? enter number or key")
                        continue
                    break

        elif cmd == CMD_CHATTERFOX:
            cf_args = node_json.get("chatterfox", node_json)
            npc_owner = cf_args.get("npc_owner", 0)
            exit_words = cf_args.get("exit_words", [])
            npc_key = npc_key_by_owner(npc_owner)
            npc_name = npc_name_by_owner(npc_owner)

            print(f"  --- words to talk, 'back' to leave ---\n")

            while True:
                try:
                    raw = input(f"  [{npc_name}] > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not raw:
                    continue
                if raw.lower() in ("back", "lobby") or raw in exit_words:
                    print("  (back to lobby)")
                    break
                if raw.lower() == "words":
                    flags_set = set()
                    for name in available_words:
                        if mxstate.has_flag(name):
                            flags_set.add(name)
                    show_words(available_words, flags_set)
                    continue

                words = resolve_words(raw.split(), available_words)
                if not words:
                    print("  no valid words. type 'words' to check")
                    continue

                player_text = gen_player_text(words)
                print(f"\n  Player: {player_text}")

                if args.rust:
                    used_list = list(recent_used.get(npc_key, set()))
                    result = db.chatterfox_search(
                        word_features_list=[w["features"] for w in words],
                        lines_owner=npc_owner,
                        viewer_id=PLAYER_ID,
                        viewer_groups=PLAYER_GROUPS,
                        current_turn=0,
                        exclude_ids=[int(x) for x in used_list] if used_list else None,
                        threshold=threshold,
                    )
                    if result["is_fallback"]:
                        print(f"  {npc_name}: {FALLBACKS.get(npc_key, '...')}")
                        line_id = "FB"
                        depth = 0
                    else:
                        print(f"  {npc_name}: {result['text']}")
                        meta = result.get("meta", "{}")
                        newly = mxstate.process_grants(
                            db._handle, meta, PLAYER_ID, PLAYER_GROUPS,
                        )
                        for kw in newly:
                            if kw in _WORDS_GETTABLE:
                                available_words[kw] = _WORDS_GETTABLE[kw]
                            print(f"  NEW \"{kw}\" GET!")
                        recent_used.setdefault(npc_key, set()).add(result["cell_id"])
                        line_id = str(result["cell_id"])
                        depth = result.get("depth", 0)
                else:
                    npc_lines = ALL_LINES.get(npc_key, [])
                    avail = [
                        line for line in npc_lines
                        if all(mxstate.has_flag(req)
                               for req in line.get("requires", []))
                    ]
                    used_ids = recent_used.get(npc_key, set())

                    hit, depth = cascade_search_py(
                        words=words, npc_lines=avail,
                        recent_used=used_ids, threshold=threshold,
                    )

                    if hit is None:
                        print(f"  {npc_name}: {FALLBACKS.get(npc_key, '...')}")
                        line_id = "FB"
                    else:
                        print(f"  {npc_name}: {hit['npc_text']}")
                        meta_dict = {
                            "grants": hit.get("grants", []),
                            "requires": hit.get("requires", []),
                        }
                        newly = mxstate.process_grants(
                            db._handle,
                            json.dumps(meta_dict, ensure_ascii=False),
                            PLAYER_ID, PLAYER_GROUPS,
                        )
                        for kw in newly:
                            from data import WORDS_GETTABLE
                            if kw in WORDS_GETTABLE:
                                available_words[kw] = WORDS_GETTABLE[kw]
                            print(f"  NEW \"{kw}\" GET!")
                        recent_used.setdefault(npc_key, set()).add(hit["id"])
                        line_id = hit["id"]

                    if debug and hit:
                        print(f"         ({line_id} / {depth}w hit)")

                conversation_log.append({
                    "npc": npc_key, "words": [w["text"] for w in words],
                    "line_id": line_id, "depth": depth,
                })
                print()

            yamva.set_result("exit")

    yamva.close()
    mxstate.close()
    db.close()


# ═══════════════════════════════════════════════════════════
#  Standalone mode (no YamAMVA, original CLI)
# ═══════════════════════════════════════════════════════════

def run_standalone_mode(args):
    from data import WORDS_GETTABLE
    from game_state import GameState

    state = GameState()
    state.init_words(WORDS_INITIAL)
    state.init_npcs(list(NPC_DEFS.keys()))
    conversation_log = []
    threshold = args.threshold
    debug = args.debug

    print("=" * 56)
    print("  MxChatterFox oyatsu demo [Standalone]")
    print("=" * 56)
    print(f"  6NPC / threshold: {threshold} / debug: {'ON' if debug else 'OFF'}")

    def show_lobby():
        print("\n  Lobby - who to talk to?")
        print("  " + "-" * 33)
        for npc_id, npc in NPC_DEFS.items():
            talked = len(state.recent_used.get(npc_id, set()))
            mark = f"[{talked}]" if talked > 0 else ""
            print(f"    go {npc_id:8s} -> {npc['name']:10s} ({npc['location']}) {mark}")
        print(f"\n    words / log / accuse / quit")

    show_lobby()

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            continue

        cmd = raw.lower().split()
        if cmd[0] == "quit":
            break
        elif cmd[0] == "words":
            state.show_words()
        elif cmd[0] == "accuse":
            print("\n  Who did it?")
            for npc_id, npc in NPC_DEFS.items():
                print(f"    {npc_id:8s} -> {npc['name']}")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                continue
            if choice in NPC_DEFS:
                if NPC_DEFS[choice]["role"] == "culprit":
                    print(f"\n  Correct! {NPC_DEFS[choice]['name']} did it!")
                else:
                    print(f"\n  Wrong... {NPC_DEFS[choice]['name']} is innocent.")
        elif cmd[0] == "go" and len(cmd) > 1:
            npc_id = cmd[1]
            if npc_id not in NPC_DEFS:
                print(f"  '{npc_id}' not found")
                continue
            npc = NPC_DEFS[npc_id]
            npc_lines = ALL_LINES[npc_id]
            print(f"\n  --- {npc['name']} ({npc['location']}) ---")
            print(f"  words to talk, 'back' to leave\n")

            while True:
                try:
                    raw2 = input(f"  [{npc['name']}] > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not raw2:
                    continue
                if raw2.lower() in ("back", "lobby"):
                    break
                if raw2.lower() == "words":
                    state.show_words()
                    continue

                words = state.resolve_words(raw2.split())
                if not words:
                    print("  no valid words")
                    continue

                print(f"\n  Player: {gen_player_text(words)}")

                available = state.filter_available_lines(npc_lines)
                recent = state.get_exclude_ids(npc_id)
                hit, depth = cascade_search_py(
                    words=words, npc_lines=available,
                    recent_used=recent, threshold=threshold,
                )
                if hit is None:
                    print(f"  {npc['name']}: {FALLBACKS[npc_id]}")
                else:
                    print(f"  {npc['name']}: {hit['npc_text']}")
                    if debug:
                        print(f"         ({hit['id']} / {depth}w hit)")
                    state.process_grants(hit)
                    state.mark_used(npc_id, hit["id"])

                conversation_log.append({
                    "npc": npc_id, "words": [w["text"] for w in words],
                    "line_id": hit["id"] if hit else "FB", "depth": depth,
                })
                print()

            show_lobby()
        elif cmd[0] == "log":
            if not conversation_log:
                print("  (no conversations yet)")
            else:
                for i, e in enumerate(conversation_log):
                    npc_name = NPC_DEFS.get(e["npc"], {}).get("name", "?")
                    print(f"  [{i+1:2d}] {npc_name:6s} <- {e['words']} -> {e['line_id']} (d={e['depth']})")
        else:
            print("  ? 'go <npc>' / 'words' / 'accuse' / 'quit'")


# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="MxChatterFox oyatsu demo")
    parser.add_argument("--threshold", "-t", type=float, default=THRESHOLD_DEFAULT)
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--rust", action="store_true",
                        help="Use Rust cascade_search via libmxbs")
    parser.add_argument("--standalone", "-s", action="store_true",
                        help="Standalone mode (no YamAMVA)")
    args = parser.parse_args()

    if args.standalone:
        run_standalone_mode(args)
    else:
        run_yamamva_mode(args)


if __name__ == "__main__":
    main()
