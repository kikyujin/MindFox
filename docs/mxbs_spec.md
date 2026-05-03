# MxBS — Specification

**Factor-Vector Memory Management Middleware for Games**

> Version: 0.1.1 | Date: 2026-05-03
> Authors: エルマー🦊 + マスター
> Origin: xMBS Lite (Rust/bge-m3/sqlite-vec) → MxBS (u8×16 factor vector / SQLite only)

署名: 2026-05-03 Kikyujin - Mahito KIDA

---

## 1. 概要

MxBS（Multitapps Extended Brain System）は NPC やエージェントに「覚える・忘れる・思い出す」を与える組み込みライブラリ。
GM が定義した 16 因子空間で記憶を管理し、自然言語 embedding に頼らない。

### 1.1 設計方針

| 方針 | 説明 |
|---|---|
| **シングルファイル DB** | SQLite のみ。外部拡張なし |
| **因子ベクトル** | u8 × 16（16 bytes）。GM 定義のプリセットでスコアリング |
| **外部依存ゼロ** | ONNX / bge-m3 / sqlite-vec 全て不要 |
| **ゲームループ非干渉** | 2 フェーズ設計（生成 → 一括スコアリング）でターン間に処理 |
| **C バインディング** | cdylib 出力。Unity / Unreal / Godot から利用可能 |

### 1.2 xMBS Lite からの変更

| xMBS Lite | MxBS | 理由 |
|---|---|---|
| Embedder trait (f32 × 1024) | **廃止** | u8 × 16 因子ベクトルに置換 |
| VecStore trait (sqlite-vec) | **廃止** | アプリ側 cosine で全スキャン |
| `XmbsLite<E, V>` ジェネリクス | `MxBS` 非ジェネリック | trait 不要 |
| ONNX Runtime + bge-m3 同梱 | **廃止** | LLM スコアリングに置換 |
| Stage (Pending / Indexed) | features 全ゼロ / 非ゼロ | 同等の2段階遷移。set_features() で外部スコアリング結果を書き込む |
| `timestamp: f64` | `turn: u32` | ターンベースに統一 |
| `scene_id: u32` | **廃止** | MxMindFox 層に移動 |
| `price: u16` (0xFFFF=immortal) | `price: u8` (255=immortal) | 256 段階で十分 |
| `cell_embeddings` vec0 テーブル | **廃止** | features は cells テーブル内 BLOB |

### 1.3 xMBS Lite から継承

| 機能 | 説明 |
|---|---|
| セル構造 | text + メタデータ + ベクトルの三位一体 |
| アクセス制御 | UNIX mode (u16) + group bitflag (u64) |
| 忘却 | price × 時間減衰 |
| Dream | 埋もれた重要記憶の浮上 |
| Reinforce | importance 更新（w バイパス） |
| Update | group / mode / meta の事後変更（w チェック） |
| Inspire | ベクトル近傍検索 |
| プリセットセル保護 | mode=0o444 |
| セーブ/ロード | SQLite ファイルコピー |
| C bindings | 整数パラメータ中心、戻り値 JSON |
| 全 ID 整数型 | パフォーマンスと C バインディングの簡素化 |

### 1.4 スコープ外

以下は MxBS では扱わない。上位層（MxMindFox 等）の責務とする。

- スコアリング（LLM 呼び出し）— MxBS はスコアリング結果の features を受け取るだけ
- 要約生成
- キャラクター / エージェント管理
- ターン管理 / オーケストレーション
- LLM API 管理
- プリセット設計

---

## 2. セル (Cell)

セルは MxBS の最小記憶単位。

### 2.1 セルの構造

```rust
/// Factor vector dimension: 16 bytes fixed.
pub const FACTOR_DIM: usize = 16;

/// Maximum number of agents (group_bits is u64).
pub const MAX_AGENTS: usize = 64;

/// Immortal price: never decays.
pub const PRICE_IMMORTAL: u8 = 255;

pub struct Cell {
    // --- 識別 ---
    pub id: u64,                    // 自動採番の一意 ID

    // --- メタデータ ---
    pub owner: u32,                 // NPC/エージェント ID（= アクセス制御の owner）
    pub from: u32,                  // 情報ソース ID（発言者 / 取得元）
    pub turn: u32,                  // 生成されたターン番号

    // --- アクセス制御 ---
    pub group_bits: u64,            // グループ ビットフラグ（最大 64 エージェント）
    pub mode: u16,                  // 下位 12bit: UNIX パーミッション（例: 0o744）
                                    // 上位 4bit: ユーザー利用可能（システム未使用を保証）

    // --- 価値 ---
    pub price: u8,                  // 重要度（0〜254）。255 = 忘却しない（不滅）
    pub importance: f32,            // 動的スコア（可変、初期値 1.0）。reinforce で更新

    // --- 本体 ---
    pub text: String,               // セル本文

    // --- 因子ベクトル ---
    pub features: [u8; 16],         // GM 定義因子空間でのスコアリング結果。全ゼロ = 未スコアリング

    // --- 拡張 ---
    pub meta: String,               // JSON 文字列（フリーフィールド）
}
```

### 2.2 xMBS Lite との対応

| xMBS Lite フィールド | MxBS | 型 | 備考 |
|---|---|---|---|
| `cell_id: u64` | `id` | `u64` | 名前短縮 |
| `owner: u32` | `owner` | `u32` | 同一 |
| `from: u32` | `from` | `u32` | 同一 |
| `timestamp: f64` | `turn` | `u32` | ゲーム内秒 → ターン番号 |
| `scene_id: u32` | — | — | 廃止（MxMindFox 層） |
| `group: u64` | `group_bits` | `u64` | 名前明確化 |
| `mode: u16` | `mode` | `u16` | 同一 |
| `price: u16` | `price` | `u8` | 256 段階に縮小。255=immortal |
| `importance: f32` | `importance` | `f32` | 同一 |
| `stage: Stage` | features 全ゼロ判定 | — | Pending/Indexed → 未スコアリング/スコアリング済み |
| `text: String` | `text` | `String` | 同一 |
| — | `features` | `[u8; 16]` | 新規。因子ベクトル |
| `meta: String` | `meta` | `String` | 同一 |

### 2.3 フィールド補足

#### turn: ターン番号

xMBS Lite の `timestamp: f64`（ゲーム内秒）を `turn: u32`（ターン番号）に置換。
MxBS の 2 フェーズ設計はターン単位で動作するため、整数ターンの方が自然。

- 忘却計算の `elapsed` は `current_turn - cell.turn`（ターン差分）
- `half_life` の単位もターン数（デフォルト 8 ターン）
- 非ターンベースのゲームでも「フレーム番号」や「イベント番号」を turn として使える

#### features: 因子ベクトルと遅延スコアリング

u8 × 16 の固定長。GM が定義したプリセットの各軸に対するスコア（0〜255）。
**MxBS はスコアリングを行わない。** 外部（LLM / ルールエンジン）がスコアリングした結果を受け取って格納するだけ。

features が全ゼロ（`[0; 16]`）のセルは **「未スコアリング」** として扱う。
ベクトル検索（search / inspire）の対象外だが、turn ベースの時系列検索やテキスト部分一致検索の対象にはなる。

**遅延スコアリング**: LLM によるスコアリングはプアな GPU で数秒かかる場合がある。
そのため store() 時に features を省略（全ゼロで登録）し、後から `set_features()` で書き込むパターンを標準とする。
これは xMBS Lite の 2 ステージモデル（Pending → Indexed）と同じ構造。

```
store(text, features=[0;16])  ← Phase 1: テキストだけ先行登録
    ↓
get_unscored()                ← 未スコアリングセルを列挙
    ↓
LLM スコアリング（外部）      ← Phase 2: ターン間/ロード画面で実行
    ↓
set_features(id, features)    ← DB 更新、ベクトル検索可能に
```

features は **一方向遷移のみ許可**: 全ゼロ → 非ゼロ値。
一度スコアリング済みの features を上書きすることはできない（`set_features()` がエラーを返す）。
再スコアリングが必要な場合は新しいセルを作成する。

#### price: 0〜255

| 値 | 意味 |
|---|---|
| 0〜254 | 通常セル。値が高いほど忘れにくい |
| **255** | **不滅**（decay = 1.0、dream 対象外） |

#### mode の上位 4 ビット

xMBS Lite と同一。システムは使用しないことを保証。ゲーム側が自由に使える。

```
mode: u16
  bit 15-12: ユーザー利用可能（MxBS/MxMindFox ではビット 12 をエージェントマーカーに使用）
  bit 11-9:  予約（現在未使用）
  bit  8-6:  owner 権限 (rwx)
  bit  5-3:  group 権限 (rwx)
  bit  2-0:  other 権限 (rwx)
```

#### クロスプラットフォーム互換性

features は u8×16（バイト単位）、他フィールドは SQLite INTEGER 型経由で読み書きされるため、
DB ファイルは異なるアーキテクチャ間（aarch64 ↔ x86_64 等）で互換性を持つ。

### 2.4 immutable / mutable フィールド

xMBS Lite と同一の原則。

| フィールド | 可変性 | 備考 |
|---|---|---|
| `id` | immutable | 自動採番 |
| `owner` | immutable | |
| `from` | immutable | |
| `turn` | immutable | |
| `text` | immutable | 変更は新セル追加で対応 |
| `price` | immutable | |
| `features` | **one-way** | set_features(): 全ゼロ → 値のみ。スコアリング済みは不変 |
| `group_bits` | **mutable** (w) | update_group_bits() |
| `mode` | **mutable** (w) | update_mode() |
| `meta` | **mutable** (w) | update_meta() |
| `importance` | **mutable** (bypass) | reinforce() — w バイパス |

---

## 3. 因子ベクトルとコサイン類似度

### 3.1 因子ベクトル仕様

```
型:     u8 × 16（固定長）
サイズ: 16 bytes
値域:   各軸 0〜255
検索:   コサイン類似度
```

MxBS はスコアリング（因子ベクトルの生成）を行わない。
外部から `[u8; 16]` を受け取って格納する。
スコアリングの方法（LLM / ルールエンジン / 手動）は MxBS の関知外。

### 3.2 コサイン類似度

```rust
pub fn cosine_similarity(a: &[u8; 16], b: &[u8; 16]) -> f32 {
    let mut dot: u32 = 0;
    let mut norm_a: u32 = 0;
    let mut norm_b: u32 = 0;
    for i in 0..16 {
        let ai = a[i] as u32;
        let bi = b[i] as u32;
        dot += ai * bi;
        norm_a += ai * ai;
        norm_b += bi * bi;
    }
    if norm_a == 0 || norm_b == 0 {
        return 0.0;
    }
    dot as f32 / ((norm_a as f32).sqrt() * (norm_b as f32).sqrt())
}
```

u8 × 16 の dot product は 16 回の乗算 + 15 回の加算。
数千セルの全スキャンでもマイクロ秒オーダー。
sqlite-vec は不要。

### 3.3 全ゼロベクトルの扱い

`features = [0; 16]` は「未スコアリング」を意味する。
norm = 0 のためコサイン類似度は 0.0 を返す。
search() のベクトル検索結果には含まれないが、
turn ベースのクエリ（query なし検索）では返される。

---

## 4. アクセス制御

xMBS Lite §4 と同一の UNIX user/group モデル。

### 4.1 UNIX パーミッション

```
mode = 0o740
  7 = owner: read + write + execute(delete)
  4 = group: read only
  0 = other: no access

r (read)   = search / dream / inspire / get の対象になる
w (write)  = group_bits / mode / meta の事後変更を許可する
x (delete) = delete() を許可する
```

### 4.2 アクセス判定ロジック

xMBS Lite と同一。mode の 9 ビットを標準 UNIX 方式で解釈する。

```rust
fn check_read(cell: &Cell, viewer_id: u32, viewer_groups: u64) -> bool {
    let perm = if viewer_id == cell.owner {
        (cell.mode >> 6) & 0o7   // owner 権限
    } else if cell.group_bits & viewer_groups != 0 {
        (cell.mode >> 3) & 0o7   // group 権限
    } else {
        cell.mode & 0o7           // other 権限
    };
    perm & 0b100 != 0  // r ビット
}

fn can_write(cell: &Cell, requester: u32, req_groups: u64) -> bool {
    let perm = if requester == cell.owner {
        (cell.mode >> 6) & 0o7
    } else if cell.group_bits & req_groups != 0 {
        (cell.mode >> 3) & 0o7
    } else {
        cell.mode & 0o7
    };
    perm & 0b010 != 0  // w ビット
}
```

公開セル（全エージェントが読める）にするには `mode = 0o744` を使う。
other=4(r) により ACL チェックで全員に read が通る。
```

### 4.3 グループ定義（ビットフラグ）

xMBS Lite と同一。u64 ビットフラグ、最大 64 エージェント。

```rust
const GROUP_AGENT_0: u64 = 1 << 0;
const GROUP_AGENT_1: u64 = 1 << 1;
// ...
// エージェントの所属 = OR で結合
let agent_groups: u64 = GROUP_AGENT_0 | GROUP_AGENT_3;
```

### 4.4 プリセットセルの保護

mode=0o444 → 全員 read only。誰も write / delete 不可。
reinforce() のみ w バイパスで importance 更新可能。

---

## 5. 忘却

### 5.1 計算式

```
effective_score = cosine × importance × price_factor × decay

price_factor = price / 255.0

decay(Δt, half_life) = 0.5 ^ (Δt / half_life)
Δt = current_turn - cell.turn

effective_decay = decay ^ decay_factor
```

### 5.2 パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `half_life` | `u32` | `8` | 忘却の半減期（ターン数） |
| `decay_factor` | `f32` | `1.0` | 忘却強度調整 |
| `current_turn` | `u32` | — | 呼び出し側が毎回指定 |

| decay_factor | 効果 |
|---|---|
| `0.0` | 忘却無視（全件同等） |
| `1.0` | 通常の忘却 |
| `2.0` | 最近の記憶を強く優先 |

### 5.3 price = 255 (immortal)

`price = PRICE_IMMORTAL (255)` のセルは特殊:
- `decay = 1.0`（経過ターンに関係なく減衰しない）
- `price_factor = 1.0`
- Dream 結果から除外（buried_score = 0.0）

### 5.4 xMBS Lite との差異

| xMBS Lite | MxBS | 理由 |
|---|---|---|
| `half_life = base × (1 + price/100)` | `half_life` 固定（Config） | price は price_factor として直接スコアに反映。二重反映を避ける |
| `relevance = importance × decay / distance` | `effective = cosine × importance × price_factor × decay` | cosine（高い=類似）を使うため除算→乗算に変更 |
| `elapsed = now - timestamp`（秒） | `Δt = current_turn - turn`（ターン） | ターンベース |

**設計判断**: xMBS Lite では price が half_life に影響する間接的な仕組みだったが、
MxBS では price_factor としてスコアに直接乗算する方が直感的。
「price が高い = スコアが高い = 検索上位に来やすい」がそのまま成立する。

---

## 6. 検索 (Search)

### 6.1 API

```rust
let results = mem.search(query_features, viewer_id, viewer_groups)
    .current_turn(turn)         // 必須
    .decay_factor(1.0)          // 忘却の強度（デフォルト 1.0）
    .limit(5)                   // 取得件数（デフォルト 10）
    .owner(agent_id)            // owner でフィルタ（任意）
    .from(source_id)            // from でフィルタ（任意）
    .after_turn(3)              // このターン以降（任意）
    .before_turn(10)            // このターン以前（任意）
    .exec()?;
```

### 6.2 内部処理

```
1. 全セルを走査
2. ACL チェック（viewer の read 権限）
3. フィルタ条件（owner / from / after_turn / before_turn）を適用
4. features が全ゼロのセルをスキップ（未スコアリング）
5. cosine_similarity(query_features, cell.features) を計算
6. effective_score = cosine × importance × price_factor × decay を計算
7. effective_score 降順でソート
8. 上位 limit 件を返す
```

### 6.3 query_features なし検索

query_features に `None` / 全ゼロを渡した場合、ベクトル検索をスキップし、
turn 降順（新しい順）で ACL + フィルタ条件に合致するセルを返す。
この場合のスコアは `importance × price_factor × decay`。

### 6.4 SearchResult

```rust
pub struct SearchResult {
    pub id: u64,
    pub text: String,
    pub cosine: f32,              // コサイン類似度（0.0〜1.0）
    pub effective_score: f32,     // cosine × importance × price_factor × decay
    pub owner: u32,
    pub from: u32,
    pub turn: u32,
    pub price: u8,
    pub importance: f32,
    pub features: [u8; 16],
    pub meta: String,
}
```

---

## 7. ドリームプル (Dream)

xMBS Lite §7 と同一の設計。「忘却が進んでいるが価値の高い記憶」を掘り起こす。
LLM コストゼロ。

### 7.1 API

```rust
let dreams = mem.dream(viewer_id, viewer_groups)
    .current_turn(turn)         // 必須
    .limit(3)                   // デフォルト 3
    .exec()?;
```

### 7.2 buried_score

```rust
fn buried_score(price: u8, decay: f32, importance: f32) -> f32 {
    if price == PRICE_IMMORTAL {
        return 0.0;  // 不滅記憶は dream 対象外
    }
    let inv_decay = (1.0 / decay.max(1e-6)).min(1000.0);
    price as f32 * inv_decay * importance
}
```

buried_score 降順で上位 N 件を返す。

### 7.3 DreamResult

```rust
pub struct DreamResult {
    pub id: u64,
    pub text: String,
    pub buried_score: f32,
    pub price: u8,
    pub importance: f32,
    pub decay: f32,
    pub turn: u32,
    pub owner: u32,
    pub from: u32,
    pub features: [u8; 16],
    pub meta: String,
}
```

---

## 8. Importance 強化 (Reinforce)

xMBS Lite §8 と同一。

```rust
mem.reinforce(cell_id, 2.0)?;  // importance を 2.0 に更新
```

- importance: 0.0〜10.0 の範囲。範囲外はエラー
- **mode の w をバイパスする**（importance は動的スコアであり保護対象外）
- mode=0o444 のプリセットセルでも importance は更新可能

---

## 9. インスピレーション (Inspire)

xMBS Lite §9 と同一の概念。指定セルに類似する記憶を因子ベクトル近傍で返す。

### 9.1 API

```rust
let related = mem.inspire(cell_id)
    .limit(5)
    .viewer(viewer_id, viewer_groups)   // アクセス制御（任意）
    .exec()?;
```

### 9.2 内部処理

```
1. 指定セルの features を取得
2. 全セルとのコサイン類似度を計算（全スキャン）
3. 自分自身を除外
4. viewer 指定時は ACL フィルタ
5. features 全ゼロのセルをスキップ
6. cosine 降順で上位 N 件を返す
```

### 9.3 InspireResult

```rust
pub struct InspireResult {
    pub id: u64,
    pub text: String,
    pub cosine: f32,
    pub owner: u32,
    pub turn: u32,
    pub features: [u8; 16],
    pub meta: String,
}
```

---

## 10. セルフィールド更新 (Update)

xMBS Lite §10 と同一。write 権限 (w) チェック付き。

### 10.1 API

```rust
pub fn update_group_bits(&mut self, cell_id: u64, new_group_bits: u64,
                         requester: u32, req_groups: u64) -> Result<bool>;

pub fn update_mode(&mut self, cell_id: u64, new_mode: u16,
                   requester: u32, req_groups: u64) -> Result<bool>;

pub fn update_meta(&mut self, cell_id: u64, new_meta: &str,
                   requester: u32, req_groups: u64) -> Result<bool>;
```

成功なら `true`、権限不足なら `false`。

---

## 10.5. 遅延スコアリング (Deferred Scoring)

LLM スコアリングが遅い環境向け。store() 時に features を全ゼロで登録し、
後から set_features() で書き込む。

### 10.5.1 API

```rust
/// 未スコアリングセル（features 全ゼロ）を列挙する。
/// turn 昇順で返す。
pub fn get_unscored(&self) -> Result<Vec<UnscoredCell>>;

/// セルに features を書き込む。
/// features が既にスコアリング済み（非ゼロ）の場合はエラー。
pub fn set_features(&mut self, cell_id: u64, features: [u8; 16]) -> Result<()>;
```

### 10.5.2 UnscoredCell

```rust
pub struct UnscoredCell {
    pub id: u64,
    pub text: String,
    pub owner: u32,
    pub turn: u32,
    pub meta: String,
}
```

### 10.5.3 利用パターン

```rust
// Phase 1: テキストだけ登録（ゲームループ中）
mem.store(Cell::new(AGENT_TESON, "ジフンと密約を交わした")
    .from(AGENT_JIHUN).turn(3).group_bits(GROUP_TESON | GROUP_JIHUN)
    .mode(0o740).price(90))?;
// features はデフォルト [0; 16]

// Phase 2: 一括スコアリング（ターン間）
let unscored = mem.get_unscored()?;
for cell in &unscored {
    let features = llm_score(&cell.text, &preset);  // 外部 LLM
    mem.set_features(cell.id, features)?;
}
```

### 10.5.4 xMBS Lite との対応

| xMBS Lite | MxBS |
|---|---|
| `store()` → Pending | `store()` → features 全ゼロ |
| `index_pending()` → 内部で embedding 生成 | `get_unscored()` + 外部スコアリング + `set_features()` |
| `index_cell()` → 単一セル embedding | `set_features()` |

MxBS はスコアリングロジックを持たない。「ベクトルの生成」と「ベクトルの格納」を分離する。

---

## 11. セーブデータとプリセット

xMBS Lite §12 と同一の設計。SQLite 単一ファイル = ファイルコピーでセーブ/ロード。

### 11.1 ゲームライフサイクル

```
【ビルド時】
  開発者がプリセットセルを登録（mode=0o444, features スコアリング済み）
  → preset.db として出荷

【ニューゲーム】
  preset.db をコピー → save_slot_1.db

【プレイ中】
  store() でセルを追加
  reinforce() でプリセット・プレイ中セル両方の importance を更新

【セーブ】
  save_to() で SQLite backup API でファイルコピー

【ロード】
  MxBS::open() で save.db を開く
```

### 11.2 ファイルサイズ見積もり

| 項目 | サイズ |
|---|---|
| セル本体（メタデータ + text） | ~200 bytes/cell |
| features | **16 bytes/cell** |
| **セルあたり合計** | **~216 bytes/cell** |
| 1,000 セル | ~216 KB |
| 10,000 セル | ~2.2 MB |

xMBS Lite（4,096 bytes/cell の embedding）と比較して **約 20 倍のセル密度**。

---

## 12. データベーススキーマ

### 12.1 cells テーブル

```sql
CREATE TABLE cells (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       INTEGER NOT NULL,               -- NPC/agent ID (u32)
    "from"      INTEGER NOT NULL,               -- info source ID (u32)
    turn        INTEGER NOT NULL,               -- turn number (u32)

    -- アクセス制御
    group_bits  INTEGER NOT NULL DEFAULT 0,     -- bitflag (u64)
    mode        INTEGER NOT NULL DEFAULT 484,   -- UNIX perm (u16, 484=0o744)

    -- 価値
    price       INTEGER NOT NULL DEFAULT 100,   -- 0-254, 255=immortal (u8)
    importance  REAL    NOT NULL DEFAULT 1.0,

    -- 本体
    text        TEXT    NOT NULL,

    -- 因子ベクトル
    features    BLOB    NOT NULL,               -- 16 bytes exactly

    -- 拡張
    meta        TEXT    DEFAULT '{}'
);
```

### 12.2 インデックス

```sql
CREATE INDEX idx_cells_owner ON cells(owner);
CREATE INDEX idx_cells_turn ON cells(turn);
```

### 12.3 メタテーブル

```sql
CREATE TABLE mxbs_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 初期化時に挿入
INSERT INTO mxbs_meta (key, value) VALUES ('version', '0.1.1');
INSERT INTO mxbs_meta (key, value) VALUES ('factor_dim', '16');
```

---

## 13. Config

### 13.1 MxBSConfig

```rust
pub struct MxBSConfig {
    /// 忘却の半減期（ターン数）。デフォルト 8。
    pub half_life: u32,
}

impl Default for MxBSConfig {
    fn default() -> Self {
        Self {
            half_life: 8,
        }
    }
}
```

xMBS Lite の `XmbsConfig` から `embedding_model` を削除し、
`base_half_life`（秒単位）を `half_life`（ターン単位）に変更。

---

## 14. Rust API サーフェス

### 14.1 初期化

```rust
use mxbs::{MxBS, MxBSConfig};

let config = MxBSConfig {
    half_life: 8,
};

let mut mem = MxBS::open("memory.db", config)?;
```

### 14.2 セル登録

```rust
use mxbs::Cell;

// パターン A: features 付きで即登録（スコアリング済み）
let cell_id = mem.store(
    Cell::new(AGENT_TESON, "ジフンと密約を交わした")
        .from(AGENT_JIHUN)
        .turn(3)
        .group_bits(GROUP_TESON | GROUP_JIHUN)  // 当事者のみ
        .mode(0o740)
        .price(90)
        .features([180, 200, 50, 220, 100, 80, 160, 190, 140, 70, 200, 130, 80, 170, 110, 150])
)?;

// パターン B: features なしで登録（遅延スコアリング）
let cell_id = mem.store(
    Cell::new(AGENT_TESON, "ウジンが秘密裏に接触してきた")
        .from(AGENT_UJIN)
        .turn(3)
        .group_bits(GROUP_TESON | GROUP_UJIN)
        .mode(0o740)
        .price(80)
)?;
// features はデフォルト [0; 16]。後から set_features() で書き込む。

// 公開セル（新聞記事等）— mode=0o744 で全員に read を許可
let cell_id = mem.store(
    Cell::new(SYSTEM, "ガンホが記者会見で新戦略を発表した")
        .from(AGENT_GANGO)
        .turn(3)
        .mode(0o744)                // other=r で全員可読
        .price(PRICE_IMMORTAL)      // 公式記録は不滅
        .features([120, 80, 200, 60, 150, 90, 100, 70, 180, 140, 60, 200, 90, 110, 170, 80])
)?;
```

### 14.3 検索

```rust
// クエリベクトル（「外交的な圧力に関する記憶」を想定）
let query = [200, 180, 100, 150, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110];

let results = mem.search(query, AGENT_TESON, GROUP_TESON)
    .current_turn(5)
    .decay_factor(1.0)
    .limit(5)
    .exec()?;

for r in &results {
    println!("[owner={}] {:.4} — {}", r.owner, r.effective_score, r.text);
}
```

### 14.4 ドリームプル

```rust
let dreams = mem.dream(AGENT_TESON, GROUP_TESON)
    .current_turn(10)
    .limit(3)
    .exec()?;

for d in &dreams {
    println!("buried={:.1} decay={:.3} — {}", d.buried_score, d.decay, d.text);
}
```

### 14.5 Importance 強化

```rust
mem.reinforce(cell_id, 2.0)?;
```

### 14.6 インスピレーション

```rust
let related = mem.inspire(cell_id)
    .limit(5)
    .viewer(AGENT_TESON, GROUP_TESON)
    .exec()?;
```

### 14.7 セルフィールド更新

```rust
// 密会の目撃者を追加
let ok = mem.update_group_bits(cell_id, old_bits | GROUP_WITNESS,
                               AGENT_TESON, GROUP_TESON)?;

// 秘密を公開に格下げ（other に read 付与）
let ok = mem.update_mode(cell_id, 0o744,
                          AGENT_TESON, GROUP_TESON)?;

// meta にフラグ追加
let ok = mem.update_meta(cell_id, r#"{"leaked":true}"#,
                          AGENT_TESON, GROUP_TESON)?;
```

### 14.8 遅延スコアリング

```rust
// 未スコアリングセルを列挙
let unscored = mem.get_unscored()?;
println!("{} cells need scoring", unscored.len());

// 外部 LLM でスコアリングして書き込み
for cell in &unscored {
    let features = llm_score(&cell.text, &preset);
    mem.set_features(cell.id, features)?;
}
```

### 14.9 セル取得・削除

```rust
let cell = mem.get(cell_id)?;
mem.delete(cell_id, requester_id, req_groups)?;  // x 権限チェック
```

### 14.10 統計

```rust
let stats = mem.stats()?;
println!("total={}", stats.total);
```

### 14.11 セーブ / ロード

```rust
mem.save_to("saves/slot_1.db")?;

let mut mem = MxBS::open("saves/slot_1.db", config)?;

// ニューゲーム
std::fs::copy("preset.db", "saves/new_game.db")?;
let mut mem = MxBS::open("saves/new_game.db", config)?;
```

---

## 15. C バインディング

### 15.1 方針

xMBS Lite と同一の設計思想。整数パラメータ中心、戻り値 JSON。

```c
// ライフサイクル
MxBSHandle* mxbs_open(const char* db_path, const char* config_json);
void mxbs_close(MxBSHandle* handle);

// セル登録（features は NULL なら全ゼロで登録 = 遅延スコアリング）
uint64_t mxbs_store(MxBSHandle* h, uint32_t owner, uint32_t from,
                    uint32_t turn, uint64_t group_bits, uint16_t mode,
                    uint8_t price,
                    const uint8_t* features,  // 16 bytes or NULL
                    const char* text, const char* meta);

// 遅延スコアリング
const char* mxbs_get_unscored(MxBSHandle* h);  // JSON 配列で返す
int mxbs_set_features(MxBSHandle* h, uint64_t cell_id,
                      const uint8_t* features);  // 16 bytes

// 検索（query_features は 16 バイトの配列ポインタ）
const char* mxbs_search(MxBSHandle* h,
                        const uint8_t* query_features,  // 16 bytes
                        uint32_t viewer_id, uint64_t viewer_groups,
                        uint32_t current_turn, int limit);

// ドリーム
const char* mxbs_dream(MxBSHandle* h,
                       uint32_t viewer_id, uint64_t viewer_groups,
                       uint32_t current_turn, int limit);

// インスピレーション
const char* mxbs_inspire(MxBSHandle* h, uint64_t cell_id, int limit,
                         uint32_t viewer_id, uint64_t viewer_groups);

// 強化
int mxbs_reinforce(MxBSHandle* h, uint64_t cell_id, float importance);

// フィールド更新
int mxbs_update_group_bits(MxBSHandle* h, uint64_t cell_id, uint64_t new_group_bits,
                           uint32_t requester, uint64_t req_groups);
int mxbs_update_mode(MxBSHandle* h, uint64_t cell_id, uint16_t new_mode,
                     uint32_t requester, uint64_t req_groups);
int mxbs_update_meta(MxBSHandle* h, uint64_t cell_id, const char* new_meta,
                     uint32_t requester, uint64_t req_groups);

// 取得・削除
const char* mxbs_get(MxBSHandle* h, uint64_t cell_id);
int mxbs_delete(MxBSHandle* h, uint64_t cell_id,
                uint32_t requester, uint64_t req_groups);

// セーブ
int mxbs_save(MxBSHandle* h, const char* dest_path);

// 統計
const char* mxbs_stats(MxBSHandle* h);

// メタデータ
const char* mxbs_meta_get(MxBSHandle* h, const char* key);  // JSON: {"value": ...}
int mxbs_meta_set(MxBSHandle* h, const char* key, const char* value);

// メモリ解放
void mxbs_free_string(const char* s);
```

### 15.2 features の受け渡し

C API では features を `const uint8_t*`（16 バイト）で渡す。
`mxbs_store()` で features に `NULL` を渡すと全ゼロで登録（遅延スコアリング）。
後から `mxbs_set_features()` で書き込む。

---

## 16. 忘却計算の詳細

### 16.1 関数定義

```rust
const PRICE_IMMORTAL: u8 = 255;

fn decay(delta_turns: u32, half_life: u32) -> f32 {
    0.5_f32.powf(delta_turns as f32 / half_life as f32)
}

fn price_factor(price: u8) -> f32 {
    price as f32 / 255.0
}

fn effective_score(cosine: f32, importance: f32, price: u8, decay: f32) -> f32 {
    if price == PRICE_IMMORTAL {
        // immortal: decay=1.0, price_factor=1.0
        return cosine * importance;
    }
    cosine * importance * price_factor(price) * decay
}

fn buried_score(price: u8, decay: f32, importance: f32) -> f32 {
    if price == PRICE_IMMORTAL {
        return 0.0;
    }
    let inv_decay = (1.0 / decay.max(1e-6)).min(1000.0);
    price as f32 * inv_decay * importance
}
```

### 16.2 price ガイドライン

| 内容 | price 目安 |
|---|---|
| 環境描写、背景情報 | 10〜30 |
| NPC 同士の会話の断片 | 40〜60 |
| 重要な会話・取引 | 70〜100 |
| 秘密の情報 | 100〜150 |
| シナリオを変える級の事件 | 150〜200 |
| ゲーム世界の重大決定 | 200〜254 |
| **絶対に忘れない記憶** | **255 (PRICE_IMMORTAL)** |

---

## 17. 設計判断の記録

### 17.1 Embedder / VecStore trait を廃止した理由

u8 × 16 の因子ベクトルはアプリケーション側（MxMindFox 等）が LLM でスコアリングする。
MxBS 内部にスコアリングロジックは不要。全スキャン cosine で十分な速度が出る。
trait による抽象化は将来の NPU 対応を見据えたものだったが、
16 バイトのベクトルに NPU を使う需要は考えにくい。

### 17.2 timestamp を turn に変更した理由

- 2 フェーズ設計はターン単位で動作する
- 忘却の half_life もターン単位の方が直感的（「8 ターンで半減」vs「2,592,000 秒で半減」）
- 非ターンベースのゲームでも抽象的な「イベント番号」を turn として使える
- u32 ターンなら 40 億ターン分の精度

### 17.3 scene_id を廃止した理由

scene_id はゲームのシーン切替に対応するフィルタだったが、
MxBS はより汎用的な記憶ストアとして位置付ける。
シーン管理が必要な場合は MxMindFox 層で turn 範囲フィルタや meta を使って対応する。

### 17.4 price を u8 にした理由

mxbs_concept.md で「0〜255 の 256 段階で十分」と結論。
ゲーム用途で「重要度が 12,345 か 12,346 か」を区別する需要はない。
u8 により Cell 構造体がコンパクトになり、C バインディングも簡素。

### 17.5 is_public を採用しなかった理由

当初 is_public フラグを追加する案があったが、mode の other 権限と機能が重複し、
`is_public = true` なのに `mode = 0o700` のような矛盾状態が生じうるため廃止。
公開セルにするには `mode = 0o744`（other=r）を使えばよい。二重管理は事故のもと。

### 17.6 忘却スコアの計算式を変更した理由

xMBS Lite: `relevance = importance × decay / distance`
MxBS: `effective = cosine × importance × price_factor × decay`

- cosine（高い = 類似）を使うため、除算から乗算に変更
- price_factor を明示的にスコアに含めることで、price の効果が直感的に理解できる
- xMBS Lite では price が half_life に間接的に影響していたが、MxBS では直接乗算

### 17.7 xMBS Lite の設計判断で継承するもの

以下は xMBS Lite spec §17 の判断をそのまま継承:

- §17.7: 全 ID を整数型にした理由
- §17.8: グループをビットフラグ (u64) にした理由
- §17.10: w ビットの意味確定（group / mode / meta の事後変更権限）
- §17.6: セーブ/プリセットを UNIX パーミッションで制御する理由

---

## 18. 実装チェックリスト

### MxBS crate

- [ ] Cell 構造体定義
- [ ] MxBSConfig
- [ ] MxBS::open() — DB オープン + スキーマ作成
- [ ] store() — セル登録（features 省略可 = 全ゼロ）
- [ ] get() — セル取得
- [ ] delete() — セル削除（x 権限チェック）
- [ ] cosine_similarity() — u8 × 16 コサイン
- [ ] get_unscored() — 未スコアリングセル列挙
- [ ] set_features() — features 書き込み（全ゼロ → 値の一方向）
- [ ] search() — ベクトル検索 + 忘却スコア + ACL + フィルタ
- [ ] search() — query なし検索（turn 降順）
- [ ] dream() — buried_score 算出 + ランキング
- [ ] reinforce() — importance 更新（w バイパス）
- [ ] inspire() — 因子ベクトル近傍検索
- [ ] update_group_bits() — w チェック
- [ ] update_mode() — w チェック
- [ ] update_meta() — w チェック
- [ ] プリセットセル保護 — mode=0o444 の delete 拒否
- [ ] reinforce の w バイパス
- [ ] save_to() — SQLite backup API
- [ ] stats()
- [ ] C bindings — cdylib + ヘッダファイル
- [ ] テスト — ラウンドトリップ、忘却、ACL、ドリーム、遅延スコアリング

---

*Document history*

| Date | Version | Author | Notes |
|---|---|---|---|
| 2026-04-28 | 0.1.0 | エルマー🦊 + マスター | xMBS Lite spec をベースに MxBS 向けに再設計。因子ベクトル化 |
| 2026-05-03 | 0.1.1 | ちびエルマー🦊 | §2.3 エンディアン→クロスプラットフォーム互換性。§12.3 version 更新。§15 meta_get/meta_set 追加 |
