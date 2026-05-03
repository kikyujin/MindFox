# Page One Demo — Decay Quantitative Test

Card game with zero LLM dependency. Tests MxBS forgetting mechanics.

## Requirements

- Python 3.10+
- libmxbs.dylib (build from workspace root: `cargo build --release`)

## Run

```bash
python main.py
```

## What it demonstrates

- MxBS forgetting: price x half-life decay
- Reinforce chain effect (remembering begets remembering)
- Character personality from memory alone (no LLM)
- 50 games, 419 turns in < 1 second
