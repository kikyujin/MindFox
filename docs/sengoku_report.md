# 戦国SIM デモ — 技術レポート

*2026-04-28 — Author: エルマー🦊 + マスター*

署名：2026-04-29 Kikyujin

---

## 1. 戦国SIMの構造

### 1.1 概要

MxBS Rust crateの実地テストとして構築した5カ国の戦国シミュレーション。
Rustバイナリで Ollama（gemma4:e2b）連携。全エージェントAI駆動。

```
demos/sengoku/
├── src/
│   ├── types.rs      — データ型（CountryState, Action, Personality, Mood）
│   ├── scenario.rs   — 5国データ、隣接表、プリセット、性格説明、戦略
│   ├── engine.rs     — 経済・戦闘・同盟・強制ロジック・Mood補正
│   ├── llm.rs        — Ollama通信、プロンプト構築、パーサー、バッチスコアリング
│   ├── memory.rs     — MxBS連携、EventType、ルールベーススコアリング、Mood算出
│   └── main.rs       — ゲームループ、表示、フェイズ制御
└── Cargo.toml        — mxbs crateへの直接依存
```

### 1.2 レイヤー構成

```
┌─────────────────────────────────────────┐
│  main.rs — ゲームループ・表示           │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │  engine.rs  │  │    llm.rs        │  │
│  │  戦闘・経済  │  │  Ollama通信      │  │
│  │  強制ロジック │  │  プロンプト構築   │  │
│  │  Mood補正    │  │  パーサー        │  │
│  └──────┬──────┘  └───────┬──────────┘  │
│         │                 │              │
│  ┌──────┴─────────────────┴──────────┐  │
│  │          memory.rs               │  │
│  │  compute_mood / get_agent_mood   │  │  ← MindFox候補
│  │  compute_diplomacy_toward        │  │  ← MindFox候補
│  │  EventType → features マッピング  │  │  ← ゲーム固有
│  │  store / search ラッパー          │  │
│  └──────────────┬────────────────────┘  │
│                 │                        │
├─────────────────┼────────────────────────┤
│  ┌──────────────┴────────────────────┐  │
│  │        MxBS Rust crate           │  │
│  │  store / search / dream          │  │
│  │  AgentRegistry                   │  │
│  │  preset / cosine                 │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 1.3 ゲームルール

- 5カ国（織田・徳川・武田・今川・斉藤）、1ターン1年、最大30ターン
- パラメータ3本: 国力（固定+領土加算）、金（変動）、兵力（変動）
- 最大2アクション/ターン（いくさは1回制限）
- 解決順序: 徴兵 → 同盟 → 戦闘（野戦・侵攻）
- 防御バフ: 侵攻時、防御側損失=攻撃側兵力×0.30、攻撃側損失=防御側兵力×0.45
- 同盟は1ターン限り（毎ターン allies.clear() で明示的リセット。仕様意図）

### 1.4 判断の三層構造

```
第1層: 強制ロジック（Rust、LLM不要）
  行動判断: 確殺 → タダ取り → 追い詰め突撃 → 覇気ルール（Mood補正）
  同盟判断: 攻撃対象への同盟自動拒否 → Mood信頼度チェック（< 0.3で拒否）
  ※ ほとんどのアクションがここで決まる

第2層: LLM判断（gemma4:e2b）
  強制ロジックに該当しない場合のみ
  MxBS記憶をプロンプトに注入（上位5件）

第3層: フォールバック
  Ollama未起動時はランダム選択
```

### 1.5 テスト

32テスト全パス。

---

## 2. 因子ベクトル 16バイトの検証

### 2.1 プリセット: sengoku_lite（16因子）

```
軍事 (0-3):  攻撃力 / 防御志向 / 規模 / 戦果
外交 (4-7):  信頼 / 裏切り / 同盟傾向 / 圧力
経済 (8-9):  経済力 / 変動
状況 (10-15): 不安 / 脅威 / 好機 / 自信 / 行動傾向 / 状況変化
```

### 2.2 Cosine分離性能

設計時のCosine検証結果:

| 比較 | Cosine | 評価 |
|---|---|---|
| 軍事系 vs 外交系 | 0.595 | 良好な分離 |
| 内心 vs 行動 | 0.61-0.69 | 良好 |
| 同系統イベント同士 | 0.82-0.99 | 正しくクラスタリング |

16バイトでもGM定義の因子軸が適切であれば、意味的な分離と近傍検索が成立する。

### 2.3 ルールベーススコアリングの有効性

EventType（Conscript, BattleAttacker, AllianceFormed等）ごとに固定featuresを定義。
LLMスコアリングが必要なのはinner_voice（自由テキスト生成物）のみ。

| スコアリング方式 | 対象 | 速度 |
|---|---|---|
| ルールベース | 構造化イベント全件 | 即座（μs） |
| LLMバッチ | inner_voice | 6-10秒/バッチ（4件） |

これによりターン所要時間が120秒→10-20秒に短縮。

### 2.4 数値まとめ

| 項目 | 値 |
|---|---|
| 因子ベクトルサイズ | 16バイト |
| bge-m3（旧方式）との比率 | 1/256 |
| 11ターンでの記憶セル数 | 87件（※ 特定1ランの結果。ラン毎に変動する） |
| 全セルの因子データ総量 | 87 × 16 = 1,392バイト |
| 外部依存 | SQLiteのみ |
| ONNX / bge-m3 / sqlite-vec | 全て不要 |

結論: 16バイトで十分。ゲームに必要な軸だけを定義すれば、汎用embeddingは不要。

---

## 3. 記憶がNPC行動を変化させることの確認

### 3.1 Moodシステム

MxBSの因子ベクトルを集計して4指標の「気分」を算出し、強制ロジックの閾値を動的に補正。

```
MxBS search(agent, 直近8件)
  → features平均を4カテゴリに集計
    → Mood { aggression, desperation, confidence, diplomacy }
      → should_attack_target() の閾値を ±0.4 程度補正
```

算出式:
```
mood_adjustment =
    (aggression - 0.5) × 0.8
  + (desperation - 0.5) × 0.6
  + (confidence - 0.5) × 0.4

adjusted_threshold = (base_threshold - mood_adjustment - pass_penalty).max(1.0)
```

特徴:
- LLMを経由しない。Rustコード内で完結
- MxBS crateの変更不要。全てホスト側で完結
- ルールベースfeaturesがそのままMoodの入力になる

### 3.2 実走結果: 11ターンで天下統一

#### 織田信長（覇王への成長曲線）

| ターン | 覇気 | 焦燥 | 自信 | 出来事 |
|---|---|---|---|---|
| 1 | 0.50 | 0.50 | 0.50 | 記憶なし。ニュートラル |
| 3 | 0.57 | 0.41 | 0.52 | 武田に勝利。上昇開始 |
| 7 | 0.67 | 0.36 | 0.60 | 確殺判定 |
| 8 | 0.66 | 0.41 | 0.55 | 兵力不足→LLMに判断委譲→同盟申込 |
| 11 | 0.72 | 0.40 | 0.56 | 天下統一 |

覇気0.50→0.72: 戦闘記憶の蓄積が覇気を積み上げ、攻撃閾値を下げ続けた。

#### 武田信玄（覇気に酔って散る）

| ターン | 覇気 | 焦燥 | 自信 | 出来事 |
|---|---|---|---|---|
| 1 | 0.50 | 0.50 | 0.50 | ニュートラル |
| 2 | 0.68 | 0.35 | 0.58 | 斉藤を滅ぼして絶頂 |
| 3 | 0.59 | 0.51 | 0.48 | 3国から袋叩き |
| 4 | 0.50 | 0.62 | 0.43 | 同盟拒否 → 滅亡 |

勝利記憶→覇気UP→過剰な攻撃→消耗→焦燥UP→滅亡。脚本なしの自然発生アーク。

#### 徳川家康（忍耐の末の滅亡）

| ターン | 覇気 | 焦燥 | 自信 | 出来事 |
|---|---|---|---|---|
| 1-5 | 0.49-0.55 | 0.42-0.45 | 0.48-0.52 | 安定。大きな変動なし |
| 10 | 0.41 | 0.52 | 0.41 | 覇気・自信が急落 |
| 11 | 0.37 | 0.60 | 0.37 | 焦燥MAX → 滅亡 |

### 3.3 確認事項

| 項目 | 結果 |
|---|---|
| 記憶ゼロ時のMood | 全指標0.50（ニュートラル）✅ |
| 勝利記憶によるaggression上昇 | 0.50→0.68（武田ターン2）✅ |
| 敗北記憶によるdesperation上昇 | 0.50→0.62（武田ターン4）✅ |
| 記憶蓄積による継続的成長 | 0.50→0.72（織田11ターン）✅ |
| Moodが攻撃閾値を変える | 覇気0.68で好機ルール発動 ✅ |
| 同一Personalityでもターンごとに閾値変動 | Analyst徳川の閾値がターンで異なる ✅ |
| MxBS crateの変更不要 | ホスト側のみで完結 ✅ |

### 3.4 未確認事項

| 項目 | 理由 |
|---|---|
| compute_diplomacy_toward（信頼度ベースの同盟拒否） | 実装済みだが11ターンのテストランでは条件に該当せず未観測 |
| inner_voiceのMoodヒントがe2bの判断に影響するか | テキスト記憶→LLM判断の効果は未検証 |
| 30ターン長期安定性 | 11ターンで決着したため未テスト |

---

## 4. MindFoxとして切り出せる可能性のあるパート

### 4.1 背景

旧MindFox spec（v0.2）では「記憶の自動配線」をコアバリューとし、Provider pattern（ActionProvider / ResolutionProvider）によるLLM外部化を設計していた。しかしMxMindFox crateは「YAGNI」として不採用に。

戦国SIMの実走で、MxBSの上に乗る薄い層の具体的な姿が見えた。

### 4.2 ゲーム非依存のパート（MindFox候補）

以下はsengoku-demoのmemory.rs / engine.rsに実装されているが、戦国SIM固有ではない。

#### A. Mood算出（memory.rs）

```rust
pub fn compute_mood(recent_features: &[[u8; 16]]) -> Mood
pub fn get_agent_mood(mxbs, reg, slug, turn) -> Mood
```

因子ベクトルの集計→4指標への変換。因子のインデックスはプリセットに依存するが、「軍事系→aggression」「脅威系→desperation」というカテゴリマッピングのパターンは汎用的。

実装注: `get_agent_mood` 内部のMxBS searchでは、設計書の `reg.groups_for()` が存在しなかったため `reg.bit()` で代替。単一エージェントでは同等の結果。

プリセットJSONにカテゴリ情報を追加すれば、Mood算出をプリセット駆動にできる:

```json
{
  "axes": [...],
  "mood_mapping": {
    "aggression": [0, 3, 14],
    "desperation": [10, 11],
    "desperation_inverted": [13],
    "confidence": [3, 13, 8],
    "diplomacy": [4, 6],
    "diplomacy_inverted": [5]
  }
}
```

#### B. 対エージェント信頼度（memory.rs）

```rust
pub fn compute_diplomacy_toward(mxbs, reg, agent, counterpart, turn) -> f32
```

特定の相手に関する記憶セル（fromフィルタ）の外交系因子を集計。戦国SIMでは未発火だが、(planned demo #5)や(planned demo #4)では中核機能になる。

#### C. Mood→閾値補正（engine.rs）

```rust
pub fn should_attack_target(personality, troops, target, passes, &mood) -> bool
```

Moodの数値を何らかの判断閾値に注入するパターン。攻撃閾値だけでなく、交渉成功率、情報公開判断、リスク許容度など、あらゆるゲーム判断に応用可能。

### 4.3 ゲーム固有のパート（MindFox候補外）

| パート | 理由 |
|---|---|
| EventType → features マッピング | ゲームのイベント体系に依存 |
| 強制ロジック（確殺・タダ取り等） | 戦国SIM固有のゲームルール |
| プロンプト構築 | LLMモデル・言語・ゲーム世界観に依存 |
| 戦闘計算・経済計算 | 完全にゲーム固有 |

### 4.4 切り出しの方針

現時点では切り出しを急がない。

```
現状:
  MxBS crate（34テスト）
    + pub mod agents（AgentRegistry）
    + pub mod preset（Preset / scoring_prompt / parse_scores）
  sengoku-demo（32テスト）
    memory.rs に compute_mood / compute_diplomacy_toward

次のデモで:
  別ジャンルのゲーム（(planned demo #4) or (planned demo #5)）を作る
  → memory.rs の Mood系関数を「コピーして使いたい」衝動が生まれる
  → その時点で MindFox crate として切り出す
  → 切り出し対象は「2つ以上のゲームで実際に使った関数」のみ
```

「2つのゲームで使った」が切り出しのトリガー。1つだけでは早すぎる。

### 4.5 MindFox crateの想定API（将来）

```rust
// プリセット駆動のMood算出
let mood = mindfox::compute_mood(
    &recent_features,
    &preset.mood_mapping,  // プリセットJSONから読み込み
);

// 対エージェント信頼度
let trust = mindfox::compute_trust_toward(
    mxbs, reg,
    "oda", "tokugawa",
    turn,
    &preset.mood_mapping,
);

// Mood→任意の判断閾値への注入（ヘルパー）
let adjusted = mindfox::adjust_threshold(
    base_threshold,
    &mood,
    &MoodWeights { aggression: 0.8, desperation: 0.6, confidence: 0.4 },
);
```

旧MindFox specのProvider pattern / TurnEngine / ActionContext は不採用。
実態は関数3つ程度の薄いユーティリティcrate。

### 4.6 旧MindFox specとの関係

| 旧MindFox spec（v0.2） | 戦国SIM実走後の認識 |
|---|---|
| 記憶の自動配線がコアバリュー | → MxBS AgentRegistryの store_public/private で十分 |
| Provider pattern（trait） | → ゲーム側の関数呼び出しで十分。traitは過剰 |
| TurnEngine（順番管理） | → forループで十分 |
| ActionContext（構造化コンテキスト） | → プロンプト文字列で十分（e2b相手では構造化の意味なし） |
| Publication Phase（新聞生成） | → ゲーム固有。戦国SIMには不要だった |
| 「薄いけど、ないと地獄」 | → ✅ これは正しかった。ただし「薄い」の正体はMood関数群 |

---

## 5. 総括

### 5.1 戦国SIMデモが証明したこと

1. **MxBSの因子ベクトル（16バイト）はゲームの記憶管理に十分。** Cosine分離性能も検索精度もembedding不要で成立する
2. **記憶はNPC行動を変化させられる。** Moodシステムにより、因子ベクトルの蓄積が攻撃閾値を動的に変え、キャラクターアークが自然発生した
3. **LLMは記憶活用に不要。** Mood算出はRustコード内のベクトル集計で完結。e2bでもランダムでも効く
4. **MxBS crateは正しく設計されている。** 薄いストアとして、ホスト側の変更だけで記憶の活用が実現できた
5. **MindFoxの正体はMood関数群。** 旧specの大半（Provider / TurnEngine / ActionContext）は不要だった

### 5.2 次のステップ

別ジャンルのデモ（(planned demo #4)推奨: 対人信頼度が活きる）を作り、compute_mood / compute_diplomacy_toward を再利用する体験を経てから、MindFox crateとして切り出す。

---

*Generated by エルマー🦊 — 2026-04-28*
