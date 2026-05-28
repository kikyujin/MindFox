"""
GameState — standalone mode only (--standalone flag).

YamAMVA mode uses MxYamAMVAState (Rust/C API) instead.
This file is kept for standalone fallback and will be removed
once MxYamAMVA fully replaces it.
"""
from data import WORDS_GETTABLE


class GameState:
    def __init__(self):
        self.flags: set[str] = set()
        self.available_words: dict[str, dict] = {}
        self.recent_used: dict[str, set[str]] = {}

    def init_words(self, initial_words: list[dict]):
        for w in initial_words:
            self.available_words[w["text"]] = w

    def init_npcs(self, npc_ids: list[str]):
        for npc_id in npc_ids:
            self.recent_used[npc_id] = set()

    def filter_available_lines(self, lines: list[dict]) -> list[dict]:
        return [
            line for line in lines
            if all(req in self.flags for req in line.get("requires", []))
        ]

    def process_grants(self, line: dict):
        for grant_name in line.get("grants", []):
            if grant_name not in self.flags:
                self.flags.add(grant_name)
                if grant_name in WORDS_GETTABLE:
                    self.available_words[grant_name] = WORDS_GETTABLE[grant_name]
                    print(f"  \U0001f511✨ NEW 「{grant_name}」GET!")
                else:
                    print(f"  \U0001f511 「{grant_name}」を記憶した")

    def mark_used(self, npc_id: str, line_id: str):
        self.recent_used.setdefault(npc_id, set()).add(line_id)

    def get_exclude_ids(self, npc_id: str) -> set[str]:
        return self.recent_used.get(npc_id, set())

    def resolve_words(self, input_texts: list[str]) -> list[dict]:
        resolved = []
        for text in input_texts:
            if text in self.available_words:
                resolved.append(self.available_words[text])
            else:
                matches = [w for key, w in self.available_words.items()
                           if text in key or key in text]
                if matches:
                    resolved.append(matches[0])
                    print(f"    → 「{text}」→「{matches[0]['text']}」に解決")
                else:
                    print(f"    ❌ 「{text}」は持ってない単語だよ")
        return resolved

    def show_words(self):
        by_slot = {}
        for w in self.available_words.values():
            slot = w["slot"]
            by_slot.setdefault(slot, []).append(w["text"])
        print("\n  \U0001f4e6 所持単語カード:")
        for slot in ["WHO", "ACTION", "WHAT", "WHERE"]:
            if slot in by_slot:
                print(f"    [{slot:6s}] {' / '.join(by_slot[slot])}")
        if self.flags:
            print(f"\n  \U0001f511 キーワード({len(self.flags)}個): {', '.join(sorted(self.flags))}")
