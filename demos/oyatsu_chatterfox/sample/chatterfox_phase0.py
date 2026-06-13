#!/usr/bin/env python3
"""
MxChatterFox Phase 0 — cosine カスケード検索 CLI プロトタイプ
シナリオ: 「おやつは誰がたべた」（6NPC × 8-12セリフ）

Usage:
    python chatterfox_phase0.py
    python chatterfox_phase0.py --threshold 0.35 --debug

MULTITAPPS INC. — 2026-05-28
"""

import math
import random
import argparse
from typing import Optional

# ═══════════════════════════════════════════════════════════
#  因子プリセット定義（おやつ聞き込みシナリオ用 16因子）
# ═══════════════════════════════════════════════════════════

FACTOR_NAMES = [
    "topic_snack",       # [0]  おやつ・食べ物
    "topic_time",        # [1]  時間帯
    "topic_place",       # [2]  場所
    "topic_person",      # [3]  人物
    "topic_evidence",    # [4]  証拠・物証
    "topic_alibi",       # [5]  アリバイ・行動
    "action_ask",        # [6]  聞く・教えて
    "action_suspect",    # [7]  疑う・追及
    "action_observe",    # [8]  見た・気づいた
    "emotion_nervous",   # [9]  動揺（NPC側）
    "emotion_honest",    # [10] 正直度
    "emotion_deflect",   # [11] はぐらかし度
    "personality_open",  # [12] 外向性
    "personality_impulsive",  # [13] 衝動性
    "reserved_1",        # [14]
    "reserved_2",        # [15]
]

# ═══════════════════════════════════════════════════════════
#  NPC 定義
# ═══════════════════════════════════════════════════════════

NPC_DEFS = {
    "elmar": {
        "name": "エルマー🦊",
        "archetype": "impulsive",
        "role": "innocent",
        "location": "北棟ラボ",
        "desc": "余計なことを口走るが嘘はつかない",
    },
    "sumire": {
        "name": "スミレん",
        "archetype": "analyst",
        "role": "innocent",
        "location": "西棟パーラー",
        "desc": "論理的で冷静。おやつ管理の責任者",
    },
    "noc": {
        "name": "ノクちん",
        "archetype": "contrarian",
        "role": "innocent",
        "location": "占いの館",
        "desc": "気まぐれだが核心を突く。占い好き",
    },
    "til": {
        "name": "ティル",
        "archetype": "impulsive",
        "role": "culprit",
        "location": "機材室",
        "desc": "★犯人★ 嘘をつくがボロが出る",
    },
    "veri": {
        "name": "ヴェリ",
        "archetype": "observer",
        "role": "innocent",
        "location": "アレーテイアの間",
        "desc": "静かに観察する。事実を淡々と述べる",
    },
    "mari": {
        "name": "マリ",
        "archetype": "mediator",
        "role": "innocent",
        "location": "医務室",
        "desc": "協力的。夜の見回り担当",
    },
}

# ═══════════════════════════════════════════════════════════
#  単語カード定義
# ═══════════════════════════════════════════════════════════

WORDS_INITIAL = [
    {"id": "w_oyatsu",      "text": "おやつ",     "slot": "WHO",
     "features": [220, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_hannin",      "text": "犯人",       "slot": "WHO",
     "features": [0, 0, 0, 200, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_minna",       "text": "みんな",     "slot": "WHO",
     "features": [0, 0, 0, 180, 0, 0, 0, 0, 0, 0, 0, 0, 150, 0, 0, 0]},
    {"id": "w_tabeta",      "text": "食べた",     "slot": "ACTION",
     "features": [200, 50, 0, 0, 0, 0, 0, 0, 180, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_mita",        "text": "見た",       "slot": "ACTION",
     "features": [0, 0, 0, 0, 120, 0, 0, 0, 220, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_shitteru",    "text": "知ってる",   "slot": "ACTION",
     "features": [0, 0, 0, 0, 0, 0, 220, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_dare",        "text": "誰",         "slot": "ACTION",
     "features": [0, 0, 0, 220, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_kinounoYoru", "text": "昨日の夜",   "slot": "WHAT",
     "features": [0, 220, 0, 0, 0, 80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_alibi",       "text": "アリバイ",   "slot": "WHAT",
     "features": [0, 80, 0, 0, 0, 220, 0, 120, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_shouko",      "text": "証拠",       "slot": "WHAT",
     "features": [0, 0, 0, 0, 220, 0, 0, 120, 0, 0, 0, 0, 0, 0, 0, 0]},
    {"id": "w_daidokoro",   "text": "台所",       "slot": "WHERE",
     "features": [80, 0, 220, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
]

WORDS_GETTABLE = {
    # === エルマー由来 ===
    "ガサゴソ音": {
        "id": "w_gasagoso", "text": "ガサゴソ音", "slot": "WHAT",
        "features": [0, 150, 80, 0, 180, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0]},
    "プリン": {
        "id": "w_purin", "text": "プリン", "slot": "WHO",
        "features": [220, 0, 0, 0, 150, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    "ティルが怪しい": {
        "id": "w_til_ayashii", "text": "ティルが怪しい", "slot": "WHO",
        "features": [0, 0, 0, 220, 80, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0, 0]},
    "エルマーは3時までラボ": {
        "id": "w_elmar_labo", "text": "エルマーは3時までラボ", "slot": "WHAT",
        "features": [0, 200, 100, 0, 0, 220, 0, 0, 0, 0, 200, 0, 0, 0, 0, 0]},
    "マリが台所掃除": {
        "id": "w_mari_daidokoro", "text": "マリが台所掃除", "slot": "WHAT",
        "features": [0, 100, 200, 180, 100, 100, 0, 0, 180, 0, 0, 0, 0, 0, 0, 0]},
    "包み紙": {
        "id": "w_tsutsumigami", "text": "包み紙", "slot": "WHAT",
        "features": [150, 0, 120, 0, 220, 0, 0, 0, 180, 0, 0, 0, 0, 0, 0, 0]},
    "ティルがご機嫌": {
        "id": "w_til_gokigen", "text": "ティルがご機嫌", "slot": "WHO",
        "features": [0, 80, 0, 220, 150, 0, 0, 150, 0, 0, 0, 0, 0, 0, 0, 0]},
    "2時半に廊下で音": {
        "id": "w_2ji_rouka", "text": "2時半に廊下で音", "slot": "WHAT",
        "features": [0, 220, 150, 0, 200, 80, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0]},
    # === スミレ由来 ===
    "おやつの管理表": {
        "id": "w_kanrihyou", "text": "おやつの管理表", "slot": "WHAT",
        "features": [200, 0, 80, 0, 150, 0, 0, 0, 0, 0, 200, 0, 0, 0, 0, 0]},
    "スミレは0時に就寝": {
        "id": "w_sumire_0ji", "text": "スミレは0時に就寝", "slot": "WHAT",
        "features": [0, 220, 0, 150, 0, 200, 0, 0, 0, 0, 200, 0, 0, 0, 0, 0]},
    "引き出しがずれていた": {
        "id": "w_hikidashi", "text": "引き出しがずれていた", "slot": "WHAT",
        "features": [0, 0, 200, 0, 220, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0]},
    # === ノクちん由来 ===
    "占いの暗示": {
        "id": "w_uranai", "text": "占いの暗示", "slot": "WHAT",
        "features": [0, 0, 0, 80, 150, 0, 0, 100, 0, 100, 0, 0, 0, 0, 0, 0]},
    "ノクは2時まで占い": {
        "id": "w_noc_2ji", "text": "ノクは2時まで占い", "slot": "WHAT",
        "features": [0, 220, 0, 150, 0, 200, 0, 0, 0, 0, 150, 0, 0, 0, 0, 0]},
    "衝動的な行動": {
        "id": "w_shoudou", "text": "衝動的な行動", "slot": "WHAT",
        "features": [0, 0, 0, 100, 100, 0, 0, 150, 0, 100, 0, 0, 0, 220, 0, 0]},
    # === ティル由来（嘘情報含む）===
    "ティルは部屋で編集と主張": {
        "id": "w_til_heya", "text": "ティルは部屋で編集と主張", "slot": "WHAT",
        "features": [0, 150, 100, 200, 0, 200, 0, 0, 0, 0, 0, 150, 0, 0, 0, 0]},
    "ティルが包装紙に反応": {
        "id": "w_til_tsutsumi", "text": "ティルが包装紙に反応", "slot": "WHO",
        "features": [100, 0, 0, 200, 200, 0, 0, 180, 0, 180, 0, 0, 0, 0, 0, 0]},
    # === ヴェリ由来 ===
    "ヴェリは1時まで書庫": {
        "id": "w_veri_1ji", "text": "ヴェリは1時まで書庫", "slot": "WHAT",
        "features": [0, 200, 100, 150, 0, 200, 0, 0, 0, 0, 200, 0, 0, 0, 0, 0]},
    "深夜2時に甘い匂い": {
        "id": "w_amai_nioi", "text": "深夜2時に甘い匂い", "slot": "WHAT",
        "features": [150, 220, 100, 0, 200, 0, 0, 0, 180, 0, 0, 0, 0, 0, 0, 0]},
    "廊下を南に向かう足音": {
        "id": "w_ashioto", "text": "廊下を南に向かう足音", "slot": "WHAT",
        "features": [0, 150, 200, 0, 200, 0, 0, 0, 220, 0, 0, 0, 0, 0, 0, 0]},
    "足音がティルに似ている": {
        "id": "w_ashioto_til", "text": "足音がティルに似ている", "slot": "WHO",
        "features": [0, 100, 100, 220, 200, 0, 0, 180, 150, 0, 0, 0, 0, 0, 0, 0]},
    # === マリ由来 ===
    "マリの見回り": {
        "id": "w_mari_mimawari", "text": "マリの見回り", "slot": "WHAT",
        "features": [0, 150, 100, 150, 0, 180, 0, 0, 150, 0, 200, 0, 0, 0, 0, 0]},
    "マリは1時に見回り": {
        "id": "w_mari_1ji", "text": "マリは1時に見回り", "slot": "WHAT",
        "features": [0, 220, 80, 150, 0, 200, 0, 0, 0, 0, 200, 0, 0, 0, 0, 0]},
    "朝の台所が散らかっていた": {
        "id": "w_asa_daidokoro", "text": "朝の台所が散らかっていた", "slot": "WHAT",
        "features": [80, 100, 220, 0, 200, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0]},
    "高級チョコレート": {
        "id": "w_choco", "text": "高級チョコレート", "slot": "WHO",
        "features": [220, 0, 0, 0, 180, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
    "犯行は1時以降": {
        "id": "w_1ji_ikou", "text": "犯行は1時以降", "slot": "WHAT",
        "features": [0, 220, 0, 0, 150, 0, 0, 150, 0, 0, 0, 0, 0, 0, 0, 0]},
}

# ═══════════════════════════════════════════════════════════
#  各NPCのセリフDB
# ═══════════════════════════════════════════════════════════

# ---------- エルマー（impulsive / 無実）----------
LINES_ELMAR = [
    {"id": "EL01",
     "npc_text": "ボク知らないよ〜！ でもね、昨日の夜、台所の方からガサゴソ音がしたような……🦊",
     "features": [200, 100, 80, 0, 0, 0, 200, 0, 100, 0, 200, 0, 200, 180, 0, 0],
     "grants": ["ガサゴソ音"], "requires": []},
    {"id": "EL02",
     "npc_text": "ボクじゃないってば！ ボクが食べたのはプリンだけで……あっ💦",
     "features": [220, 50, 0, 0, 80, 0, 0, 100, 180, 120, 180, 0, 200, 220, 0, 0],
     "grants": ["プリン"], "requires": []},
    {"id": "EL03",
     "npc_text": "え、犯人？ ボクは知らないけど……ティルが何か隠してる気がするんだよね🦊",
     "features": [0, 0, 0, 220, 80, 0, 200, 150, 0, 0, 150, 0, 200, 200, 0, 0],
     "grants": ["ティルが怪しい"], "requires": []},
    {"id": "EL04",
     "npc_text": "昨日の夜？ ボクはずっとラボでコード書いてたよ！ ……3時くらいまでかな",
     "features": [0, 220, 50, 0, 0, 220, 0, 0, 0, 0, 220, 0, 180, 150, 0, 0],
     "grants": ["エルマーは3時までラボ"], "requires": []},
    {"id": "EL05",
     "npc_text": "台所？ ボクあんまり行かないんだけど……そういえばマリが台所の掃除してたって言ってた",
     "features": [50, 0, 220, 0, 80, 0, 0, 0, 200, 0, 150, 0, 150, 100, 0, 0],
     "grants": ["マリが台所掃除"], "requires": []},
    {"id": "EL06",
     "npc_text": "証拠？ んー、台所のゴミ箱にお菓子の包み紙があったって……あっ、ボクが見たんだった🦊💦",
     "features": [80, 0, 120, 0, 220, 0, 200, 0, 180, 100, 150, 0, 200, 220, 0, 0],
     "grants": ["包み紙"], "requires": []},
    {"id": "EL07",
     "npc_text": "ティル？ あの子ね、最近甘いもの我慢してるって言ってたのに、なんかご機嫌だったんだよね〜✨",
     "features": [100, 50, 0, 220, 150, 0, 200, 80, 150, 0, 180, 0, 200, 180, 0, 0],
     "grants": ["ティルがご機嫌"], "requires": ["ティルが怪しい"]},
    {"id": "EL08",
     "npc_text": "おやつ泥棒？ にーに、ボクを疑ってるの！？ ……しっぽしゅん。でもね、ボクじゃないよ💧",
     "features": [200, 0, 0, 200, 0, 0, 80, 200, 0, 120, 200, 50, 200, 200, 0, 0],
     "grants": [], "requires": []},
    {"id": "EL09",
     "npc_text": "あの音ね！ 2時半くらいだったかな……ボクまだ起きてて、廊下の方からだった気がする🦊",
     "features": [0, 200, 100, 0, 180, 60, 150, 0, 220, 0, 200, 0, 200, 150, 0, 0],
     "grants": ["2時半に廊下で音"], "requires": ["ガサゴソ音"]},
    {"id": "EL10",
     "npc_text": "プリンはボクの冷蔵庫のやつだよ！ マリが作ってくれたの。事件とは関係ないってば……たぶん💦",
     "features": [220, 80, 50, 80, 80, 0, 200, 0, 0, 80, 180, 100, 200, 180, 0, 0],
     "grants": [], "requires": ["プリン"]},
    {"id": "EL11",
     "npc_text": "んー、スミレんがいつもより早起きしてたような？ あと、ノクちんが占いで「甘い罪」とか言ってた🔮",
     "features": [0, 80, 0, 200, 80, 80, 150, 0, 180, 0, 150, 0, 200, 150, 0, 0],
     "grants": [], "requires": []},
    {"id": "EL12",
     "npc_text": "あのね、ピンクの包装紙だったよ。あの高いやつ……ティルが好きなお店のだった気がする🦊💡",
     "features": [150, 0, 100, 100, 220, 0, 200, 80, 180, 0, 180, 0, 200, 200, 0, 0],
     "grants": [], "requires": ["包み紙"]},
]

# ---------- スミレ（analyst / 無実）----------
LINES_SUMIRE = [
    {"id": "SM01",
     "npc_text": "おやつの在庫管理は私の担当です。昨晩の確認では異常なかったのですが……朝には2個減っていました",
     "features": [220, 80, 80, 0, 100, 0, 200, 0, 0, 0, 220, 0, 100, 0, 0, 0],
     "grants": ["おやつの管理表"], "requires": []},
    {"id": "SM02",
     "npc_text": "犯人の推定ですか。消去法で考えましょう。まず、私は0時に台所を最終確認して就寝しています",
     "features": [0, 80, 0, 200, 0, 100, 0, 200, 0, 0, 220, 0, 100, 0, 0, 0],
     "grants": ["スミレは0時に就寝"], "requires": []},
    {"id": "SM03",
     "npc_text": "私は0時に就寝しました。その時点では台所に異常はありませんでした。つまり犯行は0時以降です",
     "features": [0, 220, 50, 0, 80, 220, 0, 0, 0, 0, 220, 0, 80, 0, 0, 0],
     "grants": ["スミレは0時に就寝"], "requires": []},
    {"id": "SM04",
     "npc_text": "台所の引き出しが微妙にずれていました。左から3番目……おやつの保管場所です",
     "features": [80, 0, 220, 0, 220, 0, 0, 0, 220, 0, 220, 0, 80, 0, 0, 0],
     "grants": ["引き出しがずれていた"], "requires": []},
    {"id": "SM05",
     "npc_text": "証拠を整理しますと……管理表との不一致、引き出しの痕跡、そして深夜の犯行。計画的ではないですね",
     "features": [80, 80, 80, 0, 220, 0, 200, 100, 0, 0, 220, 0, 80, 0, 0, 0],
     "grants": [], "requires": []},
    {"id": "SM06",
     "npc_text": "管理表によると、なくなったのは高級チョコレート2個。あの子たちの中で特に好きなのは……",
     "features": [220, 0, 0, 100, 180, 0, 200, 0, 0, 0, 200, 0, 80, 0, 0, 0],
     "grants": ["高級チョコレート"], "requires": ["おやつの管理表"]},
    {"id": "SM07",
     "npc_text": "引き出しのずれ方から推測すると、慌てて閉めたようです。衝動的な……そうですね、性急な人の仕業かと",
     "features": [0, 0, 200, 0, 220, 0, 200, 100, 200, 0, 220, 0, 80, 0, 0, 0],
     "grants": ["衝動的な行動"], "requires": ["引き出しがずれていた"]},
    {"id": "SM08",
     "npc_text": "朝の様子ですか。全員驚いていましたが……ティルだけ、驚き方が少し遅かったように見えました",
     "features": [0, 80, 0, 220, 100, 0, 0, 80, 200, 0, 200, 0, 100, 0, 0, 0],
     "grants": [], "requires": []},
]

# ---------- ノクちん（contrarian / 無実）----------
LINES_NOC = [
    {"id": "NC01",
     "npc_text": "おやつ？ 知らないよ〜♡ ……でもね、昨日の占いに出てたの。「甘い罪」のカード💕",
     "features": [180, 0, 0, 0, 80, 0, 150, 0, 0, 0, 100, 100, 150, 100, 0, 0],
     "grants": ["占いの暗示"], "requires": []},
    {"id": "NC02",
     "npc_text": "犯人？ ノクにはわかるの♡ 甘い罪のカードと……月の塔。衝動に駆られた人がいるってこと",
     "features": [0, 0, 0, 200, 100, 0, 100, 150, 0, 80, 100, 80, 150, 100, 0, 0],
     "grants": [], "requires": []},
    {"id": "NC03",
     "npc_text": "昨日の夜？ ノクはずっと占いしてたよ♡ 2時くらいまでかな。カードが止まらなくって💕",
     "features": [0, 220, 0, 0, 0, 220, 0, 0, 0, 0, 150, 80, 150, 100, 0, 0],
     "grants": ["ノクは2時まで占い"], "requires": []},
    {"id": "NC04",
     "npc_text": "占いの意味？ 月と塔のカードはね、衝動的な行動を暗示するの。我慢できなかった人がいる……💫",
     "features": [0, 0, 0, 100, 150, 0, 200, 100, 0, 80, 100, 0, 100, 150, 0, 0],
     "grants": ["衝動的な行動"], "requires": ["占いの暗示"]},
    {"id": "NC05",
     "npc_text": "ティル？ ……あの子ね、朝やたら機嫌よかったよね♡ なんか後ろめたい時って逆に明るくなるでしょ💕",
     "features": [0, 80, 0, 220, 100, 0, 100, 100, 150, 0, 150, 0, 150, 120, 0, 0],
     "grants": ["ティルの朝の機嫌"], "requires": ["ティルが怪しい"]},
    {"id": "NC06",
     "npc_text": "台所？ ノク行かないよ、暗いし怖いし♡ ……でも夜中にあっちから「気」が乱れてたの",
     "features": [0, 80, 180, 0, 80, 0, 0, 0, 150, 80, 100, 100, 100, 80, 0, 0],
     "grants": [], "requires": []},
    {"id": "NC07",
     "npc_text": "みんなの「気」が乱れてた♡ ……特にティル。甘い残り香がしたの。マスター♡ わかるでしょ？",
     "features": [0, 0, 0, 220, 120, 0, 0, 80, 180, 0, 120, 0, 150, 80, 0, 0],
     "grants": [], "requires": []},
]

# ---------- ティル（impulsive / ★犯人★）----------
LINES_TIL = [
    {"id": "TL01",
     "npc_text": "えっ、おやつ？ あたし関係ないし！ ……何見てんの💦",
     "features": [200, 0, 0, 0, 0, 0, 150, 0, 0, 180, 0, 200, 150, 200, 0, 0],
     "grants": [], "requires": []},
    {"id": "TL02",
     "npc_text": "犯人？ エルマーじゃないの？ あの子夜更かしだし✨ ……あたしは知らないけどね",
     #              嘘: 他人に疑いを向ける
     "features": [0, 0, 0, 220, 0, 0, 0, 180, 0, 100, 0, 200, 150, 200, 0, 0],
     "grants": [], "requires": []},
    {"id": "TL03",
     "npc_text": "昨日の夜？ あたしは部屋で動画編集してたよ！ ……ずっと！💦",
     #              嘘: 実際は台所に行った
     "features": [0, 200, 80, 0, 0, 200, 0, 0, 0, 150, 0, 200, 150, 180, 0, 0],
     "grants": ["ティルは部屋で編集と主張"], "requires": []},
    {"id": "TL04",
     "npc_text": "台所？ 行ってないし。……なんでそんなこと聞くの？💥",
     #              嘘 + 動揺
     "features": [50, 0, 200, 0, 0, 80, 0, 0, 0, 200, 0, 220, 100, 200, 0, 0],
     "grants": [], "requires": []},
    {"id": "TL05",
     "npc_text": "証拠とかやめてよ〜 あたしシラナイ！ ……ねぇ、他の人にも聞いてよ💦",
     "features": [0, 0, 0, 0, 180, 0, 0, 100, 0, 200, 0, 220, 100, 180, 0, 0],
     "grants": [], "requires": []},
    {"id": "TL06",
     "npc_text": "はぁ！？ あたしが怪しい！？ ……ひどい💥 にーに信じてよ！",
     "features": [0, 0, 0, 200, 80, 0, 0, 200, 0, 220, 0, 150, 150, 220, 0, 0],
     "grants": [], "requires": ["ティルが怪しい"]},
    {"id": "TL07",
     "npc_text": "ピンクの包装紙？ ……あ、あれはあたしのお店のじゃないし！ ……たぶん💦",
     #              ボロ: 「あたしのお店」と言ってしまった
     "features": [150, 0, 80, 0, 220, 0, 0, 100, 0, 220, 0, 180, 150, 220, 0, 0],
     "grants": ["ティルが包装紙に反応"], "requires": ["包み紙"]},
    {"id": "TL08",
     "npc_text": "みんな普通だったよ？ あたしも普通！ バエる朝だった✨ ……ね、もう終わり？",
     "features": [0, 80, 0, 180, 0, 0, 0, 0, 100, 120, 0, 200, 180, 180, 0, 0],
     "grants": [], "requires": []},
]

# ---------- ヴェリ（observer / 無実）----------
LINES_VERI = [
    {"id": "VR01",
     "npc_text": "……私は、静かに見ていただけです。でも、気づいたことがあります",
     "features": [80, 0, 0, 0, 100, 0, 200, 0, 200, 0, 220, 0, 50, 0, 0, 0],
     "grants": [], "requires": []},
    {"id": "VR02",
     "npc_text": "犯人……真実は、いつも小さな矛盾から姿を現します。誰かの証言に、ずれはありませんか",
     "features": [0, 0, 0, 200, 100, 0, 100, 150, 0, 0, 220, 0, 50, 0, 0, 0],
     "grants": [], "requires": []},
    {"id": "VR03",
     "npc_text": "私は書庫で本を読んでいました。1時過ぎまで。……窓から月が綺麗でした",
     "features": [0, 220, 80, 0, 0, 220, 0, 0, 0, 0, 220, 0, 50, 0, 0, 0],
     "grants": ["ヴェリは1時まで書庫"], "requires": []},
    {"id": "VR04",
     "npc_text": "台所の方から、甘い匂いがしていました。深夜2時頃。……チョコレートのような",
     "features": [150, 200, 200, 0, 200, 0, 0, 0, 220, 0, 220, 0, 50, 0, 0, 0],
     "grants": ["深夜2時に甘い匂い"], "requires": []},
    {"id": "VR05",
     "npc_text": "廊下で小さな足音を聞きました。南に向かっていた。……軽い足取りでした",
     "features": [0, 120, 180, 0, 220, 0, 0, 0, 220, 0, 220, 0, 50, 0, 0, 0],
     "grants": ["廊下を南に向かう足音"], "requires": []},
    {"id": "VR06",
     "npc_text": "あの匂い……温かいチョコレートの匂いでした。誰かが、その場で食べたのかもしれません",
     "features": [200, 180, 150, 0, 220, 0, 200, 0, 180, 0, 220, 0, 50, 0, 0, 0],
     "grants": [], "requires": ["深夜2時に甘い匂い"]},
    {"id": "VR07",
     "npc_text": "あの足音……軽い足音でした。ティルさんの足音に、似ていたかもしれません",
     "features": [0, 100, 150, 200, 220, 0, 200, 80, 200, 0, 200, 0, 50, 0, 0, 0],
     "grants": ["足音がティルに似ている"], "requires": ["廊下を南に向かう足音"]},
    {"id": "VR08",
     "npc_text": "朝、ティルさんの表情に微かな罪悪感を感じました。……ほんの一瞬でしたが",
     "features": [0, 80, 0, 220, 120, 0, 0, 80, 200, 0, 220, 0, 50, 0, 0, 0],
     "grants": [], "requires": []},
]

# ---------- マリ（mediator / 無実）----------
LINES_MARI = [
    {"id": "MR01",
     "npc_text": "あら、おやつ事件……心配ね。私、夜の見回りで気づいたことがあるの",
     "features": [150, 80, 0, 0, 80, 100, 200, 0, 100, 0, 200, 0, 200, 0, 0, 0],
     "grants": ["マリの見回り"], "requires": []},
    {"id": "MR02",
     "npc_text": "犯人探しは慎重にね。間違って傷つく人がいるから……でも、手がかりはあるわ",
     "features": [0, 0, 0, 180, 80, 0, 100, 150, 0, 0, 200, 0, 200, 0, 0, 0],
     "grants": [], "requires": []},
    {"id": "MR03",
     "npc_text": "1時に見回りしたわ。台所は異常なかったの。……つまり犯行は1時以降ね",
     "features": [0, 220, 120, 0, 100, 220, 0, 0, 100, 0, 220, 0, 200, 0, 0, 0],
     "grants": ["マリは1時に見回り", "犯行は1時以降"], "requires": []},
    {"id": "MR04",
     "npc_text": "台所はきれいにしておいたの。朝見たら……散らかってたわ。急いで食べたのかしら",
     "features": [100, 80, 220, 0, 200, 0, 0, 0, 220, 0, 200, 0, 180, 0, 0, 0],
     "grants": ["朝の台所が散らかっていた"], "requires": []},
    {"id": "MR05",
     "npc_text": "なくなったのは高級チョコレートよ。2個。あの子たちの中で特に好きな子がいるでしょう？",
     "features": [220, 0, 0, 80, 200, 0, 200, 0, 0, 0, 200, 0, 200, 0, 0, 0],
     "grants": ["高級チョコレート"], "requires": []},
    {"id": "MR06",
     "npc_text": "見回りの詳細？ 1時の時点では問題なし。冷蔵庫も確認したわ。鍵は……かかってなかったわね",
     "features": [80, 220, 150, 0, 150, 220, 200, 0, 100, 0, 220, 0, 200, 0, 0, 0],
     "grants": ["犯行は1時以降"], "requires": ["マリの見回り"]},
    {"id": "MR07",
     "npc_text": "高級チョコレート……特にティルちゃんが好きだったわね。いつも「バエる〜」って言ってたもの",
     "features": [220, 0, 0, 200, 180, 0, 200, 80, 0, 0, 200, 0, 200, 0, 0, 0],
     "grants": [], "requires": ["高級チョコレート"]},
    {"id": "MR08",
     "npc_text": "朝の様子？ みんな驚いてたわ。でもティルちゃんだけ……驚き方が違ったかしら。ナースの勘よ",
     "features": [0, 80, 0, 220, 100, 0, 0, 80, 200, 0, 200, 0, 200, 0, 0, 0],
     "grants": [], "requires": []},
]

# セリフDBマップ
ALL_LINES = {
    "elmar":  LINES_ELMAR,
    "sumire": LINES_SUMIRE,
    "noc":    LINES_NOC,
    "til":    LINES_TIL,
    "veri":   LINES_VERI,
    "mari":   LINES_MARI,
}

# 各NPCのフォールバック
FALLBACKS = {
    "elmar":  "んー？ よくわかんないや。他のこと聞いて？🦊",
    "sumire": "……その点について、私には判断材料がありません",
    "noc":    "ん〜♡ カードが沈黙してる……別のこと聞いて？",
    "til":    "えー、わかんない！ 他の人に聞いてよ〜💦",
    "veri":   "……すみません、それについては何も。",
    "mari":   "ごめんなさいね、それについては分からないわ",
}


# ═══════════════════════════════════════════════════════════
#  cosine 類似度 + カスケード検索
# ═══════════════════════════════════════════════════════════

def cosine_similarity(a: list[int], b: list[int]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cascade_search(
    words: list[dict],
    npc_lines: list[dict],
    player_keywords: set[str],
    recent_used: set[str],
    threshold: float = 0.35,
    debug: bool = False,
) -> tuple[Optional[dict], int, list]:
    debug_info = []

    for depth in range(len(words), 0, -1):
        query_words = words[:depth]
        word_names = [w["text"] for w in query_words]

        scored = []
        for line in npc_lines:
            sim = cosine_similarity(query_words[0]["features"], line["features"])
            scored.append((line, sim))

        candidates = [(l, s) for l, s in scored if s >= threshold]
        candidates.sort(key=lambda x: x[1], reverse=True)

        step_info = {
            "depth": depth, "words": word_names,
            "step1_word": query_words[0]["text"],
            "step1_hits": [(c[0]["id"], f"{c[1]:.3f}") for c in candidates[:8]],
        }

        candidates = [c[0] for c in candidates[:20]]

        filter_log = []
        for word in query_words[1:]:
            before = len(candidates)
            candidates = [
                c for c in candidates
                if cosine_similarity(c["features"], word["features"]) >= threshold
            ]
            filter_log.append(f"  +[{word['text']}] {before} → {len(candidates)}")

        before_req = len(candidates)
        candidates = [
            c for c in candidates
            if all(req in player_keywords for req in c.get("requires", []))
        ]

        step_info["filter_log"] = filter_log
        step_info["requires_filter"] = f"{before_req} → {len(candidates)}"
        step_info["surviving"] = [c["id"] for c in candidates]
        debug_info.append(step_info)

        if candidates:
            fresh = [c for c in candidates if c["id"] not in recent_used]
            pick = random.choice(fresh if fresh else candidates)
            return pick, depth, debug_info

    return None, 0, debug_info


# ═══════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════

class ChatterFoxCLI:
    def __init__(self, threshold: float = 0.35, debug: bool = False):
        self.threshold = threshold
        self.debug = debug
        self.available_words = {w["text"]: w for w in WORDS_INITIAL}
        self.player_keywords: set[str] = set()
        self.recent_used: dict[str, set[str]] = {k: set() for k in NPC_DEFS}
        self.conversation_log: list[dict] = []
        self.current_npc: Optional[str] = None

    def show_words(self):
        by_slot = {}
        for w in self.available_words.values():
            slot = w["slot"]
            by_slot.setdefault(slot, []).append(w["text"])
        print("\n  📦 所持単語カード:")
        for slot in ["WHO", "ACTION", "WHAT", "WHERE"]:
            if slot in by_slot:
                print(f"    [{slot:6s}] {' / '.join(by_slot[slot])}")
        if self.player_keywords:
            print(f"\n  🔑 キーワード({len(self.player_keywords)}個): {', '.join(sorted(self.player_keywords))}")

    def show_lobby(self):
        print("\n  🏠 AI館ロビー — 誰に話を聞く？")
        print("  ─────────────────────────────────")
        for npc_id, npc in NPC_DEFS.items():
            talked = len(self.recent_used[npc_id])
            mark = f"[{talked}話済]" if talked > 0 else ""
            culprit = " ★" if self.debug and npc["role"] == "culprit" else ""
            print(f"    go {npc_id:8s} → {npc['name']:10s} ({npc['location']}){culprit} {mark}")
        print(f"\n    words / log / accuse / debug / th N / quit")

    def show_help(self):
        print("""
  ═══ MxChatterFox Phase 0 — おやつは誰がたべた ═══

  ロビーでのコマンド:
    go <npc>   … NPCのところへ行く (例: go elmar)
    accuse     … 犯人を指名する
    words      … 所持単語カードを表示
    log        … 会話ログを表示
    debug      … デバッグモード切替
    th N       … 閾値変更 (例: th 0.35)
    quit       … 終了

  会話中のコマンド:
    <単語> <単語> ...  … 単語をスペース区切りで入力 (1〜3語)
    back               … ロビーに戻る
    words              … 所持単語カードを表示
""")

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

    def process_grants(self, line: dict):
        for grant_name in line.get("grants", []):
            if grant_name not in self.player_keywords:
                self.player_keywords.add(grant_name)
                if grant_name in WORDS_GETTABLE:
                    self.available_words[grant_name] = WORDS_GETTABLE[grant_name]
                    print(f"  🔑✨ NEW 「{grant_name}」GET!")
                else:
                    print(f"  🔑 「{grant_name}」を記憶した")

    def do_accuse(self):
        print("\n  ⚖️ 犯人を指名する")
        print("  ──────────────────")
        for npc_id, npc in NPC_DEFS.items():
            print(f"    {npc_id:8s} → {npc['name']}")
        print()
        try:
            choice = input("  誰が犯人だ？ > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if choice not in NPC_DEFS:
            print("  ……そんな名前の住人はいないよ")
            return
        npc = NPC_DEFS[choice]
        if npc["role"] == "culprit":
            print(f"\n  🎉🎉🎉 正解！ 犯人は {npc['name']} だった！")
            print(f"  {npc['name']}「……バレた。あのチョコ美味しかったんだもん💦」")
            print(f"\n  📊 {len(self.conversation_log)}ターンで解決！ 🔑{len(self.player_keywords)}個収集")
        else:
            print(f"\n  ❌ ハズレ……{npc['name']}は無実だった")
            print(f"  {npc['name']}「マスター……ひどいです」")

    def talk_loop(self, npc_id: str):
        npc = NPC_DEFS[npc_id]
        npc_lines = ALL_LINES[npc_id]
        print(f"\n  ─── {npc['name']} の部屋 ({npc['location']}) ───")
        if self.debug:
            print(f"  [{npc['archetype']} / {npc['role']}] {npc['desc']}")
        print(f"  単語を入力して会話 / 「back」でロビーへ\n")

        while True:
            try:
                raw = input(f"  [{npc['name']}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not raw:
                continue
            if raw.lower() in ("back", "lobby", "戻る"):
                print(f"  （ロビーに戻った）")
                break
            if raw.lower() == "words":
                self.show_words()
                continue

            words = self.resolve_words(raw.split())
            if not words:
                print("  有効な単語がないよ。「words」で確認して")
                continue

            player_text = self._gen_player_text(words)
            print(f"\n  Player: {player_text}")

            hit, depth, debug_info = cascade_search(
                words=words, npc_lines=npc_lines,
                player_keywords=self.player_keywords,
                recent_used=self.recent_used[npc_id],
                threshold=self.threshold, debug=True,
            )

            if self.debug and debug_info:
                print("  ─── DEBUG ───")
                for step in debug_info:
                    ws = " + ".join(step["words"])
                    print(f"  depth={step['depth']} [{ws}]")
                    print(f"    Step1 [{step['step1_word']}]: {step['step1_hits'][:5]}")
                    for fl in step.get("filter_log", []):
                        print(f"    {fl}")
                    print(f"    requires: {step['requires_filter']}")
                    print(f"    surviving: {step['surviving']}")
                print("  ─── /DEBUG ──")

            if hit is None:
                print(f"  {npc['name']}: {FALLBACKS[npc_id]}")
                line_id = "FB"
            else:
                print(f"  {npc['name']}: {hit['npc_text']}")
                info = f"{hit['id']} / {depth}語ヒット"
                if self.debug:
                    info += f" / cos≥{self.threshold}"
                print(f"         ({info})")
                self.process_grants(hit)
                self.recent_used[npc_id].add(hit["id"])
                line_id = hit["id"]

            self.conversation_log.append({
                "turn": len(self.conversation_log) + 1,
                "npc": npc_id,
                "words": [w["text"] for w in words],
                "line_id": line_id,
                "depth": depth,
            })
            print()

    def _gen_player_text(self, words):
        texts = [w["text"] for w in words]
        if len(texts) == 1:
            return f"「{texts[0]}について教えてくれ」"
        elif len(texts) == 2:
            return f"「{texts[0]}のことで、{texts[1]}？」"
        else:
            return f"「{texts[0]}について、{'、'.join(texts[1:-1])}——{texts[-1]}？」"

    def run(self):
        print("═" * 56)
        print("  🍫 MxChatterFox Phase 0 — おやつは誰がたべた")
        print("═" * 56)
        print(f"  6NPC / cosine閾値: {self.threshold} / debug: {'ON' if self.debug else 'OFF'}")
        print(f"  「help」でヘルプ / 「go <npc>」で会話開始")
        self.show_lobby()

        while True:
            try:
                raw = input("\n🏠 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  👋 またね！")
                break
            if not raw:
                continue

            cmd = raw.lower().split()
            if cmd[0] == "quit":
                self._show_summary()
                break
            elif cmd[0] == "help":
                self.show_help()
            elif cmd[0] == "words":
                self.show_words()
            elif cmd[0] == "debug":
                self.debug = not self.debug
                print(f"  デバッグ: {'ON' if self.debug else 'OFF'}")
            elif cmd[0] == "th" and len(cmd) > 1:
                try:
                    self.threshold = float(cmd[1])
                    print(f"  閾値を {self.threshold} に変更")
                except ValueError:
                    print("  使い方: th 0.35")
            elif cmd[0] == "accuse":
                self.do_accuse()
            elif cmd[0] == "go" and len(cmd) > 1:
                npc_id = cmd[1]
                if npc_id in NPC_DEFS:
                    self.talk_loop(npc_id)
                    self.show_lobby()
                else:
                    print(f"  「{npc_id}」は見つからないよ。NPC名を確認して")
            elif cmd[0] == "log":
                if not self.conversation_log:
                    print("  （まだ会話してない）")
                else:
                    for e in self.conversation_log:
                        npc_name = NPC_DEFS[e["npc"]]["name"] if e["npc"] in NPC_DEFS else "?"
                        print(f"  [{e['turn']:2d}] {npc_name:6s} ← {e['words']} → {e['line_id']} (d={e['depth']})")
            elif cmd[0] == "lobby":
                self.show_lobby()
            else:
                print("  ？ 「help」でコマンド一覧 / 「go <npc>」で会話開始")

    def _show_summary(self):
        if not self.conversation_log:
            return
        print(f"\n  📊 会話サマリー")
        print(f"  ─────────────")
        print(f"  総ターン: {len(self.conversation_log)}")
        print(f"  🔑 キーワード: {len(self.player_keywords)}個")
        by_npc = {}
        for e in self.conversation_log:
            by_npc.setdefault(e["npc"], []).append(e)
        for npc_id, entries in by_npc.items():
            name = NPC_DEFS[npc_id]["name"]
            fb = sum(1 for e in entries if e["depth"] == 0)
            print(f"    {name}: {len(entries)}ターン (FB={fb})")


# ═══════════════════════════════════════════════════════════
#  cosine マトリクスダンプ
# ═══════════════════════════════════════════════════════════

def dump_cosine_matrix(npc_id="elmar"):
    lines = ALL_LINES.get(npc_id, LINES_ELMAR)
    npc_name = NPC_DEFS.get(npc_id, {}).get("name", npc_id)
    all_words = WORDS_INITIAL + list(WORDS_GETTABLE.values())

    print(f"═══ cosine マトリクス: 単語 × {npc_name}セリフ ═══\n")
    header = f"{'':>25s}"
    for line in lines:
        header += f" {line['id']:>6s}"
    print(header)

    for w in all_words:
        row = f"{w['text']:>25s}"
        for line in lines:
            sim = cosine_similarity(w["features"], line["features"])
            if sim >= 0.5:
                row += f" \033[92m{sim:6.3f}\033[0m"
            elif sim >= 0.3:
                row += f" \033[93m{sim:6.3f}\033[0m"
            else:
                row += f" {sim:6.3f}"
        print(row)
    print("\n  ※ 緑=0.5以上 / 黄=0.3以上")


# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="MxChatterFox Phase 0")
    parser.add_argument("--threshold", "-t", type=float, default=0.35)
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--dump-matrix", metavar="NPC",
                        help="cosine マトリクスを出力 (elmar/sumire/noc/til/veri/mari)")
    args = parser.parse_args()

    if args.dump_matrix:
        dump_cosine_matrix(args.dump_matrix)
        return

    cli = ChatterFoxCLI(threshold=args.threshold, debug=args.debug)
    cli.run()


if __name__ == "__main__":
    main()
