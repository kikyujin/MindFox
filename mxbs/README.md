# mxbs

Factor-vector memory engine for game NPCs — 16-byte vectors, SQLite only, no embeddings.

Part of the [MxMindFox](https://github.com/kikyujin/MindFox) workspace.

## Features

- Store/search/forget/dream/inspire memory cells
- 16-byte factor vectors (GM-defined axes, not ML embeddings)
- UNIX-style ACL (owner/group/other permissions per cell)
- Price-based forgetting with configurable half-life
- Deferred scoring (store now, score later)
- C API (cdylib) + Python ctypes bridge
- SQLite only, zero external dependencies at runtime

## Quick Start

```rust
use mxbs::{MxBS, MxBSConfig};

let mxbs = MxBS::open(":memory:", MxBSConfig::default())?;
```

See the [workspace README](https://github.com/kikyujin/MindFox) for full examples.
