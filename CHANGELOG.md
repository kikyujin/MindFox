# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## MxMindFox

### [0.1.0] — 2026-05-02

Initial release. Multi-agent mood, decision, and diplomacy layer on MxBS.

#### Added
- `mood` module — `Mood`, `MoodPreset`, `MoodAxis`, `compute_mood`
- `diplomacy` module — `compute_diplomacy_toward`
- `threshold` module — `ThresholdRule`, `adjust_threshold`
- `decision` module — `remember` (Bernoulli/sigmoid), `sample` (Multinomial/softmax)
- `ffi` module — C API with 9 extern functions
- Python ctypes bridge (`mxmindfox_bridge.py`)
- 54 tests (mood 14, diplomacy 5, threshold 5, decision 11, ffi 12, python 7)

---

## MxBS

### [0.3.1] — 2026-05-02

MxMindFox integration support.

#### Changed
- Added `Deserialize` derive to `Cell` struct (1-line change, no logic change)
- Cleaned up clippy warnings for Rust 2024 edition

### [0.3.0] — 2026-04-29

Page One demo and quantitative decay testing.

#### Added
- `demos/pageone/` — LLM-zero card game demo (Matchbox AI principle)
- Quantitative decay test: 50 games, 419 turns, 3 conditions compared
- Proved: price + reinforce alone creates distinct character personalities

### [0.2.0] — 2026-04-29

C API and Python bridge.

#### Added
- `src/ffi.rs` — 17 extern "C" functions (mxbs_spec.md §15)
- `python/mxbs_bridge.py` — ctypes wrapper
- `python/test_bridge.py` — smoke tests
- `tests/ffi_test.rs` — 9 FFI integration tests
- `demos/oyatsu/` — social deduction game (7 characters, gemma4:26b)

#### Changed
- Added `serde` derives to Cell and config types
- Rust 2024 edition compliance (`#[unsafe(no_mangle)]`)

### [0.1.0] — 2026-04-28

Initial release. Full Rust implementation in one day. 34 tests passing.

#### Added
- `Cell` struct with builder pattern
- `MxBS::open()` with auto-schema creation
- `store` / `get` / `delete` (with permission checks)
- `cosine_similarity` (u8×16)
- `search` (builder pattern, ACL + filters + vector search)
- `dream` (buried_score ranking, immortal exclusion)
- `reinforce` (importance update, write permission bypass)
- `inspire` (factor vector neighbor search)
- `update_group_bits` / `update_mode` / `update_meta`
- `set_features` / `get_unscored` (deferred scoring)
- `save_to` (SQLite backup API)
- `stats` (total / scored / unscored)
- `pub mod preset` — Preset + scoring_prompt + parse_scores
- `pub mod agents` — AgentRegistry shortcuts
- `demos/sengoku/` — warlord SIM (Rust binary, rule-based scoring)
