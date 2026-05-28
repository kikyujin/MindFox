# MxYamAMVA API Reference

> Game state management module for MxBS — keyword flags, grants/requires, ACL-based word visibility.
> Version: 0.1.0 | Date: 2026-05-28

## Overview

MxYamAMVA manages game progression state on top of MxBS. It handles:

- **Keyword flags** — tracks which keywords the player has discovered
- **Grants processing** — extracts grants from NPC line metadata, sets flags, changes MxBS cell ACL
- **Requires filtering** — filters NPC lines by prerequisite keywords
- **Keyword loading** — initializes state from baker-generated MxBS cells

### Dependency boundary

MxYamAMVA does NOT depend on the YamAMVA crate. It communicates with game code via JSON strings. YamAMVA drives the scenario; MxYamAMVA handles MxBS state changes triggered by scenario events.

```
YamAMVA (YAML scenario) ──exec()──> Game code ──JSON──> MxYamAMVA ──API──> MxBS
```

---

## Rust API

### `mxbs/src/yamamva.rs`

```rust
pub struct MxYamAMVAState {
    flags: HashSet<String>,
    keyword_cells: HashMap<String, u64>,  // grant_name → cell_id
}

impl MxYamAMVAState {
    pub fn new() -> Self;
    pub fn has_flag(&self, name: &str) -> bool;
    pub fn add_flag(&mut self, name: &str);
    pub fn flag_count(&self) -> usize;
    pub fn flags(&self) -> &HashSet<String>;
}
```

### Functions

```rust
// Check match rate of keywords (0.0-1.0)
pub fn keyword_gate(state: &MxYamAMVAState, check_keywords: &[String]) -> f32;

// Grant keywords: set flags + change MxBS cell mode (0o700 → 0o744)
pub fn keyword_grant(
    state: &mut MxYamAMVAState, db: &MxBS,
    grant_names: &[String], player_id: u32, player_groups: u64,
) -> Vec<String>;  // returns newly granted names

// Get cell IDs of NPC lines whose requires are satisfied
pub fn prepare_chatterfox_lines(
    state: &MxYamAMVAState, db: &MxBS,
    npc_owner: u32, viewer_id: u32, viewer_groups: u64, current_turn: u32,
) -> Result<Vec<u64>, MxBSError>;

// Extract grants from cascade_search result meta and process them
pub fn process_grants(
    state: &mut MxYamAMVAState, db: &MxBS,
    meta_json: &str, player_id: u32, player_groups: u64,
) -> Vec<String>;  // returns newly granted names

// Load keyword cells from baker-generated DB
pub fn load_keywords(
    state: &mut MxYamAMVAState, db: &MxBS,
    player_id: u32, player_groups: u64, current_turn: u32,
) -> Result<usize, MxBSError>;  // returns count of loaded keywords
```

### load_keywords behavior

Reads all cells owned by `player_id` with `meta.type == "keyword"`:

| meta.initial | Action |
|---|---|
| `true` | Set flag (word is available from start) + register cell_id |
| `false` | Register cell_id only (word becomes available via grants) |

The `grant_name` field in meta maps to the flag name. Falls back to `word_id` if `grant_name` is absent.

---

## C API

### Lifecycle

```c
MxYamAMVAHandle* mxbs_yamamva_new();
void mxbs_yamamva_free(MxYamAMVAHandle* state);
```

### Keyword operations

```c
// Match rate (0.0-1.0). check_json: '["keyword1","keyword2"]'
float mxbs_yamamva_keyword_gate(MxYamAMVAHandle* state, const char* check_json);

// Grant keywords. Returns JSON array of newly granted names.
const char* mxbs_yamamva_keyword_grant(
    MxYamAMVAHandle* state, MxBSHandle* db,
    const char* grant_json, uint32_t player_id, uint64_t player_groups);

// Get requires-satisfied line IDs. Returns JSON array of u64.
const char* mxbs_yamamva_prepare_lines(
    MxYamAMVAHandle* state, MxBSHandle* db,
    uint32_t npc_owner, uint32_t viewer_id, uint64_t viewer_groups, uint32_t current_turn);

// Process grants from cascade_search result meta. Returns JSON array of newly granted names.
const char* mxbs_yamamva_process_grants(
    MxYamAMVAHandle* state, MxBSHandle* db,
    const char* meta_json, uint32_t player_id, uint64_t player_groups);
```

### Flag queries

```c
int mxbs_yamamva_has_flag(MxYamAMVAHandle* state, const char* name);  // 1=yes, 0=no
int mxbs_yamamva_flag_count(MxYamAMVAHandle* state);
```

### Initialization

```c
// Load keyword cells from baker DB. Returns count of loaded keywords.
int mxbs_yamamva_load_keywords(
    MxYamAMVAHandle* state, MxBSHandle* db,
    uint32_t player_id, uint64_t player_groups, uint32_t current_turn);
```

All `const char*` return values must be freed with `mxbs_free_string()`.

---

## Python API

### `MxYamAMVAState`

```python
class MxYamAMVAState:
    def __init__(self, lib):               # lib = MxBSBridge._lib
    def keyword_gate(self, check: list[str]) -> float
    def keyword_grant(self, db_handle, grants: list[str],
                      player_id: int, player_groups: int) -> list[str]
    def prepare_lines(self, db_handle, npc_owner: int,
                      viewer_id: int, viewer_groups: int, current_turn: int) -> list[int]
    def process_grants(self, db_handle, meta_json: str,
                       player_id: int, player_groups: int) -> list[str]
    def has_flag(self, name: str) -> bool
    def flag_count(self) -> int
    def load_keywords(self, db_handle, player_id: int,
                      player_groups: int, current_turn: int) -> int
    def close(self)
```

Usage:
```python
from mxbs_bridge import MxBSBridge, MxYamAMVAState

db = MxBSBridge("oyatsu.db", half_life=80)
state = MxYamAMVAState(db._lib)
state.load_keywords(db._handle, player_id=1, player_groups=0xFF, current_turn=0)

rate = state.keyword_gate(["包み紙", "ティルが怪しい"])
newly = state.process_grants(db._handle, meta_json, player_id=1, player_groups=0xFF)
```

---

## YamAMVA Python Bridge

### `YamamvaBridge`

```python
from yamamva_bridge import YamamvaBridge

yamva = YamamvaBridge(yaml_str)                # load scenario from YAML string
yamva.register("speaker", CMD_SPEAKER)          # PASS node
yamva.register("hearingmenu", CMD_HEARING, blocking=True)  # BLOCKING node

cmd, info = yamva.exec()
# cmd: command_id or YamamvaBridge.END (-1)
# info: {"node_type": str, "node_json": dict, "elements": list[dict]}

yamva.set_result("elmar")                       # answer BLOCKING node
state_val = yamva.get_state("hearing_count")    # read scenario state
yamva.set_state("heard_elmar", True)            # write scenario state
save_json = yamva.save()                        # serialize for save/load
```

Requires: `libyamamva.dylib` built from `~/work/YAMAMVA` (`cargo build --release`).

---

## Baker cell format

### NPC line cell (meta)

```json
{"type": "npc_line", "line_id": "EL01", "grants": ["ガサゴソ音"], "requires": []}
```

| Field | Owner | mode | group_bits | price |
|---|---|---|---|---|
| NPC line | NPC_ID (100-105) | 0o744 | 0xFF | 255 (immortal) |

### Keyword cell (meta)

```json
{"type": "keyword", "word_id": "w_oyatsu", "initial": true}
{"type": "keyword", "word_id": "w_gasagoso", "grant_name": "ガサゴソ音", "initial": false}
```

| Kind | Owner | mode | group_bits | price |
|---|---|---|---|---|
| Initial word | PLAYER_ID (1) | 0o744 | 0xFF | 255 |
| Gettable word (locked) | PLAYER_ID (1) | 0o700 | 0x00 | 255 |
| Gettable word (unlocked) | PLAYER_ID (1) | 0o744 | 0xFF | 255 |

Grants processing changes mode 0o700 → 0o744 via `mxbs_update_mode()`.

---

## Tests

10 Rust unit tests in `mxbs/src/yamamva.rs`:

| Test | Description |
|------|-------------|
| `test_keyword_gate_partial` | 3/5 flags → returns 0.6 |
| `test_keyword_gate_empty` | Empty check → returns 1.0 |
| `test_keyword_grant_basic` | Grants 2 keywords, flags set |
| `test_keyword_grant_duplicate` | Second grant of same name → empty result |
| `test_prepare_lines_requires_filter` | Unsatisfied requires excluded; satisfied included |
| `test_process_grants_from_meta` | Extracts grants from meta JSON |
| `test_process_grants_empty` | Empty grants → no change |
| `test_load_keywords_from_baked_db` | Initial keywords flagged, gettable registered |
| `test_keyword_grant_updates_mode` | Mode changes from 0o700 to 0o744 |

Total test count: mxbs 61 (52 unit + 9 FFI) + mxmindfox 47 = **108 tests**.
