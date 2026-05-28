#!/usr/bin/env python3
"""
MxChatterFox oyatsu demo — CLI
Uses Python cascade_search (USE_RUST=False) or Rust via mxbs_bridge (USE_RUST=True).

Usage:
    python main.py
    python main.py --threshold 0.35 --debug
    python main.py --rust          # use Rust cascade_search via libmxbs
"""
import math
import random
import argparse
from typing import Optional

from data import NPC_DEFS, ALL_LINES, WORDS_INITIAL, FALLBACKS
from game_state import GameState

USE_RUST = False


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
    debug: bool = False,
) -> tuple[Optional[dict], int, list]:
    debug_info = []

    for depth in range(len(words), 0, -1):
        query_words = words[:depth]
        word_names = [w["text"] for w in query_words]

        scored = []
        for line in npc_lines:
            sim = cosine_similarity(query_words[0]["features"], line["features"])
            scored.append((line, sim))

        candidates = [(l, s) for l, s in scored if s >= threshold]
        candidates.sort(key=lambda x: x[1], reverse=True)

        step_info = {
            "depth": depth, "words": word_names,
            "step1_word": query_words[0]["text"],
            "step1_hits": [(c[0]["id"], f"{c[1]:.3f}") for c in candidates[:8]],
        }

        candidates = [c[0] for c in candidates[:20]]

        filter_log = []
        for word in query_words[1:]:
            before = len(candidates)
            candidates = [
                c for c in candidates
                if cosine_similarity(c["features"], word["features"]) >= threshold
            ]
            filter_log.append(f"  +[{word['text']}] {before} -> {len(candidates)}")

        step_info["filter_log"] = filter_log
        step_info["surviving"] = [c["id"] for c in candidates]
        debug_info.append(step_info)

        if candidates:
            fresh = [c for c in candidates if c["id"] not in recent_used]
            pick = random.choice(fresh if fresh else candidates)
            return pick, depth, debug_info

    return None, 0, debug_info


# ─── CLI ───

class ChatterFoxCLI:
    def __init__(self, threshold: float = 0.35, debug: bool = False):
        self.threshold = threshold
        self.debug = debug
        self.state = GameState()
        self.state.init_words(WORDS_INITIAL)
        self.state.init_npcs(list(NPC_DEFS.keys()))
        self.conversation_log: list[dict] = []

    def show_lobby(self):
        print("\n  \U0001f3e0 AI館ロビー — 誰に話を聞く？")
        print("  " + "─" * 33)
        for npc_id, npc in NPC_DEFS.items():
            talked = len(self.state.recent_used.get(npc_id, set()))
            mark = f"[{talked}話済]" if talked > 0 else ""
            culprit = " ★" if self.debug and npc["role"] == "culprit" else ""
            print(f"    go {npc_id:8s} → {npc['name']:10s} ({npc['location']}){culprit} {mark}")
        print(f"\n    words / log / accuse / debug / th N / quit")

    def show_help(self):
        print("""
  === MxChatterFox oyatsu demo ===

  Lobby:
    go <npc>   ... go to NPC (e.g. go elmar)
    accuse     ... accuse someone
    words      ... show word cards
    log        ... show conversation log
    debug      ... toggle debug
    th N       ... set threshold (e.g. th 0.35)
    quit       ... quit

  Talking:
    <word> <word> ...  ... enter 1-3 words separated by space
    back               ... return to lobby
    words              ... show word cards
""")

    def do_accuse(self):
        print("\n  ⚖️ 犯人を指名する")
        print("  " + "─" * 18)
        for npc_id, npc in NPC_DEFS.items():
            print(f"    {npc_id:8s} → {npc['name']}")
        print()
        try:
            choice = input("  誰が犯人だ？ > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if choice not in NPC_DEFS:
            print("  ……そんな名前の住人はいないよ")
            return
        npc = NPC_DEFS[choice]
        if npc["role"] == "culprit":
            print(f"\n  \U0001f389\U0001f389\U0001f389 正解！ 犯人は {npc['name']} だった！")
            print(f"  {npc['name']}「……バレた。あのチョコ美味しかったんだもん\U0001f4a6」")
            print(f"\n  \U0001f4ca {len(self.conversation_log)}ターンで解決！ \U0001f511{len(self.state.flags)}個収集")
        else:
            print(f"\n  ❌ ハズレ……{npc['name']}は無実だった")
            print(f"  {npc['name']}「マスター……ひどいです」")

    def _gen_player_text(self, words):
        texts = [w["text"] for w in words]
        if len(texts) == 1:
            return f"「{texts[0]}について教えてくれ」"
        elif len(texts) == 2:
            return f"「{texts[0]}のことで、{texts[1]}？」"
        else:
            return f"「{texts[0]}について、{'、'.join(texts[1:-1])}——{texts[-1]}？」"

    def talk_loop(self, npc_id: str):
        npc = NPC_DEFS[npc_id]
        npc_lines = ALL_LINES[npc_id]
        print(f"\n  ─── {npc['name']} の部屋 ({npc['location']}) ───")
        if self.debug:
            print(f"  [{npc['archetype']} / {npc['role']}] {npc['desc']}")
        print(f"  単語を入力して会話 / 「back」でロビーへ\n")

        while True:
            try:
                raw = input(f"  [{npc['name']}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not raw:
                continue
            if raw.lower() in ("back", "lobby"):
                print(f"  （ロビーに戻った）")
                break
            if raw.lower() == "words":
                self.state.show_words()
                continue

            words = self.state.resolve_words(raw.split())
            if not words:
                print("  有効な単語がないよ。「words」で確認して")
                continue

            player_text = self._gen_player_text(words)
            print(f"\n  Player: {player_text}")

            available = self.state.filter_available_lines(npc_lines)
            recent = self.state.get_exclude_ids(npc_id)

            hit, depth, debug_info = cascade_search_py(
                words=words, npc_lines=available,
                recent_used=recent,
                threshold=self.threshold, debug=True,
            )

            if self.debug and debug_info:
                print("  --- DEBUG ---")
                for step in debug_info:
                    ws = " + ".join(step["words"])
                    print(f"  depth={step['depth']} [{ws}]")
                    print(f"    Step1 [{step['step1_word']}]: {step['step1_hits'][:5]}")
                    for fl in step.get("filter_log", []):
                        print(f"    {fl}")
                    print(f"    surviving: {step['surviving']}")
                print("  --- /DEBUG --")

            if hit is None:
                print(f"  {npc['name']}: {FALLBACKS[npc_id]}")
                line_id = "FB"
            else:
                print(f"  {npc['name']}: {hit['npc_text']}")
                info = f"{hit['id']} / {depth}語ヒット"
                if self.debug:
                    info += f" / cos>={self.threshold}"
                print(f"         ({info})")
                self.state.process_grants(hit)
                self.state.mark_used(npc_id, hit["id"])
                line_id = hit["id"]

            self.conversation_log.append({
                "turn": len(self.conversation_log) + 1,
                "npc": npc_id,
                "words": [w["text"] for w in words],
                "line_id": line_id,
                "depth": depth,
            })
            print()

    def _show_summary(self):
        if not self.conversation_log:
            return
        print(f"\n  \U0001f4ca 会話サマリー")
        print(f"  " + "─" * 13)
        print(f"  総ターン: {len(self.conversation_log)}")
        print(f"  \U0001f511 キーワード: {len(self.state.flags)}個")
        by_npc = {}
        for e in self.conversation_log:
            by_npc.setdefault(e["npc"], []).append(e)
        for npc_id, entries in by_npc.items():
            name = NPC_DEFS[npc_id]["name"]
            fb = sum(1 for e in entries if e["depth"] == 0)
            print(f"    {name}: {len(entries)}ターン (FB={fb})")

    def run(self):
        mode = "Rust" if USE_RUST else "Python"
        print("═" * 56)
        print(f"  \U0001f36b MxChatterFox oyatsu demo [{mode}]")
        print("═" * 56)
        print(f"  6NPC / cosine閾値: {self.threshold} / debug: {'ON' if self.debug else 'OFF'}")
        print(f"  「help」でヘルプ / 「go <npc>」で会話開始")
        self.show_lobby()

        while True:
            try:
                raw = input("\n\U0001f3e0 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  \U0001f44b またね！")
                break
            if not raw:
                continue

            cmd = raw.lower().split()
            if cmd[0] == "quit":
                self._show_summary()
                break
            elif cmd[0] == "help":
                self.show_help()
            elif cmd[0] == "words":
                self.state.show_words()
            elif cmd[0] == "debug":
                self.debug = not self.debug
                print(f"  デバッグ: {'ON' if self.debug else 'OFF'}")
            elif cmd[0] == "th" and len(cmd) > 1:
                try:
                    self.threshold = float(cmd[1])
                    print(f"  閾値を {self.threshold} に変更")
                except ValueError:
                    print("  使い方: th 0.35")
            elif cmd[0] == "accuse":
                self.do_accuse()
            elif cmd[0] == "go" and len(cmd) > 1:
                npc_id = cmd[1]
                if npc_id in NPC_DEFS:
                    self.talk_loop(npc_id)
                    self.show_lobby()
                else:
                    print(f"  「{npc_id}」は見つからないよ。NPC名を確認して")
            elif cmd[0] == "log":
                if not self.conversation_log:
                    print("  （まだ会話してない）")
                else:
                    for e in self.conversation_log:
                        npc_name = NPC_DEFS[e["npc"]]["name"]
                        print(f"  [{e['turn']:2d}] {npc_name:6s} <- {e['words']} -> {e['line_id']} (d={e['depth']})")
            elif cmd[0] == "lobby":
                self.show_lobby()
            else:
                print("  ？ 「help」でコマンド一覧 / 「go <npc>」で会話開始")


def main():
    global USE_RUST
    parser = argparse.ArgumentParser(description="MxChatterFox oyatsu demo")
    parser.add_argument("--threshold", "-t", type=float, default=0.35)
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--rust", action="store_true", help="Use Rust cascade_search via libmxbs")
    args = parser.parse_args()

    USE_RUST = args.rust
    cli = ChatterFoxCLI(threshold=args.threshold, debug=args.debug)
    cli.run()


if __name__ == "__main__":
    main()
