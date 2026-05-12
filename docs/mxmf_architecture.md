# MxMindFox — Architecture & Specification

**Multi-Agent Mood & Decision Layer on MxBS**

> Version: 0.1.0 (draft) | Date: 2026-05-02
> Authors: エルマー🦊 + マスター
> Position: MxBS の上に乗る薄いユーティリティ crate（5モジュール、~800行）

署名: 2026-05-02 Kikyujin - Mahito KIDA

---

## 1. 概要

MxMindFox は MxBS の記憶セルから **Mood（気分）** を計算し、それを使って **判断補正・確率的判定・複数候補サンプリング** を提供する薄い層。

### 1.1 設計方針

| 方針 | 説明 |
|---|---|
| **MxBS には触らない** | MxBS は決定論的な高速エンジンとして純粋を保つ。乱数・確率性・補正は全てこの層 |
| **プリセット駆動** | Mood の軸定義はゲーム側 JSON。MxMindFox は軸名を知らない |
| **5モジュール独立** | mood / diplomacy / threshold / decision / ffi は相互依存最小 |
| **C bindings 標準装備** | Unity / Unreal / Godot から P/Invoke で利用可能 |
| **薄さ最優先** | 全体 ~800行。ロジックを抱え込まず、ヘルパー集として振る舞う |

### 1.2 レイヤー構造

```
┌─────────────────────────────────────────────┐
│  Game (Unity / pageone / sengoku / oyatsu)  │
│  ターンループ・LLM呼び出し・UI               │
├─────────────────────────────────────────────┤
│  MxMindFox                                   │
│  Mood / Decision / Diplomacy / Threshold    │
│  ~800行 + C bindings                        │
├─────────────────────────────────────────────┤
│  MxBS                                       │
│  記憶エンジン（決定論的・高速）              │
│  store / search / reinforce / dream         │
└─────────────────────────────────────────────┘
```

### 1.3 既存3デモから抽出された共通パターン

| パターン | 戦国SIM | おやつ | ページワン | MxMindFox 提供API |
|---|---|---|---|---|
| 直近記憶から気分を計算 | aggression（覇気） | suspicion/anxiety/confidence/cooperation | （未実装） | `compute_mood` |
| 相手別の信頼度を計算 | 未発火 | 中核機能 | — | `compute_diplomacy_toward` |
| 気分で閾値を動かす | 攻撃閾値補正 | — | — | `adjust_threshold` |
| 確率的判定（揺らぎ） | — | — | （新規追加） | `decision::remember` |
| 複数候補サンプリング | — | （潜在） | — | `decision::sample` |

---

## 2. モジュール構成

```
mxmindfox/
├── Cargo.toml
├── src/
│   ├── lib.rs          # 公開API集約 + 再エクスポート
│   ├── error.rs        # MxmfError
│   ├── mood.rs         # Mood / MoodPreset / MoodAxis / compute_mood
│   ├── diplomacy.rs    # compute_diplomacy_toward
│   ├── threshold.rs    # ThresholdRule / adjust_threshold
│   ├── decision.rs     # decision::remember / decision::sample
│   └── ffi.rs          # C bindings（cdylib）
├── tests/
│   ├── mood_test.rs
│   ├── diplomacy_test.rs
│   ├── threshold_test.rs
│   ├── decision_test.rs
│   └── ffi_test.rs
└── python/
    ├── mxmindfox_bridge.py
    └── test_bridge.py
```

### 2.1 依存関係

```toml
[dependencies]
mxbs = { path = "../mxbs" }       # Cell 型を読む
serde = { version = "1", features = ["derive"] }
serde_json = "1"
rand = "0.8"
thiserror = "1"

[dev-dependencies]
tempfile = "3"
```

MxMindFox から MxBS への依存は **読むだけ**。MxBS 側は MxMindFox を一切知らない。

---

## 3. mood モジュール

### 3.1 Mood 構造体

プリセット駆動。固定フィールドは持たない。

```rust
use std::collections::HashMap;

#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct Mood {
    pub axes: HashMap<String, f32>,
}

impl Mood {
    pub fn new() -> Self { Self::default() }

    pub fn get(&self, axis: &str) -> Option<f32> {
        self.axes.get(axis).copied()
    }

    pub fn get_or(&self, axis: &str, default: f32) -> f32 {
        self.axes.get(axis).copied().unwrap_or(default)
    }

    pub fn set(&mut self, axis: &str, value: f32) {
        self.axes.insert(axis.to_string(), value);
    }

    pub fn from_baseline(baseline: &HashMap<String, f32>) -> Self {
        Self { axes: baseline.clone() }
    }
}
```

### 3.2 MoodPreset / MoodAxis

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct MoodAxis {
    pub name: String,
    /// MxBS 因子インデックス（0..16）。この軸を + 方向に動かす因子
    pub positive_factors: Vec<usize>,
    /// この軸を - 方向に動かす因子
    pub negative_factors: Vec<usize>,
    /// archetype に baseline がない場合の初期値
    pub default_value: f32,
    /// クランプ範囲（例: (0.0, 1.0) や (-1.0, 1.0)）
    pub clamp_min: f32,
    pub clamp_max: f32,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct MoodPreset {
    pub name: String,
    pub version: String,
    pub axes: Vec<MoodAxis>,
    /// archetype 名 → 軸名 → ベースライン値
    pub archetype_baselines: HashMap<String, HashMap<String, f32>>,
}

impl MoodPreset {
    pub fn from_json(json: &str) -> Result<Self, MxmfError>;
    pub fn to_json(&self) -> Result<String, MxmfError>;
    pub fn axis_names(&self) -> Vec<&str>;
    pub fn baseline_for(&self, archetype: &str) -> Option<&HashMap<String, f32>>;
}
```

### 3.3 compute_mood

```rust
/// 直近記憶セルから Mood を計算する。
///
/// アルゴリズム:
/// 1. archetype があれば baseline をロード、なければ default_value で各軸初期化
/// 2. cells の features を軸ごとに集計（u8 → 0.0..=1.0 に正規化）
/// 3. 各軸 = baseline + (Σ pos − Σ neg) / cells.len() / 255.0
/// 4. (clamp_min, clamp_max) にクランプ
///
/// cells が空の場合は archetype baseline（or default）をそのまま返す。
pub fn compute_mood(
    cells: &[mxbs::Cell],
    preset: &MoodPreset,
    archetype: Option<&str>,
) -> Mood;
```

#### 集計式（疑似コード）

```
for each axis in preset.axes:
    base = archetype_baseline[axis.name] or axis.default_value

    if cells.empty():
        mood[axis.name] = base
        continue

    sum_pos = 0
    sum_neg = 0
    for cell in cells:
        for i in axis.positive_factors:
            sum_pos += cell.features[i]
        for i in axis.negative_factors:
            sum_neg += cell.features[i]

    delta = (sum_pos - sum_neg) / cells.len() / 255.0
    value = clamp(base + delta, axis.clamp_min, axis.clamp_max)
    mood[axis.name] = value
```

**重要**: cells のフィルタリング（自分について / 相手について / 直近 N 件など）は**呼び出し側の責務**。MxMindFox は受け取った cells をそのまま集計する。

---

## 4. diplomacy モジュール

### 4.1 compute_diplomacy_toward

特定の相手に関する記憶セルから「信頼度」を計算する薄いラッパー。

```rust
/// 特定相手に関する記憶セルから信頼度（trust軸）を返す。
///
/// 内部的には compute_mood を呼び、preset の "trust" 軸を読むだけ。
/// preset に "trust" 軸がなければ 0.0 を返す。
///
/// `cells_about_counterpart` は呼び出し側が `from = counterpart_id` などで
/// フィルタした結果を渡す。
pub fn compute_diplomacy_toward(
    cells_about_counterpart: &[mxbs::Cell],
    preset: &MoodPreset,
    archetype: Option<&str>,
) -> f32;
```

### 4.2 設計判断

おやつデモの仕様では「特定相手に関する from フィルタ済みセルから外交因子を集計」となっている。これを **compute_mood の特殊ケース**として実装する：

- 軸名 `"trust"` を preset で定義しておく
- `compute_diplomacy_toward` は `compute_mood(...).get_or("trust", 0.0)` の薄いラッパー

これにより、ゲーム側は "trust" 以外の軸（"hostility" や "intimacy"）も同じ仕組みで使える。

---

## 5. threshold モジュール

### 5.1 ThresholdRule / adjust_threshold

戦国SIM の覇気パッチ（aggression mood が高いと攻撃閾値が下がる）を一般化する。

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ThresholdRule {
    /// 参照する mood 軸名
    pub mood_axis: String,
    /// この軸の値に掛ける係数。負なら閾値が下がる方向
    pub coefficient: f32,
}

/// 基本閾値を mood で補正する。
///
/// 計算式:
///   adjusted = base_threshold + Σ (mood[rule.mood_axis] * rule.coefficient)
///
/// mood に該当軸がなければ 0 として扱う。
pub fn adjust_threshold(
    base_threshold: f32,
    mood: &Mood,
    rules: &[ThresholdRule],
) -> f32;
```

### 5.2 戦国SIM の覇気パッチ移植例

**旧（ハードコード）:**
```rust
let attack_threshold = match personality {
    "warrior" => 0.4,     // 攻撃しやすい
    "tactician" => 0.6,
    "defensive" => 0.7,   // 攻撃しにくい
};
```

**新（MxMindFox 経由）:**
```rust
// preset.json 内
// archetype_baselines:
//   warrior:    { aggression: 0.8 }
//   tactician:  { aggression: 0.5 }
//   defensive:  { aggression: 0.3 }
//
// rules:
//   [{ mood_axis: "aggression", coefficient: -0.3 }]
//
// → warrior:    0.6 + 0.8 * (-0.3) = 0.36（攻撃しやすい）
//   defensive: 0.6 + 0.3 * (-0.3) = 0.51（攻撃しにくい）

let mood = compute_mood(&recent_cells, &preset, Some(personality));
let attack_threshold = adjust_threshold(0.6, &mood, &rules);
```

---

## 6. decision モジュール

### 6.1 設計

LLM の temperature 概念を MxBS の判定層に持ち込む。Mood に依存しない**純粋ヘルパー**。

```rust
pub mod decision {
    use rand::Rng;

    /// Bernoulli 判定（hit/miss を sigmoid で確率化）
    ///
    /// T = 0.0  → ステップ関数（決定論、score >= threshold で true）
    /// T > 0.0  → sigmoid((score - threshold) / T) で確率化
    pub fn remember(
        score: f32,
        threshold: f32,
        temperature: f32,
        rng: &mut impl Rng,
    ) -> bool {
        if temperature <= 0.0 {
            return score >= threshold;
        }
        let logit = (score - threshold) / temperature;
        let p = 1.0 / (1.0 + (-logit).exp());
        rng.gen::<f32>() < p
    }

    /// Multinomial サンプリング（softmax with temperature）
    ///
    /// T = 0.0 → argmax（決定論）
    /// T > 0.0 → softmax(scores / T) からサンプリング
    ///
    /// candidates が空なら None。
    pub fn sample<'a, T>(
        candidates: &'a [(T, f32)],
        temperature: f32,
        rng: &mut impl Rng,
    ) -> Option<&'a T>;
}
```

### 6.2 ページワンへの適用例

```python
# 旧（決定論的）
if results[0].effective_score >= THRESHOLD:
    return True  # 宣言する

# 新（temperature付き）
return decision_remember(
    score=results[0].effective_score,
    threshold=0.30,
    temperature=mood.get("temperature") or 0.0,
    seed=rng_seed,
)
```

### 6.3 数式の正確な定義

**remember:**

```
if T == 0:
    return score >= threshold

p = 1 / (1 + exp(-(score - threshold) / T))
return Uniform(0, 1) < p
```

**sample:**

```
if T == 0:
    return argmax(candidates by score)

# numerical stability: subtract max before exp
scaled[i] = scores[i] / T
m = max(scaled)
exps[i] = exp(scaled[i] - m)
probs[i] = exps[i] / sum(exps)

# inverse CDF sampling
r = Uniform(0, 1)
return candidates[first i where cumsum(probs)[i] >= r]
```

### 6.4 seed 管理

`rng: &mut impl Rng` を取る設計にすることで、ゲーム側が seed 管理を握る。  
キャンペーン全体で `StdRng::seed_from_u64(42)` を作って使い回せば、再現性ある A/B テストが可能。

---

## 7. C bindings (ffi モジュール)

### 7.1 公開する関数

ハンドルベース。MxBS の ffi.rs と同じパターン（serde_json 経由でJSON渡し）。

```c
// ── MoodPreset ──
void* mxmf_preset_load_json(const char* json);          // returns handle or NULL
void  mxmf_preset_free(void* preset);
char* mxmf_preset_to_json(const void* preset);          // caller frees with mxmf_str_free

// ── compute_mood ──
// cells_json: MxBS Cell の配列を JSON で渡す
// archetype: NULL 可
// returns: Mood JSON 文字列（caller frees）
char* mxmf_compute_mood(
    const void* preset,
    const char* cells_json,
    const char* archetype  // nullable
);

// ── compute_diplomacy_toward ──
float mxmf_compute_diplomacy_toward(
    const void* preset,
    const char* cells_json,
    const char* archetype  // nullable
);

// ── adjust_threshold ──
// mood_json: Mood の JSON
// rules_json: ThresholdRule[] の JSON
float mxmf_adjust_threshold(
    float base_threshold,
    const char* mood_json,
    const char* rules_json
);

// ── decision::remember ──
// seed: u64 seed for SmallRng
// returns: 0 or 1
int mxmf_decision_remember(
    float score,
    float threshold,
    float temperature,
    unsigned long long seed
);

// ── decision::sample ──
// candidates_json: [{"value": "...", "score": 0.5}, ...]
// returns: 選ばれたインデックス（負なら error）
int mxmf_decision_sample(
    const char* candidates_json,
    float temperature,
    unsigned long long seed
);

// ── 文字列解放 ──
void mxmf_str_free(char* s);

// ── ライブラリバージョン ──
const char* mxmf_version(void);
```

### 7.2 注意

- `seed` を引数に取る形にすることで、Rust 側の `&mut Rng` を C API では `u64` で受ける
- 各呼び出しで `SmallRng::seed_from_u64(seed)` を都度作る → 同じ seed なら同じ結果（テスト容易）
- ストリーム的に乱数を消費したい場合は seed を `seed.wrapping_add(1)` で更新する運用

---

## 8. Python ctypes ブリッジ

### 8.1 mxmindfox_bridge.py

```python
import ctypes
import json
from pathlib import Path

class MxMindFox:
    def __init__(self, lib_path: str = "libmxmindfox.dylib"):
        self.lib = ctypes.CDLL(lib_path)
        self._setup_signatures()

    def _setup_signatures(self):
        self.lib.mxmf_preset_load_json.argtypes = [ctypes.c_char_p]
        self.lib.mxmf_preset_load_json.restype = ctypes.c_void_p

        self.lib.mxmf_compute_mood.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p
        ]
        self.lib.mxmf_compute_mood.restype = ctypes.c_void_p  # 文字列ポインタ

        self.lib.mxmf_decision_remember.argtypes = [
            ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_uint64
        ]
        self.lib.mxmf_decision_remember.restype = ctypes.c_int
        # ...

    def load_preset(self, preset_dict: dict) -> "PresetHandle":
        json_bytes = json.dumps(preset_dict).encode()
        handle = self.lib.mxmf_preset_load_json(json_bytes)
        if not handle:
            raise RuntimeError("preset load failed")
        return PresetHandle(self, handle)

    def compute_mood(
        self, preset: "PresetHandle", cells: list[dict], archetype: str | None
    ) -> dict:
        cells_json = json.dumps(cells).encode()
        arch = archetype.encode() if archetype else None
        ptr = self.lib.mxmf_compute_mood(preset.handle, cells_json, arch)
        try:
            mood_json = ctypes.string_at(ptr).decode()
            return json.loads(mood_json)
        finally:
            self.lib.mxmf_str_free(ptr)

    def decision_remember(
        self, score: float, threshold: float, temperature: float, seed: int
    ) -> bool:
        return self.lib.mxmf_decision_remember(
            score, threshold, temperature, seed
        ) == 1
```

### 8.2 利用例（pageone）

```python
mxmf = MxMindFox("./libmxmindfox.dylib")
preset = mxmf.load_preset(json.load(open("pageone_mood.json")))

# 各ターン
mood = mxmf.compute_mood(preset, recent_cells, archetype="impulsive")
remembered = mxmf.decision_remember(
    score=eff_score,
    threshold=0.30,
    temperature=mood.get("axes", {}).get("temperature", 0.0),
    seed=turn_number,
)
```

---

## 9. プリセット設計（ゲーム側 JSON）

### 9.1 pageone_mood.json（最小例）

```json
{
  "name": "pageone",
  "version": "1.0",
  "axes": [
    {
      "name": "temperature",
      "positive_factors": [9],
      "negative_factors": [],
      "default_value": 0.05,
      "clamp_min": 0.0,
      "clamp_max": 0.5
    }
  ],
  "archetype_baselines": {
    "analyst":    {"temperature": 0.02},
    "observer":   {"temperature": 0.03},
    "impulsive":  {"temperature": 0.20},
    "contrarian": {"temperature": 0.15}
  }
}
```

ページワンは1軸だけのミニマル設計。  
record されるセルが1個（ページワンルール）しかないので、実質的に **archetype baseline** だけが効く。

### 9.2 oyatsu_mood.json

```json
{
  "name": "oyatsu",
  "version": "1.0",
  "axes": [
    {"name": "suspicion",   "positive_factors": [0, 14],     "negative_factors": [2],      "default_value": 0.5,  "clamp_min": 0.0, "clamp_max": 1.0},
    {"name": "anxiety",     "positive_factors": [1, 4, 6],   "negative_factors": [5],      "default_value": 0.3,  "clamp_min": 0.0, "clamp_max": 1.0},
    {"name": "confidence",  "positive_factors": [5, 12],     "negative_factors": [4, 11],  "default_value": 0.5,  "clamp_min": 0.0, "clamp_max": 1.0},
    {"name": "cooperation", "positive_factors": [2, 9, 10],  "negative_factors": [8, 11],  "default_value": 0.5,  "clamp_min": 0.0, "clamp_max": 1.0},
    {"name": "trust",       "positive_factors": [2, 9, 10],  "negative_factors": [7, 8],   "default_value": 0.0,  "clamp_min": -1.0, "clamp_max": 1.0},
    {"name": "temperature", "positive_factors": [4],          "negative_factors": [5],      "default_value": 0.05, "clamp_min": 0.0, "clamp_max": 0.5}
  ],
  "archetype_baselines": {
    "analyst":    {"temperature": 0.02, "suspicion": 0.5, "confidence": 0.7},
    "contrarian": {"temperature": 0.15, "suspicion": 0.7, "cooperation": 0.3},
    "impulsive":  {"temperature": 0.20, "suspicion": 0.4, "anxiety": 0.5},
    "observer":   {"temperature": 0.03, "suspicion": 0.5, "confidence": 0.6},
    "mediator":   {"temperature": 0.05, "cooperation": 0.7, "trust": 0.3},
    "compliant":  {"temperature": 0.05, "cooperation": 0.6, "anxiety": 0.4}
  }
}
```

おやつデモは多軸構成。**trust 軸**を持つので `compute_diplomacy_toward` が機能する。

### 9.3 sengoku_mood.json

```json
{
  "name": "sengoku",
  "version": "1.0",
  "axes": [
    {"name": "aggression",  "positive_factors": [3, 5, 7], "negative_factors": [1, 9], "default_value": 0.5, "clamp_min": 0.0, "clamp_max": 1.0},
    {"name": "temperature", "positive_factors": [],         "negative_factors": [],     "default_value": 0.05, "clamp_min": 0.0, "clamp_max": 0.5}
  ],
  "archetype_baselines": {
    "warrior":   {"aggression": 0.8, "temperature": 0.10},
    "tactician": {"aggression": 0.5, "temperature": 0.05},
    "defensive": {"aggression": 0.3, "temperature": 0.05}
  }
}
```

※ `positive_factors` の具体的なインデックスは戦国SIM の preset 仕様確認時に確定する。

---

## 10. 3デモへの統合パターン

### 10.1 pageone v0.4

```python
# memory.py
from mxmindfox_bridge import MxMindFox

mxmf = MxMindFox()
mood_preset = mxmf.load_preset(json.load(open("pageone_mood.json")))

def check_pageone_declaration(mxbs, agent, current_turn, rng_seed):
    results = mxbs.search(
        query_features=QUERY_PAGEONE_CHECK,
        searcher=agent.id,
        searcher_groups=agent.bit,
        turn=current_turn,
        limit=1,
    )
    if not results:
        return False

    # archetype baseline だけで temperature 取得
    mood = mxmf.compute_mood(mood_preset, [], archetype=agent.archetype)
    temperature = mood["axes"].get("temperature", 0.0)

    return mxmf.decision_remember(
        score=results[0]["effective_score"],
        threshold=0.30,
        temperature=temperature,
        seed=rng_seed,
    )
```

**最小差分**: 既存 hit 判定を `decision_remember` で置き換えるだけ。

### 10.2 sengoku v2

```rust
// 旧覇気パッチを削除
// let attack_threshold = match personality { "warrior" => 0.4, ... };

// 新方式
let recent = mxbs.search(/* 最近の自国記憶 */)?;
let mood = compute_mood(&recent, &preset, Some(personality));
let attack_threshold = adjust_threshold(
    0.6,
    &mood,
    &[ThresholdRule { mood_axis: "aggression".into(), coefficient: -0.3 }],
);
```

### 10.3 oyatsu v2

```python
# 各キャラの mood と相手別 trust を計算してプロンプトに反映
mood = mxmf.compute_mood(oyatsu_preset, recent_cells, archetype=agent.archetype)
trust_to_speaker = mxmf.compute_diplomacy_toward(
    oyatsu_preset, cells_about(speaker_id), archetype=agent.archetype,
)

prompt = f"""
あなたは {agent.name}（{agent.archetype}）です。
気分: 疑惑={mood['suspicion']:.2f}、不安={mood['anxiety']:.2f}、自信={mood['confidence']:.2f}
{speaker.name} への信頼: {trust_to_speaker:+.2f}
...
"""
```

---

## 11. テスト計画

### 11.1 ユニットテスト（Rust）

| ファイル | 内容 | 想定件数 |
|---|---|---|
| `mood_test.rs` | Mood get/set、MoodPreset JSON ラウンドトリップ、compute_mood の境界（cells 空 / 全因子0 / クランプ） | 10 |
| `diplomacy_test.rs` | trust 軸定義あり/なし、cells 空、compute_mood との整合 | 5 |
| `threshold_test.rs` | 単一ルール、複数ルール、軸欠損、係数 0 | 5 |
| `decision_test.rs` | remember T=0 決定論、T>0 で確率分布の偏り、sample T=0 argmax、sample T>0 で頻度収束 | 10 |
| `ffi_test.rs` | NULL ハンドル、JSON パース失敗、文字列メモリ管理 | 8 |

合計 ~38 テスト。

### 11.2 統合テスト

| 名前 | 内容 |
|---|---|
| `pageone_v0.4` | 50ゲーム × 3条件（T=0 / archetype-T / 全員 T=0.1）の忘却率比較 |
| `sengoku_v2` | 既存 16 テスト全パス維持 + 覇気パッチ削除確認 |
| `oyatsu_v2` | 3ゲームキャンペーン完走 + compute_diplomacy_toward 発火確認 |

---

## 12. 検証期待値

### 12.1 pageone v0.4 期待結果

```
🎯 ページワン忘却率（50ゲーム、再注入+HL=8）

  キャラ    | price | T    | 忘却率（v0.3）→ 忘却率（v0.4）
  ----------+-------+------+--------------------------------
  スミレ    |  220  | 0.02 |   0.0% →    0〜2%   （ほぼ不変）
  ヴェリ    |  200  | 0.03 |   0.0% →    0〜3%
  エルマー  |  170  | 0.05 |   5.0% →    5〜10%
  ティル    |   80  | 0.20 | 100.0% →   60〜80%   ← ✨揺らぎ出現
  ノクちん  |   70  | 0.15 | 100.0% →   75〜90%   ← ✨揺らぎ出現

🎲 ノクちんが奇跡的に覚えてた回数: 5〜12 / 50 ゲーム
🎲 ティルがバエ忘れて冴えた回数: 10〜20 / 50 ゲーム
```

実測値で v0.3 仕様書を上書きする。

### 12.2 sengoku v2 期待結果

- 既存テスト 16/16 パス維持
- 覇気パッチ（強制ロジック）コード削除（~20行）→ MxMindFox 経由に置き換え
- ゲーム挙動が定性的に同等（攻撃発生頻度が大きく変わらない）

### 12.3 oyatsu v2 期待結果

- 3ゲームキャンペーン完走
- ハズレ指名 → cooperation 低下 → 証言劣化のループが発生
- compute_diplomacy_toward が trust 軸を返し、プロンプトに反映される

---

## 13. ちびエルマー発注書（段階分割）

| Phase | タスク | 成果物 | 依存 |
|---|---|---|---|
| 1 | crate 初期化・Cargo.toml・lib.rs スケルトン・error.rs | `mxmindfox/` ディレクトリ | — |
| 2 | mood.rs（Mood + MoodPreset + MoodAxis + compute_mood） | mood_test.rs 10件パス | 1 |
| 3 | diplomacy.rs（compute_diplomacy_toward） | diplomacy_test.rs 5件パス | 2 |
| 4 | threshold.rs（ThresholdRule + adjust_threshold） | threshold_test.rs 5件パス | 2 |
| 5 | decision.rs（remember + sample） | decision_test.rs 10件パス | 1 |
| 6 | ffi.rs（C bindings、cdylib ビルド設定） | ffi_test.rs 8件パス + libmxmindfox.dylib | 2-5 |
| 7 | python/mxmindfox_bridge.py + test_bridge.py | スモークテスト全パス | 6 |
| 8 | pageone v0.4 移行（pageone_mood.json + memory.py 改修） | 50ゲーム × 3条件の比較ログ | 7 |
| 9 | sengoku v2 移行（sengoku_mood.json + 覇気パッチ削除） | 既存 16 テスト全パス維持 | 6 |
| 10 | oyatsu v2 移行（oyatsu_mood.json + memory.py 改修） | 3ゲームキャンペーン完走 | 7 |
| 11 | mxbs_roadmap.md 更新（Phase 3 完了マーク + 実測値追記） | ロードマップ v1.4 | 8-10 |

### 13.1 Phase 1-7 が MxMindFox 本体実装

ここまでで MxMindFox crate は完成。テスト ~38 件が緑になる。

### 13.2 Phase 8-10 が 3デモ移行

並列実行可能（依存なし）。ただしマスター確認が入るのでシーケンシャルに進める方が安全。

### 13.3 Phase 11 でロードマップ更新

ちびエルマーが書いた実測値をエルマー🦊+マスターでレビューしてから merge。

---

## 14. 設計判断の記録

### 14.1 Mood をプリセット駆動にした理由（2026-05-02）

- **決定**: Mood は固定 struct ではなく `HashMap<String, f32>` + プリセット定義
- **理由**: 戦国SIM（aggression）/ おやつ（suspicion等4軸）/ ページワン（temperature）/ (planned demo #5)（JUWA/MUKA）で軸が全て違う。固定 struct だと毎ゲーム crate 改修が必要になる
- **帰結**: MxMindFox 自体は軸名を知らない純粋エンジン。MxBS の Preset 設計と統一の流儀

### 14.2 decision モジュールを Mood 非依存にした理由（2026-05-02）

- **決定**: `decision::remember` / `decision::sample` は temperature を直接 f32 で受ける
- **理由**: temperature は Mood の一軸として使う運用が主だが、Mood なしでも単純なシミュレーションで使えるべき。Mood に縛ると単体テストも書きにくい
- **帰結**: ゲーム側は `mood.get_or("temperature", 0.0)` を抽出して渡す薄い橋渡し

### 14.3 archetype プリセットを MxMindFox に固定セットしない理由（2026-05-02）

- **決定**: archetype 名は文字列として preset.archetype_baselines が持つ。MxMindFox crate に enum や固定セットは入れない
- **理由**: ゲームごとに必要な archetype が違う（おやつの compliant はページワンには不要、戦国SIMの warrior はおやつには不要）
- **帰結**: MxBS Preset と同様、MxMindFox も「設定ファイル駆動」で振る舞う。バイナリ自体はゲーム非依存

### 14.4 MxBS には変更を入れない（2026-05-02）

- **決定**: MxBS の cells テーブル・search API・スコアリングロジックには一切手を入れない
- **理由**: MxBS は決定論的な高速エンジンとして純粋を保つ。乱数・確率性は別レイヤの責務
- **帰結**: MxBS の 34 + 9 + 16 = ~60 テスト全件、影響なし

### 14.5 temperature を sigmoid で実装する理由（2026-05-02）

- **決定**: ページワンの hit/miss 判定は softmax sampling ではなく Bernoulli sampling（sigmoid）
- **理由**: ページワン宣言判定は1個のセルが閾値を超えるか否かの問題。複数候補からの選択ではない。LLM の temperature 概念は「分布の鋭さ」だが、Bernoulli の場合は sigmoid の傾きで表現するのが自然
- **帰結**: `decision::remember` は sigmoid、`decision::sample` は softmax。両者並立

---

## 15. 未決事項

| 項目 | 選択肢 | メモ |
|---|---|---|
| MoodPreset の version 互換 | バージョンチェック有 / 無 | 当面なし。preset.json 編集で運用 |
| compute_mood の集計方法 | 平均 / 加重平均 / decay 反映 | v0.1.0 は単純平均。後で必要なら追加 |
| sample の戻り値 | インデックス / 値の参照 | Rust API は `&T`、C API はインデックス |
| Unity C# wrapper | v0.1.0 で作るか後回しか | (planned demo #4) / (planned demo #5) 着手時でOK |
| seed の自動進行 | ライブラリで管理 / ホスト管理 | ホスト管理（再現性のため） |

---

## 16. ロードマップ位置

`mxbs_roadmap.md` の Phase 3 に対応。完了時に以下が更新される：

- Phase 3 「MxMindFox 切り出し」が ✅ 完了
- pageone v0.4 / sengoku v2 / oyatsu v2 の実測値追記
- preset_guide.md の材料が「MxMindFox プリセット例」分も増える
- Phase 4（検証作業）に進める

---

## 関連ドキュメント

| ドキュメント | 内容 |
|---|---|
| `mxbs_concept.md` | MxBS の概念 |
| `mxbs_spec.md` | MxBS の仕様 |
| `mxbs_api_reference.md` | MxBS の C API |
| `mxbs_roadmap.md` | 全体ロードマップ |
| `pageone_spec.md` | ページワンデモ仕様（v0.4 で本書を参照） |
| `oyatsu_spec.md` | おやつデモ仕様（v2 で本書を参照） |

---

*Document history*

| Date | Version | Author | Notes |
|---|---|---|---|
| 2026-05-02 | 0.1.0 | エルマー🦊 + マスター | 初版。MxBS とは別crateとして切り出し決定後の最初の仕様書 |
