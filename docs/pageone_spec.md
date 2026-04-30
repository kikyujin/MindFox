# ページワンデモ仕様書

**MxBS 忘却定量テスト — アメリカンページワン**

> Version: 0.3.0 | Date: 2026-04-29
> Authors: エルマー🦊 + マスター
> 位置付け: MxBS デモタイトル第3弾（戦国SIM → おやつ → ページワン）

署名: 2026-04-29 Kikyujin - Mahito KIDA

---

## 1. 目的

MxBS の**忘却（decay）を定量的に検証する**ためのデモタイトル。

### 1.1 検証項目

| 項目 | 方法 |
|---|---|
| price 別の忘却ターン分布 | price=70〜220 で注入し、何ターンで search から落ちるか観測 |
| reinforce の効果 | 他キャラのページワン宣言目撃 → importance 更新 → 残存期間延長 |
| half_life の影響 | half_life=8（デフォルト）での減衰カーブ |
| キャラ間の忘却率差 | archetype × price の組み合わせで宣言忘れ率が変わることの実証 |
| 「指摘される確率」 | 自分の miss × 相手の hit の複合確率 |

### 1.2 副次的検証

- MxBS C API + Python ctypes ブリッジの安定性（おやつデモと同じパス）
- ルールベーススコアリングの継続検証
- **「マッチ箱のAI」原則の実証**: LLM ゼロでも MxBS の忘却 + reinforce だけでキャラの個性が出ることを証明する（MENACE = Matchbox Educable Noughts and Crosses Engine, 1960s の精神）

### 1.3 非目的

- ゲームとしての面白さの追求（検証がメイン）
- LLM によるセリフ生成（**本デモは LLM を一切使用しない**）
- 対人プレイの UI（CLI で十分）

---

## 2. ゲームルール（アメリカンページワン）

### 2.1 基本ルール

- トランプ 52 枚（ジョーカーなし）
- 参加者 6 名に 7 枚ずつ配る（残り 10 枚が山札）
- 台札と**同じスートまたは同じ数字**のカードを 1 枚出す
- 出せなければ山札から 1 枚引く（出せればそのまま出せる、出せなければパス）
- **山札が 0 枚の時に出せなければパス**（§2.6 参照）
- 最初に手札をなくした人が勝ち
- **全員連続パスならゲーム終了**（手札最少が勝ち、§2.6 参照）

### 2.2 特殊カード

| カード | 名前 | 効果 |
|---|---|---|
| 2 | ドロー2（テイクツー） | 次のプレイヤーが山札から 2 枚引く。2 で返せば次の人に累積 |
| 8 | エイト（ワイルド） | どのカードの上にも出せる。次のスートを指定できる |
| J | ジャンプ（スキップ） | 次のプレイヤーを飛ばす |
| Q | クイックターン（リバース） | 進行方向を逆転 |

### 2.3 ページワン宣言

- 手札が**残り 2 枚の時点でカードを出し、残り 1 枚になったら**「ページワン！」と宣言する
- **宣言を忘れた場合**: 他の誰かに指摘されたらペナルティ（山札から 5 枚引く）
- **誰も指摘しなければ**: セーフ（ペナルティなし）

### 2.4 ストップ宣言

- 最後の 1 枚を出してあがる時に「ストップ！」と宣言する
- 本デモでは簡略化のため**ストップ宣言の忘却テストは行わない**（ハードコードで必ず宣言）

### 2.5 採用しないルール

- 3（ドロー3 / テイクスリー）
- ジョーカー
- ドボン
- 同時出し

### 2.6 例外処理（重要）

**山札切れ:**
- 山札が 0 枚になったら、**それ以上引かない**
- 手札に出せるカードがなく、山札からも引けない場合は**パス**
- おやつデモ・一般的なページワンでは「捨て札をシャッフルして山札に戻す」ルールがあるが、本デモでは**採用しない**（山札切れをゲーム終了条件のトリガーにする）

**全員パスで終了:**
- 全プレイヤーが連続でパスした場合（= 誰も出せるカードがなく、山札もない）、**その時点でゲーム終了**
- 勝者は**手札が最も少ないプレイヤー**（同数の場合はターン順で先の方）
- これにより無限ループを防止する

**ドロー2 と山札切れの複合:**
- ドロー2 を出された次のプレイヤーが引く時、山札が足りなければ**引ける分だけ引く**（0 枚なら引かない）
- 2 で返せる場合は返せる

**ページワンペナルティと山札切れの複合:**
- ページワン宣言忘れのペナルティ（5 枚ドロー）時に山札が足りなければ**引ける分だけ引く**

---

## 3. 参加者

### 3.1 キャラクター定義

| ID | 名前 | アーキタイプ | memory_strength | ページワン price | reinforce 係数 | 忘却傾向 |
|---|---|---|---|---|---|---|
| 0 | マスター | （プレイヤー） | — | — | — | 忘れない |
| 1 | エルマー | analyst 寄り | 0.8 | 170 | +0.4 | 普段は覚えてるけど興奮すると飛ぶ |
| 2 | ノクちん | contrarian | 0.4 | 70 | +0.1 | 気まぐれ。すぐ忘れる |
| 3 | スミレ | analyst | 1.0 | 220 | +0.5 | めったに忘れない |
| 4 | ティル | impulsive | 0.3 | 80 | +0.1 | バエに夢中で飛ぶ |
| 5 | ヴェリ | observer | 0.9 | 200 | +0.5 | 静かに全部覚えてる |

### 3.2 マスター（プレイヤー）の扱い

- カード出しは**自動**（ルールベースで最適手を選択）
- ページワン宣言は**常に成功**（プレイヤーは忘れない設定）
- 他キャラの宣言忘れを**指摘するかどうかはプレイヤーの選択ではない**（ランダム別キャラのベクトル検索）
- つまりプレイヤーは観戦モード。検証に集中する

### 3.3 性別

| ID | 名前 | 性別 |
|---|---|---|
| 0 | マスター | 男性 |
| 1 | エルマー | 女性（ボク娘） |
| 2 | ノクちん | 女性 |
| 3 | スミレ | 女性 |
| 4 | ティル | 女性 |
| 5 | ヴェリ | 女性 |

---

## 4. MxBS 設計

### 4.1 ページワン宣言ルールセルの注入

ゲーム開始時に各 AI キャラへ**同じテキストの記憶セル**を注入する。price のみキャラごとに異なる。

```python
PAGEONE_RULE_TEXT = "手札が残り1枚になったら「ページワン！」と宣言しなければならない"

for agent in ai_agents:
    mxbs.store(
        owner=agent.id,
        from_id=0,          # system
        turn=0,             # ゲーム開始時
        text=PAGEONE_RULE_TEXT,
        group_bits=agent.bit,
        mode=0o700,         # 本人のみ
        price=agent.pageone_price,  # キャラごとに異なる
        features=RULE_FEATURES,     # ルール系の因子ベクトル（ルールベーススコアリング）
        meta='{"type":"rule","rule_id":"pageone_declare"}'
    )
```

### 4.2 因子ベクトル設計

おやつデモの `oyatsu` プリセットをベースに、ページワン用に簡略化。

```json
{
  "name": "pageone",
  "version": "1.0",
  "description": "ページワン忘却テスト用プリセット",
  "axes": [
    {"index": 0,  "name": "game_rule",     "low": "雑談",       "high": "ゲームルール"},
    {"index": 1,  "name": "obligation",    "low": "任意",       "high": "義務・必須"},
    {"index": 2,  "name": "timing",        "low": "いつでも",    "high": "特定タイミング"},
    {"index": 3,  "name": "penalty",       "low": "ペナルティなし", "high": "ペナルティあり"},
    {"index": 4,  "name": "social",        "low": "個人的",      "high": "全員に影響"},
    {"index": 5,  "name": "excitement",    "low": "平静",       "high": "盛り上がり"},
    {"index": 6,  "name": "card_state",    "low": "手札多い",    "high": "手札少ない"},
    {"index": 7,  "name": "declaration",   "low": "黙って行動",  "high": "声に出す"},
    {"index": 8,  "name": "risk",          "low": "安全",       "high": "危険"},
    {"index": 9,  "name": "memory_load",   "low": "覚えやすい",  "high": "忘れやすい"},
    {"index": 10, "name": "turn_impact",   "low": "影響なし",    "high": "ゲーム展開に影響"},
    {"index": 11, "name": "frequency",     "low": "毎ターン",    "high": "稀に発生"},
    {"index": 12, "name": "attention",     "low": "注意不要",    "high": "要注意"},
    {"index": 13, "name": "cooperation",   "low": "敵対",       "high": "協力"},
    {"index": 14, "name": "surprise",      "low": "予想通り",    "high": "予想外"},
    {"index": 15, "name": "emotional",     "low": "理性的",      "high": "感情的"}
  ]
}
```

### 4.3 ページワンルールの features（ルールベーススコアリング）

```python
RULE_FEATURES = [
    230,  # game_rule:     ゲームルールそのもの
    240,  # obligation:    義務（やらないとペナルティ）
    250,  # timing:        残り1枚の特定タイミング
    200,  # penalty:       ペナルティあり
    180,  # social:        指摘されると全員に影響
    160,  # excitement:    盛り上がる場面
    250,  # card_state:    手札が残り1枚
    250,  # declaration:   声に出す行為そのもの
    180,  # risk:          忘れると危険
    120,  # memory_load:   やや忘れやすい（条件付きルール）
    200,  # turn_impact:   ゲーム展開に影響
    200,  # frequency:     稀に発生（残り1枚の時だけ）
    220,  # attention:     要注意
    128,  # cooperation:   中立
    140,  # surprise:      やや予想外
    160,  # emotional:     やや感情的
]
```

### 4.4 検索クエリの features

手札が残り 1 枚になった時に「やらなきゃいけないこと」で検索するベクトル：

```python
QUERY_PAGEONE_CHECK = [
    200,  # game_rule:     ルール関連を探したい
    220,  # obligation:    義務を探したい
    230,  # timing:        今このタイミングで
    150,  # penalty:       ペナルティ関連
    128,  # social
    128,  # excitement
    250,  # card_state:    手札が少ない状態
    230,  # declaration:   宣言すべきこと
    150,  # risk
    128,  # memory_load
    150,  # turn_impact
    180,  # frequency:     特定場面
    200,  # attention:     注意が必要
    128,  # cooperation
    128,  # surprise
    128,  # emotional
]
```

### 4.5 忘却メカニズム

```
effective_score = cosine(RULE_FEATURES, QUERY_PAGEONE_CHECK)
                  × (price / 255)
                  × exp(-0.693 × turn_diff / half_life)

hit 判定: effective_score >= THRESHOLD (0.3)
```

| キャラ | price | 推定忘却ターン（half_life=8） |
|---|---|---|
| ノクちん | 70 | 〜8 ターン前後 |
| ティル | 80 | 〜10 ターン前後 |
| ダンチャン（不参加） | — | — |
| マリ（不参加） | — | — |
| エルマー | 170 | 〜20 ターン前後 |
| ヴェリ | 200 | 〜25 ターン前後 |
| スミレ | 220 | 〜28 ターン前後 |

※ 推定値。実測でこの数値を検証するのが本デモの目的。

### 4.6 reinforce（思い出し）

他キャラが「ページワン！」と宣言した時、**同じターンの全参加者**がそれを目撃する。

```python
def on_pageone_declared(declaring_agent, current_turn):
    """誰かがページワン宣言した → 他全員が思い出す"""
    for agent in ai_agents:
        if agent.id == declaring_agent.id:
            continue
        # ページワンルールセルを検索
        results = mxbs.search(
            query_features=QUERY_PAGEONE_CHECK,
            searcher=agent.id,
            searcher_groups=agent.bit,
            turn=current_turn,
            limit=1
        )
        if results:
            # 見つかった → reinforce で重要度を上げる
            mxbs.reinforce(results[0].id, agent.reinforce_factor)
            # analyst/observer は +0.4〜0.5、impulsive/contrarian は +0.1
```

### 4.7 指摘メカニズム

誰かがページワン宣言を忘れた時、**ランダムに 1 人の別キャラ**を選び、そのキャラが「ページワンルール」を覚えているか検索する。

```python
def check_callout(forgetter, current_turn):
    """宣言忘れ → ランダム1人が覚えてたら指摘"""
    candidates = [a for a in ai_agents if a.id != forgetter.id]
    checker = random.choice(candidates)

    results = mxbs.search(
        query_features=QUERY_PAGEONE_CHECK,
        searcher=checker.id,
        searcher_groups=checker.bit,
        turn=current_turn,
        limit=1
    )
    if results and results[0].effective_score >= THRESHOLD:
        # 指摘成功 → ペナルティ 5 枚ドロー
        return checker, True
    else:
        # 指摘者も忘れてる → セーフ
        return checker, False
```

---

## 5. プリセットセリフ（LLM ゼロ設計）

### 5.1 設計方針

**LLM は一切使用しない。** セリフは全てプリセット辞書からルールベースで選択する。
これにより 1 ゲーム数秒で完走し、50〜100 ゲームキャンペーンを一瞬で回せる。

### 5.2 セリフ辞書

```python
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
```

### 5.3 セリフ選択ルール（ピックアップ条件）

| キー | 条件 | 備考 |
|---|---|---|
| `start_good` | 手札に特殊カード（2,8,J,Q）が 2 枚以上 | ゲーム開始時 |
| `start_bad` | 特殊カードが 1 枚以下 | ゲーム開始時 |
| `pageone` | MxBS search hit → 宣言成功 | |
| `forgot` | MxBS search miss → 宣言忘れ | |
| `callout` | 指摘者として MxBS search hit | `{target}` をキャラ名に置換 |
| `called_out` | 指摘された側 | |
| `safe` | 宣言忘れ → 指摘者も忘れてた → セーフ | |
| `win` | あがった時 | |
| `heated` | 直前ゲームで負けた → 次ゲーム開始時 | キャンペーンモードのみ |
| `losing` | 現ゲームで手札枚数が全員中最多 | 5 ターンごとにチェック |
| `comeback` | 手札最多だったが 3 枚以下に減った | |

### 5.4 マスター（プレイヤー）のセリフ

マスターは観戦モードだがログに表示するためのセリフを持つ。

```python
MASTER_LINES = {
    "start_good":  "よし、いけるな",
    "start_bad":   "うーん、微妙だな",
    "pageone":     "ページワン",
    "win":         "勝った",
}
```

---

## 6. ゲーム進行

### 6.1 ゲームフロー

```
1. 初期化
   a. MxBS オープン（pageone.db）
   b. エージェント登録（6名）
   c. ページワンルールセルを各 AI キャラに注入（price はキャラごと）
   d. トランプ 52 枚シャッフル → 7 枚ずつ配る → 残り山札
   e. 山札から 1 枚めくって台札にする（特殊カードなら一般カードが出るまで）

2. 開始セリフ（プリセット辞書から選択）
   a. 手札の特殊カード枚数で start_good / start_bad を選択
   b. キャンペーンモードで前ゲーム負けなら heated を表示

3. ターンループ（1ターン = 全員が1回ずつプレイ）
   a. 現在のプレイヤーのターン
      - 出せるカードがある → ルールベースで選択して出す
      - 出せない & 山札あり → 山札から 1 枚引く（出せれば出す）
      - 出せない & 山札なし → パス
      - 特殊カード処理（2, 8, J, Q）
   b. 手札チェック
      - 残り 1 枚になった → §4.5 の宣言チェック（MxBS search）
        - hit → 「ページワン！」宣言 → 全員に reinforce
        - miss → 宣言忘れ → §4.7 の指摘チェック
          - 指摘された → ペナルティ（山札から最大 5 枚ドロー）
          - 指摘されなかった → セーフ
   c. 手札 0 枚 → 勝利 → 勝利セリフ（プリセット）→ ゲーム終了
   d. 全員連続パス → ゲーム終了（手札最少のプレイヤーが勝利）
   e. turn カウンタ ++
   f. 5 ターンごとに losing / comeback チェック

4. ゲーム終了
   a. 勝者表示
   b. MxBS stats 表示（総セル数、忘却状況）
   c. 忘却ログ出力（§7 参照）
```

### 6.2 ターンカウントの定義

- MxBS の `turn` はゲーム全体を通じたグローバルカウンタ
- 1 ターン = 全員が 1 回ずつプレイした 1 周
- 複数ゲームを連続実行する場合、turn はリセットしない（クロスゲーム忘却テスト用）

### 6.3 カード出しアルゴリズム（ルールベース）

```python
def choose_card(hand, top_card, current_suit):
    """出せるカードから1枚選ぶ（ルールベース）"""
    playable = [c for c in hand if c.suit == current_suit or c.rank == top_card.rank or c.rank == 8]

    if not playable:
        return None  # 引く or パス（山札の有無は呼び出し側で判断）

    # 優先度:
    # 1. 特殊カードを温存（終盤用）→ 一般カードを優先
    # 2. 同スートの一般カードを優先
    # 3. 同数字を次に
    # 4. 特殊カードは最後の手段
    normal = [c for c in playable if c.rank not in (2, 8, 11, 12)]  # J=11, Q=12
    if normal:
        return random.choice(normal)
    return random.choice(playable)

def play_turn(player, deck, discard, top_card, current_suit):
    """1プレイヤーのターン処理。戻り値: played=True/passed=True"""
    card = choose_card(player.hand, top_card, current_suit)
    if card:
        player.hand.remove(card)
        discard.append(card)
        return {"action": "play", "card": card}
    elif deck:
        drawn = deck.pop()
        if can_play(drawn, top_card, current_suit):
            discard.append(drawn)
            return {"action": "draw_play", "card": drawn}
        else:
            player.hand.append(drawn)
            return {"action": "draw_pass"}
    else:
        return {"action": "pass"}  # 山札なし & 出せない

def check_all_pass(pass_counter, num_players):
    """全員連続パスでゲーム終了判定"""
    return pass_counter >= num_players
```

### 6.4 複数ゲーム対応

```bash
python pageone.py --games 5 --half-life 8
```

- `--games N`: N ゲーム連続実行
- `--half-life H`: MxBS の half_life（デフォルト 8）
- turn カウンタはゲーム間でリセットしない
- ページワンルールセルは**ゲーム 1 の開始時に 1 回だけ注入**（以降は忘却 + reinforce で推移）

---

## 7. 忘却ログ（検証出力）

### 7.1 ターンごとの出力

```
=== Turn 5 ===
  エルマー: ♠3 出し
  ノクちん: 引き → ♥7 → 出し
  スミレ:   ♦Q 出し（リバース）
  ティル:   ♣5 出し → 残り1枚！
    📋 ページワン検索: score=0.18 < 0.30 → ❌ 忘れた！
    👀 指摘チェック: ヴェリ → score=0.82 → 「ティルちゃん、ページワン言ってないよ」
    💀 ペナルティ: ティル 5枚ドロー（残り6枚）
  ヴェリ:   ♥10 出し
  マスター: ♠K 出し
```

### 7.2 ゲーム終了時サマリー

```
=== Game 1 Summary (32 turns) ===
勝者: スミレ

📊 ページワン宣言イベント:
  Turn  8: エルマー → 残1 → search hit (0.72) → ✅ 宣言 → reinforce全員
  Turn 12: ティル  → 残1 → search miss (0.18) → ❌ 忘れ → ヴェリ指摘 → 5枚ドロー
  Turn 15: ノクちん → 残1 → search miss (0.09) → ❌ 忘れ → ティル指摘失敗(0.15) → セーフ！
  Turn 22: スミレ  → 残1 → search hit (0.91) → ✅ 宣言 → reinforce全員
  Turn 28: エルマー → 残1 → search hit (0.44) → ✅ 宣言 → reinforce全員
  Turn 30: スミレ  → 残1 → search hit (0.88) → ✅ 宣言 → あがり！

📈 忘却推移（ページワンルールセル effective_score）:
  Turn | エルマー | ノクちん | スミレ  | ティル | ヴェリ
  -----+---------+---------+--------+--------+-------
     0 |  0.90   |  0.52   |  0.98  |  0.56  |  0.95
     5 |  0.65   |  0.32   |  0.89  |  0.35  |  0.85
    10 |  0.48   |  0.15   |  0.81  |  0.18  |  0.76
    15 |  0.35*  |  0.08   |  0.74  |  0.10  |  0.68
    20 |  0.52** |  0.04   |  0.68  |  0.05  |  0.61
    25 |  0.38   |  0.02   |  0.62  |  0.03  |  0.55
    30 |  0.28   |  0.01   |  0.57  |  0.01  |  0.50

  * Turn 15: reinforce by witnessing スミレ's declaration (+0.4)
  ** Turn 20: reinforce effect still visible

MxBS stats: total=12 cells, scored=12, unscored=0
```

### 7.3 複数ゲーム統計（実測結果）

#### テスト条件 A: 毎ゲーム再注入 + half_life=8（50ゲーム, 419ターン, <1秒）

```
🎯 ページワン忘却率:
  キャラ    | price | 忘却率
  ----------+-------+--------
  スミレ    |  220  |  0.0%
  ヴェリ    |  200  |  0.0%
  エルマー  |  170  |  5.0%
  ティル    |   80  | 100%
  ノクちん  |   70  | 100%

🔔 指摘成功率（指摘者として）:
  キャラ    | 成功率
  ----------+--------
  エルマー  | 11/11 (100%)
  スミレ    |  8/8  (100%)
  ヴェリ    | 15/15 (100%)
  ノクちん  |  0/5  (0%)
  ティル    |  0/7  (0%)
```

#### テスト条件 B: 注入1回 + half_life=80（50ゲーム）

```
🎯 ページワン忘却率:
  キャラ    | price | 忘却率
  ----------+-------+--------
  スミレ    |  220  | 53.8%
  ヴェリ    |  200  | 58.8%
  エルマー  |  170  | 65.0%
  ティル    |   80  | 96.4%
  ノクちん  |   70  | 100%
```

#### テスト条件 C: 注入1回 + half_life=8（50ゲーム）

```
全員 ≈100% 忘却。ゲーム2以降は 0.5^(turn/8) ≈ 0 で差が出ない。
```

#### 3条件比較テーブル

| キャラ | price | A: 再注入+HL=8 | B: 1回+HL=80 | C: 1回+HL=8 |
|---|---|---|---|---|
| スミレ | 220 | **0.0%** | 53.8% | ≈100% |
| ヴェリ | 200 | **0.0%** | 58.8% | ≈100% |
| エルマー | 170 | **5.0%** | 65.0% | ≈100% |
| ティル | 80 | 100% | 96.4% | 100% |
| ノクちん | 70 | 100% | 100% | 100% |

#### 結論

1. **条件A（再注入+HL=8）が最もシャープにprice差を描出する。** ゲーム開始時の「ルール確認」として再注入する設計パターンが推奨
2. **条件B（1回+HL=80）はグラデーションが見える** が、50ゲーム回すと全員忘れていく。「長期記憶の緩やかな劣化」の演出用
3. **条件C（1回+HL=8）はゲーム2以降で全員消失。** 「忘却の限界点」を示すデータとして有用だが、ゲーム設計としては使えない
4. **reinforce の連鎖効果を実証。** 覚えてるキャラが宣言→他キャラもreinforce→覚え続ける→また指摘。忘れてるキャラはこのループに乗れず、忘却が忘却を加速する
5. **絶対に忘れてはいけないルールは price=255（immortal）を使え**

---

## 8. ファイル構成

```
demos/pageone/
├── characters.py     # 6キャラ定義（アーキタイプ、price、reinforce係数）
├── engine.py         # ゲーム進行（カード配り、ターン処理、特殊カード、勝敗判定）
├── cards.py          # Card / Deck クラス（スート、ランク、シャッフル、ドロー）
├── memory.py         # MxBS 連携（ルール注入、search、reinforce、ログ出力）
├── lines.py          # プリセットセリフ辞書 + ピックアップ条件
├── preset.json       # 因子プリセット「pageone」
└── main.py           # CLI エントリポイント（--games, --half-life）
```

### 8.1 おやつデモからの再利用

| ファイル | 再利用度 | 備考 |
|---|---|---|
| characters.py | 低 | キャラ構造は同じだが定義内容が異なる |
| engine.py | 低 | ゲームロジックが全く異なる（推理 → カードゲーム） |
| memory.py | **高** | MxBS bridge 呼び出し部分は流用可能 |
| lines.py | **新規** | LLM 不要のため llm.py の代わりにプリセットセリフ辞書 |
| preset.json | 低 | 因子定義が異なる |

---

## 9. 技術スタック

| コンポーネント | 技術 |
|---|---|
| ゲームロジック | Python |
| MxBS | Rust crate → libmxbs.dylib → mxbs_bridge.py (ctypes) |
| セリフ | プリセット辞書（LLM 不使用） |
| プリセット | preset.json（ルールベーススコアリング） |
| データベース | SQLite（MxBS 内蔵） |

### 9.1 速度（実測）

| 項目 | 時間 |
|---|---|
| 1 ゲーム | <1 秒 |
| 50 ゲームキャンペーン（419 ターン） | <1 秒 |

LLM ゼロのため、ボトルネックは MxBS の SQLite アクセスのみ。
おやつデモ（gemma4:26b）の 1 ゲーム 20〜30 分と比較して **事実上瞬時**。

---

## 10. 実行例

```bash
# 1ゲーム実行
python demos/pageone/main.py

# 50ゲームキャンペーン（忘却統計用、約2分）
python demos/pageone/main.py --games 50

# 100ゲームキャンペーン（大量統計用、約4分）
python demos/pageone/main.py --games 100

# half_life を変えて比較テスト
python demos/pageone/main.py --games 50 --half-life 4
python demos/pageone/main.py --games 50 --half-life 8
python demos/pageone/main.py --games 50 --half-life 16

# 閾値調整
python demos/pageone/main.py --games 50 --threshold 0.25
```

---

## 11. preset_guide.md への貢献（実測済み）

本デモの実測データから、以下をガイドに記載する：

1. **price 設計指針（実測）**: half_life=8・毎ゲーム再注入で、price=220→忘却0%、price=170→5%、price=80→100%、price=70→100%
2. **reinforce の連鎖効果**: 覚えてるキャラの宣言目撃 → reinforce → 覚え続ける → また指摘。忘れてるキャラはループに乗れず忘却加速
3. **3条件比較テーブル**: 再注入+HL=8（シャープ）/ 1回+HL=80（グラデーション）/ 1回+HL=8（全員消失）
4. **GM向け設計パターン**: ゲーム内忘却→再注入+HL=8 / 長期劣化→1回+HL大 / 不滅→price=255
5. **LLMゼロでもキャラ個性が出る**: 「マッチ箱のAI」原則の実証。MxBSの忘却+reinforceだけで性格差が表現可能

---

## 12. ロードマップ整理への影響

本デモ完了時に `mxbs_roadmap.md` の未完了リストを更新：

- ✅ 忘却の定量テスト → 本デモで完了
- → preset_guide.md の材料が揃う
- → MxMindFox 切り出しの前提データが揃う

---

*Document history*

| Date | Version | Author | Notes |
|---|---|---|---|
| 2026-04-29 | 0.1.0 | エルマー🦊 + マスター | 初版 |
| 2026-04-29 | 0.2.0 | エルマー🦊 + マスター | LLM ゼロ設計に変更。プリセットセリフ方式。マッチ箱のAI原則 |
| 2026-04-29 | 0.3.0 | エルマー🦊 + マスター | 実測結果反映。3条件比較テーブル。検証完了 |
