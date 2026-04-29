"""AI館おやつデモ — LLM通信"""
import json
import re
import random
import requests
from typing import Optional

from characters import Character

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:26b"


def call_ollama(prompt: str, temperature: float = 0.7) -> str:
    resp = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }, timeout=120)
    resp.raise_for_status()
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
    edible_names: list[str],
    turn: int,
    turn_in_game: int,
    memories: str,
    today_events: str,
) -> dict:
    prompt = f"""あなたたちは犯人です。
{culprit_a.name}と{culprit_b.name}が夜、こっそり相談しています。

## 性格
{culprit_a.name}: {culprit_a.personality}
{culprit_b.name}: {culprit_b.personality}

## 標的選択の傾向
{culprit_a.name}: {culprit_a.target_strategy}
{culprit_b.name}: {culprit_b.target_strategy}

## 現在の状況
ターン{turn_in_game}の夜。
食べられるのは: {edible_names}

## 過去の記憶
{memories}

## 今日の昼に起きたこと
{today_events}

## 指示
2人の会話を生成してください。
なぜその相手を狙うのか、理由もセリフに含めてください。
{culprit_a.name}の口調（一人称: {culprit_a.pronoun}）、
{culprit_b.name}の口調（一人称: {culprit_b.pronoun}）で。

JSONのみで回答:
{{"conversation": [{{"speaker": "{culprit_a.name}", "speech": "セリフ", "gesture": "しぐさ"}}, {{"speaker": "{culprit_b.name}", "speech": "セリフ", "gesture": "しぐさ"}}], "target": "おやつを食べる対象の名前", "reason": "選択理由"}}"""

    raw = call_ollama(prompt, temperature=0.8)
    result = parse_json_response(raw)
    if result is None or "target" not in result:
        target = random.choice(edible_names)
        result = {
            "conversation": [
                {"speaker": culprit_a.name, "speech": f"……{target}のにしよう", "gesture": ""},
                {"speaker": culprit_b.name, "speech": "……うん", "gesture": ""},
            ],
            "target": target,
            "reason": "フォールバック（LLM応答パース失敗）",
        }
    if result["target"] not in edible_names:
        result["target"] = random.choice(edible_names)
    return result


def generate_solo_night(
    culprit: Character,
    edible_names: list[str],
    turn: int,
    turn_in_game: int,
    memories: str,
) -> dict:
    prompt = f"""あなたは{culprit.name}です。犯人です。
相棒がバレてしまい、あなた1人で行動しています。

## 性格
{culprit.personality}

## 食べられるのは
{edible_names}

## 記憶
{memories}

## 指示
誰のおやつを食べるか決めて、その時の独り言を生成してください。
JSONのみで回答:
{{"speech": "独り言", "gesture": "しぐさ", "target": "対象の名前", "reason": "理由"}}"""

    raw = call_ollama(prompt, temperature=0.8)
    result = parse_json_response(raw)
    if result is None or "target" not in result:
        target = random.choice(edible_names)
        result = {
            "speech": "……", "gesture": "", "target": target,
            "reason": "フォールバック",
            "conversation": [{"speaker": culprit.name, "speech": "……", "gesture": ""}],
        }
    if "conversation" not in result:
        result["conversation"] = [
            {"speaker": culprit.name, "speech": result.get("speech", ""), "gesture": result.get("gesture", "")}
        ]
    if result["target"] not in edible_names:
        result["target"] = random.choice(edible_names)
    return result


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
