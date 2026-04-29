# CLAUDE.md

## Project Overview

MxMindFox workspace — Rust crate for game NPC memory management using GM-defined factor vectors (u8x16) instead of language model embeddings. SQLite only, zero external AI dependencies at runtime.

## Architecture

- **mxbs crate** (`mxbs/`): Core memory engine. Cell CRUD, cosine similarity search, forgetting (decay), dream, inspire, reinforce, UNIX-style ACL, deferred scoring, save/load. Outputs both `lib` and `cdylib` (libmxbs.dylib/.so).
  - `src/lib.rs` — Core types and engine (Cell, MxBS, SearchBuilder, DreamBuilder, InspireBuilder)
  - `src/agents.rs` — AgentRegistry: thin helper for group_bits/mode wiring
  - `src/preset.rs` — Preset loading from JSON, scoring prompt generation, LLM response parsing
  - `src/ffi.rs` — C API (17 extern "C" functions). See mxbs_spec.md §15
  - `python/mxbs_bridge.py` — Python ctypes wrapper for libmxbs
- **mxmindfox crate** (`mxmindfox/`): Orchestration layer, currently a skeleton.
- **demos/oyatsu/** — "AI館おやつデモ": social deduction game (7 AI characters, Ollama gemma4:26b). Uses mxbs_bridge.py for cross-game memory, Mood system, diplomacy_toward.
  - `characters.py` — Character dataclass (gender field, archetype-based target scoring)
  - `memory.py` — MxBS integration (Mood, diplomacy, store helpers)
  - `llm.py` — Ollama prompt builders (testimony, night_plot, ending comments)
  - `engine.py` — Game loop (night/morning/testimony/accusation phases)
  - `main.py` — Campaign runner (`--games N`)
- **docs/** — Design documents (mxbs_concept.md, mxbs_spec.md, oyatsu_spec.md). Authoritative for design decisions.

## Build & Test

```bash
cargo test -p mxbs        # Run all MxBS tests (34 unit + 9 FFI integration)
cargo check               # Check both crates
cargo build -p mxbs       # Produces target/debug/libmxbs.dylib (cdylib)
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

## Dependencies

- `rusqlite` with `bundled` + `backup` features
- `serde` with `derive` feature (config deserialization, result type serialization for FFI)
- `serde_json` (preset loading + FFI JSON output)

## Conventions

- Builder pattern for search/dream/inspire queries
- All IDs are integer types (no strings in core)
- Tests use `:memory:` SQLite databases
- Japanese text in tests is intentional (language-independent factor vectors)
