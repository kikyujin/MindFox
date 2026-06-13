# MxYamAMVA — Concept

**MxBS / MxMindFox / MxChatterFox 連携オーケストレーション層**

> Version: 0.1.0 (draft) | Date: 2026-05-28
> Authors: エルマー🦊 + マスター
> Position: YamAMVA（MIT OSS）の MindFox シリーズ拡張。ステートフルなゲーム進行管理を担う

---

## 1. MxYamAMVA とは何か

MxYamAMVA は、YamAMVA（汎用 YAML シナリオディスパッチャ）に MxBS / MxMindFox / MxChatterFox 連携機能を追加するオーケストレーション層である。

YamAMVA 本体は MIT OSS として公開済み。MxYamAMVA はその上に乗る拡張であり、YamAMVA 本体に MindFox 依存を持ち込まない。

```
YamAMVA（MIT OSS）
  汎用 YAML ディスパッチャ
  speak / move / menu / jump / when ...

MxYamAMVA（MindFox 拡張）
  mxbs_push / chatterfox / cerif_db 切替 / キーワード分岐 ...
```

### 1.1 設計方針

| 方針 | 説明 |
|---|---|
| **YamAMVA 本体を汚さない** | 拡張ノードは全て MxYamAMVA 側に定義。本体は MIT OSS のまま |
| **ステートフルはここだけ** | MxBS はストレージ、MxChatterFox はステートレス検索。ゲーム進行状態は MxYamAMVA が握る |
| **YAML で全制御** | シナリオライターがコードを書かずに NPC 登場・セリフDB切替・キーワード分岐を記述できる |
| **疎結合** | MxBS / MxMindFox / MxChatterFox のどれが欠けても、対応ノードがスキップされるだけで全体は動く |

### 1.2 MindFox シリーズでの位置づけ

```
┌─────────────────────────────────────────────────────────┐
│  Game（Unity / Web / CLI）                               │
│  UI・ゲームループ                                        │
├─────────────────────────────────────────────────────────┤
│  MxYamAMVA ★                                            │
│  オーケストレーター: シナリオ進行・状態管理               │
│  ┌─────────────┬─────────────┬───────────────┐          │
│  │ mxbs_push   │ chatterfox  │ mood_gate     │ 拡張ノード│
│  └─────────────┴─────────────┴───────────────┘          │
├───────────────┬─────────────┬────────────────────────────┤
│  MxChatterFox │ MxMindFox   │ YamAMVA（OSS本体）        │
│  会話検索      │ Mood/判断    │ speak/move/menu/jump      │
├───────────────┴─────────────┴────────────────────────────┤
│  MxBS                                                    │
│  記憶セル・因子ベクトル・SQLite                           │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 責務一覧

| # | 責務 | 説明 |
|---|---|---|
| 1 | **NPC 登場管理** | シーンごとにどの NPC が会話可能かを定義 |
| 2 | **cerif_db 切り替え** | ストーリー進行度で NPC のセリフDBセット（`cerif_db_id`）を差し替え |
| 3 | **キーワード分岐** | プレイヤーの所持キーワードによるシーン遷移・イベント発火 |
| 4 | **キーワードインベントリ管理** | プレイヤーがどの単語を持っているかの状態管理 |
| 5 | **chatterfox ノード** | 固定セリフ区間（speak）↔ 自由会話区間（chatterfox）の切り替え |
| 6 | **mxbs_push ノード** | シナリオイベントから MxBS への記憶書き込み |
| 7 | **mood_gate ノード** | MxMindFox の Mood 値によるシーン分岐（オプション） |
| 8 | **bake パイプライン管理** | cerif.json（手書き or LLM生成）→ bake_16element → MxBS プリセットの実行制御 |
| 9 | **進行フラグ管理** | キーワードマッチ率による進行判定（不完全情報 OK） |

---

## 3. 拡張ノード定義

### 3.1 chatterfox — 自由会話ノード

MxChatterFox を呼び出して自由会話区間に入る。

```yaml
- chatterfox:
    npc: village_elder
    cerif_db: elder_phase1
    available_words:
      WHO:    [魔女, 鍛冶屋, 村長]
      ACTION: [探す, 聞く, 買う]
      WHERE:  [このあたり, 森, 街]
    exit_words: [もういい, さよなら]
    on_exit: scene_forest_entrance
    max_turns: null
```

| フィールド | 必須 | 説明 |
|---|---|---|
| npc | ✅ | 会話対象 NPC の ID |
| cerif_db | ✅ | 使用するセリフDB の ID |
| available_words | ✅ | スロット別の選択可能単語リスト |
| exit_words | | 会話終了トリガー単語 |
| on_exit | | 会話終了後の遷移先シーン |
| max_turns | | 最大ターン数（null = 無制限） |

MxChatterFox に `cerif_db` と `available_words` を渡すだけ。MxChatterFox は渡されたものの中で検索して結果を返す。

### 3.2 mxbs_push — 記憶書き込みノード

```yaml
- mxbs_push:
    target: player
    key: "村の長老と会話した"
    factors: { topic_person: 0.5, topic_location: 0.3 }
```

既存の MxADVeng mxbs_push と同一仕様。

### 3.3 keyword_gate — キーワード分岐ノード

```yaml
- keyword_gate:
    check: [森の奥, 魔女, エレナ]
    min_match: 0.6
    branches:
      - match: 1.0
        goto: scene_elena_perfect
      - match: 0.6
        goto: scene_elena_risky
      - fallback:
        speak:
          who: narrator
          text: "まだ情報が足りないようだ……"
```

| フィールド | 必須 | 説明 |
|---|---|---|
| check | ✅ | チェック対象のキーワードリスト |
| min_match | | 最低マッチ率（デフォルト: 1.0 = 全部必要） |
| branches | ✅ | マッチ率による分岐先 |

### 3.4 mood_gate — Mood 分岐ノード（オプション）

```yaml
- mood_gate:
    agent: village_elder
    axis: suspicion
    branches:
      - above: 0.7
        goto: scene_elder_suspicious
      - below: 0.3
        goto: scene_elder_friendly
      - fallback:
        goto: scene_elder_neutral
```

MxMindFox の Mood 値を参照してシーン分岐。MxMindFox が存在しない場合はフォールバックに直行。

### 3.5 keyword_grant — キーワード直接付与ノード

```yaml
- keyword_grant:
    words: [森の奥, 危険]
    source: item_pickup
```

会話以外のイベント（アイテム取得、シーン遷移等）でキーワードを付与。

---

## 4. シナリオ例

```yaml
# ミラの森 — Phase 1: 村の聞き込み

scenes:
  village_square:
    - speak:
        who: narrator
        text: "ミラの村の広場にたどり着いた。村人たちが行き交っている。"

    - speak:
        who: village_elder
        text: "旅の人かい。何か用かね"

    - chatterfox:
        npc: village_elder
        cerif_db: elder_phase1
        available_words:
          WHO:    [魔女, 鍛冶屋, 村長, その人]
          ACTION: [探す, 聞く, 教えて, 買う]
          WHERE:  [このあたり, 森, 街, 北の山]
          WHAT:   [名前, 年齢, 男女, 危険]
        exit_words: [もういい, さよなら, 行く]
        on_exit: village_choice

  village_choice:
    - keyword_gate:
        check: [森の奥, 魔女, エレナ, 危険, お守り]
        min_match: 0.6
        branches:
          - match: 1.0
            goto: forest_perfect
          - match: 0.6
            goto: forest_risky
          - fallback:
            speak:
              who: narrator
              text: "まだ情報が足りない。もう少し聞き込みを続けよう。"
            goto: village_square

  forest_perfect:
    - speak:
        who: narrator
        text: "十分な情報を得て、自信を持って森へ向かった。"
    - mxbs_push:
        target: player
        key: "万全の準備で森へ"
        factors: { topic_location: 0.8 }

  forest_risky:
    - speak:
        who: narrator
        text: "まだ不安は残るが、意を決して森へ足を踏み入れた。"
```

---

## 5. 状態管理

### 5.1 MxYamAMVA が管理する状態

| 状態 | 格納先 | 説明 |
|---|---|---|
| プレイヤーのキーワードインベントリ | MxBS セル (price=255) | 因子ベクトル付き単語カード |
| 現在のシーン | セッション変数 | 現在どのシーンにいるか |
| 会話履歴 | MxBS セル (price=80-150) | 誰と何を話したか |
| NPC の cerif_db_id | シナリオ YAML で静的定義 | シーンごとに決まっている |

### 5.2 MxYamAMVA が管理しない状態

| 状態 | 管理者 | 理由 |
|---|---|---|
| NPC の因子ベクトル | MxBS プリセット | bake 時に確定済み |
| NPC のセリフ内容 | MxBS セル | bake 時に確定済み |
| Mood 値 | MxMindFox | リアルタイム算出 |
| 会話中のコンテキスト | MxChatterFox セッション | 会話エンジン内部 |

---

## 6. YamAMVA 本体との境界

```
YamAMVA（MIT OSS）が処理:
  speak / move / menu / jump / when / bgm / ...

MxYamAMVA（拡張）が処理:
  chatterfox / mxbs_push / keyword_gate / mood_gate / keyword_grant / ...
```

YamAMVA 本体のディスパッチャは未知のノードタイプを拡張ハンドラに委譲する仕組みを持つ。MxYamAMVA はそのハンドラとして登録される。

本体に MxBS/MxMindFox/MxChatterFox の依存は一切入らない。

---

## 7. 障害耐性

| 障害 | 影響 | 対策 |
|---|---|---|
| MxBS 障害 | mxbs_push / chatterfox / keyword 系が停止 | speak / move 等の YamAMVA 本体ノードは正常動作 |
| MxChatterFox 障害 | chatterfox ノードが停止 | on_exit にフォールバック遷移 |
| MxMindFox 障害 | mood_gate が判定不能 | フォールバック分岐に直行 |
| cerif_db 欠損 | 該当 NPC の会話不能 | chatterfox ノードをスキップして on_exit へ |

**疎結合の恩恵**: どのコンポーネントが落ちても、そのノードだけがスキップされ、シナリオ全体は進行を続けられる。

---

## 8. 関連ドキュメント

| ドキュメント | ファイル | 関連 |
|---|---|---|
| MxChatterFox コンセプト | `mxchatterfox_concept.md` | 会話エンジン本体 |
| MxBS 仕様 | `mxbs_spec.md` | 記憶基盤 |
| MxMindFox 設計 | `mxmf_architecture.md` | Mood 連動 |
| YamAMVA 設計 | `yamamva_architecture.md` | OSS 本体 |
| Archetypes 定義 | `archetypes.md` | NPC 性格テンプレート |
| MxADVeng ロードマップ | `madv_roadmap.md` | Web UI 統合 |

---

*Document history*

| Date | Version | Author | Notes |
|---|---|---|---|
| 2026-05-28 | 0.1.0 | エルマー🦊 + マスター | 初版。MxChatterFox concept から分離 |
