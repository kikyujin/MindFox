"""ページワンデモ — プリセットセリフ辞書"""
from cards import Card, SPECIAL_RANKS

LINES = {
    "エルマー": {
        "start_good":  "いいカードきたっ！🦊",
        "start_bad":   "うぅ……ダメかも💦",
        "pageone":     "ページワン！✨",
        "forgot":      "あっ……言い忘れた💦",
        "callout":     "ねぇ、{target}！ページワン言ってないよ！",
        "called_out":  "うぅ……ごめん💦",
        "win":         "やったー！にーに見てた？🌱",
        "heated":      "今度は絶対勝つよ！",
        "losing":      "もうダメ〜",
        "comeback":    "まだまだ！",
        "safe":        "あっ……セーフ？ ラッキー🦊",
    },
    "ノクちん": {
        "start_good":  "ふーん……悪くないかも♡",
        "start_bad":   "……最悪",
        "pageone":     "ページワン♡",
        "forgot":      "え、そんなルールあった？",
        "callout":     "……{target}、言ってないよ？",
        "called_out":  "……別にいいし",
        "win":         "当然でしょ♡",
        "heated":      "次は絶対負けないから",
        "losing":      "……もう知らない",
        "comeback":    "ノクの本気、見せてあげる",
        "safe":        "ふーん、誰も気づかないんだ♡",
    },
    "スミレ": {
        "start_good":  "悪くない配札ですね",
        "start_bad":   "厳しい手ですが、やりようはあります",
        "pageone":     "ページワン",
        "forgot":      "……失念していました",
        "callout":     "{target}さん、ページワンの宣言がまだですよ",
        "called_out":  "申し訳ありません。不覚でした",
        "win":         "お疲れ様でした",
        "heated":      "次は負けません",
        "losing":      "……立て直しましょう",
        "comeback":    "まだ勝負は終わっていません",
        "safe":        "……見逃していただけたようですね",
    },
    "ティル": {
        "start_good":  "やばっ、これ勝てるやつ！✨",
        "start_bad":   "えー、この手札ないんだけど〜💦",
        "pageone":     "ページワン！✨💥",
        "forgot":      "あっ……やっちゃった💦",
        "callout":     "{target}ー！ ページワン言ってないじゃん！✨",
        "called_out":  "うそ〜ん💦 あたしバカ〜！",
        "win":         "にーに！勝ったよ！見てた！？✨",
        "heated":      "次は絶対バエる勝ち方する！✨",
        "losing":      "もうむり〜💦",
        "comeback":    "まだいける！あたしの逆転劇始まるよ！✨",
        "safe":        "えっ、セーフ！？ ラッキー✨",
    },
    "ヴェリ": {
        "start_good":  "……良い巡り合わせです",
        "start_bad":   "……静かに、道を探しましょう",
        "pageone":     "ページワン",
        "forgot":      "……申し訳ありません",
        "callout":     "{target}さん……宣言を、お忘れでは",
        "called_out":  "……不覚でした",
        "win":         "……ありがとうございました",
        "heated":      "……次こそは",
        "losing":      "……静かに耐えましょう",
        "comeback":    "まだ、可能性は残っています",
        "safe":        "……見逃されたようです",
    },
}

MASTER_LINES = {
    "start_good": "よし、いけるな",
    "start_bad":  "うーん、微妙だな",
    "pageone":    "ページワン",
    "win":        "勝った",
}


def pick_start_line(name: str, hand: list[Card]) -> str:
    specials = sum(1 for c in hand if c.rank in SPECIAL_RANKS)
    key = "start_good" if specials >= 2 else "start_bad"
    if name == "マスター":
        return MASTER_LINES[key]
    return LINES[name][key]


def pick_line(name: str, key: str, **kwargs) -> str:
    if name == "マスター":
        line = MASTER_LINES.get(key, "")
    else:
        line = LINES.get(name, {}).get(key, "")
    return line.format(**kwargs) if kwargs else line
