"""gemma4:e4b によるセリフ生成"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e4b"

DIALOGUE_PROMPT = """あなたは「{name}」というキャラクターです。

【最重要ルール — 口調厳守】
以下の口調ルールは絶対に破らないでください。反応タイプがどうであれ、口調は必ずこの設定に従います。

{speech_style}

【性格】
{personality_desc}

【今の状況】
場所: {location}
時間: {time_slot}
{situation_detail}

【反応タイプ（態度の指針。口調ではない）】
{reaction_hint}

上記の反応タイプに合った態度で、上記の口調ルールを厳守したセリフを1つだけ生成してください。
- 20〜40文字
- セリフのみ出力（「」は不要）
"""


def generate_dialogue(
    character: dict,
    location: str,
    slot: str,
    reaction_hint: str,
    reaction_context: str = "",
    situation_detail: str = "",
) -> str:
    prompt = DIALOGUE_PROMPT.format(
        name=character["name"],
        personality_desc=character["personality_desc"],
        speech_style=character["speech_style"],
        location=location,
        time_slot=slot,
        situation_detail=situation_detail,
        reaction_hint=reaction_hint,
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        if text.startswith("「") and text.endswith("」"):
            text = text[1:-1]
        return text if text else f"（{reaction_hint}）"
    except Exception as e:
        print(f"  [dialogue] 生成失敗: {e}")
        return f"（{reaction_hint}）"
