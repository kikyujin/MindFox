# CLAUDE.md

## Project Overview

MxMindFox workspace — Rust crate for game NPC memory management using GM-defined factor vectors (u8x16) instead of language model embeddings. SQLite only, zero external AI dependencies at runtime.

## Architecture

- **mxbs crate** (`mxbs/`): Core memory engine. Cell CRUD, cosine similarity search, forgetting (decay), dream, inspire, reinforce, UNIX-style ACL, deferred scoring, save/load.
  - `src/lib.rs` — Core types and engine (Cell, MxBS, SearchBuilder, DreamBuilder, InspireBuilder)
  - `src/agents.rs` — AgentRegistry: thin helper for group_bits/mode wiring
  - `src/preset.rs` — Preset loading from JSON, scoring prompt generation, LLM response parsing
- **mxmindfox crate** (`mxmindfox/`): Orchestration layer, currently a skeleton.
- **docs/** — Design documents (mxbs_concept.md, mxbs_spec.md). Authoritative for design decisions.

## Build & Test

```bash
cargo test -p mxbs        # Run all MxBS tests (34 tests)
cargo check               # Check both crates
```

Rust edition 2024 (requires rustc 1.85+). Currently on rustc 1.94.0.

## Key Design Decisions

- Factor vectors are u8x16 (16 bytes), not f32 embeddings. MxBS does NOT do scoring — external LLM/rules score text, MxBS stores and searches the results.
- `from` is a SQL reserved word — always double-quoted in queries (`"from"`).
- features BLOB is exactly 16 bytes. All-zero = unscored. One-way transition only (zero -> scored, never overwrite).
- SQLite INTEGER is i64. u32/u64 values are cast to i64 for storage, same cast on read.
- ACL uses UNIX mode (u16) + group bitflag (u64). `get_perm()` is the common helper.
- AgentRegistry does NOT own MxBS — takes `&MxBS` references to avoid lifetime complexity.
- `serde_json` is used only for Preset JSON loading. Cell/MxBS core has no serde dependency.

## Dependencies

- `rusqlite` with `bundled` + `backup` features
- `serde_json` (preset loading only)

## Conventions

- Builder pattern for search/dream/inspire queries
- All IDs are integer types (no strings in core)
- Tests use `:memory:` SQLite databases
- Japanese text in tests is intentional (language-independent factor vectors)
