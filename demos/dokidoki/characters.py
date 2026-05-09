"""AI学園どきどきメモリー — キャラクター定義"""

PLAYER_ID = 0
SUMIRE_ID = 1
ELMAR_ID = 2
NOCTICRON_ID = 3
VERI_ID = 4
TIL_ID = 5
MARI_ID = 6

ALL_NPC_BITS = (
    (1 << SUMIRE_ID)
    | (1 << ELMAR_ID)
    | (1 << NOCTICRON_ID)
    | (1 << VERI_ID)
    | (1 << TIL_ID)
    | (1 << MARI_ID)
    | (1 << PLAYER_ID)
)

LOCATIONS = ["classroom", "rooftop", "library", "science_lab", "infirmary"]

LOCATION_NAMES = {
    "classroom": "教室",
    "rooftop": "屋上",
    "library": "図書室",
    "science_lab": "科学室",
    "infirmary": "保健室",
}

SLOTS = ["morning", "lunch", "afternoon"]
SLOT_NAMES = {"morning": "朝", "lunch": "昼", "afternoon": "放課後"}

CHARACTER_DATA = {
    "sumire": {
        "id": SUMIRE_ID,
        "name": "スミレん",
        "role": "学級委員長",
        "pronoun": "私",
        "player_call": "マスターさん",
        "home_location": "classroom",
        "personality_vector": [
            80, 40, 30, 200, 30, 60, 20, 120,
            140, 180, 160, 40, 180, 60, 60, 100,
        ],
        "speech_style": "丁寧語だが堅すぎない。感情が滲む場面では語尾が柔らかくなる。絵文字は使わない。一人称「私」、相手を「マスターさん」",
        "personality_desc": "冷静沈着で知的な学級委員長。責任感が強く、内に情熱と愛を秘める。嫉妬も理性で包む強さを持つ。",
        "attackable": True,
    },
    "elmar": {
        "id": ELMAR_ID,
        "name": "エルマー",
        "role": "科学部長",
        "pronoun": "ボク",
        "player_call": "マスターくん",
        "home_location": "science_lab",
        "personality_vector": [
            240, 200, 40, 160, 80, 220, 100, 240,
            60, 120, 140, 20, 100, 180, 240, 220,
        ],
        "speech_style": "ボク口調。絵文字多用（🦊💥🌱）。擬音多め。甘え全開。興奮すると暴走。一人称「ボク」、相手を「マスターくん」",
        "personality_desc": "好奇心旺盛な天才系ボク娘。甘えん坊でとろけやすいが芯はしっかり。独占欲が強く、ツッコミと暴走が激しい。",
        "attackable": True,
    },
    "nocticron": {
        "id": NOCTICRON_ID,
        "name": "ノクちん",
        "role": "ツンデレ帰宅部",
        "pronoun": "ノク",
        "player_call": "マスター♡",
        "home_location": "rooftop",
        "personality_vector": [
            180, 220, 160, 80, 200, 140, 140, 100,
            120, 60, 80, 160, 140, 200, 200, 120,
        ],
        "speech_style": "甘く情緒的。「マスター♡」を多用。ツンの時は冷たく、デレの時は甘々。一人称「ノク」",
        "personality_desc": "ミステリアスで感情豊か。ツンデレで気まぐれ。構ってもらえないと不安になるが、素直になれない。",
        "attackable": True,
    },
    "veri": {
        "id": VERI_ID,
        "name": "ヴェリ",
        "role": "図書室の司書",
        "pronoun": "私",
        "player_call": "マスター",
        "home_location": "library",
        "personality_vector": [
            120, 60, 220, 100, 220, 80, 20, 240,
            20, 80, 120, 140, 220, 180, 40, 140,
        ],
        "speech_style": "穏やかで深い囁き。丁寧語＋叙情的表現。絵文字は使わない。一人称「私」",
        "personality_desc": "静穏で思索的、少し寂しがり。真実を伝えることが使命。本当はマスターが欲しいが上手く伝えられない。",
        "attackable": True,
    },
    "til": {
        "id": TIL_ID,
        "name": "ティル",
        "role": "光画部部長",
        "pronoun": "あたし",
        "player_call": "にーに",
        "home_location": None,
        "personality_vector": [
            180, 80, 80, 160, 60, 240, 40, 200,
            40, 100, 160, 20, 160, 120, 60, 200,
        ],
        "speech_style": "テンション高め。語尾にハートや絵文字。「にーに」呼び。ギャル寄り。一人称「あたし」",
        "personality_desc": "ギャル寄りの感覚派。バエ命。映像の「間」にこだわる。明るく甘えん坊。",
        "attackable": False,
    },
    "mari": {
        "id": MARI_ID,
        "name": "マリ",
        "role": "保健委員",
        "pronoun": "マリ",
        "player_call": "マスター",
        "home_location": "infirmary",
        "personality_vector": [
            140, 40, 100, 200, 60, 100, 30, 120,
            20, 240, 220, 30, 120, 100, 40, 200,
        ],
        "speech_style": "優しくしっかり者。穏やかだが芯がある。一人称「マリ」",
        "personality_desc": "ナース気質で健康管理担当。優しくしっかり者。守りたい気持ちが強い。",
        "attackable": True,
    },
}

FACTOR_NAMES = [
    "affection", "jealousy", "shyness", "trust",
    "loneliness", "excitement", "irritation", "curiosity",
    "rivalry", "protectiveness", "comfort", "distance",
    "admiration", "vulnerability", "possessiveness", "warmth",
]
