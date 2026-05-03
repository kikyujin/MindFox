# Sengoku SIM Demo

5-nation warlord simulation using MxBS with rule-based scoring.

## Requirements

- Rust (2024 edition)
- Ollama with gemma4:e2b (for LLM-assisted mode)

## Run

```bash
cargo run --release
```

## What it demonstrates

- MxBS search/reinforce for decision-making context
- Rule-based factor scoring (no LLM needed for scoring)
- Mood-based attack thresholds (morale patch)
- Memory-driven character arcs (aggression accumulates over turns)
