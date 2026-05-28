#!/usr/bin/env python3
"""
Baker: bake data.py lines/words into MxBS cells.

Usage:
    python baker.py              # -> oyatsu_chatterfox.db
    python baker.py --db out.db
"""
import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxbs" / "python"))
from mxbs_bridge import MxBSBridge

from data import (
    NPC_ID_MAP, PLAYER_ID, SYSTEM_ID,
    ALL_LINES, WORDS_INITIAL, WORDS_GETTABLE, FALLBACKS,
)


def bake(db_path: str = "oyatsu_chatterfox.db"):
    db = MxBSBridge(db_path, half_life=80)
    line_count = 0
    word_count = 0

    for npc_key, lines in ALL_LINES.items():
        owner = NPC_ID_MAP[npc_key]
        for line in lines:
            db.store(
                owner=owner,
                text=line["npc_text"],
                from_id=SYSTEM_ID,
                turn=0,
                group_bits=0xFF,
                mode=0o744,
                price=255,
                features=line["features"],
                meta=json.dumps({
                    "type": "npc_line",
                    "line_id": line["id"],
                    "grants": line.get("grants", []),
                    "requires": line.get("requires", []),
                }, ensure_ascii=False),
            )
            line_count += 1

    for word in WORDS_INITIAL:
        db.store(
            owner=PLAYER_ID,
            text=word["text"],
            from_id=SYSTEM_ID,
            turn=0,
            group_bits=0xFF,
            mode=0o744,
            price=255,
            features=word["features"],
            meta=json.dumps({
                "type": "keyword",
                "slot": word["slot"],
                "word_id": word["id"],
                "initial": True,
            }, ensure_ascii=False),
        )
        word_count += 1

    for name, word in WORDS_GETTABLE.items():
        db.store(
            owner=PLAYER_ID,
            text=word["text"],
            from_id=SYSTEM_ID,
            turn=0,
            group_bits=0x00,
            mode=0o700,
            price=255,
            features=word["features"],
            meta=json.dumps({
                "type": "keyword",
                "slot": word["slot"],
                "word_id": word["id"],
                "grant_name": name,
                "initial": False,
            }, ensure_ascii=False),
        )
        word_count += 1

    stats = db.stats()
    print(f"Baked to {db_path}: {stats.get('total', '?')} cells ({line_count} lines + {word_count} words)")
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Baker: data.py -> MxBS DB")
    parser.add_argument("--db", default="oyatsu_chatterfox.db")
    args = parser.parse_args()
    bake(args.db)


if __name__ == "__main__":
    main()
