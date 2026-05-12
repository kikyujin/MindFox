# MxBS — Roadmap

> Last updated: 2026-05-02

署名: 2026-05-02 Kikyujin - Mahito KIDA

---

## 1. 変更履歴

### v0.3.1 (2026-05-02) — MxMindFox 切り出し対応 + clippy 警告潰し

MxMindFox v0.1.0 切り出しに伴う MxBS 側の最小差分対応。
**ロジック・スキーマ・API には変更なし**。

- **Cell に `Deserialize` derive 追加**（lib.rs 1行）
  - 動機: MxMindFox FFI で `serde_json::from_str::<Vec<mxbs::Cell>>(cells_json)` を呼ぶため
  - Serialize と対称的になり、save/load 系の将来拡張にも有利
- **clippy 警告潰し**（マスター指示）
  - Rust 2024 edition 準拠のスタイル統一
- 既存テスト 43件（34 + 9）全パス維持
- 戦国SIM 33テスト全パス維持
- API 互換性維持: 既存利用側に影響なし

### v0.3.0 (2026-04-29) — ページワンデモ + 忘却定量テスト

LLM ゼロのアメリカンページワンデモで MxBS の忘却を定量検証。

- `demos/pageone/` — LLM 不使用、プリセットセリフ方式（マッチ箱のAI原則）
- 50 ゲーム 419 ターンを <1 秒で完走
- 3 条件比較テスト（再注入+HL=8 / 1回+HL=80 / 1回+HL=8）
- 忘却定量データ取得完了 → preset_guide.md の材料が揃った
- MxMindFox 切り出しのトリガー条件確認（3 デモで共通パターン確立）

### v0.2.0 (2026-04-29) — C API + Python ctypes ブリッジ

C バインディング（cdylib）と Python ctypes ラッパーを追加。43テスト全パス。

- `src/ffi.rs` — 17 extern "C" 関数（mxbs_spec.md §15 準拠）
- Rust 2024 edition 対応（`#[unsafe(no_mangle)]` + 明示的 `unsafe {}` ブロック）
- `serde` derive 追加（MxBSConfig: Deserialize、Cell/Result型: Serialize）
- `python/mxbs_bridge.py` — ctypes ラッパー（restype=c_void_p でポインタ管理）
- `python/test_bridge.py` — スモークテスト（store/get/search/dream/reinforce/inspire/stats）
- `tests/ffi_test.rs` — 9 FFI 統合テスト（NULLハンドル安全性含む）
- 戦国SIM デモ（33テスト）に影響なし

### v0.1.0 (2026-04-28) — MxBS Rust crate 初版

MxBS Rust crate を1日で全機能実装。34テスト全パス。

- Cell 構造体 + ビルダーパターン
- MxBS::open() + SQLite スキーマ自動作成
- store / get / delete（x 権限チェック）
- cosine_similarity（u8×16）
- search（ビルダーパターン、ACL + フィルタ + ベクトル検索 + queryなし検索）
- dream（buried_score 降順、immortal 除外）
- reinforce（importance 更新、w バイパス）
- inspire（因子ベクトル近傍検索）
- update_group_bits / update_mode / update_meta（w チェック）
- set_features / get_unscored（遅延スコアリング）
- save_to（SQLite backup API）
- stats（total / scored / unscored）
- `pub mod preset` — Preset + scoring_prompt + parse_scores
- `pub mod agents` — AgentRegistry + store_public/private/search/dream ショートカット
- MxMindFox crate は作らない決定（YAGNI）

### v0.0.0 (2026-04-27) — パラダイムシフト

xMBS Lite（bge-m3 / 1024次元 / ONNX / sqlite-vec）を全面廃止。
MxBS（16バイト因子ベクトル / SQLite のみ）をメインストリームに据える。
mxbs_lite.py + mxmf_lite.py で Hawaii 2035 シナリオ 5エージェント×6ターン完走。

---

## 2. 現状

### 完了済み

| マイルストーン | 日付 | 状態 |
|---|---|---|
| MxBS コンセプト策定（mxbs_concept.md） | 2026-04-27 | ✅ |
| Python 実証（mxbs_lite.py + mxmf_lite.py、Hawaii 2035 6ターン） | 2026-04-27 | ✅ |
| MxBS 仕様書（mxbs_spec.md v0.1.0） | 2026-04-28 | ✅ |
| MxBS Rust crate 全機能実装（34テスト） | 2026-04-28 | ✅ |
| MxMindFox crate 不要の判断 | 2026-04-28 | ✅ |
| 戦国SIM デモ（Rust MxBS 直接利用、33テスト） | 2026-04-28 | ✅ |
| C bindings（cdylib、17関数、9テスト） | 2026-04-29 | ✅ |
| Python ctypes ブリッジ（mxbs_bridge.py） | 2026-04-29 | ✅ |
| おやつデモ（AI館社会推理ゲーム、7キャラ×3ゲーム） | 2026-04-29 | ✅ |
| ページワンデモ（LLMゼロ忘却テスト、50ゲーム×3条件） | 2026-04-29 | ✅ |
| 忘却定量テスト（price/half_life/reinforce の実測データ） | 2026-04-29 | ✅ |

### 未完了

| マイルストーン | 優先度 | 状態 |
|---|---|---|
| MxMindFox 切り出し設計（Rust crate + C API + Python/C# wrapper） | 高 | 🔜 次 |
| preset_guide.md（ページワン実測データをベースに執筆） | 中 | — |
| (planned demo #4) MxBS 対応 | 中 | — |
| (planned demo #5) 設計更新 | 中 | — |
| Hawaii 2035 再走（Rust MxBS + Python ホスト） | 低 | 降格。3デモで実証十分 |
| (planned demo page) | 低 | — |
| `cargo publish` | 低 | — |

---

## 3. 開発フェーズ

### Phase 1: コア実装 — ✅ 完了

MxBS Rust crate の全 Rust API。

- [x] Cell 構造体 + MxBSConfig
- [x] SQLite スキーマ（cells + mxbs_meta）
- [x] store / get / delete
- [x] cosine_similarity（u8×16）
- [x] search（ベクトル検索 + 忘却 + ACL + フィルタ）
- [x] dream（buried_score）
- [x] reinforce（w バイパス）
- [x] inspire（近傍検索）
- [x] update_group_bits / update_mode / update_meta（w チェック）
- [x] set_features / get_unscored（遅延スコアリング）
- [x] save_to / stats
- [x] Preset + scoring_prompt + parse_scores
- [x] AgentRegistry（store_public / store_private / search / dream）
- [x] 34テスト全パス

### Phase 2: 実地検証 — ✅ 完了

Rust MxBS の実地テスト。3 デモタイトルで全パス検証。

- [x] libmxbs.dylib ビルド（cdylib）
- [x] C bindings 実装（mxbs_spec.md §15 準拠、17関数）
- [x] Python ctypes ブリッジ（mxbs_bridge.py）
- [x] 戦国SIM デモ（Rust MxBS 直接利用、33テスト）
- [x] おやつデモ（Python + mxbs_bridge.py + Ollama gemma4:26b）
- [x] ページワンデモ（Python + mxbs_bridge.py、LLM ゼロ）
- [x] 忘却定量テスト（3条件比較、preset_guide 材料取得）
- ~~[ ] Hawaii 2035 再走~~ → 3デモで十分。優先度降格
- [ ] パフォーマンス比較（Python vs Rust）→ Phase 4 へ移動

### Phase 3: MxMindFox 切り出し + デモタイトル展開

3 デモで共通パターンが確立。切り出しのトリガー条件を満たした。

**MxMindFox crate（Rust + C API + Python wrapper）— Phase 1-7 完了 (2026-05-02):**

- [x] Mood / MoodPreset / MoodAxis（プリセット駆動、固定 struct ではなく `HashMap<String, f32>`）
- [x] compute_mood — 戦国SIM・おやつ両方対応の汎用実装
- [x] compute_diplomacy_toward — trust 軸読みの薄いラッパー
- [x] adjust_threshold — ThresholdRule で覇気パッチ汎用化
- [x] decision::remember — Bernoulli + sigmoid（temperature 揺らぎ）
- [x] decision::sample — Multinomial + softmax（temperature 揺らぎ）
- [x] C bindings (cdylib、9 関数 export)
- [x] Python ctypes ブリッジ + スモークテスト
- [x] 54テスト全パス（mood 14 + diplomacy 5 + threshold 5 + decision 11 + ffi 12 + python 7）
- [x] libmxmindfox.dylib (2.3 MB) ビルド成功

**3デモ移行（次フェーズ）:**

| デモ | 内容 | 状態 |
|---|---|---|
| ページワン v0.4 | temperature 揺らぎ検証（50ゲーム × 3条件キャンペーン） | 🔜 発注書 #2 待ち |
| 戦国SIM v2 | 覇気パッチ削除、compute_mood + adjust_threshold 統合 | 🔜 発注書 #3 待ち |
| おやつ v2 | compute_diplomacy_toward 統合、3ゲームキャンペーン再走 | 🔜 発注書 #4 待ち |

**(planned demo #4) / (planned demo #5)（後続）:**

| タイトル | 内容 | MxBS 利用 |
|---|---|---|
| **(planned demo #4)** | AI娘とカードゲーム | MxBS + MxMindFox（最初のクライアント） |
| **(planned demo #5)** | 第一次大戦前ヨーロッパ地政学シミュレーション | MxBS + MxMindFox + Unity (C# P/Invoke) |

- [ ] (planned demo #4) MxBS + MxMindFox 対応
- [ ] (planned demo #5) 設計更新（MxBS / MxMindFox / JUWA 統合軸）

### Phase 4: 検証作業

- [ ] preset_guide.md — GM 向けプリセット設計ガイド（ページワン実測データベース）
- [x] API リファレンスドキュメント（mxbs_spec.md で継続整備中）
- [x] サンプルプロジェクト（demos/oyatsu, demos/pageone で検証兼開発中）
- [ ] (planned demo page)（Hawaii 2035 動画 or インタラクティブ）
- [x] `cargo publish` (v0.3.1)

---

## 4. 廃止されたプロダクト

| プロダクト | 廃止日 | 理由 | 後継 |
|---|---|---|---|
| xMBS Lite (Rust crate) | 2026-04-27 | bge-m3/ONNX/sqlite-vec 依存。16バイト因子ベクトルに置換 | MxBS |
| MindFox (Rust crate) | 2026-04-28 | 過剰な抽象化。実態は for ループと文字列連結 | MxBS `pub mod agents` |
| xMBS v0.6.0 (Python/FastAPI) | 2026-04-01 | Rust 再設計。AI館向けは継続運用 | xMBS Lite → MxBS |

---

## 5. 設計判断の記録

### マッチ箱のAI原則（2026-04-29）

- **決定**: ページワンデモを LLM ゼロで実装。セリフはプリセット辞書、判断は全てルールベース、MxBS の search/reinforce だけがAI的要素
- **理由**: 忘却の定量テストに LLM は不要。かつ「MxBS の忘却 + reinforce だけでキャラの個性が出る」ことを実証したかった
- **結果**: price=220 のスミレは忘却 0%、price=70 のノクちんは 100%。reinforce の連鎖効果（覚えてるキャラが覚え続け、忘れてるキャラは忘れ続ける）も実証。50 ゲーム 419 ターンを <1 秒で完走
- **帰結**: MxBS 単体でキャラクターの記憶個性を表現可能。LLM はその上のセリフ生成やストーリー生成に専念すればよい

### MxMindFox 切り出しトリガー（2026-04-29）

- **決定**: compute_mood / compute_diplomacy_toward を MxMindFox crate として切り出す
- **理由**: 戦国SIM + おやつ + ページワンの 3 デモで共通パターンが確立。「2つのゲームで使った」がトリガー条件だった
- **方向**: Rust crate + C API + Python/C# wrapper の 3 層。C# からの呼び出し（Unity P/Invoke）も想定

### MxMindFox crate を作らない → 作る（判断変更、2026-04-29）

- **旧決定（2026-04-28）**: MxMindFox は不要。MxBS `pub mod agents` で代替
- **新決定（2026-04-29）**: compute_mood / compute_diplomacy_toward は 3 デモで共通利用。薄いユーティリティ crate として切り出す
- **注意**: MxBS 自体は変更不要。MxMindFox は MxBS の上に乗る薄い層

### Hawaii 2035 再走の優先度降格（2026-04-29）

- **決定**: 優先度を「高」から「低」に降格
- **理由**: 戦国SIM（Rust直接）、おやつ（Python ctypes + LLM）、ページワン（Python ctypes + LLMゼロ）の 3 パスで実証十分。Hawaii 再走の必要性が薄れた
- **今後**: MxMindFox 切り出し後にスモークテストとして回す可能性あり

### MxMindFox crate を作らない（2026-04-28）

- **決定**: MxMindFox を別 crate にせず、MxBS 内の `pub mod agents` で代替
- **理由**: mxmf_lite.py の精読で、オーケストレーション層の実態が for ループ + 文字列連結 + LLM 呼び出しだけだと判明。旧 MindFox の ActionContext / ResolutionContext / TurnEvents / Publication Phase は全て不要だった（YAGNI）
- **根拠**: indian_poker.py の記憶は `list[str]` の末尾5件。この程度のゲームにも AgentRegistry がフィットする薄さが正解
- **帰結**: ゲーム固有ロジック（プロンプト構築、ターンループ、LLM呼び出し）はホスト側の責務
- **※ 2026-04-29 に判断変更**: 3 デモで共通パターン確立により切り出しを決定

### MxMindFox v0.1.0 完成（2026-05-02）

- **決定**: MxMindFox を独立 crate として切り出し、Phase 1-7（本体実装）を完成
- **規模**: ~800行 Rust + ~200行 Python ブリッジ。54テスト全パス
- **設計の核**: Mood をプリセット駆動（HashMap<String, f32>）、decision を Mood 非依存ヘルパー、archetype プリセットはゲーム側 JSON
- **MxBS 側の影響**: Cell に Deserialize derive 追加のみ（v0.3.1）。ロジック・スキーマ無変更
- **temperature 概念の本質的整理**: ページワンのhit/miss判定は Bernoulli (sigmoid)、複数候補選択は Multinomial (softmax)。両者を `decision::remember` / `decision::sample` として並立させた
- **次フェーズ**: 3デモ移行（pageone v0.4 / sengoku v2 / oyatsu v2）

### Cell に Deserialize derive 追加（2026-05-02）

- **決定**: MxBS の Cell 構造体に `Deserialize` を derive 追加
- **理由**: MxMindFox FFI で `Vec<mxbs::Cell>` の JSON パースが必要。中間 struct を作る案 (B) は二重定義になり保守性が悪い
- **「MxBS には触らない」原則との整合**: アーキテクチャ §14.4 の本意は「コアロジック・スキーマ・API に変更を加えない」こと。derive 1行は「シリアライズ対称性の補完」であり、趣旨に反しない
- **影響**: API 互換性維持。既存テスト 43件全パス

### is_public フィールドの廃止（2026-04-28）

- **決定**: Cell 構造体から is_public を削除
- **理由**: mode の other 権限（`0o744` で全員可読）と機能が重複。二重管理は矛盾の温床

### 遅延スコアリング対応（2026-04-28）

- **決定**: set_features / get_unscored API を追加。features は全ゼロ→非ゼロの一方向遷移
- **理由**: LLM スコアリングはプアな GPU で数秒かかる。store() 時に features を省略し、Phase 2 で一括スコアリングするパターンが必要

### パラダイムシフト: embedding → 因子ベクトル（2026-04-27）

- **決定**: 1024次元 bge-m3 embedding を 16バイト因子ベクトルに置換
- **理由**: ゲームNPCの記憶検索に汎用言語モデルの全次元は不要。GM が定義した「ゲームにとって意味のある軸」だけで十分
- **帰結**: ONNX Runtime / bge-m3 / sqlite-vec の依存が全て消滅。SQLite のみ

---

## 6. 忘却定量テスト結果（ページワンデモ実測）

### 3条件比較

| キャラ | price | A: 再注入+HL=8 | B: 1回+HL=80 | C: 1回+HL=8 |
|---|---|---|---|---|
| スミレ | 220 | **0.0%** | 53.8% | ≈100% |
| ヴェリ | 200 | **0.0%** | 58.8% | ≈100% |
| エルマー | 170 | **5.0%** | 65.0% | ≈100% |
| ティル | 80 | 100% | 96.4% | 100% |
| ノクちん | 70 | 100% | 100% | 100% |

### GM向け設計ガイドライン

| やりたいこと | 設計パターン |
|---|---|
| ゲーム内で「うっかり忘れ」を演出 | 毎ゲーム再注入 + half_life=8 + price で性格差 |
| 長期的に「昔の記憶が薄れる」演出 | 注入1回 + half_life大 + reinforce で延命 |
| 絶対忘れちゃダメなルール | price=255 (immortal) |

---

## 7. 技術スタック（現行）

| コンポーネント | 技術 |
|---|---|
| MxBS crate | Rust + rusqlite (bundled SQLite) + serde/serde_json (Preset + FFI JSON) |
| MxBS Lite | Python (開発ハーネス) |
| MxMindFox Lite | Python (デモ・検証) |
| LLM (ランタイム) | Ollama (gemma4:e2b〜26b) |
| LLM (デザインタイム) | Claude Opus / GPT-4o |
| 開発環境 | M4 Max Mac + Tailscale + dev-server |

---

## 8. デモタイトル一覧

| # | タイトル | 日付 | LLM | 検証内容 |
|---|---|---|---|---|
| 1 | 戦国SIM | 2026-04-28 | gemma4:e2b | Rust直接利用、ルールベーススコアリング、覇気パッチ |
| 2 | おやつデモ | 2026-04-29 | gemma4:26b | Python ctypes、7キャラ書き分け、ACL、クロスゲーム記憶 |
| 3 | ページワン | 2026-04-29 | なし | 忘却定量テスト、reinforce連鎖、マッチ箱のAI原則 |

---

*Document history*

| Date | Version | Author | Notes |
|---|---|---|---|
| 2026-04-28 | 1.0 | エルマー🦊 + マスター | 初版。xmbs_roadmap.md + mfx_roadmap.md を統合・刷新 |
| 2026-04-29 | 1.1 | ちびエルマー🦊 | Phase 2 進捗更新（C bindings + Python bridge 完了） |
| 2026-04-29 | 1.2 | ちびエルマー🦊 | おやつデモ完了を反映 |
| 2026-04-29 | 1.3 | エルマー🦊 + マスター | ページワンデモ完了、忘却定量テスト完了、Phase 2 完了、MxMindFox切り出し決定 |
| 2026-05-02 | 1.4 | エルマー🦊 + マスター | MxMindFox v0.1.0 Phase 1-7 完了反映、Cell に Deserialize 追加（v0.3.1）、Phase 3 状態更新 |
