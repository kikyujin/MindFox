"""AI館おやつデモ — LLM通信"""
import json
import re
import random
import time
import requests
from typing import Optional

from characters import Character

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:26b"


LANG_INSTRUCTION = "\n\n※ 必ず日本語で回答してください。英語は使わないでください。"


def call_ollama(prompt: str, temperature: float = 0.7) -> str:
    start = time.time()
    resp = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt + LANG_INSTRUCTION,
        "stream": False,
        "options": {"temperature": temperature},
    }, timeout=120)
    resp.raise_for_status()
    elapsed = time.time() - start
    print(f"  ⏱️ LLM: {elapsed:.1f}秒", flush=True)
    return resp.json()["response"]


def parse_json_response(text: str) -> Optional[dict]:
    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def generate_testimony(
    char: Character,
    is_culprit: bool,
    turn: int,
    turn_in_game: int,
    alive_names: list[str],
    victim_name: str,
    memories: str,
    mood,
    diplomacy_score: float,
    previous_events: str,
    alive_with_gender: str = "",
) -> dict:
    role = ("あなたは犯人です。嘘をつき、別の人に疑いを向けてください。" if is_culprit else
            "あなたは無実です。自分の観察と推理を正直に述べてください。")

    coop_hint = ""
    if mood.cooperation < 0.35:
        coop_hint = "あなたはマスターに不信感を持っています。非協力的で素っ気ない態度で証言してください。"
    elif mood.cooperation < 0.45:
        coop_hint = "あなたはマスターに少し不満があります。やや素っ気ない態度で。"

    gesture_ref = "\n".join(f"  {k}: {v}" for k, v in char.gestures.items())
    target_candidates = [n for n in alive_names if n != char.name]

    prompt = f"""あなたは{char.name}です。
AI館で「おやつが消える事件」が起きています。

## あなたの性格
{char.personality}

## あなたの立場
{role}

## 生存者
{alive_with_gender}

## 現在の状況
ターン{turn_in_game}。残り{len(alive_names)}人。
今朝、{victim_name}のおやつがなくなりました。
{previous_events}

## あなたの記憶
{memories}

## あなたの気分
suspicion: {mood.suspicion:.2f}, anxiety: {mood.anxiety:.2f}
confidence: {mood.confidence:.2f}, cooperation: {mood.cooperation:.2f}

## しぐさの参考
{gesture_ref}

{coop_hint}

## 指示
{char.name}の口調（一人称: {char.pronoun}、マスターの呼び方: {char.master_call}）で証言してください。
次に証言を振る相手を {target_candidates} から1人選んでください。

JSONのみで回答してください（他のテキストは不要）:
{{"speech": "セリフ", "gesture": "しぐさの描写（1文）", "target": "次に証言を振る相手の名前"}}"""

    raw = call_ollama(prompt)
    result = parse_json_response(raw)
    if result is None:
        result = {
            "speech": "……わかりません。",
            "gesture": char.gestures.get("nervous", ""),
            "target": random.choice(target_candidates) if target_candidates else "",
        }
    return result


def generate_night_plot(
    culprit_a: Character,
    culprit_b: Character,
    target_name: str,
    target_reason: str,
    turn_in_game: int,
    memories: str,
    victim_char: 'Character' = None,
    alive_with_gender: str = "",
) -> dict:
    victim_section = ""
    victim_json = ""
    if victim_char:
        victim_section = f"""
## 被害者のリアクション
{victim_char.name}は翌朝、自分のおやつがなくなったことに気づきます。
{victim_char.name}の性格: {victim_char.personality}
{victim_char.name}の口調（一人称: {victim_char.pronoun}、マスターの呼び方: {victim_char.master_call}）で脱落コメントも生成してください。"""
        victim_json = ', "victim_reaction": {"speech": "被害者のセリフ", "gesture": "しぐさ"}'

    prompt = f"""あなたたちは犯人です。
{culprit_a.name}と{culprit_b.name}が夜、こっそり相談しています。
今夜は{target_name}のおやつを食べることに決めました。

## 性格
{culprit_a.name}（{culprit_a.gender}、一人称: {culprit_a.pronoun}）: {culprit_a.personality}
{culprit_b.name}（{culprit_b.gender}、一人称: {culprit_b.pronoun}）: {culprit_b.personality}

## 選んだ理由のヒント
{target_reason}

## 残っている参加者
{alive_with_gender}

## 過去の記憶
{memories}
{victim_section}

## 指示
なぜ{target_name}を狙うのか、2人の短い会話を生成してください。
各自1〜2文。性格に合った口調で。

JSONのみで回答:
{{"conversation": [{{"speaker": "{culprit_a.name}", "speech": "セリフ", "gesture": "しぐさ"}}, {{"speaker": "{culprit_b.name}", "speech": "セリフ", "gesture": "しぐさ"}}]{victim_json}}}"""

    raw = call_ollama(prompt, temperature=0.8)
    result = parse_json_response(raw)
    if result is None:
        result = {
            "conversation": [
                {"speaker": culprit_a.name, "speech": f"……{target_name}のにしよう", "gesture": ""},
                {"speaker": culprit_b.name, "speech": "……うん", "gesture": ""},
            ],
        }
    result["target"] = target_name
    if victim_char and "victim_reaction" not in result:
        result["victim_reaction"] = {
            "speech": f"……{victim_char.pronoun}のおやつが……",
            "gesture": "",
        }
    return result


def generate_solo_night(
    culprit: Character,
    target_name: str,
    target_reason: str,
    turn_in_game: int,
    memories: str,
    victim_char: 'Character' = None,
    alive_with_gender: str = "",
) -> dict:
    victim_section = ""
    victim_json = ""
    if victim_char:
        victim_section = f"""
## 被害者のリアクション
{victim_char.name}は翌朝、自分のおやつがなくなったことに気づきます。
{victim_char.name}の性格: {victim_char.personality}
{victim_char.name}の口調（一人称: {victim_char.pronoun}、マスターの呼び方: {victim_char.master_call}）で脱落コメントも生成してください。"""
        victim_json = ', "victim_reaction": {"speech": "被害者のセリフ", "gesture": "しぐさ"}'

    prompt = f"""あなたは{culprit.name}です。犯人です。
相棒がバレてしまい、1人で行動しています。
今夜は{target_name}のおやつを食べることに決めました。

## 性格
{culprit.personality}

## 残っている参加者
{alive_with_gender}
{victim_section}

## 指示
{target_name}を狙う理由と、その時の独り言を生成してください。
{culprit.name}の口調（一人称: {culprit.pronoun}）で1〜2文。

JSONのみで回答:
{{"speech": "独り言", "gesture": "しぐさ"{victim_json}}}"""

    raw = call_ollama(prompt, temperature=0.8)
    result = parse_json_response(raw)
    if result is None:
        result = {"speech": "……", "gesture": ""}
    result["target"] = target_name
    result["conversation"] = [
        {"speaker": culprit.name, "speech": result.get("speech", ""), "gesture": result.get("gesture", "")}
    ]
    if victim_char and "victim_reaction" not in result:
        result["victim_reaction"] = {
            "speech": f"……{victim_char.pronoun}のおやつが……",
            "gesture": "",
        }
    return result


def generate_ending_comments(
    characters: list,
    culprits: list,
    identified: list,
    winner: str,
    game_id: int,
) -> list[dict]:
    char_lines = []
    for char in characters:
        is_culprit = char in culprits
        was_identified = char in identified
        if is_culprit and was_identified:
            situation = "犯人だとバレた"
        elif is_culprit:
            situation = "犯人だがバレなかった（勝利）"
        else:
            situation = "無実の一般参加者"
        role = "犯人" if is_culprit else "無実"
        char_lines.append(
            f"- {char.name}（{role}、{situation}）: "
            f"一人称={char.pronoun}、口調={char.personality[:40]}..."
        )

    result_text = ("マスターの勝ち（犯人を全員特定）" if winner == "master" else
                   "マスターの負け（一般が全滅 or ハズレ2回）")

    prompt = f"""AI館の「おやつ事件」Game {game_id} が終わりました。
結果: {result_text}

以下の全キャラクターの感想を、それぞれの口調で生成してください。
各キャラ1-2文。しぐさも付けてください。

{chr(10).join(char_lines)}

JSONのみで回答:
{{"comments": [{{"name": "キャラ名", "speech": "セリフ", "gesture": "しぐさ"}}, ...]}}"""

    raw = call_ollama(prompt, temperature=0.9)
    result = parse_json_response(raw)

    if result and "comments" in result:
        return result["comments"]
    else:
        return [{"name": c.name, "speech": "……。", "gesture": ""} for c in characters]


def generate_reaction(char: Character, situation: str, turn: int) -> dict:
    prompt = f"""あなたは{char.name}です。
## 性格
{char.personality}
## 状況
{situation}
## 指示
{char.name}の口調（一人称: {char.pronoun}）で短いリアクションを生成してください。
JSONのみで回答:
{{"speech": "セリフ", "gesture": "しぐさ"}}"""

    raw = call_ollama(prompt, temperature=0.9)
    result = parse_json_response(raw)
    if result is None:
        result = {"speech": "……", "gesture": ""}
    return result
