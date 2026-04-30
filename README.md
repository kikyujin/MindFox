# MxMindFox Workspace

Multi-agent memory middleware for game NPCs.
Uses GM-defined 16-byte factor vectors instead of language model embeddings.

## Crates

| Crate | Description |
|---|---|
| **mxbs** | Factor-vector memory management (u8x16, SQLite only) |
| **mxmindfox** | Multi-agent orchestration layer (planned) |

## MxBS — Quick Start

```rust
use mxbs::{MxBS, MxBSConfig, Cell, AgentRegistry, FACTOR_DIM};

// Open an in-memory database
let mxbs = MxBS::open(":memory:", MxBSConfig::default())?;

// Register agents
let mut reg = AgentRegistry::new();
reg.register("teson", "テソン")?;
reg.register("jihun", "ジフン")?;

// Store a public memory (visible to all agents)
let features = [180, 200, 50, 220, 100, 80, 160, 190, 140, 70, 200, 130, 80, 170, 110, 150];
reg.store_public(&mxbs, 1, "teson", "ジフンと密約を交わした", features, 90)?;

// Store a private memory (owner only)
reg.store_private(&mxbs, 1, "teson", "内心ではジフンを信用していない", features, 120)?;

// Search from an agent's perspective
let results = reg.search(&mxbs, "teson", features, 1)?;

// Dream: surface buried but important memories
let dreams = reg.dream(&mxbs, "teson", 10)?;

// Save to file
mxbs.save_to("save.db")?;
```

## Key Features

- **Factor vectors**: u8x16 (16 bytes) per cell, not f32x1024 embeddings
- **SQLite only**: no ONNX, no sqlite-vec, no external models
- **UNIX-style ACL**: owner/group/other permissions with rwx bits
- **Forgetting**: price x decay over turns, configurable half-life
- **Dream**: surfaces buried important memories (zero LLM cost)
- **Deferred scoring**: store text first, score with LLM later
- **Preset system**: GM-designed factor axes, LLM scoring prompts included

## Dependencies

- `rusqlite` (bundled SQLite)
- `serde_json` (preset JSON loading only)

## Project Structure

```
mxmindfox-workspace/
├── mxbs/                  # MxBS crate
│   ├── src/
│   │   ├── lib.rs         # Core: Cell, MxBS, search, dream, inspire
│   │   ├── agents.rs      # AgentRegistry helper
│   │   ├── preset.rs      # Preset loading + scoring prompts
│   │   └── ffi.rs         # C API (17 extern "C" functions)
│   └── python/
│       └── mxbs_bridge.py # Python ctypes wrapper for libmxbs
├── mxmindfox/             # Orchestration layer (planned)
├── docs/                  # Design documents
│   ├── mxbs_concept.md    # Design philosophy
│   ├── mxbs_spec.md       # Full specification
│   ├── pageone_spec.md    # Page One demo spec (decay test)
│   └── sengoku_report.md  # Sengoku SIM technical report
└── demos/
    ├── sengoku/           # Sengoku SIM (Rust direct, rule-based scoring)
    ├── oyatsu/            # Social deduction game (LLM: gemma4:26b)
    └── pageone/           # Page One card game (LLM-zero, decay test)
```

## Demos

| Demo | LLM | Purpose |
|------|-----|---------|
| **sengoku** | gemma4:e2b | Sengoku warlord SIM — Rust direct, rule-based scoring, morale patch |
| **oyatsu** | gemma4:26b | Social deduction with 7 AI characters, cross-game memory |
| **pageone** | None | Decay quantitative test — price-based forgetting over 50+ games |

## Docs

- [mxbs_concept.md](docs/mxbs_concept.md) — Why factor vectors instead of embeddings
- [mxbs_spec.md](docs/mxbs_spec.md) — Full API specification
- [sengoku_report.md](docs/sengoku_report.md) — Sengoku SIM technical report
- [pageone_spec.md](docs/pageone_spec.md) — Page One demo: decay test design

## License

MIT — See [LICENSE](LICENSE) for details.
