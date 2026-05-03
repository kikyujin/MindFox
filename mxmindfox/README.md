# mxmindfox

Multi-agent mood, decision and diplomacy layer for game NPCs — built on MxBS.

Part of the [MxMindFox](https://github.com/kikyujin/MindFox) workspace.

## Features

- Preset-driven mood computation (axes defined in game JSON, not hardcoded)
- Diplomacy: per-agent trust from memory cells
- Threshold adjustment (mood shifts decision boundaries)
- Probabilistic decisions with temperature (sigmoid + softmax)
- C API (cdylib) + Python ctypes bridge
- ~800 lines of Rust, no heavy dependencies

## Quick Start

```rust
use mxmindfox::{compute_mood, MoodPreset};

let preset = MoodPreset::from_json(include_str!("preset.json"))?;
let mood = compute_mood(&recent_cells, &preset, Some("warrior"));
```

See the [workspace README](https://github.com/kikyujin/MindFox) for full examples.
