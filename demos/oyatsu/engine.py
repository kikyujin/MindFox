"""AI館おやつデモ — ゲームエンジン"""
import random
from dataclasses import dataclass, field

from characters import Character, CHARACTERS, GROUP_ALL, SYSTEM_OWNER, get_character_by_name, alive_list_with_gender
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
    generate_ending_comments,
)


def choose_target(
    culprits_alive: list,
    edible: list,
    mxbs,
    turn: int,
) -> tuple:
    if len(edible) == 1:
        return edible[0], "最後の1人"

    scores = {}
    for target in edible:
        score = random.uniform(0.0, 1.0)
        if "analyst" in target.archetype or "leader" in target.archetype:
            score += 0.2
        if target.archetype == "impulsive":
            score += 0.1
        if target.archetype == "contrarian":
            score -= 0.15
        if target.archetype == "compliant":
            score -= 0.1
        if target.archetype == "observer":
            score += 0.05
        if target.archetype == "mediator":
            score -= 0.1
        scores[target] = score

    target = max(scores, key=scores.get)
    reason = f"脅威度スコア最高({scores[target]:.2f})"
    return target, reason


@dataclass
class GameResult:
    game_id: int
    culprits: list
    identified: list
    winner: str
    turns_played: int
    events_log: list = field(default_factory=list)
    night_plot_ids: list = field(default_factory=list)


def play_one_game(mxbs: MxBSBridge, characters: list[Character],
                  game_id: int, turn_offset: int) -> GameResult:
    culprits = random.sample(characters, 2)
    alive = list(characters)
    identified = []
    events_log = []
    today_events = ""

    night_plot_ids = []
    miss_count = 0
    MAX_MISSES = 1

    for turn_in_game in range(1, 6):
        turn = turn_offset + turn_in_game

        culprits_alive = [c for c in culprits if c in alive and c not in identified]
        edible = [c for c in alive if c not in culprits]

        if not edible:
            result = GameResult(game_id, culprits, identified, "culprits", turn_in_game, events_log, night_plot_ids)
            show_ending(mxbs, result, characters, turn)
            return result

        if not culprits_alive:
            result = GameResult(game_id, culprits, identified, "master", turn_in_game, events_log, night_plot_ids)
            show_ending(mxbs, result, characters, turn)
            return result

        # === 夜フェイズ ===
        print(f"\n{'─'*50}")
        print(f"  🌙 ターン{turn_in_game} — 夜")
        print(f"{'─'*50}")

        target_char, target_reason = choose_target(culprits_alive, edible, mxbs, turn)
        alive_gender_str = alive_list_with_gender(alive)

        if len(culprits_alive) == 2:
            ca, cb = culprits_alive
            memories = get_memories_for_prompt(mxbs, ca, turn, limit=5)
            night = llm_night_plot(ca, cb, target_char.name, target_reason,
                                   turn_in_game, memories,
                                   victim_char=target_char,
                                   alive_with_gender=alive_gender_str)
        else:
            ca = culprits_alive[0]
            memories = get_memories_for_prompt(mxbs, ca, turn, limit=5)
            night = llm_solo_night(ca, target_char.name, target_reason,
                                   turn_in_game, memories,
                                   victim_char=target_char,
                                   alive_with_gender=alive_gender_str)
            cb = [c for c in culprits if c != ca][0]

        victim = get_character_by_name(night["target"])
        alive.remove(victim)

        night_text = " / ".join(
            f'{e["speaker"]}「{e["speech"]}」({e.get("gesture","")})'
            for e in night.get("conversation", [])
        )
        night_cell_id = mem_store_night_plot(mxbs, night_text, culprits[0], culprits[1],
                                             turn, victim.name)
        night_plot_ids.append({
            "cell_id": night_cell_id,
            "turn_in_game": turn_in_game,
            "target": victim.name,
            "text": night_text,
        })

        # === 朝フェイズ ===
        print(f"\n{'─'*50}")
        print(f"  ☀️ ターン{turn_in_game} — 朝")
        print(f"{'─'*50}")
        print(f"\n  😱 {victim.name}のおやつがなくなりました……")

        vr = night.get("victim_reaction", {})
        victim_speech = vr.get("speech", "……")
        victim_gesture = vr.get("gesture", "")
        print(f"  {victim.name}「{victim_speech}」({victim_gesture})")

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
                      pronoun="", master_call="", archetype="", gender="",
                      personality="", testimony_style="", liar_style="",
                      target_strategy=""),
            turn,
        )
        mem1 = get_memories_for_prompt(mxbs, first, turn)
        alive_names = [c.name for c in witnesses]

        witness_gender_str = alive_list_with_gender(witnesses)
        t1 = llm_testimony(
            first, first in culprits, turn, turn_in_game,
            alive_names, victim.name, mem1, mood1, diplo1,
            "\n".join(events_log[-3:]),
            alive_with_gender=witness_gender_str,
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
            alive_with_gender=witness_gender_str,
        )
        print(f"\n  {second.name}「{t2.get('speech','')}」")
        print(f"    ({t2.get('gesture','')})")

        store_testimony(mxbs, second, f"{second.name}の証言: {t2.get('speech','')}",
                       "testimony_accuse", turn, {"target": t2.get("target","")})

        today_events = f"{victim.name}のおやつがなくなった。{first.name}と{second.name}が証言した。"
        master_passed = False

        # === 犯人指名フェイズ ===
        remaining_chances = MAX_MISSES - miss_count
        print(f"\n  🔍 犯人を指名しますか？（パスも可）（残りチャンス: {remaining_chances}回）")
        print(f"    [0] パス")
        for i, c in enumerate(witnesses):
            print(f"    [{i+1}] {c.name}")

        acc_choice = input("  > ").strip()
        if not acc_choice or acc_choice == "0":
            master_passed = True
            today_events += "\n※ マスターは犯人指名をパスしました。"
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
                        result = GameResult(game_id, culprits, identified, "master", turn_in_game, events_log, night_plot_ids)
                        show_ending(mxbs, result, characters, turn)
                        return result
                else:
                    miss_count += 1
                    remaining_chances = MAX_MISSES - miss_count
                    print(f"\n  ❌ ハズレ……{accused.name}は無実でした。（残りチャンス: {remaining_chances}回）")
                    miss = generate_reaction(accused,
                        f"マスターに犯人だと疑われましたが、無実です。濡れ衣です。", turn)
                    print(f"  {accused.name}「{miss.get('speech','')}」({miss.get('gesture','')})")
                    store_event(mxbs, f"マスターが{accused.name}を犯人と指名したがハズレだった",
                               "accusation_miss", turn, {"accused": accused.slug})
                    events_log.append(f"ターン{turn_in_game}: {accused.name}に濡れ衣（ハズレ）")

                    if miss_count >= MAX_MISSES:
                        print(f"\n  💀 ハズレ{MAX_MISSES}回！ マスターの負けです……")
                        result = GameResult(game_id, culprits, identified, "culprits", turn_in_game, events_log, night_plot_ids)
                        show_ending(mxbs, result, characters, turn)
                        return result

    result = GameResult(game_id, culprits, identified, "culprits", 5, events_log, night_plot_ids)
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

    if result.night_plot_ids:
        print(f"\n  【犯人の夜 — リプレイ】")
        for plot in result.night_plot_ids:
            print(f"    ターン{plot['turn_in_game']}の夜（→ {plot['target']}のおやつを狙う）:")
            print(f"      {plot['text']}")
    else:
        print(f"\n  【犯人の夜 — リプレイ】")
        print(f"  （night_plot データなし）")

    print(f"\n  【みんなの感想】")
    comments = generate_ending_comments(
        characters, result.culprits, result.identified,
        result.winner, result.game_id,
    )
    for comment in comments:
        name = comment.get("name", "???")
        speech = comment.get("speech", "……")
        gesture = comment.get("gesture", "")
        char = None
        for c in characters:
            if c.name == name:
                char = c
                break
        emoji = "🔴" if char and char in result.culprits else "⚪"
        print(f"  {emoji} {name}「{speech}」({gesture})")
