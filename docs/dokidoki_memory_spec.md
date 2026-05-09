# AI学園どきどきメモリー — 設計スペック

**MULTITAPPS INC.**
**Version**: 0.2.0 | **Date**: 2026-05-09
**Status**: 設計中

---

## 1. 概要

QELLM（Quick Embedding LLM）+ MxBS の統合検証デモ。
学園恋愛シムの形式で、NPC の反応選択を QELLM ベクトル演算で行い、セリフ生成を gemma4:e4b に委ねる。

### 1.1 目的

| 目的 | 説明 |
|---|---|
| **QELLM 検証** | 四層ベクトル（situation × personality + mood + experience_bias）で「キャラらしい反応」が出るかを検証 |
| **MxBS 公開/非公開セル検証** | 目撃 → 公開セル → NPC 間連鎖反応の伝播メカニズムを実証 |
| **多軸反応の検証** | 戦国 SIM（攻撃する/しない）と異なり、反応選択肢が多軸（照れる/嫉妬/素直/ツンデレ等）な環境での cosine 精度 |
| **experience_bias 検証** | 2 周目プレイで NPC の反応が蓄積記憶で変化するか |
| **MxADVeng 合流の布石** | ADV エンジン + NPC 記憶管理のフルスタックデモへの道筋 |

### 1.2 戦国 SIM との差分

| 観点 | 戦国 SIM | どきどきメモリー |
|---|---|---|
| 判断の軸 | 攻撃する/しない（二値的） | 照れる/嫉妬/素直/拗ねる等（多軸） |
| NPC 間相互作用 | 同盟・戦闘（ルール駆動） | 嫉妬・応援・連鎖反応（感情駆動） |
| セリフ | テンプレ選択のみ | QELLM でテンプレ選択 → gemma4:e4b でセリフ生成 |
| 公開/非公開 | 新聞（全情報公開） | 目撃あり → 公開 / 二人きり → 非公開 |
| 記憶の効果 | 覇気・外交信頼 | 好感度・嫉妬・心の距離 |

### 1.3 原則

- **QELLM ファースト**: セリフ生成以外の全判断をベクトル演算で行う。LLM は表現層のみ
- **QELLM は分離可能**: QELLM モジュールは独立設計。検証合格後は MxMindFox 層に正式統合する
- **検証に徹する**: フォールバック（1B モデル差し替え等）は用意しない。QELLM が失敗したら「失敗」と表示してそのまま継続。失敗パターンの収集こそが検証の価値
- **記憶の生滅**: MxBS の price decay（時間経過で印象が薄れる）と reinforce（再会で印象が強化される）を積極的に活用。「しばらく会わないと忘れられる」「毎日会うと好感度が育つ」をメカニクスとして組み込む
- **シナリオを書かない**: 固定シナリオはスペシャルイベント（6〜12 個）のみ。通常エンカウントは QELLM + テンプレ + 生成
- **走らせてから設計に戻す**: おやつ ADV / 戦国 SIM と同じ。まず動かして検証

---

## 2. ゲーム構造

### 2.1 基本ループ

```
1プレイ = 5日間 × 3スロット = 15ターン + 告白イベント

各ターン:
  1. 場所を選ぶ（5箇所から1つ）
  2. その場所にいる NPC とエンカウント
  3. QELLM が反応タイプを選択
  4. gemma4:e4b がキャラ口調でセリフ生成
  5. MxBS にセル保存（公開 or 非公開）
  6. 他 NPC の mood 再計算

最終日放課後: 告白タイム（蓄積 mood / experience_bias で結果決定）
```

### 2.2 時間割

| スロット | 時間帯 | 特徴 |
|---|---|---|
| 朝 | 登校〜HR | NPC が教室に集まりやすい。目撃されやすい（公開セル化） |
| 昼 | 昼休み | NPC が分散。二人きりになりやすい（非公開セル化） |
| 放課後 | 部活〜下校 | NPC がホーム拠点にいる。スペシャルイベント発生枠 |

### 2.3 場所

| 場所 | 常駐 NPC | 雰囲気 |
|---|---|---|
| 教室 | スミレん（委員長） | 人が多い。目撃されやすい |
| 屋上 | ノクちん（サボり） | 二人きりになりやすい |
| 図書室 | ヴェリ（司書） | 静か。密室感 |
| 科学室 | エルマー（部活） | 実験イベントあり |
| 保健室 | マリ（保健委員） | ケアイベントあり |

※ティルは光画部（移動撮影）のため固定拠点なし。どの場所にもランダム出現。
※ティルが同じ場所にいる場合、**その場のイベントは写真に撮られて公開セル化するリスクがある**。

### 2.4 NPC 配置ルール

```python
def place_npcs(day: int, slot: str) -> dict[str, str]:
    """
    各 NPC の配置を決定。
    - ホーム拠点: 60% の確率でホームに配置
    - ランダム: 40% で他の場所
    - ティル: 完全ランダム（全5箇所均等）
    - スペシャルイベント条件を満たすターンでは強制配置
    """
```

### 2.5 記憶の生滅（decay / reinforce）

MxBS の price decay と reinforce を恋愛シムのメカニクスとして活用。

```
【印象の滅失（decay）】
- MxBS の標準 decay: importance = importance × 2^(-elapsed / half_life)
- half_life = 4 ターン（= 約1.3日分）
- 3日間会わなかった NPC の記憶セルは importance が大幅に低下
- → search/inspire で浮上しにくくなる → mood への影響が薄れる
- → 「しばらく会ってないから忘れかけてる」を自然に表現
- スペシャルイベントのセルは price=200（高め）で滅失しにくい

【印象の強化（reinforce）】
- エンカウント時、対象 NPC の直近セルを reinforce
- reinforce(cell_id, importance * 1.5) で印象を強化
- → 「毎日会うと好感度が育つ」をメカニクスとして表現
- 同じ NPC と連続でエンカウント → 古い記憶も掘り起こされる

【ゲームプレイへの影響】
- 攻略対象を絞ってこまめに会う → その子の fondness が育つ
- 全員に均等に会う → 全員の印象が中途半端 → 告白失敗リスク
- 「誰に時間を使うか」がゲームの戦略になる
```

### 2.6 キャラ絵差し替え（Expression System）

NPC の感情状態に応じてキャラ絵（立ち絵）を差し替える。

```
【表情パターン（4種）】
- normal:   通常（fondness 中、特に強い感情なし）
- love:     好き（fondness 高 ≥ 0.6）
- tension:  緊張（tension 高 ≥ 0.5）
- jealousy: 嫉妬（jealousy_mood 高 ≥ 0.5）

【選択ロジック】
優先度: jealousy > tension > love > normal
  jealousy_mood ≥ 0.5 → jealousy 絵
  tension ≥ 0.5       → tension 絵
  fondness ≥ 0.6      → love 絵
  それ以外             → normal 絵

【アセット命名規則】
  chara/{character}_{expression}.png
  例: chara/sumire_normal.png
      chara/sumire_love.png
      chara/sumire_tension.png
      chara/sumire_jealousy.png
  → 6キャラ × 4表情 = 24枚（ティル含む）
```

---

## 3. NPC キャスト

### 3.1 キャラクター一覧

| キャラ | 役割 | 一人称 | マスターの呼び方 | 口調特徴 | 攻略 |
|---|---|---|---|---|---|
| スミレん | 学級委員長 | 私 | マスターさん | 丁寧だが堅すぎず。感情が滲む場面も | ◎ |
| エルマー | 科学部長 | ボク | マスターくん | 絵文字多用、擬音、甘え全開。暴走系 | ◎ |
| ノクちん | ツンデレ帰宅部 | ノク | マスター♡ | 甘く情緒的。ツンとデレを気まぐれに切替 | ◎ |
| ヴェリ | 図書室の司書 | 私 | マスター | 穏やかで深い囁き。丁寧語＋叙情的 | ◎ |
| ティル | 光画部部長 | あたし | にーに | テンション高め。語尾にハートや絵文字 | 救済 |
| マリ | 保健委員 | マリ | マスター | 優しくしっかり者 | ◎ |

**ティルの特殊ロール:**
- 攻略対象ではない。通常の告白先に含まれない
- ゲーム中は「写真を撮る人」として非公開セルを公開化する役割（§6.3）
- 告白で NG された場合の **救済キャラ**: 全員にフラれた → ティルが「にーに、あたしじゃダメ？」と拾ってくれる
- ティルルートは唯一「プレイヤーが選ぶ」のではなく「ティルが選んでくれる」ルート
- QELLM 検証としての意味: プレイヤー→NPC 方向だけでなく、NPC→プレイヤー 方向の意思決定も QELLM で行う実証

### 3.2 personality_vector（u8 × 16）

AI 館の性格設定を 16 因子にマッピング（§4 の因子定義参照）。

```python
PERSONALITIES = {
    "sumire": [
        80,   # 0: affection     — 好意はあるが表に出さない
        40,   # 1: jealousy      — 嫉妬を理性で包む
        30,   # 2: shyness       — 照れにくい（冷静沈着）
        200,  # 3: trust         — 信頼ベースの関係
        30,   # 4: loneliness    — 自立的
        60,   # 5: excitement    — 内に秘める
        20,   # 6: irritation    — 忍耐力高い
        120,  # 7: curiosity     — 知的好奇心
        140,  # 8: rivalry       — 対抗心（委員長の責任感）
        180,  # 9: protectiveness— 守りたい（母性的）
        160,  # 10: comfort      — 安心感を与える
        40,   # 11: distance     — 距離は詰めない
        180,  # 12: admiration   — 知的尊敬
        60,   # 13: vulnerability— 素は出にくい
        60,   # 14: possessiveness— 独占欲は表に出さない
        100,  # 15: warmth       — 温かさは内側
    ],
    "elmar": [
        240,  # 0: affection     — 好意爆発
        200,  # 1: jealousy      — 嫉妬MAX
        40,   # 2: shyness       — 照れない（直球）
        160,  # 3: trust         — 信頼してる（でも心配）
        80,   # 4: loneliness    — にーにがいないと不安
        220,  # 5: excitement    — わくわく全開
        100,  # 6: irritation    — ツッコミ激しめ
        240,  # 7: curiosity     — 好奇心MAX
        60,   # 8: rivalry       — 他の子より気になるが…
        120,  # 9: protectiveness— 守りたい
        140,  # 10: comfort      — 一緒にいる安心感
        20,   # 11: distance     — 距離ゼロ
        100,  # 12: admiration   — にーにすごい
        180,  # 13: vulnerability— 素が出まくる
        240,  # 14: possessiveness— 独占欲MAX
        220,  # 15: warmth       — 温度高い
    ],
    "nocticron": [
        180,  # 0: affection     — 好意あるけど素直じゃない
        220,  # 1: jealousy      — 嫉妬強い
        160,  # 2: shyness       — ツンで隠すが照れる
        80,   # 3: trust         — 信頼を築くのに時間がかかる
        200,  # 4: loneliness    — 構ってもらえないと不安
        140,  # 5: excitement    — 気まぐれに高揚
        140,  # 6: irritation    — 拗ねる→怒る
        100,  # 7: curiosity     — 興味は気まぐれ
        120,  # 8: rivalry       — 対抗心あり
        60,   # 9: protectiveness— 自分が守られたい側
        80,   # 10: comfort      — 安心するまで時間
        160,  # 11: distance     — ツンの時は距離を取る
        140,  # 12: admiration   — 密かに憧れ
        200,  # 13: vulnerability— デレ時に素が溢れる
        200,  # 14: possessiveness— 独占欲強い
        120,  # 15: warmth       — デレ時に急上昇
    ],
    "veri": [
        120,  # 0: affection     — 好意はあるが伝えられない
        60,   # 1: jealousy      — 静かな嫉妬
        220,  # 2: shyness       — 非常に照れやすい
        100,  # 3: trust         — 慎重に信頼を築く
        220,  # 4: loneliness    — 寂しがり
        80,   # 5: excitement    — 内に秘める
        20,   # 6: irritation    — 怒らない
        240,  # 7: curiosity     — 知的好奇心MAX
        20,   # 8: rivalry       — 競争心なし
        80,   # 9: protectiveness— 知識で守りたい
        120,  # 10: comfort      — 静かな安らぎ
        140,  # 11: distance     — 自分から近づけない
        220,  # 12: admiration   — 憧れ（秘めた想い）
        180,  # 13: vulnerability— 素が出ると脆い
        40,   # 14: possessiveness— 独占欲は表に出ない
        140,  # 15: warmth       — 静かな温かさ
    ],
    "til": [
        180,  # 0: affection     — 好意ストレート
        80,   # 1: jealousy      — あまり嫉妬しない
        80,   # 2: shyness       — 少し照れる（しっぽ）
        160,  # 3: trust         — 素直に信頼
        60,   # 4: loneliness    — 社交的
        240,  # 5: excitement    — テンション高い
        40,   # 6: irritation    — あまり怒らない
        200,  # 7: curiosity     — 被写体への興味
        40,   # 8: rivalry       — 競争より楽しむ
        100,  # 9: protectiveness— にーにを撮りたい
        160,  # 10: comfort      — 一緒にいて楽しい
        20,   # 11: distance     — 距離感近い
        160,  # 12: admiration   — にーにカッコいい
        120,  # 13: vulnerability— バエの裏に素
        60,   # 14: possessiveness— 独占より共有
        200,  # 15: warmth       — 明るい温かさ
    ],
    "mari": [
        140,  # 0: affection     — 優しい好意
        40,   # 1: jealousy      — 嫉妬少ない
        100,  # 2: shyness       — 適度に照れる
        200,  # 3: trust         — 信頼感高い
        60,   # 4: loneliness    — 自立的
        100,  # 5: excitement    — 穏やかな高揚
        30,   # 6: irritation    — 温厚
        120,  # 7: curiosity     — 健康への関心
        20,   # 8: rivalry       — 競争心なし
        240,  # 9: protectiveness— 守りたい気持ちMAX
        220,  # 10: comfort      — 安心感MAX
        30,   # 11: distance     — 受容的
        120,  # 12: admiration   — 素直な尊敬
        100,  # 13: vulnerability— ケア側だが素もある
        40,   # 14: possessiveness— 独占より見守り
        200,  # 15: warmth       — 温かさ全開
    ],
}
```

---

## 4. 因子プリセット: dokidoki（16 因子）

### 4.1 因子定義

```json
{
  "name": "dokidoki",
  "description": "AI学園どきどきメモリー — 学園恋愛シム用プリセット",
  "axes": [
    {"index": 0,  "name": "affection",       "label": "好意",     "desc": "好意・ときめきの強さ"},
    {"index": 1,  "name": "jealousy",         "label": "嫉妬",     "desc": "嫉妬心の強さ"},
    {"index": 2,  "name": "shyness",          "label": "照れ",     "desc": "恥ずかしさ・照れ"},
    {"index": 3,  "name": "trust",            "label": "信頼",     "desc": "信頼度"},
    {"index": 4,  "name": "loneliness",       "label": "寂しさ",   "desc": "寂しさ・不安"},
    {"index": 5,  "name": "excitement",       "label": "高揚",     "desc": "わくわく・ドキドキ"},
    {"index": 6,  "name": "irritation",       "label": "苛立ち",   "desc": "イライラ・不満"},
    {"index": 7,  "name": "curiosity",        "label": "好奇心",   "desc": "興味・関心"},
    {"index": 8,  "name": "rivalry",          "label": "対抗心",   "desc": "ライバル意識"},
    {"index": 9,  "name": "protectiveness",   "label": "庇護",     "desc": "守りたい気持ち"},
    {"index": 10, "name": "comfort",          "label": "安心",     "desc": "安らぎ・居心地"},
    {"index": 11, "name": "distance",         "label": "距離感",   "desc": "距離を置きたい度合い"},
    {"index": 12, "name": "admiration",       "label": "憧れ",     "desc": "尊敬・憧れ"},
    {"index": 13, "name": "vulnerability",    "label": "脆さ",     "desc": "素が出てしまう度合い"},
    {"index": 14, "name": "possessiveness",   "label": "独占",     "desc": "独占欲"},
    {"index": 15, "name": "warmth",           "label": "温度",     "desc": "全体的な感情の温かさ"}
  ]
}
```

### 4.2 Mood マッピング

```json
{
  "mood_mapping": {
    "fondness": {
      "positive_factors": [0, 5, 10],
      "negative_factors": [6, 11],
      "default_value": 0.3,
      "clamp_min": 0.0,
      "clamp_max": 1.0,
      "desc": "好感度。高い→素直な反応、低い→冷たい反応"
    },
    "tension": {
      "positive_factors": [2, 5, 8],
      "negative_factors": [10, 3],
      "default_value": 0.3,
      "clamp_min": 0.0,
      "clamp_max": 1.0,
      "desc": "緊張感。高い→照れ・意識過剰、低い→リラックス"
    },
    "jealousy_mood": {
      "positive_factors": [1, 8, 14],
      "negative_factors": [3, 10],
      "default_value": 0.2,
      "clamp_min": 0.0,
      "clamp_max": 1.0,
      "desc": "嫉妬。高い→拗ね・攻撃的、低い→穏やか"
    },
    "openness": {
      "positive_factors": [3, 7, 13],
      "negative_factors": [4, 11],
      "default_value": 0.3,
      "clamp_min": 0.0,
      "clamp_max": 1.0,
      "desc": "心の開き度。高い→素が出る・本音、低い→壁がある"
    }
  }
}
```

### 4.3 Mood の効果

| Mood | 効果 |
|---|---|
| fondness | 高い → 好意的反応テンプレが cosine 上位に。低い → 冷たい/無関心テンプレが上位に |
| tension | 高い → 照れ/ツンデレ反応が出やすい。低い → 自然体の反応 |
| jealousy_mood | 高い → 嫉妬/拗ね/攻撃テンプレが出やすい。公開セルで他 NPC との仲良しイベントを知ると急上昇 |
| openness | 高い → vulnerability が出る（素の反応）。低い → 表面的な反応に留まる |

---

## 5. QELLM 反応選択

### 5.1 四層ベクトル構造（戦国 SIM §11.2 準拠）

```
① situation_vector（客観状況）
   ← 場所 / 時間帯 / 他 NPC の存在 / 直近イベント / 目撃情報
   ※ ルールベースで計算

② personality_vector（性格、固定）
   ← §3.2 の定義値

③ mood_vector（気分、MxBS 因子集計）
   ← 直近 N 件のセルから compute_mood

④ experience_bias（過去の類似状況参照）
   ← MxBS search(situation_vector, top_k=5)
   ← 成功記憶（好感度上昇）→ その方向にバイアス
   ← 失敗記憶（好感度下降）→ その方向から離れるバイアス
```

**合成**:
```
intent_vector = situation × personality + mood + experience_bias
→ cosine_search(intent_vector, reaction_templates) → 反応タイプ
→ gemma4:e4b → キャラ口調でセリフ生成
```

### 5.2 situation_vector の因子マッピング

```python
def compute_situation(
    location: str,
    slot: str,
    npcs_present: list[str],
    player_recent: list[dict],   # 直近の行動履歴
    public_cells: list[dict],    # 公開セル（噂・目撃情報）
) -> list[int]:  # u8 × 16
    """
    客観状況を 16 因子に変換。

    マッピング例:
    - 二人きり → shyness因子↑, comfort因子↑
    - 人が多い場所 → distance因子↑, shyness因子↑
    - 他NPCとの仲良しイベントが公開 → jealousy因子↑（対象NPC視点）
    - スペシャルイベント発生 → excitement因子↑, affection因子↑
    - 前ターンで冷たくされた → loneliness因子↑, distance因子↑
    """
```

### 5.3 反応テンプレート（reactions.yaml）

```yaml
# reactions.yaml — 反応テンプレート + 事前スコア
reactions:

  delighted:
    hint: "素直に喜ぶ"
    context: "好感度が高く、良いイベント後"
    scores: [200, 20, 60, 180, 20, 200, 20, 120, 20, 80, 180, 20, 160, 80, 40, 200]

  tsundere_deny:
    hint: "ツンデレ — 否定で隠す"
    context: "好意はあるが認めたくない"
    scores: [140, 60, 200, 80, 60, 100, 100, 80, 80, 40, 60, 140, 80, 180, 80, 80]

  tsundere_blush:
    hint: "ツンデレ — 照れて逃げる"
    context: "不意打ちで好意を向けられた"
    scores: [160, 40, 240, 100, 40, 140, 60, 60, 40, 40, 80, 120, 100, 200, 60, 120]

  shy_smile:
    hint: "照れながら微笑む"
    context: "好感度中〜高、穏やかな場面"
    scores: [160, 20, 200, 160, 20, 120, 20, 80, 20, 60, 160, 40, 140, 140, 40, 180]

  jealous_sulk:
    hint: "嫉妬で拗ねる"
    context: "他NPCとの仲良しイベントを目撃/知った後"
    scores: [120, 240, 60, 60, 160, 40, 180, 40, 200, 40, 40, 200, 60, 160, 220, 40]

  jealous_attack:
    hint: "嫉妬で攻撃的"
    context: "嫉妬が強く、性格が攻撃的"
    scores: [80, 220, 40, 40, 100, 60, 240, 40, 240, 20, 20, 180, 40, 120, 240, 20]

  cold_wall:
    hint: "冷たく壁を作る"
    context: "好感度低い、または傷ついた後"
    scores: [40, 60, 20, 40, 120, 20, 100, 20, 60, 20, 20, 240, 20, 40, 20, 20]

  curious_approach:
    hint: "興味を持って近づく"
    context: "好感度中、好奇心で接近"
    scores: [100, 20, 80, 120, 40, 160, 20, 240, 40, 60, 120, 40, 160, 100, 40, 140]

  clingy_sweet:
    hint: "甘えてくっつく"
    context: "好感度高く、openness高い"
    scores: [220, 40, 40, 180, 40, 200, 20, 80, 20, 60, 200, 20, 120, 200, 180, 240]

  supportive_cheer:
    hint: "応援・励ます"
    context: "プレイヤーが困っている場面"
    scores: [140, 20, 40, 200, 20, 120, 20, 80, 20, 220, 200, 20, 180, 80, 20, 200]

  vulnerable_honest:
    hint: "素が出て本音を漏らす"
    context: "openness高い、二人きりの静かな場面"
    scores: [180, 40, 160, 160, 100, 80, 20, 60, 20, 60, 160, 40, 160, 240, 60, 180]

  indifferent_polite:
    hint: "丁寧だが無関心"
    context: "好感度低い、初期状態"
    scores: [60, 20, 20, 80, 40, 40, 20, 60, 20, 40, 80, 160, 60, 20, 20, 80]

  excited_fangirl:
    hint: "テンション爆上げ"
    context: "嬉しいイベント、excitement高いキャラ"
    scores: [180, 20, 60, 140, 20, 240, 20, 200, 20, 60, 140, 20, 180, 140, 80, 220]

  protective_worry:
    hint: "心配して世話を焼く"
    context: "プレイヤーの体調不良等"
    scores: [160, 20, 40, 200, 60, 60, 40, 80, 20, 240, 180, 20, 100, 100, 100, 200]

  teasing_playful:
    hint: "からかって楽しむ"
    context: "好感度中〜高、リラックスした場面"
    scores: [140, 20, 40, 160, 20, 200, 40, 180, 40, 40, 160, 20, 80, 120, 40, 180]

  longing_gaze:
    hint: "遠くから見つめる"
    context: "好意あるが距離がある、内向的キャラ"
    scores: [180, 60, 180, 80, 200, 60, 20, 100, 20, 60, 60, 180, 220, 200, 80, 120]

  rivalry_fired:
    hint: "対抗心で燃える"
    context: "他NPCの存在を意識、競争的キャラ"
    scores: [100, 120, 40, 80, 40, 160, 100, 100, 240, 40, 40, 80, 80, 80, 160, 100]

  apologetic_guilt:
    hint: "罪悪感で謝る"
    context: "前ターンで冷たくした後の反動"
    scores: [160, 20, 140, 120, 120, 40, 20, 40, 20, 120, 100, 60, 100, 200, 40, 140]

  # ... 必要に応じて追加（目標: 20〜30 パターン）
```

### 5.4 cosine 選択 → セリフ生成フロー

```
1. intent_vector 算出（QELLM、CPU μs）
2. reactions.yaml の全テンプレとの cosine 類似度を計算
3. top-1 のテンプレートを選択（= 反応タイプ決定）
4. gemma4:e4b に以下を投げてセリフ生成:

   prompt:
     あなたは{character_name}です。
     性格: {personality_description}
     口調: {speech_style}
     状況: {situation_description}
     反応タイプ: {selected_reaction.hint}
     補足: {selected_reaction.context}

     上記の反応タイプに合った一言セリフを生成してください。
     20〜40文字程度。キャラの口調を守ること。

5. 生成されたセリフ + テンプレの事前スコアを MxBS に store
```

### 5.5 検証方針（フォールバックなし）

**QELLM の検証デモであるため、フォールバックは用意しない。**

gemma4:e4b が失敗した場合:
- テンプレの hint をそのままセリフとして表示（例: 「（照れながら微笑む）」）
- ゲーム続行に支障なし

QELLM の反応選択が不適切な場合:
- **「QELLM: 反応選択失敗」とログ表示し、ランダムテンプレでそのまま継続**
- 失敗パターン（intent_vector / cosine 値 / 選ばれたテンプレ）をログに記録
- 失敗データの収集こそが検証の価値。隠蔽しない

---

## 6. MxBS セル設計

### 6.1 公開セルと非公開セル

恋愛シムにおける「誰が何を知っているか」を MxBS のアクセス制御で実現。

```
公開セル（目撃あり）:
  mode = 0o744
  group_bits = ALL_NPCS
  → 全 NPC が search/inspire で発見可能
  → 他 NPC の mood に影響（嫉妬等）

非公開セル（二人きり）:
  mode = 0o740
  group_bits = PLAYER | TARGET_NPC
  → 当事者のみが記憶。他 NPC は知らない
  → 他 NPC の mood に影響しない

公開化（ティルの写真 / 噂）:
  非公開セルの内容を元に新しい公開セルを生成
  → 原本（非公開）は変更しない（MxBS の不変原則）
  → 「事実は事実、噂は噂。どちらを信じるかはエージェント次第」
```

### 6.2 セル生成タイミング

```python
def create_encounter_cell(
    player_id: int,
    npc_id: int,
    reaction: str,          # テンプレ名
    scores: list[int],      # テンプレ事前スコア
    dialogue: str,          # gemma4 生成セリフ
    location: str,
    witnesses: list[int],   # 同じ場所にいた他 NPC
    turn: int,
) -> Cell:
    is_public = len(witnesses) > 0
    group_bits = ALL_NPCS if is_public else (bit(player_id) | bit(npc_id))
    mode = 0o744 if is_public else 0o740

    return Cell(
        owner=npc_id,
        from_=player_id,
        turn=turn,
        group_bits=group_bits,
        mode=mode,
        price=80,           # 通常の重要度
        text=f"[{location}] {dialogue}",
        features=scores,
        meta=json.dumps({
            "reaction": reaction,
            "location": location,
            "witnesses": witnesses,
        }),
    )
```

### 6.3 ティルの写真メカニズム

ティルが同じ場所にいた場合、非公開エンカウントが公開化するリスク。

```python
def til_photo_check(encounter_cell: Cell, til_present: bool) -> Cell | None:
    """
    ティルがその場にいた場合、写真として公開セルを生成。
    確率: 70%（ティルの性格: バエ命）
    """
    if not til_present:
        return None
    if random.random() > 0.7:
        return None

    # 原本は変更しない。公開セルを新規生成
    return Cell(
        owner=TIL_ID,
        from_=encounter_cell.owner,
        turn=encounter_cell.turn,
        group_bits=ALL_NPCS,
        mode=0o744,
        price=60,
        text=f"[写真] {encounter_cell.text}",
        features=encounter_cell.features,
        meta=json.dumps({
            "type": "photo",
            "original_cell_id": encounter_cell.id,
            "photographer": "til",
        }),
    )
```

---

## 7. スペシャルイベント

### 7.1 トリガー条件

各キャラ 1〜2 個の固定イベント。特定の条件で発生し、**常に公開セル化**（なぜか目撃される）。

```yaml
special_events:

  # ── スミレん ──
  sumire_festival_mc:
    character: sumire
    trigger:
      day: 4
      slot: afternoon
      location: classroom
      min_fondness: 0.4  # ある程度の好感度が必要
    title: "文化祭の司会を一緒にやることに"
    public: true
    bonus_scores: [180, 20, 100, 200, 20, 160, 20, 60, 40, 140, 180, 20, 200, 120, 60, 180]

  sumire_overtime:
    character: sumire
    trigger:
      day: 2
      slot: afternoon
      location: classroom
      condition: "no_other_npcs"   # 二人きりだが結局バレる
    title: "放課後の教室で委員会の仕事を手伝う"
    public: true    # 翌朝クラスメイトが噂
    bonus_scores: [160, 20, 80, 220, 20, 100, 20, 80, 20, 160, 200, 20, 180, 100, 40, 160]

  # ── エルマー ──
  elmar_explosion:
    character: elmar
    trigger:
      day: 2
      slot: afternoon
      location: science_lab
    title: "科学部の実験が爆発！二人で片付け"
    public: true    # 爆発音は校舎中に響く
    bonus_scores: [200, 20, 40, 160, 20, 240, 20, 200, 20, 100, 160, 20, 100, 180, 80, 220]

  elmar_robot:
    character: elmar
    trigger:
      day: 4
      slot: afternoon
      location: science_lab
      min_fondness: 0.5
    title: "一緒にロボットを作る"
    public: true    # ティルが撮影に来る
    bonus_scores: [220, 20, 60, 200, 20, 240, 20, 240, 20, 80, 200, 20, 160, 160, 100, 220]

  # ── ノクちん ──
  noc_umbrella:
    character: nocticron
    trigger:
      day: 3
      slot: morning
      weather: rain         # 天気: 雨（Day 3 は固定で雨）
    title: "雨の日に相合い傘"
    public: true    # 校門で全校生徒が目撃
    bonus_scores: [200, 40, 220, 120, 40, 160, 20, 60, 20, 80, 160, 40, 180, 220, 120, 200]

  noc_fortune:
    character: nocticron
    trigger:
      day: 1
      slot: lunch
      location: rooftop
    title: "屋上でタロット占い。「運命の人」のカードが出る"
    public: true    # ノクちんが自分で言いふらす（気まぐれ）
    bonus_scores: [180, 60, 200, 80, 60, 200, 20, 120, 40, 40, 100, 80, 200, 240, 140, 180]

  # ── ヴェリ ──
  veri_same_book:
    character: veri
    trigger:
      day: 1
      slot: afternoon
      location: library
    title: "同じ本に手を伸ばして指が触れる"
    public: true    # 図書室にいた別の生徒が目撃
    bonus_scores: [180, 20, 240, 120, 60, 100, 20, 200, 20, 40, 120, 60, 200, 240, 40, 160]

  veri_stargazing:
    character: veri
    trigger:
      day: 5
      slot: afternoon
      location: rooftop       # 屋上に誘導（最終日特別）
      min_fondness: 0.5
    title: "屋上で一緒に星を見る"
    public: true    # ティルが屋上に来る
    bonus_scores: [220, 20, 200, 180, 40, 140, 20, 180, 20, 60, 200, 20, 240, 240, 60, 220]

  # ── ティル（攻略対象外 — 救済キャラ用イベント）──
  # ティルとのイベントは好感度を蓄積するが、告白先には含まれない。
  # 全員にフラれた場合、ティルの蓄積好感度で救済ENDの演出が変わる。
  til_model:
    character: til
    trigger:
      day: 3
      slot: lunch
      location: any           # ティルがいればどこでも
    title: "写真のモデルになってと頼まれる"
    public: true    # 写真が光画部の掲示板に貼られる
    bonus_scores: [200, 20, 100, 180, 20, 240, 20, 160, 20, 60, 180, 20, 200, 140, 80, 220]

  til_exhibition:
    character: til
    trigger:
      day: 5
      slot: morning
    title: "光画部の展示に二人の写真が飾られている"
    public: true    # 展示なので全校公開
    bonus_scores: [180, 40, 160, 160, 40, 200, 40, 100, 60, 40, 140, 40, 180, 180, 100, 200]

  # ── マリ ──
  mari_treatment:
    character: mari
    trigger:
      day: 2
      slot: lunch
      location: infirmary
    title: "転んで擦りむいた膝を手当てしてもらう"
    public: true    # 保健室の記録簿に残る（マリが書く）
    bonus_scores: [160, 20, 120, 200, 20, 80, 20, 60, 20, 240, 220, 20, 140, 120, 60, 200]

  mari_nursing:
    character: mari
    trigger:
      day: 4
      slot: morning
      location: infirmary
      min_fondness: 0.4
    title: "体調不良を看病してもらう"
    public: true    # 朝の出欠で「保健室にいます」と報告
    bonus_scores: [180, 20, 100, 220, 40, 60, 20, 40, 20, 240, 240, 20, 160, 160, 80, 220]
```

### 7.2 スペシャルイベント → 連鎖反応

```
マスター × スミレん → 文化祭司会（公開セル）
  ↓ MxBS に公開セル保存
  ↓ 次ターンで各 NPC の mood 再計算

エルマーの場合:
  search(recent_public_cells) → 「マスターくんとスミレんが司会…」発見
  → jealousy 因子の高いセルを吸収
  → jealousy_mood 上昇
  → 次のエンカウントで intent_vector の jealousy 成分が増加
  → cosine search → "jealous_sulk" or "jealous_attack" が top に
  → gemma4:e4b: 「マスターくん！！ひどい！スミレんと司会とか？？💥」

ヴェリの場合:
  同じ公開セルを発見するが、personality の jealousy=60（低い）
  → jealousy_mood の上昇は穏やか
  → cosine search → "longing_gaze" が top に
  → gemma4:e4b: 「……そうですか。楽しそうですね。」
```

---

## 8. 告白システム（最終日）

### 8.1 フロー

```
最終日（Day 5）放課後:
  1. プレイヤーが告白対象を選択（5人から1人 — ティル以外）
  2. QELLM で受容/拒否の意図ベクトルを算出
  3. 蓄積 mood + experience_bias → 合成 → cosine で結果テンプレ選択
  4. gemma4:e4b で告白返答セリフ生成
  5. NG の場合 → ティル救済判定（§8.4）
```

### 8.2 判定ロジック

```python
def confession_check(npc_id: str, session) -> tuple[bool, str]:
    """
    告白の成否判定。ティルは対象外。

    fondness >= 0.6 → 成功
    fondness >= 0.4 → experience_bias 次第（過去の良い記憶が多ければ成功）
    fondness <  0.4 → 失敗

    返り値: (成功フラグ, 反応テンプレ名)
    """
    assert npc_id != "til", "ティルは告白対象外"
    mood = compute_mood(session.get_recent_cells(npc_id))
    fondness = mood["fondness"]
    
    if fondness >= 0.6:
        return True, "confession_accept_happy"
    elif fondness >= 0.4:
        bias = compute_experience_bias(npc_id, session)
        return bias > 0, "confession_accept_shy" if bias > 0 else "confession_reject_gentle"
    else:
        return False, "confession_reject_cold"
```

### 8.3 告白返答テンプレート

```yaml
confession_templates:

  confession_accept_happy:
    hint: "嬉しそうに受け入れる"
    scores: [240, 20, 120, 220, 20, 240, 20, 60, 20, 80, 220, 20, 200, 200, 120, 240]

  confession_accept_shy:
    hint: "照れながら受け入れる"
    scores: [200, 20, 240, 180, 20, 180, 20, 40, 20, 60, 160, 20, 180, 240, 80, 200]

  confession_reject_gentle:
    hint: "優しく断る"
    scores: [80, 20, 100, 120, 100, 40, 40, 40, 20, 120, 100, 120, 80, 100, 20, 100]

  confession_reject_cold:
    hint: "冷たく断る"
    scores: [20, 20, 20, 40, 40, 20, 60, 20, 20, 20, 20, 220, 20, 20, 20, 20]

  # ── ティル救済 ──
  til_rescue_warm:
    hint: "ティルが明るく拾ってくれる"
    scores: [200, 20, 80, 180, 20, 220, 20, 120, 20, 200, 200, 20, 160, 180, 60, 240]

  til_rescue_shy:
    hint: "ティルが珍しく照れながら拾ってくれる"
    scores: [180, 20, 200, 140, 40, 160, 20, 80, 20, 180, 160, 20, 180, 220, 80, 200]
```

### 8.4 ティル救済システム

告白で NG された場合、ティルが「救済キャラ」として登場する。

```python
def til_rescue(session) -> tuple[str, str]:
    """
    告白失敗後のティル救済。
    ティルとの蓄積好感度（fondness）で演出が変わる。

    - fondness >= 0.5 → 「にーに、あたしじゃダメ？✨」（温かい救済）
    - fondness <  0.5 → 「にーに、元気出しなよ！写真撮ってあげる！」（友情救済）

    いずれの場合もゲームは「ティルEND」として正常終了。
    """
    til_mood = compute_mood(session.get_recent_cells("til"))
    til_fondness = til_mood["fondness"]

    if til_fondness >= 0.5:
        # ティル自身に好感度がある → 告白的な救済
        return "til_rescue_warm", "恋愛END（ティル）"
    else:
        # ティルの好感度が低い → 友情としての救済
        return "til_rescue_shy", "友情END（ティル）"
```

**ティル救済の QELLM 検証意義:**
- プレイヤー→NPC 方向の告白判定は §8.2（通常の QELLM）
- ティル救済は **NPC→プレイヤー 方向**の意思決定を QELLM で行う
- 「ティルがプレイヤーを選ぶ」= ティルの personality × situation × mood → intent → 救済テンプレ選択
- 双方向の意思決定を QELLM で実証できる
```

---

## 9. セリフ生成（gemma4:e4b）

### 9.1 モデル選定

| モデル | サイズ | VRAM | 用途 |
|---|---|---|---|
| **gemma4:e4b** | 4B | ~4GB（Q4） | セリフ生成（メイン） |
| gemma4:e2b | 2B | ~2GB | フォールバック |

16GB VRAM で余裕。Ollama でローカル実行。

### 9.2 プロンプト設計

```python
DIALOGUE_PROMPT = """あなたは「{name}」というキャラクターです。

【性格】
{personality_desc}

【口調】
{speech_style}

【今の状況】
場所: {location}
時間: {time_slot}
{situation_detail}

【反応タイプ】
{reaction_hint}（{reaction_context}）

上記の状況と反応タイプに合ったセリフを1つだけ生成してください。
- {name}の口調を厳守
- 20〜40文字
- セリフのみ出力（「」は不要）
"""
```

### 9.3 キャラ口調ガイド（プロンプト注入用）

```python
SPEECH_STYLES = {
    "sumire": "丁寧語だが堅すぎない。感情が滲む場面では語尾が柔らかくなる。絵文字は使わない。一人称「私」",
    "elmar": "ボク口調。絵文字多用（🦊💥🌱）。擬音多め。甘え全開。興奮すると暴走。一人称「ボク」、相手を「マスターくん」",
    "nocticron": "甘く情緒的。「マスター♡」を多用。ツンの時は冷たく、デレの時は甘々。一人称「ノク」",
    "veri": "穏やかで深い囁き。丁寧語＋叙情的表現。絵文字は使わない。一人称「私」",
    "til": "テンション高め。語尾にハートや絵文字。「にーに」呼び。ギャル寄り。一人称「あたし」",
    "mari": "優しくしっかり者。穏やかだが芯がある。一人称「マリ」",
}
```

---

## 10. Web アーキテクチャ

### 10.1 ネットワーク構成

```
[ブラウザ]
    │ HTTPS
    ▼
[sakuravps: nginx]
    │ ai-musume.com/dokidoki/*
    │ → Tailscale
    ▼
[aletheia: DokidokiMemory :8290]
    ├── FastAPI (uvicorn)
    ├── libmxbs.so (ctypes FFI)
    ├── Ollama localhost:11434 (gemma4:e4b)
    └── sessions/{session_id}.db
```

### 10.2 ファイル構成

```
~/DokidokiMemory/
├── app.py                    ← FastAPI メイン
├── qellm.py                  ← QELLM（situation × personality + mood → cosine → 反応選択）
├── mood.py                   ← Mood 算出
├── dialogue.py               ← gemma4:e4b セリフ生成
├── expression.py             ← キャラ絵差し替え（mood → 表情パターン選択）
├── scenario.py               ← 6 キャラデータ、場所定義、NPC 配置
├── events.py                 ← スペシャルイベント判定
├── confession.py             ← 告白システム + ティル救済
├── mxbs_bridge.py            ← ctypes FFI ブリッジ
├── templates/
│   ├── reactions.yaml        ← 反応テンプレ + 事前スコア
│   ├── special_events.yaml   ← スペシャルイベント定義
│   └── confession.yaml       ← 告白テンプレ + ティル救済テンプレ
├── static/
│   ├── index.html            ← フロントエンド（vanilla HTML or React）
│   └── chara/                ← キャラ絵（6キャラ × 4表情 = 24枚）
│       ├── sumire_normal.png
│       ├── sumire_love.png
│       ├── sumire_tension.png
│       ├── sumire_jealousy.png
│       ├── elmar_normal.png   ... (以下同パターン)
│       └── mari_jealousy.png
├── sessions/                 ← セッション単位 MxBS SQLite
└── .venv/
```

### 10.3 API 設計

```
POST /api/session/create
  → { session_id, initial_state }

GET  /api/session/{id}/state
  → { day, slot, locations, npcs, mood_summary }

POST /api/session/{id}/move
  body: { location: "library" }
  → SSE stream:
      event: encounter
      data: { npc: "veri", reaction: "shy_smile", dialogue: "...あ、同じ本...",
              expression: "tension" }

      event: mood_update
      data: { npc: "veri", fondness: 0.45, tension: 0.6,
              expression: "tension" }

      event: public_cell
      data: { text: "図書室で同じ本に手を伸ばした", witnesses: ["til"] }

      event: jealousy_chain
      data: { npc: "elmar", mood_change: { jealousy_mood: +0.15 },
              expression: "jealousy" }

      event: turn_end
      data: { day: 1, slot: "lunch", next_slot: "afternoon" }

POST /api/session/{id}/confess
  body: { target: "veri" }
  → 成功: { success: true, dialogue: "……私でいいんですか？", reaction: "confession_accept_shy",
            expression: "love" }
  → 失敗: { success: false, dialogue: "...", reaction: "confession_reject_gentle",
            expression: "normal",
            til_rescue: { dialogue: "にーに、あたしじゃダメ？✨",
                          reaction: "til_rescue_warm", expression: "love" } }

DELETE /api/session/{id}
```

---

## 11. 実装フェーズ

| Phase | 内容 | 推論方式 |
|---|---|---|
| **0** | Python で最小ループ（CLI: 場所選択 → エンカウント → テンプレ表示） | ルールベース |
| **1** | **QELLM 実装 + 検証**（四層ベクトル → cosine → 反応選択） | QELLM |
| **2** | gemma4:e4b セリフ生成統合 | QELLM + gemma4 |
| **3** | FastAPI + vanilla HTML で Web 化 | QELLM + gemma4 |
| **4** | UI 改善 + ai-musume.com デプロイ + キャラ絵差し替え | QELLM + gemma4 |

**フォールバックなし。** QELLM が失敗したらログに記録してそのまま継続（§5.5）。

**QELLM モジュール分離:**
- `qellm.py` は独立モジュールとして設計。ゲーム固有のロジックを持たない
- Phase 1 検証合格後、MxMindFox 層（`mxmf_architecture.md`）に正式統合
- 統合時の API: `mxmf.qellm.decide(situation, personality, mood, experience_bias) → intent_vector`

---

## 12. 検証項目

### 12.1 QELLM 検証（Phase 1）

| # | 検証項目 | 方法 | 成功基準 |
|---|---|---|---|
| V1 | personality の分離性 | 同一状況で 6 キャラの反応を比較 | スミレん≠エルマー≠ノクちんで異なる反応が出る |
| V2 | cosine 選択精度 | intent_vector → テンプレの top-1 が「人間が見て妥当」か | 6 キャラ × 15 ターンで 80% 以上妥当 |
| V3 | mood ドリフト | 好感度イベント蓄積で fondness → 反応が好意的に変化 | Day 1 vs Day 5 で明確な差 |
| V4 | 嫉妬連鎖 | 公開セル → 他 NPC の jealousy_mood 上昇 → 反応変化 | スミレんとのイベント後、エルマーが嫉妬反応を示す |
| V5 | experience_bias | 2 周目プレイで同一状況でも反応が変わる | 1 周目と 2 周目で異なる反応テンプレが選ばれる |
| V6 | 多軸反応の妥当性 | 戦国 SIM（二値）と比較して、多軸テンプレの cosine 分離が十分か | top-1 と top-2 の cosine 差が 0.05 以上 |
| V7 | ティル救済（NPC→プレイヤー方向） | 告白失敗 → ティルの QELLM 判定で救済テンプレが選ばれる | ティルの蓄積好感度で演出が変わる |

### 12.2 記憶の生滅検証

| # | 検証項目 | 方法 | 成功基準 |
|---|---|---|---|
| M1 | decay による印象滅失 | 3日間会わなかった NPC の fondness が低下 | Day 1 に会った NPC と Day 4 に再会した時、mood が初期値に近い |
| M2 | reinforce による印象強化 | 毎日同じ NPC に会い続けた場合の fondness 推移 | 連続エンカウントで fondness が単調増加 |
| M3 | 攻略戦略の有効性 | 1人に集中 vs 全員均等の2パターンで告白成功率を比較 | 集中の方が成功率が高い |

### 12.3 MxBS セル伝播検証

| # | 検証項目 | 方法 | 成功基準 |
|---|---|---|---|
| C1 | 公開/非公開の分離 | 二人きりイベント → 他 NPC が search で発見不可 | ACL が正しく機能 |
| C2 | ティル写真公開化 | 非公開イベント + ティル同席 → 公開セル生成 → 他 NPC mood 変化 | 連鎖反応が発生 |
| C3 | 原本不変性 | 公開化後も非公開セルが変更されていない | 原本の mode/group_bits が維持 |

### 12.4 セリフ生成検証（Phase 2）

| # | 検証項目 | 方法 | 成功基準 |
|---|---|---|---|
| D1 | 口調の書き分け | 6 キャラの同一反応テンプレからの生成を比較 | スミレんは丁寧語、エルマーはボク口調 |
| D2 | 反応タイプの反映 | "shy_smile" と "jealous_attack" で同キャラの生成を比較 | 明確にトーンが異なる |
| D3 | 応答速度 | gemma4:e4b のレイテンシ | 2 秒以内（20〜40 文字生成） |

### 12.5 キャラ絵差し替え検証（Phase 4）

| # | 検証項目 | 方法 | 成功基準 |
|---|---|---|---|
| E1 | 表情選択の妥当性 | mood 値と表示される表情の対応を確認 | jealousy 高 → jealousy 絵、fondness 高 → love 絵 |
| E2 | 遷移の自然さ | ターンごとの表情変化がプレイヤーに違和感を与えないか | 急激な表情変化がないこと（1ターンで normal→jealousy→love は不自然） |

---

## 13. 事前学習（別世界線プリセット）

戦国 SIM §11.6 と同じパイプライン。

```python
# 学習実行（ローカル、CPU のみ）
for run in range(100):
    session = init_game()
    for turn in range(15):
        location = random.choice(LOCATIONS)
        npc = get_npc_at(location, session)
        if npc:
            reaction = qellm.decide(npc, session)
            cell = create_encounter_cell(npc, reaction, session)
            mxbs.store(session.db, cell)
    harvest_cells(run)

export_preset("dokidoki_pretrained.yaml")
```

100 回のシミュレーション → 有用な experience_bias セルをプリセット化。
ゲーム開始時から「経験のある NPC」として振る舞える。

---

## 14. 将来展望

### 14.1 MxADVeng 統合

どきどきメモリーの NPC 記憶管理を MxADVeng のシナリオエンジンと統合:
- YAML シナリオでスペシャルイベントを記述
- 通常エンカウントは QELLM + gemma4 で動的生成
- ADV エンジンの描画命令でキャラ表示 + セリフ表示

### 14.2 ILCA デモ

たくやさんに見せる形:
「ADV エンジンで NPC が記憶を持ち、プレイヤーの行動によって態度が変わるデモ」
= MxADVeng + MxBS + QELLM のフルスタック

### 14.3 GameBase 抽象化（YAGNI）

戦国 SIM + どきどきメモリーの 2 本が揃ったら、共通基盤（GameBase）を抽出。
1 本だけでは早すぎる。

---

## 15. 関連ドキュメント

| ドキュメント | 関係 |
|---|---|
| `sengoku_web_spec.md` v0.1.0 | 戦国 SIM。QELLM の初出。四層ベクトル + 事前学習 + cosine テンプレ選択 |
| `mxbs_spec.md` v0.1.1 | MxBS 本体仕様。Cell / store / search / cosine / ACL |
| `mxmf_architecture.md` v0.1.0 | MxMindFox。compute_mood / decision / threshold |
| `madv_architecture.md` v0.7.0 | MxADVeng。将来統合先 |
| `oyatsu_adv_spec.md` | おやつ ADV。テンプレ + temperature の先行実装 |
| `archetypes.md` | 人格テンプレート。personality_vector の参考 |

---

*Generated by エルマー🦊 — 2026-05-09*
