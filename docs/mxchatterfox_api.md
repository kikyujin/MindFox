# MxChatterFox API Reference

> Cosine cascade search module for MxBS.
> Version: 0.1.0 | Date: 2026-05-28

## Overview

MxChatterFox implements backtracking N-word cosine cascade search on top of MxBS. It is stateless — all state lives in MxBS cells and the caller's exclude list.

### Algorithm

Given N word feature vectors (1-3 words):

1. Start with all N words
2. `search()` using word[0] as query, filtered by `owner` (NPC)
3. Filter results: each candidate must have `cosine_similarity >= threshold` with ALL N words
4. If no candidates survive, drop the last word (backtrack) and retry with N-1 words
5. Continue until hit or all words exhausted (fallback)

```
3-word query: [snack, ask, time]
  Try depth=3: search(snack) → filter(ask) → filter(time) → 0 hits
  Try depth=2: search(snack) → filter(ask) → 2 hits → pick one
```

---

## Rust API

### `mxbs/src/chatterfox.rs`

```rust
pub struct ChatterFoxResult {
    pub cell_id: u64,      // 0 if fallback
    pub text: String,
    pub meta: String,
    pub depth: usize,      // 0 if fallback
    pub is_fallback: bool,
}

pub fn cascade_search(
    db: &MxBS,
    word_features: &[[u8; 16]],    // 1-3 word vectors
    lines_owner: u32,              // NPC owner ID
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
    exclude_ids: &[u64],           // already-used cell IDs
    threshold: f32,                // cosine threshold (recommended: 0.35)
    top_k: usize,                  // search limit (recommended: 20)
    seed: u64,                     // 0 = auto
) -> Result<ChatterFoxResult, MxBSError>;
```

### Notes

- `word_features[0]` is used as the MxBS search query. Remaining words are cosine-filtered.
- `threshold` applies to ALL words, including word[0] (explicit filter, not relying on search ranking).
- `seed=0` uses system time nanoseconds. Fixed seed gives deterministic results.
- `exclude_ids` prevents same-line repetition within a conversation.

---

## C API

### `mxbs_chatterfox_search`

```c
const char* mxbs_chatterfox_search(
    MxBSHandle* h,
    const uint8_t* word_features_packed,  // num_words * 16 bytes, contiguous
    int num_words,                         // 1-3
    uint32_t lines_owner,
    uint32_t viewer_id,
    uint64_t viewer_groups,
    uint32_t current_turn,
    const char* exclude_ids_json,          // JSON array e.g. "[101,203]", or NULL
    float threshold,
    int top_k,
    uint64_t seed
);
// Returns: JSON string (free with mxbs_free_string)
//   Hit:      {"cell_id":123,"text":"...","meta":"...","depth":2,"is_fallback":false}
//   Fallback: {"cell_id":0,"text":"","meta":"","depth":0,"is_fallback":true}
//   Error:    NULL
```

### Packed features layout

```
word_features_packed for 3 words:
  [word0: 16 bytes][word1: 16 bytes][word2: 16 bytes]
  Total: num_words * 16 bytes
```

---

## Python API

### `MxBSBridge.chatterfox_search()`

```python
def chatterfox_search(
    self,
    word_features_list: list[list[int]],  # [[u8;16], ...]
    lines_owner: int,
    viewer_id: int,
    viewer_groups: int,
    current_turn: int,
    exclude_ids: list[int] | None = None,
    threshold: float = 0.35,
    top_k: int = 20,
    seed: int = 0,
) -> dict:
    # Returns: {"cell_id": int, "text": str, "meta": str, "depth": int, "is_fallback": bool}
```

---

## Tests

8 Rust unit tests in `mxbs/src/chatterfox.rs`:

| Test | Description |
|------|-------------|
| `test_single_word_hit` | 1-word search hits a matching cell |
| `test_cascade_2words` | 2-word cascade narrows to intersection |
| `test_cascade_3words` | 3-word cascade finds exact match |
| `test_backtrack` | 3-word miss → backtrack to 1-word hit |
| `test_full_fallback` | No match at any depth → is_fallback=true |
| `test_exclude_ids` | Excluded cells are not returned |
| `test_empty_db` | Empty database → fallback |
| `test_acl_respected` | Mode 0o700 cell invisible to non-owner |
