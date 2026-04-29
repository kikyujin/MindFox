"""AI館：おやつを食べたのは誰だ — メインエントリポイント"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mxbs" / "python"))

from mxbs_bridge import MxBSBridge
from characters import CHARACTERS
from engine import play_one_game
from memory import store_event, store_personal_memory


DB_PATH = str(Path(__file__).parent / "oyatsu.db")


def campaign():
    mxbs = MxBSBridge(DB_PATH, half_life=8)

    print("=" * 60)
    print("  🍪 AI館：おやつを食べたのは誰だ")
    print("  3ゲームキャンペーン")
    print("=" * 60)

    results = []

    for game_id in range(1, 4):
        turn_offset = (game_id - 1) * 100

        print(f"\n{'='*60}")
        print(f"  🍪 Game {game_id} / 3 開始！")
        print(f"{'='*60}")

        result = play_one_game(mxbs, CHARACTERS, game_id, turn_offset)
        results.append(result)

        game_end_turn = turn_offset + 6
        culprit_names = " と ".join(c.name for c in result.culprits)
        winner_text = "マスターの勝ち" if result.winner == "master" else "マスターの負け"
        store_event(mxbs, f"Game {game_id}: 犯人は{culprit_names}。{winner_text}",
                    "game_summary", game_end_turn, {"game_id": game_id})

        for char in CHARACTERS:
            is_culprit = char in result.culprits
            was_caught = char in result.identified
            if is_culprit and was_caught:
                text = f"Game {game_id}で犯人だったがバレてしまった"
            elif is_culprit and not was_caught:
                text = f"Game {game_id}で犯人だったがバレなかった"
            else:
                text = f"Game {game_id}に参加した。{winner_text}"
            store_personal_memory(mxbs, char, text, game_end_turn,
                                  price=150, game_id=game_id)

        if game_id < 3:
            input("\n  [Enter] で次のゲームへ……")

    print(f"\n{'='*60}")
    print(f"  📊 キャンペーン結果")
    print(f"{'='*60}")
    wins = sum(1 for r in results if r.winner == "master")
    print(f"  マスター: {wins}勝 {3-wins}敗")
    for r in results:
        emoji = "🎉" if r.winner == "master" else "💀"
        culprit_names = " & ".join(c.name for c in r.culprits)
        identified_names = " & ".join(c.name for c in r.identified) if r.identified else "なし"
        print(f"  {emoji} Game {r.game_id}: 犯人={culprit_names}, 特定={identified_names}, {r.turns_played}ターン")

    stats = mxbs.stats()
    print(f"\n  MxBS統計: {stats}")
    mxbs.close()


if __name__ == "__main__":
    campaign()
