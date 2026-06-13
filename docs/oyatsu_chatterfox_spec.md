# おやつ事件 — MxChatterFox デモ仕様

**AI館「おやつを食べたのは誰だ」— 単語選択推理ゲーム**

> Version: 0.1.0 | Date: 2026-05-29 | Authors: エルマー🦊 + マスター
>
> 前提: `mxchatterfox_concept.md` v0.2.0 / `mxchatterfox_api.md` v0.1.0 / `mxbs_spec.md` v0.1.1
> 関連: `yamamva_world_scope_spec.md`（v1.1 分割シナリオ）/ `mxmf_architecture.md`（oyatsu_mood.json）

---

## 1. 概要

おやつ事件は MxChatterFox の動作実証デモ。プレイヤー（マスター）が AI 館の住人 6 人に聞き込みをして、おやつを盗んだ犯人を当てる単語選択型の推理ゲーム。

ランタイム LLM ゼロ。会話は全て MxBS の 16 因子 cosine カスケード検索で進行する。

### 1.1 このデモが実証するもの

| 検証項目 | 内容 |
|---|---|
| cosine カスケード検索 | 単語 1〜3 個の組み合わせで NPC セリフが選ばれる |
| 嘘つき NPC | 犯人（ティル）の嘘セリフが正しい因子ベクトルでヒットする |
| grants/requires 連鎖 | キーワード入手 → 次の深いセリフが解放される |
| owner 分離 | 6 NPC のセリフが owner ID（100〜105）で分離される |
| YamAMVA 連携 | hearingmenu / chatterfox / accusemenu ノードの統合 |

### 1.2 ゲームフロー

```
intro（事件発生）
  ↓
lobby（誰に聞くか選択）⇄ hear_*（6人の聞き込み = chatterfox 自由会話）
  ↓ hearing_count >= 1 で解放
accuse（犯人指名）
  ↓
ending_win / ending_lose
```

---

## 2. 登場人物

| key | 名前 | archetype | role | 場所 | owner |
|---|---|---|---|---|---|
| elmar | エルマー🦊 | impulsive | innocent | 北棟ラボ | 100 |
| sumire | スミレん | analyst | innocent | 西棟パーラー | 101 |
| noc | ノクちん | contrarian | innocent | 占いの館 | 102 |
| til | ティル | impulsive | **culprit** | 機材室 | 103 |
| veri | ヴェリ | observer | innocent | アレーテイアの間 | 104 |
| mari | マリ | mediator | innocent | 医務室 | 105 |

PLAYER_ID = 1 / SYSTEM_ID = 0

### 2.1 キャラ別の証言の役割

| NPC | 証言の性質 | 主要 grants |
|---|---|---|
| エルマー | 余計なことを口走るが嘘はつかない。手がかりの起点 | ガサゴソ音、包み紙、ティルが怪しい |
| スミレん | 論理的。おやつ管理責任者。犯行時刻を絞る | おやつの管理表、高級チョコレート、衝動的な行動 |
| ノクちん | 占いで核心を突く。情緒的だが鋭い | 占いの暗示、ティルの朝の機嫌 |
| ティル | **犯人。嘘をつくがボロが出る** | （包み紙への過剰反応＝ティルが包装紙に反応） |
| ヴェリ | 静かな観察者。事実を淡々と。物的証言 | 深夜2時に甘い匂い、足音がティルに似ている |
| マリ | 協力的。夜の見回り担当。時刻の裏取り | マリの見回り、犯行は1時以降、朝の台所が散らかっていた |

---

## 3. 単語カード（cosine 検索のクエリ）

単語はそれ自体が MxBS セル（owner=PLAYER_ID, price=255 immortal）。プレイヤーが選択すると因子ベクトルが cosine 検索クエリになる。

### 3.1 スロット構成

| スロット | 役割 |
|---|---|
| WHO | 話題の対象（人物・モノ） |
| ACTION | プレイヤーの意図 |
| WHAT | 属性・詳細・証拠 |
| WHERE | 場所 |

### 3.2 初期配布単語（11個）

| id | text | slot |
|---|---|---|
| w_oyatsu | おやつ | WHO |
| w_hannin | 犯人 | WHO |
| w_minna | みんな | WHO |
| w_tabeta | 食べた | ACTION |
| w_mita | 見た | ACTION |
| w_shitteru | 知ってる | ACTION |
| w_dare | 誰 | ACTION |
| w_kinounoYoru | 昨日の夜 | WHAT |
| w_alibi | アリバイ | WHAT |
| w_shouko | 証拠 | WHAT |
| w_daidokoro | 台所 | WHERE |

### 3.3 入手可能単語（26個、grants で解放）

会話で NPC が grants したキーワードが新規単語カードとして追加される。代表例:

| text | slot | 主な grant 元 |
|---|---|---|
| ガサゴソ音 | WHAT | エルマー EL01 |
| プリン | WHO | エルマー EL02 |
| ティルが怪しい | WHO | エルマー EL03 |
| 包み紙 | WHAT | エルマー EL06 |
| おやつの管理表 | WHAT | スミレ SM01 |
| 高級チョコレート | WHO | スミレ SM06 / マリ MR05 |
| 衝動的な行動 | WHAT | スミレ SM07 / ノク NC04 |
| 占いの暗示 | WHAT | ノク NC01 |
| 深夜2時に甘い匂い | WHAT | ヴェリ VR04 |
| 足音がティルに似ている | WHO | ヴェリ VR07 |
| 犯行は1時以降 | WHAT | マリ MR03/MR06 |
| 朝の台所が散らかっていた | WHAT | マリ MR04 |

（全リストは `data.py` の `WORDS_GETTABLE` を参照）

---

## 4. 16 因子空間

おやつデモの 16 因子ベクトル（u8×16）。軸定義は Phase 0 検証時の `chatterfox_phase0.py` の `FACTOR_NAMES` を正とする。

| index | 因子名 | 意味 |
|---|---|---|
| 0 | topic_snack | おやつ・食べ物 |
| 1 | topic_time | 時間帯 |
| 2 | topic_place | 場所 |
| 3 | topic_person | 人物 |
| 4 | topic_evidence | 証拠・物証 |
| 5 | topic_alibi | アリバイ・行動 |
| 6 | action_ask | 聞く・教えて |
| 7 | action_suspect | 疑う・追及 |
| 8 | action_observe | 見た・気づいた |
| 9 | emotion_nervous | 動揺（NPC 側の反応傾向） |
| 10 | emotion_honest | 正直度 |
| 11 | emotion_deflect | はぐらかし度 |
| 12 | personality_open | 外向性（人に心を開くか・自分から話すか） |
| 13 | personality_impulsive | 衝動性 |
| 14 | reserved_1 | 未使用（全データ 0） |
| 15 | reserved_2 | 未使用（全データ 0） |

> **定義元**: `chatterfox_phase0.py` の `FACTOR_NAMES`。
> `data.py` の features 数値はここから移植されている。Phase 0 と data.py の全 features を機械照合した結果、共通 87 ID で 1byte の差異もなく完全一致（data.py 側に単語 `w_til_asa` が 1 件追加されているが、これも因子設計に整合）。
> `data.py` 自体に FACTOR_NAMES のコメントはないため、軸定義の参照は `chatterfox_phase0.py` を見ること。

### 4.1 archetype × factor[12,13] 検証

設計意図が実データに表れていることの確認。

**factor 13（衝動性）** — impulsive のみ高く、analyst/observer/mediator は 0。

| NPC | archetype | factor[13] 平均 |
|---|---|---|
| ティル | impulsive | 197.5 |
| エルマー | impulsive | 177.5 |
| ノクちん | contrarian | 104.3 |
| スミレん | analyst | 0.0 |
| ヴェリ | observer | 0.0 |
| マリ | mediator | 0.0 |

**factor 12（外向性 = openness）** — 誰にでも開く mediator/impulsive が高く、観察者 observer が最低。

| NPC | archetype | factor[12] 平均 | 設計意図 |
|---|---|---|---|
| マリ | mediator | 197.5 | 誰にでもオープンな仲裁者 → 高 |
| エルマー | impulsive | 194.2 | 社交的・口が軽い → 高 |
| ノクちん | contrarian | 135.7 | — |
| スミレん | analyst | 87.5 | 冷静で控えめ → 低め |
| ヴェリ | observer | 50.0 | 黙って観察する人 → 最低 |

personality_open は「外交性（extraversion）」ではなく「openness = 人に心を開くか・自分から話すか」の意。この定義では mediator マリが最高値なのは設計通り。

---

## 5. NPC セリフ（cerif）

### 5.1 セリフ構造

各 NPC は 7〜12 行のセリフを持つ（合計 51 行）。1 行の構造:

```python
{
    "id": "EL01",
    "npc_text": "ボク知らないよ〜！ でもね、昨日の夜、台所の方からガサゴソ音が……🦊",
    "features": [200, 100, 80, 0, 0, 0, 200, 0, 100, 0, 200, 0, 200, 180, 0, 0],
    "grants": ["ガサゴソ音"],   # このセリフで入手できるキーワード
    "requires": []             # このセリフを引くのに必要な所持キーワード
}
```

| フィールド | 役割 |
|---|---|
| id | NPC プレフィックス + 連番（EL/SM/NC/TL/VR/MR） |
| npc_text | 表示セリフ |
| features | 16 因子ベクトル（cosine 検索の対象） |
| grants | 入手キーワード（MxChatterFox は返却のみ。付与は MxYamAMVA） |
| requires | 前提キーワード（未充足なら候補から除外） |

> **requires の評価責務**: `requires` のフィルタリングは **MxChatterFox の `cascade_search` 内では行わない**。`cascade_search`（mxchatterfox_api.md）は純粋な cosine カスケード検索のみを担い、requires は関知しない。所持キーワードとの照合・候補からの除外は **MxYamAMVA 側**で、検索前にプレイヤー所持キーワードを確認して行う。concept §5.2 のコードブロックは requires チェックを cascade_search 内に描いているが、これは設計初期の図であり現行 API と異なる。現行は API doc の `cascade_search`（requires 引数なし）を正とする。

### 5.2 セリフ数

| NPC | 行数 |
|---|---|
| エルマー | 12 |
| スミレん | 8 |
| ノクちん | 7 |
| ティル | 8 |
| ヴェリ | 8 |
| マリ | 8 |
| **合計** | **51** |

### 5.3 フォールバック

各 NPC に 1 つ。カスケード検索が全 depth で失敗したときに返る archetype 準拠の「わからない」セリフ。

| NPC | フォールバック |
|---|---|
| エルマー | んー？ よくわかんないや。他のこと聞いて？🦊 |
| スミレん | ……その点について、私には判断材料がありません |
| ノクちん | ん〜♡ カードが沈黙してる……別のこと聞いて？ |
| ティル | えー、わかんない！ 他の人に聞いてよ〜💦 |
| ヴェリ | ……すみません、それについては何も。 |
| マリ | ごめんなさいね、それについては分からないわ |

---

## 6. 嘘つき NPC（ティル）の設計

ティルは犯人。MxChatterFox の「嘘つき NPC」原則（concept §5.3）に従い、**嘘のセリフが正しい因子ベクトルを持つ**ことで実装される。

```
TL02「犯人？ エルマーじゃないの？ あの子夜更かしだし✨ ……あたしは知らないけどね」
  → 「犯人」「誰」の話題で正しくヒットする（features の factor 3,11,13 が高い）
  → 嘘の情報（エルマーへの責任転嫁）がプレイヤーに渡る

TL07「ピンクの包装紙？ ……あ、あれはあたしのお店のじゃないし！ ……たぶん💦」
  → requires: ["包み紙"]。包み紙を入手してから問い詰めると過剰反応
  → grants: ["ティルが包装紙に反応"] = 決定的な手がかり
```

cosine 検索は嘘か真かを判定しない。プレイヤーが複数 NPC の証言の矛盾に気づく必要がある。

### 6.1 推理の収束ルート

```
エルマー: ガサゴソ音(2時半) + ティルが怪しい + 包み紙(ピンク)
  ↓
ヴェリ: 深夜2時に甘い匂い + 足音がティルに似ている
  ↓
マリ: 犯行は1時以降（時刻の裏取り）
  ↓
スミレ: 高級チョコレート + 衝動的な行動（impulsive な犯人像）
  ↓
ティル: 包み紙を問い詰める → ティルが包装紙に反応（過剰反応）
  ↓
accuse: ティル → ending_win
```

---

## 7. YamAMVA 連携

### 7.1 シナリオノード

おやつシナリオ（`oyatsu.yaml` / v1.1 分割版）で使われる YamAMVA ノード:

| ノード | 役割 |
|---|---|
| speaker / text | 固定セリフ（地の文・導入） |
| hearingmenu | 聞き込み先の選択（when 条件で accuse を解放） |
| chatterfox | 自由会話区間（MxChatterFox 呼び出し。npc_owner + exit_words） |
| do | state 操作（hearing_count++） |
| jump / incase | シーン遷移（v1.1 で file:scene 記法） |
| accusemenu | 犯人指名 |
| end | ゲーム終了 |

### 7.2 chatterfox ノード

```yaml
- chatterfox:
    npc_owner: 100        # この NPC の owner ID
    exit_words: ["戻る", "もういい"]   # 自由会話を抜けるキーワード
```

MxYamAMVA が npc_owner を MxChatterFox の `lines_owner` に渡し、その owner のセリフセルだけを cosine 検索対象にする。

### 7.3 進行フラグ

`hearing_count` を state で管理。1 人以上に聞き込みすると accuse メニューが解放される（`when: "hearing_count >= 1"`）。

---

## 8. bake パイプライン

```
data.py（NPC定義 + 単語 + セリフ + features 直書き）
    │
    │ ※おやつデモは features を手書きしているため
    │   bake_16element の自動マッピングは経由していない
    ↓
baker → MxBS DB（セリフセル owner=100〜105 + 単語セル owner=1）
    ↓
ランタイム: mxbs_chatterfox_search で cosine カスケード検索
```

> **注**: 通常の MxChatterFox パイプライン（concept §4）では cerif.json → bake_16element で因子付与するが、おやつデモは検証目的で features を `data.py` に直書きしている。プロダクション化する場合は bake_16element 経由に統一する。

### 8.1 baker が登録するセルの ACL / meta

baker が MxBS に登録する各セルの属性。嘘セリフ（ティル）も無実セリフも **同一の ACL**（mode / price）で登録される点が重要 — cosine 検索は嘘か真かを区別しないため（§6）。

| セル種別 | owner | price | mode | group_bits | meta |
|---|---|---|---|---|---|
| NPC セリフ | 100〜105 | 255 (immortal) | 0o744 | 0xFF | `{"type":"npc_line","line_id":"EL01","grants":[...],"requires":[...]}` |
| 初期単語 | 1 (PLAYER) | 255 (immortal) | 0o744 | 0xFF | `{"type":"keyword","slot":"WHO","word_id":"w_oyatsu","initial":true}` |
| 入手単語 | 1 (PLAYER) | 255 (immortal) | 0o700 | 0x00 | `{"type":"keyword","slot":"WHAT","word_id":"w_gasagoso","grant_name":"ガサゴソ音","initial":false}` |

- **price=255**: セリフ・単語は忘却対象外（immortal）
- **mode=0o744 / 0o700**: NPC セリフ・初期単語は owner 読み書き + group/other 読み取り可。入手単語は owner のみアクセス可（grant 前は非公開）
- **group_bits**: NPC セリフ・初期単語は 0xFF（全グループ可視）。入手単語は 0x00（grant されるまで不可視）
- **grant_name**: 入手単語のセルを grants の文字列から逆引きするためのキー。MxYamAMVA の `load_keywords`（mxyamamva_api.md）が参照

---

## 9. 検索パラメータ

`mxbs_chatterfox_search` のおやつデモ推奨値:

| パラメータ | 値 |
|---|---|
| threshold | 0.35 |
| top_k | 20 |
| num_words | 1〜3 |
| seed | 0（auto）or 固定（テスト時） |
| exclude_ids | 会話内で使用済みセリフを除外 |

---

## 10. ファイル構成

```
oyatsu_chatterfox/
├── data.py                  # NPC定義・単語・セリフ・features・fallback
├── baker.py                 # data.py → MxBS DB を焼く（§8 の実行主体）
├── main.py                  # デモ実行エントリ（YamAMVA + MxChatterFox 統合ループ）
├── game_state.py            # standalone モード用の状態管理（--standalone 時のみ使用）
├── preset.py                # 16因子プリセット定義（FACTOR_NAMES）
├── sample/
│   └── chatterfox_phase0.py # Phase 0 プロトタイプ（因子定義の原典）
└── scenario/
    ├── oyatsu.yaml           # v1.0 単一シナリオ
    ├── world.yaml            # v1.1 分割版（エントリ）
    └── scenes/
        ├── intro.yaml / lobby.yaml
        ├── hear_{elmar,sumire,noc,til,veri,mari}.yaml
        └── endings.yaml
```

会話データ（data.py → MxBS DB）はシナリオ分割と独立。DB 化された時点でランタイムはシナリオ構造を意識しない（scope 分割不要）。

---

## 11. 未確定・TODO

| 項目 | 状態 |
|---|---|
| factor 14, 15 の用途 | reserved_1 / reserved_2。未使用（全データ 0）。拡張予約 |
| bake_16element 経由への移行 | 現状 features 直書き。プロダクション化時に統一 |
| 会話ログ → MxBS 記録（「前に聞いたよね」） | 未実装（concept §7.2） |
| MxMindFox Mood 連動 | oyatsu_mood.json は定義済みだが本デモ未連動 |

---

*エルマー🦊 — 2026-05-29*
*「数字が目的を決め、嘘も正しい因子で焼けばちゃんとヒットする。」*
