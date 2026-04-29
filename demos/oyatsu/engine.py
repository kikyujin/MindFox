"""AI館おやつデモ — ゲームエンジン"""
import random
from dataclasses import dataclass, field

from characters import Character, CHARACTERS, GROUP_ALL, SYSTEM_OWNER, get_character_by_name
from memory import (
    MxBSBridge, get_agent_mood, compute_diplomacy_toward,
    store_testimony, store_night_plot as mem_store_night_plot,
    store_event, store_personal_memory, get_memories_for_prompt, Mood,
)
from llm import (
    generate_testimony as llm_testimony,
    generate_night_plot as llm_night_plot,
    generate_solo_night as llm_solo_night,
    generate_reaction,
)


@dataclass
class GameResult:
    game_id: int
    culprits: list
    identified: list
    winner: str
    turns_played: int
    events_log: list = field(default_factory=list)


def play_one_game(mxbs: MxBSBridge, characters: list[Character],
                  game_id: int, turn_offset: int) -> GameResult:
    culprits = random.sample(characters, 2)
    alive = list(characters)
    identified = []
    events_log = []
    today_events = ""

    print(f"\n  犯人は……{'と'.join(c.name for c in culprits)}（デバッグ表示）")

    for turn_in_game in range(1, 6):
        turn = turn_offset + turn_in_game

        culprits_alive = [c for c in culprits if c in alive and c not in identified]
        edible = [c for c in alive if c not in culprits]

        if not edible:
            result = GameResult(game_id, culprits, identified, "culprits", turn_in_game, events_log)
            show_ending(mxbs, result, characters, turn)
            return result

        if not culprits_alive:
            result = GameResult(game_id, culprits, identified, "master", turn_in_game, events_log)
            show_ending(mxbs, result, characters, turn)
            return result

        # === 夜フェイズ ===
        print(f"\n{'─'*50}")
        print(f"  🌙 ターン{turn_in_game} — 夜")
        print(f"{'─'*50}")

        if len(culprits_alive) == 2:
            ca, cb = culprits_alive
            memories = get_memories_for_prompt(mxbs, ca, turn, limit=5)
            night = llm_night_plot(ca, cb, [c.name for c in edible],
                                   turn, turn_in_game, memories, today_events)
        else:
            ca = culprits_alive[0]
            memories = get_memories_for_prompt(mxbs, ca, turn, limit=5)
            night = llm_solo_night(ca, [c.name for c in edible],
                                   turn, turn_in_game, memories)
            cb = [c for c in culprits if c != ca][0]

        victim = get_character_by_name(night["target"])
        alive.remove(victim)

        night_text = " / ".join(
            f'{e["speaker"]}「{e["speech"]}」({e.get("gesture","")})'
            for e in night.get("conversation", [])
        )
        mem_store_night_plot(mxbs, night_text, culprits[0], culprits[1],
                            turn, victim.name)

        # === 朝フェイズ ===
        print(f"\n{'─'*50}")
        print(f"  ☀️ ターン{turn_in_game} — 朝")
        print(f"{'─'*50}")
        print(f"\n  😱 {victim.name}のおやつがなくなりました……")

        farewell = generate_reaction(victim, "あなたのおやつが食べられてしまいました。ゲームから脱落です。", turn)
        print(f"  {victim.name}「{farewell.get('speech','')}」({farewell.get('gesture','')})")

        event_text = f"{victim.name}のおやつがなくなり脱落した"
        store_event(mxbs, event_text, "elimination", turn, {"victim": victim.slug})
        events_log.append(f"ターン{turn_in_game}: {event_text}")

        # === 証言フェイズ ===
        witnesses = [c for c in alive if c not in identified]
        print(f"\n  📢 証言フェイズ（生存者: {', '.join(c.name for c in witnesses)}）")
        print(f"  誰に話を聞きますか？")
        for i, c in enumerate(witnesses):
            print(f"    [{i+1}] {c.name}")

        choice = input("  > ").strip()
        try:
            first = witnesses[int(choice) - 1]
        except (ValueError, IndexError):
            first = random.choice(witnesses)

        mood1 = get_agent_mood(mxbs, first, turn)
        diplo1 = compute_diplomacy_toward(
            mxbs, first,
            Character(id=98, slug="master", name="マスター", bit=0,
                      pronoun="", master_call="", archetype="", personality="",
                      testimony_style="", liar_style="", target_strategy=""),
            turn,
        )
        mem1 = get_memories_for_prompt(mxbs, first, turn)
        alive_names = [c.name for c in witnesses]

        t1 = llm_testimony(
            first, first in culprits, turn, turn_in_game,
            alive_names, victim.name, mem1, mood1, diplo1,
            "\n".join(events_log[-3:]),
        )
        print(f"\n  {first.name}「{t1.get('speech','')}」")
        print(f"    ({t1.get('gesture','')})")

        store_testimony(mxbs, first, f"{first.name}の証言: {t1.get('speech','')}",
                       "testimony_accuse", turn, {"target": t1.get("target","")})

        # 2人目の証言
        second_name = t1.get("target", "")
        second = None
        for c in witnesses:
            if c.name == second_name and c != first:
                second = c
                break
        if second is None:
            candidates = [c for c in witnesses if c != first]
            second = random.choice(candidates) if candidates else first

        mood2 = get_agent_mood(mxbs, second, turn)
        mem2 = get_memories_for_prompt(mxbs, second, turn)
        t2 = llm_testimony(
            second, second in culprits, turn, turn_in_game,
            alive_names, victim.name, mem2, mood2, 0.5,
            "\n".join(events_log[-3:]),
        )
        print(f"\n  {second.name}「{t2.get('speech','')}」")
        print(f"    ({t2.get('gesture','')})")

        store_testimony(mxbs, second, f"{second.name}の証言: {t2.get('speech','')}",
                       "testimony_accuse", turn, {"target": t2.get("target","")})

        today_events = f"{victim.name}のおやつがなくなった。{first.name}と{second.name}が証言した。"

        # === 犯人指名フェイズ ===
        print(f"\n  🔍 犯人を指名しますか？（パスも可）")
        print(f"    [0] パス")
        for i, c in enumerate(witnesses):
            print(f"    [{i+1}] {c.name}")

        acc_choice = input("  > ").strip()
        if acc_choice and acc_choice != "0":
            try:
                accused = witnesses[int(acc_choice) - 1]
            except (ValueError, IndexError):
                accused = None

            if accused:
                if accused in culprits:
                    print(f"\n  🎉 正解！ {accused.name}は犯人でした！")
                    hit = generate_reaction(accused,
                        f"マスターに犯人だとバレました。ターン{turn_in_game}。", turn)
                    print(f"  {accused.name}「{hit.get('speech','')}」({hit.get('gesture','')})")
                    identified.append(accused)
                    store_event(mxbs, f"マスターが{accused.name}を犯人と特定した",
                               "accusation_hit", turn, {"accused": accused.slug})
                    events_log.append(f"ターン{turn_in_game}: {accused.name}が犯人と判明！")

                    if len(identified) == 2:
                        result = GameResult(game_id, culprits, identified, "master", turn_in_game, events_log)
                        show_ending(mxbs, result, characters, turn)
                        return result
                else:
                    print(f"\n  ❌ ハズレ……{accused.name}は無実でした。")
                    miss = generate_reaction(accused,
                        f"マスターに犯人だと疑われましたが、無実です。濡れ衣です。", turn)
                    print(f"  {accused.name}「{miss.get('speech','')}」({miss.get('gesture','')})")
                    store_event(mxbs, f"マスターが{accused.name}を犯人と指名したがハズレだった",
                               "accusation_miss", turn, {"accused": accused.slug})
                    events_log.append(f"ターン{turn_in_game}: {accused.name}に濡れ衣（ハズレ）")

    result = GameResult(game_id, culprits, identified, "culprits", 5, events_log)
    show_ending(mxbs, result, characters, turn_offset + 5)
    return result


def show_ending(mxbs: MxBSBridge, result: GameResult,
                characters: list[Character], turn: int):
    print(f"\n{'='*50}")
    if result.winner == "master":
        print(f"  🎉 マスターの勝ち！ Game {result.game_id}")
    else:
        print(f"  💀 マスターの負け…… Game {result.game_id}")
    print(f"  犯人は {result.culprits[0].name} と {result.culprits[1].name} でした。")
    print(f"{'='*50}")

    print(f"\n  【犯人の夜 — リプレイ】")
    print(f"  （実装予定: night_plot セルの表示）")

    print(f"\n  【みんなの感想】")
    for char in characters:
        is_culprit = char in result.culprits
        if result.winner == "master":
            if is_culprit:
                situation = "犯人だとバレました。マスターの勝ちです。一言どうぞ。"
            else:
                situation = "おやつ事件が解決しました！マスターが犯人を見破りました。一言どうぞ。"
        else:
            if is_culprit:
                situation = "犯人として勝利しました！マスターを欺きました。勝利宣言をどうぞ。"
            else:
                situation = "おやつを守れませんでした……マスターの負けです。一言どうぞ。"

        reaction = generate_reaction(char, situation, turn)
        emoji = "🔴" if is_culprit else "⚪"
        print(f"  {emoji} {char.name}「{reaction.get('speech','')}」({reaction.get('gesture','')})")
