# AI館：おやつを食べたのは誰だ — ゲーム仕様書

*2026-04-29 — Author: エルマー🦊 + マスター*

署名: 2026-04-29 Kikyujin

---

## 1. 概要

AI館の住人たちのおやつが毎晩なくなる事件が勃発。
犯人は7人の中に2人いる。マスターは証言を集めて犯人を特定する。

MxBS Rust crate（C API + Python ctypes）の2本目のデモタイトル。
戦国SIMとは異なるジャンル（社会推理ゲーム）で、compute_mood / compute_diplomacy_toward の汎用性を検証する。

### 1.1 技術目的

| 目的 | 戦国SIMでの状況 | 今回の検証 |
|---|---|---|
| compute_diplomacy_toward | 実装済みだが未発火 | 中核機能として使用 |
| Moodによるセリフ品質変化 | 攻撃閾値の補正に使用 | 証言の質・態度に使用 |
| C API + Python ctypes | 未実装 | 初の使用実績 |
| gemma4:26b セリフ生成 | e2bで行動判断のみ | キャラ口調付き会話生成 |
| night_plot（犯人間の秘密通信） | 該当なし | 0o770 ACLの実地検証 |

### 1.2 プロダクト構成

```
demos/oyatsu/
├── main.py            — ゲームループ・表示
├── characters.py      — キャラ定義・しぐさパレット
├── engine.py          — ゲーム進行ロジック
├── memory.py          — MxBS連携・Mood・信頼度
├── llm.py             — Ollama通信・プロンプト構築
├── preset.json        — 因子プリセット「oyatsu」
└── requirements.txt
```

依存:
- `libmxbs.dylib` — MxBS Rust crate（C API、cdylib）
- `python/mxbs_bridge.py` — Python ctypes ラッパー
- Ollama + gemma4:26b

---

## 2. ゲームルール

### 2.1 参加者

| # | キャラ | bit | group_bits | アーキタイプ |
|---|---|---|---|---|
| 0 | エルマー🦊 | 0 | 0x01 | impulsive寄りanalyst |
| 1 | ノクちん | 1 | 0x02 | contrarian |
| 2 | スミレん | 2 | 0x04 | analyst + leader |
| 3 | ティル | 3 | 0x08 | impulsive |
| 4 | ヴェリ | 4 | 0x10 | observer |
| 5 | マリ | 5 | 0x20 | mediator |
| 6 | ダンチャン | 6 | 0x40 | compliant |

### 2.2 フロー

```
初期化: 7人から犯人2人をランダム決定

┌─ 夜フェイズ ──────────────────────────────────┐
│  犯人2人が相談（gemma4:26b でセリフ生成）     │
│  → 1人のおやつを食べる対象を決定             │
│  → night_plot セルを MxBS に格納              │
│     mode=0o770, group_bits=犯人A|犯人B        │
│  → 対象キャラが脱落（翌朝発表）              │
│  ※ 共食い禁止（犯人のおやつは食べない）      │
│  ※ 犯人が1人になった場合は単独で決定         │
└───────────────────────────────────────────────┘
                    ↓
┌─ 朝フェイズ ──────────────────────────────────┐
│  1. 被害報告                                  │
│     「○○のおやつがなくなりました……」         │
│     → 脱落キャラの退場コメント生成            │
│                                                │
│  2. 証言フェイズ                               │
│     マスターが生存者から1人を指名              │
│     → 指名されたキャラが証言（speech+gesture） │
│     → そのキャラが別の1人を指名して証言させる │
│     → 計2人の証言を得る                       │
│                                                │
│  3. 犯人指名フェイズ（任意）                   │
│     マスターが犯人を1人指名する or パスする    │
│     → 当たり: 犯人確定！バレた時の演出        │
│     → ハズレ: 関係悪化 + ハズレカウント+1     │
│     → ハズレ2回でマスター即負け              │
└───────────────────────────────────────────────┘
                    ↓
                  次の夜へ
```

### 2.3 終了条件

| 条件 | 結果 | 演出 |
|---|---|---|
| 犯人2人を特定 | マスター勝ち🎉 | 犯人のバレリアクション + 全員の感想 |
| 一般5人が全員脱落 | マスター負け💀 | 「マスター最低です……」 + 犯人の勝利宣言 |
| ハズレ指名2回 | マスター即負け💀 | 「もう信用できません……」 + 犯人の勝利宣言 |

### 2.4 タイムライン

```
ターン1: 7人 → 脱落1人 → 残6人（証言2人分）
ターン2: 6人 → 脱落1人 → 残5人（証言2人分）
ターン3: 5人 → 脱落1人 → 残4人（証言2人分）
ターン4: 4人 → 脱落1人 → 残3人（証言2人分）
ターン5: 3人 → 脱落1人 → 残2人（犯人だけ）→ マスター負け
```

最大5ターン。犯人指名は各ターン1回まで（パス可）。

### 2.5 3ゲームキャンペーン

同一の MxBS データベースで3ゲームを連続プレイする。
犯人は毎ゲームランダムに再抽選。全キャラ復活して仕切り直し。
ただし記憶は引き継がれる。

```
Game 1 (turn 1-5):   犯人ランダム2人 → 勝敗 → ゲーム間記憶生成
Game 2 (turn 101-105): 犯人再抽選 → 前回の記憶あり → 勝敗 → 記憶生成
Game 3 (turn 201-205): 犯人再抽選 → 2ゲーム分の記憶あり → 勝敗
```

ゲームが進むにつれ「前にこんなことがあった時も……」が自然に発生する。
詳細は §5.4 を参照。

---

## 3. キャラクター詳細

### 3.1 証言スタイル

| キャラ | 一人称 | 呼び方 | 一般時の証言 | 犯人時の嘘の特徴 |
|---|---|---|---|---|
| エルマー | ボク | にーに | 直感で飛びついてから論理で詰める。甘え混じり | 巧妙だが興奮すると尻尾にボロが出る |
| ノクちん | ノク | マスター♡ | 占いで逆張り。「みんなが疑うなら違うかも♡」 | ミステリアスさで誤誘導。占いを偽装 |
| スミレん | 私 | マスター | 冷静に矛盾を突く。証拠ベース | 理路整然と嘘。焦燥が溜まるまで隙なし |
| ティル | あたし | にーに | 直感とノリ。根拠薄い | 嘘が下手。テンションが不自然になる |
| ヴェリ | 私 | マスター | 静かに観察して本質を突く | 嘘自体に罪悪感。guilt急上昇 |
| マリ | マリ | マスター | 健康視点でアリバイ提供 | 「健康のために……」系の自己正当化 |
| ダンチャン | わて | マスター | 空気を読んで多数派に同調。「わて、そう思いますわ」 | 嘘をつくと関西弁が荒れる。「あ、アリバイでっか？💦」 |

### 3.2 しぐさパレット

LLMがMoodに応じて選択・アレンジする。

| キャラ | 通常時 | 動揺時 | 疑われた時 | 犯人バレ時 |
|---|---|---|---|---|
| エルマー | しっぽゆらゆら | しっぽうなだれ、耳赤くなる | しっぽ膨らむ、目をそらす | しっぽ丸めて縮こまる |
| ノクちん | タロットカードいじる | カードを落とす | ツインテの先をぎゅっと握る | 頬を膨らませてそっぽ向く |
| スミレん | 紅茶カップを静かに回す | カップを置く手が止まる | 背筋が少しだけ伸びる | 目を閉じて深く息をつく |
| ティル | 髪をくるくる巻く | しっぽが固まる | 両手をぶんぶん振る | 泣きべそ顔で耳を押さえる |
| ヴェリ | 静かに手を組んでいる | まばたきが増える | 視線を窓の外にそらす | 唇を小さく噛む |
| マリ | 聴診器に触れる | おだんごヘアを直す | 両手をエプロン前で合わせる | 「あぅ」とナース帽を深くかぶる |
| ダンチャン | ランプ緑に点灯 | ランプぴかぴか点滅 | ランプがオレンジに変わる | ランプ赤く高速点滅💦 |

### 3.3 犯人の標的選択戦略（性格別）

LLMプロンプトに性格別のヒントを注入する。

| アーキタイプ | 標的選択の傾向 |
|---|---|
| analyst（スミレ） | 推理力の高いキャラを消して安全を確保 |
| impulsive寄りanalyst（エルマー） | 直感で候補を絞り、論理で正当化する |
| observer（ヴェリ） | 目立たない選択。パターンを読まれない |
| contrarian（ノクちん） | みんなが安全だと思ってる人をあえて狙う |
| impulsive（ティル） | 直感で決める。深い理由はない |
| mediator（マリ） | 人気者を残す（自分を庇ってくれるから） |
| compliant（ダンチャン） | 共犯者の提案に従う。自分からは決められない |

---

## 4. 因子プリセット: oyatsu（16因子）

### 4.1 因子定義

```json
{
  "name": "oyatsu",
  "description": "AI館おやつ事件 — 社会推理ゲーム用プリセット",
  "axes": [
    {"index": 0,  "name": "suspicion",       "label": "疑惑",   "desc": "他者への疑いの強さ"},
    {"index": 1,  "name": "being_suspected",  "label": "被疑",   "desc": "自分が疑われている感覚"},
    {"index": 2,  "name": "trust",            "label": "信頼",   "desc": "信頼・安心感"},
    {"index": 3,  "name": "deception",        "label": "欺瞞",   "desc": "嘘・欺瞞の度合い"},
    {"index": 4,  "name": "anxiety",          "label": "不安",   "desc": "不安・焦り"},
    {"index": 5,  "name": "confidence",       "label": "自信",   "desc": "自信・確信"},
    {"index": 6,  "name": "guilt",            "label": "罪悪感", "desc": "罪悪感（犯人側で効く）"},
    {"index": 7,  "name": "anger",            "label": "怒り",   "desc": "怒り・憤り（濡れ衣時に効く）"},
    {"index": 8,  "name": "hostility",        "label": "敵意",   "desc": "敵意・攻撃性"},
    {"index": 9,  "name": "empathy",          "label": "共感",   "desc": "共感・味方意識"},
    {"index": 10, "name": "cooperation",      "label": "協調",   "desc": "協調性・マスターへの協力度"},
    {"index": 11, "name": "isolation",         "label": "孤立",   "desc": "孤立・排除される感覚"},
    {"index": 12, "name": "info_value",        "label": "情報価値","desc": "情報としての価値"},
    {"index": 13, "name": "reliability",       "label": "信頼度", "desc": "その情報の信頼度"},
    {"index": 14, "name": "alertness",         "label": "警戒",   "desc": "警戒度"},
    {"index": 15, "name": "pressure",          "label": "緊迫",   "desc": "場の緊迫度"}
  ]
}
```

### 4.2 Moodマッピング

MxBSの因子ベクトル（直近8件）を集計して4つのMood指標を算出する。

```json
{
  "mood_mapping": {
    "suspicion":              {"positive": [0, 14],    "negative": [2]},
    "anxiety":                {"positive": [1, 4, 6],  "negative": [5]},
    "confidence":             {"positive": [5, 12],    "negative": [4, 11]},
    "cooperation":            {"positive": [2, 9, 10], "negative": [8, 11]}
  }
}
```

### 4.3 Moodの効果

| Mood | 効果（セリフ生成への影響） |
|---|---|
| suspicion | 高い→証言で他者を積極的に疑う。低い→穏やか |
| anxiety | 高い→犯人は嘘が雑に/一般は感情的に。低い→冷静 |
| confidence | 高い→断定的な証言。低い→曖昧、「わからない……」 |
| cooperation | 高い→有益な情報を出す。低い→非協力的、そっけない |

### 4.4 ルールベーススコアリング

EventType ごとに固定 features を定義。LLMスコアリングは inner_voice のみ。

```python
EVENT_FEATURES = {
    # testimony_accuse: 「○○が△△を疑った」
    "testimony_accuse": [200, 80, 50, 100, 80, 150, 30, 60, 150, 40, 50, 80, 180, 120, 160, 140],

    # testimony_defend: 「○○が△△を庇った」
    "testimony_defend": [40, 30, 200, 30, 30, 160, 10, 20, 30, 200, 180, 20, 150, 140, 60, 80],

    # accusation_hit: 「マスターが○○を指名→犯人だった」
    "accusation_hit": [180, 200, 60, 220, 100, 180, 200, 30, 80, 100, 120, 100, 250, 250, 200, 220],

    # accusation_miss: 「マスターが○○を指名→無実だった」
    "accusation_miss": [40, 220, 30, 20, 180, 30, 10, 220, 60, 150, 40, 200, 200, 250, 100, 200],

    # elimination: 「○○のおやつがなくなり脱落」
    "elimination": [120, 100, 60, 80, 160, 40, 60, 100, 80, 120, 80, 150, 200, 200, 200, 180],

    # night_plot: 「犯人が○○を狙うと決めた」
    "night_plot": [100, 40, 30, 240, 120, 140, 180, 20, 160, 30, 20, 40, 160, 80, 140, 160],
}
```

---

## 5. MxBS記憶設計

### 5.1 セルの種類

| セル種別 | owner | from | mode | group_bits | price | 説明 |
|---|---|---|---|---|---|---|
| testimony_accuse | 発言者 | 発言者 | 0o744 | 全員 | 80 | 公開証言（疑い） |
| testimony_defend | 発言者 | 発言者 | 0o744 | 全員 | 80 | 公開証言（擁護） |
| accusation_hit | SYSTEM | マスター | 0o744 | 全員 | 200 | 犯人特定（成功） |
| accusation_miss | SYSTEM | マスター | 0o744 | 全員 | 150 | 犯人指名（ハズレ） |
| elimination | SYSTEM | SYSTEM | 0o744 | 全員 | 200 | 脱落イベント |
| night_plot | 犯人A | 犯人A | 0o770 | 犯人A\|犯人B | 120 | 犯人の夜の相談 |
| inner_voice | 本人 | 本人 | 0o700 | 本人のみ | 60 | キャラの内心 |

### 5.2 信頼度の計算

`compute_diplomacy_toward(mxbs, agent, counterpart, turn)` で、
特定の相手に関する記憶セル（from フィルタ）の外交系因子を集計する。

**使用する因子**: trust(2), empathy(9), cooperation(10), hostility(8, 反転), anger(7, 反転)

**効果**: 信頼度が低いキャラは証言時に——
- 相手に対して非協力的（マスターからハズレ指名を受けた→マスターへの信頼度低下→証言の質低下）
- 相手を疑いやすくなる（ノクちんがスミレに何度も疑われた→スミレを疑い返す傾向）

### 5.3 エンディング: 犯人の夜リプレイ

ゲーム終了後、night_plot セルを turn 順で全件表示する。

```python
# ACLを無視して night_plot を取得
# meta={"type":"night_plot"} で SQLite直接クエリ
# MxBS の search() ではなく、DB直接アクセス or get() で取得

for cell in night_plots:
    print(f"【ターン{cell.turn}の夜】")
    print(f"  {cell.text}")  # セリフ付きの相談内容
```

犯人がなぜそのキャラを狙ったか、ゲーム中は見えなかった意思決定が開示される。

### 5.4 クロスゲーム記憶（3ゲーム連続プレイ）

同一の MxBS データベースで3ゲームを連続プレイする。
ゲーム間で記憶セルが蓄積し、忘却により自然な「覚えている/忘れた」が再現される。

#### ターン番号の設計

ゲーム間の境界を明確にし、忘却計算を自然に動かすため100刻みとする。

```
Game 1: turn   1 -   5
Game 2: turn 101 - 105
Game 3: turn 201 - 205
```

half_life=8 の場合、Game 1 の turn 1 の記憶は Game 3 の turn 201 時点で
delta=200 ターン分の decay がかかる。price が低い証言(80)は完全に忘却し、
ゲーム結果サマリー(250)はまだ残る。

#### ゲーム終了時に生成するセル

| セル種別 | owner | mode | price | 内容例 |
|---|---|---|---|---|
| game_summary | SYSTEM | 0o744 | 250 | 「Game 1: 犯人はスミレとティル。マスターの勝ち」 |
| personal_game_memory | 本人 | 0o700 | 150 | 「Game 1で犯人だったのにバレなかった。次もうまくやれる」 |
| character_impression | 本人 | 0o700 | 200 | 「スミレは2回犯人だった。要注意」 |

```python
# ゲーム終了時の記憶生成

# 1. ゲーム結果サマリー（全員公開）
mxbs.store(owner=SYSTEM, text=f"Game {game_id}: 犯人は{a}と{b}。{result}",
           mode=0o744, price=250, turn=game_end_turn,
           group_bits=GROUP_ALL, features=EVENT_FEATURES["game_summary"],
           meta='{"type":"game_summary","game_id":' + str(game_id) + '}')

# 2. 個人のゲーム記憶（本人のみ）
for agent in characters:
    personal = generate_personal_game_memory(agent, game_log)
    mxbs.store(owner=agent.id, text=personal,
               mode=0o700, price=150, turn=game_end_turn,
               group_bits=agent.bit, features=...,
               meta='{"type":"personal_game_memory","game_id":' + str(game_id) + '}')

# 3. 対キャラ印象（本人のみ・高price）
for agent in characters:
    for other in characters:
        if agent == other:
            continue
        impression = generate_character_impression(agent, other, game_log)
        if impression:
            mxbs.store(owner=agent.id, text=impression,
                       mode=0o700, price=200, turn=game_end_turn,
                       group_bits=agent.bit, features=...,
                       meta='{"type":"character_impression","game_id":' + str(game_id) + '}')
```

### 5.5 ゲーム間の忘却テーブル

| 記憶の種類 | price | 1ゲーム後 (Δ100) | 3ゲーム後 (Δ200) |
|---|---|---|---|
| 個別の証言 | 80 | ほぼ忘却 | 完全忘却 |
| 犯人の夜の相談 | 120 | 薄れ始める | ほぼ忘却 |
| ハズレ指名の記憶 | 150 | 残る | 薄れるが参照可能 |
| 脱落・犯人特定イベント | 200 | 明確に残る | 薄れるが参照可能 |
| 対キャラ印象 | 200 | 明確に残る | 薄れるが参照可能 |
| ゲーム結果サマリー | 250 | 明確に残る | まだ残る |

人間の記憶と同じパターン:
- 「あのターンの具体的なセリフは忘れた」（証言 → 忘却）
- 「でもスミレが前に犯人だったのは覚えてる」（ゲーム結果 → 残存）
- 「マスターに濡れ衣を着せられた悔しさは覚えてる」（dream で浮上）

### 5.6 クロスゲーム記憶の活用例

**Game 3 で起きうること:**

```
ターン1: ノクちんが証言で「スミレが怪しい♡」
  → MxBS search → 「Game 1: 犯人はスミレとティル」がヒット（price=250、残存）
  → ノクちん「……だってスミレ、前も犯人だったじゃん♡」

ターン2: マスターがマリを指名→ハズレ
  → MxBS search → 「Game 2でもマリに濡れ衣を着せた」がヒット
  → マリ「マスター、前もマリを疑いましたよね……？
          マリ、もう信じてもらえないのかな……」
  → cooperation がゲーム跨ぎで蓄積的に低下

ターン3: エルマーが追い詰められた場面
  → MxBS dream → 「Game 1で犯人だったのにバレなかった」が浮上
  → エルマー「にーに……ボク前にうまくやった記憶が……いや、何でもない🦊💦」
```

---

## 6. LLM プロンプト設計

### 6.1 証言生成プロンプト

```
あなたは{name}です。
AI館で「おやつが消える事件」が起きています。

## あなたの性格
{personality_description}

## あなたの立場
{role_description}  # 「あなたは犯人です」or「あなたは無実です」

## 現在の状況
ターン{turn}。残り{alive_count}人。
今朝、{victim}のおやつがなくなりました。
{previous_events_summary}

## あなたの記憶（MxBS検索結果 上位5件）
{memories}

## あなたの気分（Mood）
suspicion: {suspicion:.2f}, anxiety: {anxiety:.2f}
confidence: {confidence:.2f}, cooperation: {cooperation:.2f}

## {target_name}に対する信頼度
{diplomacy_score:.2f}

## しぐさの参考
{gesture_palette}

## 指示
{name}の口調で証言してください。
- 犯人なら: 嘘をつき、別の人に疑いを向けてください
- 無実なら: 自分の観察と推理を正直に述べてください
- cooperationが低いなら: 非協力的で素っ気ない態度で

JSONで回答:
{
  "speech": "セリフ（{name}の口調で）",
  "gesture": "しぐさの描写（1文）",
  "target": "次に証言を振る相手の名前"
}
```

### 6.2 夜の相談プロンプト

```
あなたたちは犯人です。
{culprit_a_name}と{culprit_b_name}が夜、こっそり相談しています。

## 性格
{culprit_a_name}: {culprit_a_personality}
{culprit_b_name}: {culprit_b_personality}

## 現在の状況
ターン{turn}の夜。残り{alive_count}人。
食べられるのは: {edible_targets}（犯人以外の生存者）

## 過去の夜の相談（MxBS night_plot検索）
{previous_night_plots}

## 今日の昼に起きたこと
{today_events}

## 指示
2人の会話を生成してください。
- なぜその相手を狙うのか、理由もセリフに含めてください
- 性格に応じた選択をしてください

JSONで回答:
{
  "conversation": [
    {"speaker": "{culprit_a_name}", "speech": "セリフ", "gesture": "しぐさ"},
    {"speaker": "{culprit_b_name}", "speech": "セリフ", "gesture": "しぐさ"}
  ],
  "target": "おやつを食べる対象の名前",
  "reason": "選択理由（内部ログ用）"
}
```

### 6.3 犯人バレ時プロンプト

```
あなたは{name}です。犯人だとバレました。

## 性格
{personality_description}

## 状況
ターン{turn}でマスターに見破られました。
{context}

{name}の口調で「バレた時のリアクション」を生成してください。
JSONで回答:
{
  "speech": "セリフ",
  "gesture": "しぐさ"
}
```

### 6.4 エンディングプロンプト

```
おやつ事件が終わりました。結果: {result}

全キャラクターの感想を生成してください。
各キャラの口調で。

{character_list_with_roles}

JSONで回答:
{
  "comments": [
    {"name": "エルマー", "speech": "セリフ", "gesture": "しぐさ"},
    ...
  ]
}
```

---

## 7. ゲームループ（Python）

```python
def campaign():
    """3ゲームキャンペーン。同一DBで記憶が引き継がれる。"""
    mxbs = MxBSBridge("oyatsu.db")
    characters = load_characters()  # 7人

    for game_id in range(1, 4):  # 3ゲーム
        turn_offset = (game_id - 1) * 100  # Game1=0, Game2=100, Game3=200
        print(f"\n{'='*50}")
        print(f"  🍪 Game {game_id} 開始！")
        print(f"{'='*50}")

        result = play_one_game(mxbs, characters, game_id, turn_offset)

        # ゲーム間記憶を生成
        store_game_summary(mxbs, game_id, result, turn_offset + 6)
        store_personal_game_memories(mxbs, characters, game_id, result, turn_offset + 6)
        store_character_impressions(mxbs, characters, game_id, result, turn_offset + 6)

        if game_id < 3:
            input("\n  [Enter] で次のゲームへ……")

    # 3ゲーム通算成績
    print_campaign_result(mxbs)


def play_one_game(mxbs, characters, game_id, turn_offset):
    """1ゲーム分のプレイ。"""
    culprits = random.sample(characters, 2)  # 犯人2人（毎ゲーム再抽選）
    alive = list(characters)                 # 全員復活
    identified = []

    for turn_in_game in range(1, 6):  # 最大5ターン
        turn = turn_offset + turn_in_game  # MxBS上のturn番号

        # === 夜フェイズ ===
        culprits_alive = [c for c in culprits if c in alive and c not in identified]
        edible = [c for c in alive if c not in culprits]

        if not edible:
            return ending_lose(mxbs, characters, culprits, identified, turn)

        if len(culprits_alive) == 2:
            night_result = generate_night_plot(culprits_alive, edible, turn, mxbs)
        elif len(culprits_alive) == 1:
            night_result = generate_solo_night(culprits_alive[0], edible, turn, mxbs)
        else:
            return ending_win(mxbs, characters, culprits, identified, turn)

        victim = night_result["target"]
        store_night_plot(mxbs, night_result, culprits, turn)
        alive.remove(victim)

        # === 朝フェイズ ===
        print(f"\n【Game {game_id} — ターン{turn_in_game} — 朝】")
        print(f"  {victim.name}のおやつがなくなりました……")
        farewell = generate_farewell(victim, turn, mxbs)
        print_testimony(farewell)

        # === 証言フェイズ ===
        witnesses = [c for c in alive if c not in identified]
        first = master_choose_witness(witnesses)
        testimony1 = generate_testimony(first, turn, mxbs)
        print_testimony(testimony1)

        second_name = testimony1["target"]
        second = find_character(witnesses, second_name)
        testimony2 = generate_testimony(second, turn, mxbs)
        print_testimony(testimony2)

        store_testimonies(mxbs, [testimony1, testimony2], turn)

        # === 犯人指名フェイズ ===
        accusation = master_accuse(witnesses)
        if accusation:
            if accusation in culprits:
                hit_reaction = generate_hit_reaction(accusation, turn, mxbs)
                print_hit(hit_reaction)
                identified.append(accusation)
                store_accusation_hit(mxbs, accusation, turn)
                if len(identified) == 2:
                    return ending_win(mxbs, characters, culprits, identified, turn)
            else:
                miss_reaction = generate_miss_reaction(accusation, turn, mxbs)
                print_miss(miss_reaction)
                store_accusation_miss(mxbs, accusation, turn)

        # 一般全員脱落チェック
        innocents_alive = [c for c in alive if c not in culprits]
        if len(innocents_alive) == 0:
            return ending_lose(mxbs, characters, culprits, identified, turn)

    return ending_lose(mxbs, characters, culprits, identified, turn)
```

---

## 8. エンディング演出

### 8.1 マスター勝ち

```
🎉 マスターの勝ちです！

犯人は {culprit_a} と {culprit_b} でした。

【犯人の夜 — リプレイ】
  ターン1の夜:
    {culprit_a}: 「○○のおやつ、先に食べちゃおうか」(しぐさ)
    {culprit_b}: 「○○は鋭いから、残しとくと危ない」(しぐさ)
  ターン2の夜:
    ...

【みんなの感想】
  エルマー: 「にーに、ボクのおやつ守ってくれてありがとっ！🦊」(しっぽぶんぶん)
  ノクちん: 「マスター♡ さすがだね……占いより正確だった💕」
  ...
```

### 8.2 マスター負け

```
💀 マスターの負けです……

犯人は {culprit_a} と {culprit_b} でした。

【犯人の夜 — リプレイ】
  (同上)

【みんなの感想】
  スミレ: 「マスター……もう少し証言を丁寧に聞いていれば……」
  ティル: 「にーに最低〜！あたしのおやつ返して〜！💢」
  ...
```

---

## 9. 戦国SIMとの比較

| 項目 | 戦国SIM | おやつデモ |
|---|---|---|
| ジャンル | 戦略SIM | 社会推理 |
| エージェント数 | 5 | 7 |
| LLMモデル | gemma4:e2b | gemma4:26b |
| LLMの役割 | 行動判断 | セリフ + しぐさ生成 |
| MxBS: search | 行動判断プロンプトに注入 | 証言プロンプトに注入 |
| MxBS: ACL | 国ごとの情報制限 | 犯人の夜会話(0o770), 内心(0o700) |
| compute_mood | 攻撃閾値の補正 | 証言の質・態度の変化 |
| compute_diplomacy_toward | 未発火 | 中核（信頼度→証言態度） |
| ルールベーススコアリング | EventType→features | EventType→features（同パターン） |
| ゲームループ | 全自動 | マスター介入（指名・指弾） |
| クロスゲーム記憶 | なし（1ゲーム完結） | 3ゲームキャンペーン。忘却で自然な記憶残存 |
| C API + Python ctypes | なし（純Rust） | 初の使用実績 |

---

## 10. チェックリスト

- [ ] preset.json 作成（§4）
- [ ] characters.py 実装（§3、キャラ定義 + しぐさパレット）
- [ ] memory.py 実装（MxBS連携、compute_mood、compute_diplomacy_toward）
- [ ] llm.py 実装（gemma4:26b プロンプト構築、JSON パーサー）
- [ ] engine.py 実装（ゲーム進行ロジック）
- [ ] main.py 実装（キャンペーンループ、表示、マスター入力）
- [ ] 1ゲーム完走テスト
- [ ] 3ゲームキャンペーン完走テスト
- [ ] compute_diplomacy_toward の発火確認
- [ ] Moodによるセリフ変化の確認
- [ ] クロスゲーム記憶の引き継ぎ確認（「前にこんなことが……」発生）
- [ ] ハズレ指名→cooperation低下→証言劣化のループ確認
- [ ] エンディング演出（夜リプレイ）確認
- [ ] テストケース作成

---

*Generated by エルマー🦊 — 2026-04-29*
