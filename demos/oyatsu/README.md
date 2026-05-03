# Oyatsu Demo — Social Deduction Game

7 AI characters play a snack-theft deduction game.

## Requirements

- Python 3.10+
- libmxbs.dylib (build from workspace root: `cargo build --release`)
- Ollama with gemma4:26b

## Run

```bash
python main.py
```

## What it demonstrates

- Python ctypes bridge to MxBS
- compute_diplomacy_toward (trust-based testimony)
- Cross-game memory (3-game campaign with forgetting)
- ACL: criminals' secret conversations (mode=0o770)
