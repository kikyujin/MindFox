# oyatsu_chatterfox — おやつを食べたのは誰だ（MxChatterFox版）

6NPC x 51 lines の聞き込み推理ゲーム。YAML シナリオ駆動 + cosine カスケード検索。

## Architecture

```
YamAMVA (scenario/oyatsu.yaml)
  │  YAML シナリオ制御: intro → lobby → hearing → accuse → ending
  │
  ├─ speaker / hearingmenu / accusemenu  → CLI 表示 & 入力
  │
  └─ chatterfox node (BLOCKING)
       │
       ├─ MxChatterFox (cascade_search)  → cosine バックトラック検索
       ├─ MxYamAMVA (process_grants)     → キーワードフラグ管理 + ACL 変更
       └─ MxBS (search / store / ACL)    → SQLite セルストレージ
```

## Setup

```bash
# 1. Build libraries
cargo build -p mxbs --release                    # libmxbs.dylib
cd ~/work/YAMAMVA && cargo build --release        # libyamamva.dylib

# 2. Bake data into MxBS database
cd demos/oyatsu_chatterfox
python3 baker.py                                  # → oyatsu_chatterfox.db (88 cells)
```

## Run

```bash
python3 main.py                # YamAMVA mode, Python cascade_search
python3 main.py --rust         # YamAMVA mode, Rust cascade_search (all Rust)
python3 main.py --standalone   # Standalone mode (no YamAMVA)
python3 main.py --debug        # Show hit line IDs
python3 main.py --threshold 0.3  # Change cosine threshold (default: 0.35)
```

## How to play

1. ロビーで NPC を選ぶ（番号入力）
2. 単語を入力して会話（スペース区切りで1〜3語）
3. `words` で所持単語カードを確認
4. `back` でロビーに戻る
5. 1人以上聞き込むと「犯人を指名する」が出現
6. 正しい犯人を当てればクリア

## Files

| File | Description |
|------|-------------|
| `main.py` | CLI entry. YamAMVA / standalone 両モード |
| `data.py` | 6NPC定義, 51セリフ, 11+26単語カード, 因子ベクトル |
| `baker.py` | data.py → MxBS cells (oyatsu_chatterfox.db) |
| `scenario/oyatsu.yaml` | YamAMVA シナリオ定義 |
| `preset.py` | 16因子名 |
| `game_state.py` | standalone mode 用（deprecated） |

## NPC & ID Map

| Key | Name | Owner ID | Role |
|-----|------|----------|------|
| elmar | エルマー | 100 | innocent |
| sumire | スミレ | 101 | innocent |
| noc | ノクちん | 102 | innocent |
| til | ティル | 103 | **culprit** |
| veri | ヴェリ | 104 | innocent |
| mari | マリ | 105 | innocent |

Player ID: 1 / System ID: 0

## Word cards

- **Initial (11)**: おやつ, 犯人, みんな, 食べた, 見た, 知ってる, 誰, 昨日の夜, アリバイ, 証拠, 台所
- **Gettable (26)**: NPC の grants で獲得。ガサゴソ音, プリン, ティルが怪しい, 包み紙, etc.

## Cascade search algorithm

```
Input: [word1, word2, word3] (1-3 words)

Try 3 words: search(word1) → filter(cos >= 0.35 with word2) → filter(word3)
  → hit? done
Try 2 words: search(word1) → filter(word2)
  → hit? done
Try 1 word:  search(word1)
  → hit? done
All missed → fallback line
```

## Related docs

- [MxChatterFox API](../../docs/mxchatterfox_api.md)
- [MxYamAMVA API](../../docs/mxyamamva_api.md)
- [MxChatterFox Concept](../../docs/mxchatterfox_concept.md)
- [MxYamAMVA Concept](../../docs/mxyamva_concept.md)
