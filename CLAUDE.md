# CLAUDE.md

## Project Overview

MxMindFox workspace — Rust crate for game NPC memory management using GM-defined factor vectors (u8x16) instead of language model embeddings. SQLite only, zero external AI dependencies at runtime.

## Architecture

- **mxbs crate** (`mxbs/`): Core memory engine. Cell CRUD, cosine similarity search, forgetting (decay), dream, inspire, reinforce, UNIX-style ACL, deferred scoring, save/load. Outputs both `lib` and `cdylib` (libmxbs.dylib/.so).
  - `src/lib.rs` — Core types and engine (Cell, MxBS, SearchBuilder, DreamBuilder, InspireBuilder)
  - `src/agents.rs` — AgentRegistry: thin helper for group_bits/mode wiring
  - `src/preset.rs` — Preset loading from JSON, scoring prompt generation, LLM response parsing
  - `src/chatterfox.rs` — MxChatterFox: cosine cascade search (backtracking N-word filter on top of MxBS search)
  - `src/yamamva.rs` — MxYamAMVA: game state management (keyword flags, grants/requires, ACL-based word visibility)
  - `src/ffi.rs` — C API (30 extern "C" functions). See mxbs_spec.md §15, docs/mxchatterfox_api.md, docs/mxyamamva_api.md
  - `python/mxbs_bridge.py` — Python ctypes wrapper for libmxbs (MxBSBridge + MxYamAMVAState)
  - `python/yamamva_bridge.py` — Python ctypes wrapper for libyamamva (YamAMVA scenario engine)
- **mxmindfox crate** (`mxmindfox/`): Orchestration layer, currently a skeleton.
- **demos/oyatsu_chatterfox/** — "おやつは誰がたべた（MxChatterFox版）": YAML-driven detective game (6 NPC × 51 lines). YamAMVA scenario + MxChatterFox cascade search + MxYamAMVA state management.
  - `scenario/oyatsu.yaml` — YamAMVA scenario (intro → lobby → hearing → chatterfox → accuse → ending)
  - `data.py` — NPC definitions, 51 NPC lines, 11+26 word cards, factor vectors
  - `baker.py` — Bakes data.py into MxBS cells (oyatsu_chatterfox.db, 88 cells)
  - `main.py` — CLI entry. Default: YamAMVA mode. `--standalone`: no YamAMVA. `--rust`: Rust cascade_search
  - `game_state.py` — Standalone mode only (deprecated, replaced by MxYamAMVAState)
  - `preset.py` — 16 factor names for the oyatsu scenario
- **demos/oyatsu/** — "AI館おやつデモ": social deduction game (7 AI characters, Ollama gemma4:26b). Uses mxbs_bridge.py for cross-game memory, Mood system, diplomacy_toward.
  - `characters.py` — Character dataclass (gender field, archetype-based target scoring)
  - `memory.py` — MxBS integration (Mood, diplomacy, store helpers)
  - `llm.py` — Ollama prompt builders (testimony, night_plot, ending comments)
  - `engine.py` — Game loop (night/morning/testimony/accusation phases)
  - `main.py` — Campaign runner (`--games N`)
- **demos/pageone/** — MxBS decay quantitative test. American Page One card game, LLM-zero (preset lines only). Tests price-based forgetting, reinforce chaining, half_life tuning.
  - `cards.py` — Card/Deck (52 cards, shuffle, draw)
  - `characters.py` — 6 characters with per-character price (70-220) and reinforce factor
  - `lines.py` — Preset line dictionary (no LLM)
  - `memory.py` — MxBS integration (rule injection, search, reinforce, callout)
  - `engine.py` — Game loop (card play, special cards, pageone check, penalty)
  - `main.py` — CLI entry (`--games N --half-life H --threshold T --seed S`)
- **docs/** — Design documents (mxbs_concept.md, mxbs_spec.md, oyatsu_spec.md, pageone_spec.md). Authoritative for design decisions.

## Build & Test

```bash
cargo test -p mxbs        # Run all MxBS tests (52 unit + 9 FFI integration)
cargo test -p mxmindfox   # Run MxMindFox tests (47 tests)
cargo check               # Check both crates
cargo build -p mxbs       # Produces target/debug/libmxbs.dylib (cdylib)
cargo build -p mxbs --release  # Release build (required for Python bridge)

# oyatsu_chatterfox demo
cd demos/oyatsu_chatterfox
python3 baker.py           # Bake data → oyatsu_chatterfox.db
python3 main.py            # YamAMVA mode (Python cascade_search)
python3 main.py --rust     # YamAMVA mode (Rust cascade_search)
python3 main.py --standalone  # Standalone mode (no YamAMVA)
```

Rust edition 2024 (requires rustc 1.85+). Currently on rustc 1.94.0.

## Key Design Decisions

- Factor vectors are u8x16 (16 bytes), not f32 embeddings. MxBS does NOT do scoring — external LLM/rules score text, MxBS stores and searches the results.
- `from` is a SQL reserved word — always double-quoted in queries (`"from"`).
- features BLOB is exactly 16 bytes. All-zero = unscored. One-way transition only (zero -> scored, never overwrite).
- SQLite INTEGER is i64. u32/u64 values are cast to i64 for storage, same cast on read.
- ACL uses UNIX mode (u16) + group bitflag (u64). `get_perm()` is the common helper.
- AgentRegistry does NOT own MxBS — takes `&MxBS` references to avoid lifetime complexity.
- `serde` derive is used on MxBSConfig (Deserialize) and result types (Serialize) for FFI JSON serialization.
- MxChatterFox (`cascade_search`) is stateless — combines MxBS search() + cosine_similarity(), no internal state.
- MxYamAMVA (`MxYamAMVAState`) holds keyword flags + cell_id map. Does NOT depend on YamAMVA crate — communicates via JSON strings.
- `search([0u8; 16], ...)` with all-zero query returns all cells (non-vector mode). Used by prepare_chatterfox_lines.
- YamAMVA (external, [github.com/kikyujin/YAMAMVA](https://github.com/kikyujin/YAMAMVA)) is MIT OSS. MxBS has zero compile-time dependency on it — Python bridge only.

## Dependencies

- `rusqlite` with `bundled` + `backup` features
- `serde` with `derive` feature (config deserialization, result type serialization for FFI)
- `serde_json` (preset loading + FFI JSON output)

## Conventions

- Builder pattern for search/dream/inspire queries
- All IDs are integer types (no strings in core)
- Tests use `:memory:` SQLite databases
- Japanese text in tests is intentional (language-independent factor vectors)
