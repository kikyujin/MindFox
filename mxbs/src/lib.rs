//! MxBS — Multitapps Extended Brain System
//!
//! Factor-vector memory management middleware for game NPCs.
//! Uses u8×16 factor vectors instead of language model embeddings.
//! Only depends on SQLite.

pub mod preset;
pub mod agents;
pub mod ffi;

pub use preset::{Preset, Axis, parse_scores, default_scores};
pub use agents::AgentRegistry;

use rusqlite::Connection;

pub const FACTOR_DIM: usize = 16;
pub const MAX_AGENTS: usize = 64;
pub const PRICE_IMMORTAL: u8 = 255;

// ─── Vector Math ───────────────────────────────────────────

pub fn cosine_similarity(a: &[u8; FACTOR_DIM], b: &[u8; FACTOR_DIM]) -> f32 {
    let mut dot: u32 = 0;
    let mut norm_a: u32 = 0;
    let mut norm_b: u32 = 0;
    for i in 0..FACTOR_DIM {
        let ai = a[i] as u32;
        let bi = b[i] as u32;
        dot += ai * bi;
        norm_a += ai * ai;
        norm_b += bi * bi;
    }
    if norm_a == 0 || norm_b == 0 {
        return 0.0;
    }
    dot as f32 / ((norm_a as f32).sqrt() * (norm_b as f32).sqrt())
}

// ─── Decay / Scoring ───────────────────────────────────────

fn decay(delta_turns: u32, half_life: u32) -> f32 {
    if half_life == 0 { return 0.0; }
    0.5_f32.powf(delta_turns as f32 / half_life as f32)
}

fn price_factor(price: u8) -> f32 {
    price as f32 / 255.0
}

fn effective_score(cosine: f32, importance: f32, price: u8, decay_val: f32) -> f32 {
    if price == PRICE_IMMORTAL {
        return cosine * importance;
    }
    cosine * importance * price_factor(price) * decay_val
}

fn buried_score(price: u8, decay_val: f32, importance: f32) -> f32 {
    if price == PRICE_IMMORTAL {
        return 0.0;
    }
    let inv_decay = (1.0 / decay_val.max(1e-6)).min(1000.0);
    price as f32 * inv_decay * importance
}

// ─── Cell ──────────────────────────────────────────────────

#[derive(serde::Serialize, serde::Deserialize)]
pub struct Cell {
    pub id: u64,
    pub owner: u32,
    pub from: u32,
    pub turn: u32,
    pub group_bits: u64,
    pub mode: u16,
    pub price: u8,
    pub importance: f32,
    pub text: String,
    pub features: [u8; FACTOR_DIM],
    pub meta: String,
}

impl Cell {
    pub fn new(owner: u32, text: impl Into<String>) -> Self {
        Self {
            id: 0,
            owner,
            from: owner,
            turn: 0,
            group_bits: 0,
            mode: 0o744,
            price: 100,
            importance: 1.0,
            text: text.into(),
            features: [0u8; FACTOR_DIM],
            meta: "{}".to_string(),
        }
    }

    pub fn from(mut self, from: u32) -> Self { self.from = from; self }
    pub fn turn(mut self, turn: u32) -> Self { self.turn = turn; self }
    pub fn group_bits(mut self, group_bits: u64) -> Self { self.group_bits = group_bits; self }
    pub fn mode(mut self, mode: u16) -> Self { self.mode = mode; self }
    pub fn price(mut self, price: u8) -> Self { self.price = price; self }
    pub fn importance(mut self, importance: f32) -> Self { self.importance = importance; self }
    pub fn features(mut self, features: [u8; FACTOR_DIM]) -> Self { self.features = features; self }
    pub fn meta(mut self, meta: impl Into<String>) -> Self { self.meta = meta.into(); self }
}

// ─── Result Types ──────────────────────────────────────────

#[derive(serde::Serialize)]
pub struct SearchResult {
    pub id: u64,
    pub text: String,
    pub cosine: f32,
    pub effective_score: f32,
    pub owner: u32,
    pub from: u32,
    pub turn: u32,
    pub price: u8,
    pub importance: f32,
    pub features: [u8; FACTOR_DIM],
    pub meta: String,
}

#[derive(serde::Serialize)]
pub struct DreamResult {
    pub id: u64,
    pub text: String,
    pub buried_score: f32,
    pub price: u8,
    pub importance: f32,
    pub decay: f32,
    pub turn: u32,
    pub owner: u32,
    pub from: u32,
    pub features: [u8; FACTOR_DIM],
    pub meta: String,
}

#[derive(serde::Serialize)]
pub struct InspireResult {
    pub id: u64,
    pub text: String,
    pub cosine: f32,
    pub owner: u32,
    pub turn: u32,
    pub features: [u8; FACTOR_DIM],
    pub meta: String,
}

#[derive(serde::Serialize)]
pub struct UnscoredCell {
    pub id: u64,
    pub text: String,
    pub owner: u32,
    pub turn: u32,
    pub meta: String,
}

#[derive(serde::Serialize)]
pub struct Stats {
    pub total: u64,
    pub scored: u64,
    pub unscored: u64,
}

// ─── Error ─────────────────────────────────────────────────

#[derive(Debug)]
pub enum MxBSError {
    Sqlite(rusqlite::Error),
    NotFound(u64),
    PermissionDenied,
    AlreadyScored(u64),
    InvalidImportance(f32),
    AgentNotFound(String),
    TooManyAgents,
    Io(String),
}

impl From<rusqlite::Error> for MxBSError {
    fn from(e: rusqlite::Error) -> Self { MxBSError::Sqlite(e) }
}

impl std::fmt::Display for MxBSError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MxBSError::Sqlite(e) => write!(f, "SQLite error: {e}"),
            MxBSError::NotFound(id) => write!(f, "Cell not found: {id}"),
            MxBSError::PermissionDenied => write!(f, "Permission denied"),
            MxBSError::AlreadyScored(id) => write!(f, "Cell already scored: {id}"),
            MxBSError::InvalidImportance(v) => write!(f, "Invalid importance value: {v}"),
            MxBSError::AgentNotFound(id) => write!(f, "Agent not found: {id}"),
            MxBSError::TooManyAgents => write!(f, "Too many agents (max 64)"),
            MxBSError::Io(msg) => write!(f, "IO error: {msg}"),
        }
    }
}

impl std::error::Error for MxBSError {}

// ─── Config ────────────────────────────────────────────────

#[derive(serde::Deserialize)]
pub struct MxBSConfig {
    pub half_life: u32,
}

impl Default for MxBSConfig {
    fn default() -> Self {
        Self { half_life: 8 }
    }
}

// ─── MxBS ──────────────────────────────────────────────────

pub struct MxBS {
    conn: Connection,
    config: MxBSConfig,
}

impl MxBS {
    pub fn open(db_path: &str, config: MxBSConfig) -> Result<Self, MxBSError> {
        let conn = Connection::open(db_path)?;
        let mxbs = Self { conn, config };
        mxbs.create_schema()?;
        Ok(mxbs)
    }

    fn create_schema(&self) -> Result<(), MxBSError> {
        self.conn.execute_batch("
            CREATE TABLE IF NOT EXISTS cells (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                owner       INTEGER NOT NULL,
                \"from\"    INTEGER NOT NULL,
                turn        INTEGER NOT NULL,
                group_bits  INTEGER NOT NULL DEFAULT 0,
                mode        INTEGER NOT NULL DEFAULT 484,
                price       INTEGER NOT NULL DEFAULT 100,
                importance  REAL    NOT NULL DEFAULT 1.0,
                text        TEXT    NOT NULL,
                features    BLOB    NOT NULL,
                meta        TEXT    DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_cells_owner ON cells(owner);
            CREATE INDEX IF NOT EXISTS idx_cells_turn ON cells(turn);

            CREATE TABLE IF NOT EXISTS mxbs_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO mxbs_meta (key, value) VALUES ('version', '0.1.0');
            INSERT OR IGNORE INTO mxbs_meta (key, value) VALUES ('factor_dim', '16');
        ")?;
        Ok(())
    }

    // ─── Row helper ────────────────────────────────────────

    fn row_to_cell(row: &rusqlite::Row) -> rusqlite::Result<Cell> {
        let features_blob: Vec<u8> = row.get(9)?;
        let mut features = [0u8; FACTOR_DIM];
        if features_blob.len() >= FACTOR_DIM {
            features.copy_from_slice(&features_blob[..FACTOR_DIM]);
        }
        Ok(Cell {
            id: row.get::<_, i64>(0)? as u64,
            owner: row.get::<_, i64>(1)? as u32,
            from: row.get::<_, i64>(2)? as u32,
            turn: row.get::<_, i64>(3)? as u32,
            group_bits: row.get::<_, i64>(4)? as u64,
            mode: row.get::<_, i64>(5)? as u16,
            price: row.get::<_, i64>(6)? as u8,
            importance: row.get::<_, f64>(7)? as f32,
            text: row.get(8)?,
            features,
            meta: row.get(10)?,
        })
    }

    fn load_all_cells(&self) -> Result<Vec<Cell>, MxBSError> {
        let mut stmt = self.conn.prepare(
            "SELECT id, owner, \"from\", turn, group_bits, mode, price, importance, text, features, meta
             FROM cells"
        )?;
        let cells = stmt.query_map([], Self::row_to_cell)?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(cells)
    }

    // ─── ACL ───────────────────────────────────────────────

    fn get_perm(cell: &Cell, actor_id: u32, actor_groups: u64) -> u16 {
        if actor_id == cell.owner {
            (cell.mode >> 6) & 0o7
        } else if cell.group_bits & actor_groups != 0 {
            (cell.mode >> 3) & 0o7
        } else {
            cell.mode & 0o7
        }
    }

    fn check_read(cell: &Cell, viewer_id: u32, viewer_groups: u64) -> bool {
        Self::get_perm(cell, viewer_id, viewer_groups) & 0b100 != 0
    }

    fn can_write(cell: &Cell, requester: u32, req_groups: u64) -> bool {
        Self::get_perm(cell, requester, req_groups) & 0b010 != 0
    }

    fn can_execute(cell: &Cell, requester: u32, req_groups: u64) -> bool {
        Self::get_perm(cell, requester, req_groups) & 0b001 != 0
    }

    // ─── CRUD ──────────────────────────────────────────────

    pub fn store(&self, cell: Cell) -> Result<u64, MxBSError> {
        self.conn.execute(
            "INSERT INTO cells (owner, \"from\", turn, group_bits, mode, price, importance, text, features, meta)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
            rusqlite::params![
                cell.owner as i64,
                cell.from as i64,
                cell.turn as i64,
                cell.group_bits as i64,
                cell.mode as i64,
                cell.price as i64,
                cell.importance as f64,
                cell.text,
                cell.features.as_slice(),
                cell.meta,
            ],
        )?;
        Ok(self.conn.last_insert_rowid() as u64)
    }

    pub fn get(&self, cell_id: u64) -> Result<Cell, MxBSError> {
        let mut stmt = self.conn.prepare(
            "SELECT id, owner, \"from\", turn, group_bits, mode, price, importance, text, features, meta
             FROM cells WHERE id = ?1"
        )?;

        let cell = stmt.query_row([cell_id as i64], Self::row_to_cell)
            .map_err(|e| match e {
                rusqlite::Error::QueryReturnedNoRows => MxBSError::NotFound(cell_id),
                other => MxBSError::Sqlite(other),
            })?;

        Ok(cell)
    }

    pub fn delete(&self, cell_id: u64, requester: u32, req_groups: u64) -> Result<bool, MxBSError> {
        let cell = self.get(cell_id)?;

        if !Self::can_execute(&cell, requester, req_groups) {
            return Ok(false);
        }

        self.conn.execute("DELETE FROM cells WHERE id = ?1", [cell_id as i64])?;
        Ok(true)
    }

    // ─── Search ────────────────────────────────────────────

    pub fn search(&self, query_features: [u8; FACTOR_DIM],
                  viewer_id: u32, viewer_groups: u64) -> SearchBuilder<'_> {
        SearchBuilder {
            mxbs: self,
            query_features: Some(query_features),
            viewer_id,
            viewer_groups,
            current_turn: 0,
            decay_factor_exp: 1.0,
            limit: 10,
            filter_owner: None,
            filter_from: None,
            after_turn: None,
            before_turn: None,
        }
    }

    // ─── Dream ─────────────────────────────────────────────

    pub fn dream(&self, viewer_id: u32, viewer_groups: u64) -> DreamBuilder<'_> {
        DreamBuilder {
            mxbs: self,
            viewer_id,
            viewer_groups,
            current_turn: 0,
            limit: 3,
        }
    }

    // ─── Reinforce ─────────────────────────────────────────

    pub fn reinforce(&self, cell_id: u64, importance: f32) -> Result<(), MxBSError> {
        if !(0.0..=10.0).contains(&importance) {
            return Err(MxBSError::InvalidImportance(importance));
        }
        let updated = self.conn.execute(
            "UPDATE cells SET importance = ?1 WHERE id = ?2",
            rusqlite::params![importance as f64, cell_id as i64],
        )?;
        if updated == 0 {
            return Err(MxBSError::NotFound(cell_id));
        }
        Ok(())
    }

    // ─── Inspire ───────────────────────────────────────────

    pub fn inspire(&self, cell_id: u64) -> InspireBuilder<'_> {
        InspireBuilder {
            mxbs: self,
            cell_id,
            limit: 5,
            viewer_id: None,
            viewer_groups: 0,
        }
    }

    // ─── Update ────────────────────────────────────────────

    pub fn update_group_bits(&self, cell_id: u64, new_group_bits: u64,
                             requester: u32, req_groups: u64) -> Result<bool, MxBSError> {
        let cell = self.get(cell_id)?;
        if !Self::can_write(&cell, requester, req_groups) {
            return Ok(false);
        }
        self.conn.execute(
            "UPDATE cells SET group_bits = ?1 WHERE id = ?2",
            rusqlite::params![new_group_bits as i64, cell_id as i64],
        )?;
        Ok(true)
    }

    pub fn update_mode(&self, cell_id: u64, new_mode: u16,
                       requester: u32, req_groups: u64) -> Result<bool, MxBSError> {
        let cell = self.get(cell_id)?;
        if !Self::can_write(&cell, requester, req_groups) {
            return Ok(false);
        }
        self.conn.execute(
            "UPDATE cells SET mode = ?1 WHERE id = ?2",
            rusqlite::params![new_mode as i64, cell_id as i64],
        )?;
        Ok(true)
    }

    pub fn update_meta(&self, cell_id: u64, new_meta: &str,
                       requester: u32, req_groups: u64) -> Result<bool, MxBSError> {
        let cell = self.get(cell_id)?;
        if !Self::can_write(&cell, requester, req_groups) {
            return Ok(false);
        }
        self.conn.execute(
            "UPDATE cells SET meta = ?1 WHERE id = ?2",
            rusqlite::params![new_meta, cell_id as i64],
        )?;
        Ok(true)
    }

    // ─── Deferred Scoring ──────────────────────────────────

    pub fn get_unscored(&self) -> Result<Vec<UnscoredCell>, MxBSError> {
        let zero_features = [0u8; FACTOR_DIM];
        let mut stmt = self.conn.prepare(
            "SELECT id, text, owner, turn, meta FROM cells WHERE features = ?1 ORDER BY turn ASC"
        )?;
        let results = stmt.query_map([zero_features.as_slice()], |row| {
            Ok(UnscoredCell {
                id: row.get::<_, i64>(0)? as u64,
                text: row.get(1)?,
                owner: row.get::<_, i64>(2)? as u32,
                turn: row.get::<_, i64>(3)? as u32,
                meta: row.get(4)?,
            })
        })?.collect::<Result<Vec<_>, _>>()?;
        Ok(results)
    }

    pub fn set_features(&self, cell_id: u64, features: [u8; FACTOR_DIM]) -> Result<(), MxBSError> {
        let cell = self.get(cell_id)?;
        if cell.features != [0u8; FACTOR_DIM] {
            return Err(MxBSError::AlreadyScored(cell_id));
        }
        self.conn.execute(
            "UPDATE cells SET features = ?1 WHERE id = ?2",
            rusqlite::params![features.as_slice(), cell_id as i64],
        )?;
        Ok(())
    }

    // ─── Save ──────────────────────────────────────────────

    pub fn save_to(&self, dest_path: &str) -> Result<(), MxBSError> {
        let mut dst = Connection::open(dest_path)?;
        let backup = rusqlite::backup::Backup::new(&self.conn, &mut dst)?;
        backup.run_to_completion(5, std::time::Duration::from_millis(250), None)?;
        Ok(())
    }

    // ─── Stats ─────────────────────────────────────────────

    pub fn stats(&self) -> Result<Stats, MxBSError> {
        let total: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM cells", [], |row| row.get(0)
        )?;
        let zero_features = [0u8; FACTOR_DIM];
        let unscored: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM cells WHERE features = ?1",
            [zero_features.as_slice()], |row| row.get(0)
        )?;
        Ok(Stats {
            total: total as u64,
            unscored: unscored as u64,
            scored: (total - unscored) as u64,
        })
    }
}

// ─── SearchBuilder ─────────────────────────────────────────

pub struct SearchBuilder<'a> {
    mxbs: &'a MxBS,
    query_features: Option<[u8; FACTOR_DIM]>,
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
    decay_factor_exp: f32,
    limit: usize,
    filter_owner: Option<u32>,
    filter_from: Option<u32>,
    after_turn: Option<u32>,
    before_turn: Option<u32>,
}

impl<'a> SearchBuilder<'a> {
    pub fn current_turn(mut self, t: u32) -> Self { self.current_turn = t; self }
    pub fn decay_factor(mut self, f: f32) -> Self { self.decay_factor_exp = f; self }
    pub fn limit(mut self, n: usize) -> Self { self.limit = n; self }
    pub fn owner(mut self, id: u32) -> Self { self.filter_owner = Some(id); self }
    pub fn from(mut self, id: u32) -> Self { self.filter_from = Some(id); self }
    pub fn after_turn(mut self, t: u32) -> Self { self.after_turn = Some(t); self }
    pub fn before_turn(mut self, t: u32) -> Self { self.before_turn = Some(t); self }

    pub fn exec(self) -> Result<Vec<SearchResult>, MxBSError> {
        let cells = self.mxbs.load_all_cells()?;

        let query = self.query_features.unwrap_or([0u8; FACTOR_DIM]);
        let is_vector_search = query != [0u8; FACTOR_DIM];

        let mut results: Vec<SearchResult> = Vec::new();

        for cell in &cells {
            if !MxBS::check_read(cell, self.viewer_id, self.viewer_groups) {
                continue;
            }
            if let Some(o) = self.filter_owner && cell.owner != o { continue; }
            if let Some(f) = self.filter_from && cell.from != f { continue; }
            if let Some(t) = self.after_turn && cell.turn < t { continue; }
            if let Some(t) = self.before_turn && cell.turn > t { continue; }

            let delta = self.current_turn.saturating_sub(cell.turn);
            let d = if cell.price == PRICE_IMMORTAL { 1.0 }
                    else { decay(delta, self.mxbs.config.half_life) };
            let effective_decay = d.powf(self.decay_factor_exp);

            if is_vector_search {
                if cell.features == [0u8; FACTOR_DIM] { continue; }
                let cos = cosine_similarity(&query, &cell.features);
                let score = effective_score(cos, cell.importance, cell.price, effective_decay);
                results.push(SearchResult {
                    id: cell.id, text: cell.text.clone(), cosine: cos,
                    effective_score: score, owner: cell.owner, from: cell.from,
                    turn: cell.turn, price: cell.price, importance: cell.importance,
                    features: cell.features, meta: cell.meta.clone(),
                });
            } else {
                let score = cell.importance * price_factor(cell.price) * effective_decay;
                results.push(SearchResult {
                    id: cell.id, text: cell.text.clone(), cosine: 0.0,
                    effective_score: score, owner: cell.owner, from: cell.from,
                    turn: cell.turn, price: cell.price, importance: cell.importance,
                    features: cell.features, meta: cell.meta.clone(),
                });
            }
        }

        results.sort_by(|a, b| b.effective_score.partial_cmp(&a.effective_score)
            .unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(self.limit);
        Ok(results)
    }
}

// ─── DreamBuilder ──────────────────────────────────────────

pub struct DreamBuilder<'a> {
    mxbs: &'a MxBS,
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
    limit: usize,
}

impl<'a> DreamBuilder<'a> {
    pub fn current_turn(mut self, t: u32) -> Self { self.current_turn = t; self }
    pub fn limit(mut self, n: usize) -> Self { self.limit = n; self }

    pub fn exec(self) -> Result<Vec<DreamResult>, MxBSError> {
        let cells = self.mxbs.load_all_cells()?;

        let mut results: Vec<DreamResult> = Vec::new();

        for cell in &cells {
            if cell.price == PRICE_IMMORTAL { continue; }
            if cell.features == [0u8; FACTOR_DIM] { continue; }
            if !MxBS::check_read(cell, self.viewer_id, self.viewer_groups) { continue; }

            let delta = self.current_turn.saturating_sub(cell.turn);
            let d = decay(delta, self.mxbs.config.half_life);
            let bs = buried_score(cell.price, d, cell.importance);

            results.push(DreamResult {
                id: cell.id, text: cell.text.clone(), buried_score: bs,
                price: cell.price, importance: cell.importance, decay: d,
                turn: cell.turn, owner: cell.owner, from: cell.from,
                features: cell.features, meta: cell.meta.clone(),
            });
        }

        results.sort_by(|a, b| b.buried_score.partial_cmp(&a.buried_score)
            .unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(self.limit);
        Ok(results)
    }
}

// ─── InspireBuilder ────────────────────────────────────────

pub struct InspireBuilder<'a> {
    mxbs: &'a MxBS,
    cell_id: u64,
    limit: usize,
    viewer_id: Option<u32>,
    viewer_groups: u64,
}

impl<'a> InspireBuilder<'a> {
    pub fn limit(mut self, n: usize) -> Self { self.limit = n; self }
    pub fn viewer(mut self, viewer_id: u32, viewer_groups: u64) -> Self {
        self.viewer_id = Some(viewer_id);
        self.viewer_groups = viewer_groups;
        self
    }

    pub fn exec(self) -> Result<Vec<InspireResult>, MxBSError> {
        let source = self.mxbs.get(self.cell_id)?;
        if source.features == [0u8; FACTOR_DIM] {
            return Ok(vec![]);
        }

        let cells = self.mxbs.load_all_cells()?;
        let mut results: Vec<InspireResult> = Vec::new();

        for cell in &cells {
            if cell.id == self.cell_id { continue; }
            if cell.features == [0u8; FACTOR_DIM] { continue; }
            if let Some(vid) = self.viewer_id
                && !MxBS::check_read(cell, vid, self.viewer_groups) { continue; }

            let cos = cosine_similarity(&source.features, &cell.features);
            results.push(InspireResult {
                id: cell.id, text: cell.text.clone(), cosine: cos,
                owner: cell.owner, turn: cell.turn,
                features: cell.features, meta: cell.meta.clone(),
            });
        }

        results.sort_by(|a, b| b.cosine.partial_cmp(&a.cosine)
            .unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(self.limit);
        Ok(results)
    }
}

// ─── Tests ─────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn mem() -> MxBS {
        MxBS::open(":memory:", MxBSConfig::default()).unwrap()
    }

    // --- Step 1 tests ---

    #[test]
    fn test_store_and_get() {
        let m = mem();
        let id = m.store(
            Cell::new(1, "テスト記憶")
                .from(2).turn(1).group_bits(0b11).mode(0o744).price(50)
                .features([10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160])
        ).unwrap();

        let cell = m.get(id).unwrap();
        assert_eq!(cell.owner, 1);
        assert_eq!(cell.from, 2);
        assert_eq!(cell.turn, 1);
        assert_eq!(cell.group_bits, 0b11);
        assert_eq!(cell.mode, 0o744);
        assert_eq!(cell.price, 50);
        assert_eq!(cell.text, "テスト記憶");
        assert_eq!(cell.features[0], 10);
        assert_eq!(cell.features[15], 160);
    }

    #[test]
    fn test_store_default_features() {
        let m = mem();
        let id = m.store(Cell::new(1, "未スコアリング").turn(1)).unwrap();
        let cell = m.get(id).unwrap();
        assert_eq!(cell.features, [0u8; 16]);
    }

    #[test]
    fn test_delete_with_permission() {
        let m = mem();
        let id = m.store(
            Cell::new(1, "削除テスト").turn(1).mode(0o744)
        ).unwrap();

        assert!(m.delete(id, 1, 0).unwrap());
        assert!(matches!(m.get(id), Err(MxBSError::NotFound(_))));
    }

    #[test]
    fn test_delete_permission_denied() {
        let m = mem();
        let id = m.store(
            Cell::new(1, "保護セル").turn(1).mode(0o444)
        ).unwrap();

        assert!(!m.delete(id, 1, 0).unwrap());
        assert!(m.get(id).is_ok());
    }

    #[test]
    fn test_not_found() {
        let m = mem();
        assert!(matches!(m.get(999), Err(MxBSError::NotFound(999))));
    }

    // --- Step 2 tests ---

    #[test]
    fn test_cosine_identical() {
        let a = [100, 200, 50, 150, 80, 120, 90, 170, 60, 130, 40, 110, 70, 160, 30, 140];
        assert!((cosine_similarity(&a, &a) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_cosine_zero_vector() {
        let a = [100; FACTOR_DIM];
        let z = [0u8; FACTOR_DIM];
        assert_eq!(cosine_similarity(&a, &z), 0.0);
    }

    #[test]
    fn test_search_basic() {
        let m = mem();
        let features_a = [200, 180, 100, 50, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110];
        let features_b = [50, 30, 200, 180, 120, 170, 30, 40, 150, 200, 40, 160, 180, 50, 170, 60];

        m.store(Cell::new(1, "外交的圧力").turn(1).mode(0o744).price(80).features(features_a)).unwrap();
        m.store(Cell::new(1, "経済政策").turn(1).mode(0o744).price(80).features(features_b)).unwrap();

        let query = [190, 170, 110, 60, 70, 50, 130, 150, 80, 40, 150, 90, 60, 120, 80, 100];
        let results = m.search(query, 1, 0).current_turn(1).limit(2).exec().unwrap();
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].text, "外交的圧力");
    }

    #[test]
    fn test_search_acl() {
        let m = mem();
        let f = [100; FACTOR_DIM];
        m.store(Cell::new(1, "秘密").turn(1).mode(0o700).price(80).features(f)).unwrap();
        m.store(Cell::new(1, "公開").turn(1).mode(0o744).price(80).features(f)).unwrap();

        let results = m.search(f, 2, 0).current_turn(1).limit(10).exec().unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].text, "公開");
    }

    #[test]
    fn test_search_skips_unscored() {
        let m = mem();
        m.store(Cell::new(1, "未スコアリング").turn(1).mode(0o744).price(80)).unwrap();
        m.store(Cell::new(1, "スコアリング済み").turn(1).mode(0o744).price(80)
            .features([100; FACTOR_DIM])).unwrap();

        let results = m.search([100; FACTOR_DIM], 1, 0).current_turn(1).limit(10).exec().unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].text, "スコアリング済み");
    }

    #[test]
    fn test_search_decay() {
        let m = mem();
        let f = [100; FACTOR_DIM];
        m.store(Cell::new(1, "古い").turn(1).mode(0o744).price(80).features(f)).unwrap();
        m.store(Cell::new(1, "新しい").turn(10).mode(0o744).price(80).features(f)).unwrap();

        let results = m.search(f, 1, 0).current_turn(10).limit(2).exec().unwrap();
        assert_eq!(results[0].text, "新しい");
    }

    #[test]
    fn test_dream_basic() {
        let m = mem();
        let f = [100; FACTOR_DIM];
        m.store(Cell::new(1, "重要な古い記憶").turn(1).mode(0o744).price(200).features(f)).unwrap();
        m.store(Cell::new(1, "普通の新しい記憶").turn(9).mode(0o744).price(50).features(f)).unwrap();
        m.store(Cell::new(1, "不滅記憶").turn(1).mode(0o744).price(PRICE_IMMORTAL).features(f)).unwrap();

        let dreams = m.dream(1, 0).current_turn(10).limit(10).exec().unwrap();
        assert!(dreams.iter().all(|d| d.text != "不滅記憶"));
        assert_eq!(dreams[0].text, "重要な古い記憶");
    }

    #[test]
    fn test_dream_skips_unscored() {
        let m = mem();
        m.store(Cell::new(1, "未スコアリング").turn(1).mode(0o744).price(100)).unwrap();
        let dreams = m.dream(1, 0).current_turn(10).limit(10).exec().unwrap();
        assert!(dreams.is_empty());
    }

    // --- Step 3 tests ---

    #[test]
    fn test_reinforce() {
        let m = mem();
        let id = m.store(Cell::new(1, "記憶").turn(1).mode(0o744).price(80)
            .features([100; FACTOR_DIM])).unwrap();
        m.reinforce(id, 5.0).unwrap();
        let cell = m.get(id).unwrap();
        assert!((cell.importance - 5.0).abs() < 1e-6);
    }

    #[test]
    fn test_reinforce_bypasses_readonly() {
        let m = mem();
        let id = m.store(Cell::new(1, "プリセット").turn(1).mode(0o444).price(80)
            .features([100; FACTOR_DIM])).unwrap();
        m.reinforce(id, 3.0).unwrap();
        assert!((m.get(id).unwrap().importance - 3.0).abs() < 1e-6);
    }

    #[test]
    fn test_reinforce_range_error() {
        let m = mem();
        let id = m.store(Cell::new(1, "記憶").turn(1).features([100; FACTOR_DIM])).unwrap();
        assert!(m.reinforce(id, 11.0).is_err());
        assert!(m.reinforce(id, -0.1).is_err());
    }

    #[test]
    fn test_inspire() {
        let m = mem();
        let f_diplo = [200, 180, 100, 50, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110];
        let f_econ  = [50, 30, 200, 180, 120, 170, 30, 40, 150, 200, 40, 160, 180, 50, 170, 60];
        let f_diplo2 = [190, 170, 110, 60, 70, 50, 130, 150, 80, 40, 150, 90, 60, 120, 80, 100];

        let id1 = m.store(Cell::new(1, "外交A").turn(1).mode(0o744).features(f_diplo)).unwrap();
        m.store(Cell::new(1, "経済").turn(1).mode(0o744).features(f_econ)).unwrap();
        m.store(Cell::new(1, "外交B").turn(1).mode(0o744).features(f_diplo2)).unwrap();

        let related = m.inspire(id1).limit(2).exec().unwrap();
        assert_eq!(related.len(), 2);
        assert_eq!(related[0].text, "外交B");
    }

    #[test]
    fn test_update_group_bits() {
        let m = mem();
        let id = m.store(Cell::new(1, "密会").turn(1).mode(0o740)
            .group_bits(0b01).features([100; FACTOR_DIM])).unwrap();

        assert!(m.update_group_bits(id, 0b11, 1, 0).unwrap());
        assert_eq!(m.get(id).unwrap().group_bits, 0b11);

        assert!(!m.update_group_bits(id, 0b111, 3, 0).unwrap());
    }

    #[test]
    fn test_update_mode_and_meta() {
        let m = mem();
        let id = m.store(Cell::new(1, "秘密").turn(1).mode(0o740)
            .features([100; FACTOR_DIM])).unwrap();

        assert!(m.update_mode(id, 0o744, 1, 0).unwrap());
        assert_eq!(m.get(id).unwrap().mode, 0o744);

        assert!(m.update_meta(id, r#"{"leaked":true}"#, 1, 0).unwrap());
        assert_eq!(m.get(id).unwrap().meta, r#"{"leaked":true}"#);
    }

    #[test]
    fn test_update_denied_on_readonly() {
        let m = mem();
        let id = m.store(Cell::new(1, "保護").turn(1).mode(0o444)
            .features([100; FACTOR_DIM])).unwrap();

        assert!(!m.update_group_bits(id, 0b11, 1, 0).unwrap());
        assert!(!m.update_mode(id, 0o744, 1, 0).unwrap());
        assert!(!m.update_meta(id, "new", 1, 0).unwrap());
    }

    // --- Step 4 tests ---

    #[test]
    fn test_deferred_scoring() {
        let m = mem();
        let id = m.store(Cell::new(1, "未スコアリング").turn(1).mode(0o744).price(80)).unwrap();

        let unscored = m.get_unscored().unwrap();
        assert_eq!(unscored.len(), 1);
        assert_eq!(unscored[0].id, id);

        let features = [100, 200, 50, 150, 80, 120, 90, 170, 60, 130, 40, 110, 70, 160, 30, 140];
        m.set_features(id, features).unwrap();

        assert!(m.get_unscored().unwrap().is_empty());

        let cell = m.get(id).unwrap();
        assert_eq!(cell.features, features);

        let results = m.search(features, 1, 0).current_turn(1).limit(5).exec().unwrap();
        assert_eq!(results.len(), 1);
    }

    #[test]
    fn test_set_features_already_scored() {
        let m = mem();
        let f = [100; FACTOR_DIM];
        let id = m.store(Cell::new(1, "スコアリング済み").turn(1).features(f)).unwrap();

        assert!(matches!(m.set_features(id, [200; FACTOR_DIM]), Err(MxBSError::AlreadyScored(_))));
        assert_eq!(m.get(id).unwrap().features, f);
    }

    #[test]
    fn test_get_unscored_order() {
        let m = mem();
        m.store(Cell::new(1, "ターン3").turn(3)).unwrap();
        m.store(Cell::new(1, "ターン1").turn(1)).unwrap();
        m.store(Cell::new(1, "ターン2").turn(2)).unwrap();
        m.store(Cell::new(1, "済み").turn(0).features([100; FACTOR_DIM])).unwrap();

        let unscored = m.get_unscored().unwrap();
        assert_eq!(unscored.len(), 3);
        assert_eq!(unscored[0].turn, 1);
        assert_eq!(unscored[1].turn, 2);
        assert_eq!(unscored[2].turn, 3);
    }

    #[test]
    fn test_stats() {
        let m = mem();
        m.store(Cell::new(1, "未1").turn(1)).unwrap();
        m.store(Cell::new(1, "未2").turn(1)).unwrap();
        m.store(Cell::new(1, "済").turn(1).features([100; FACTOR_DIM])).unwrap();

        let s = m.stats().unwrap();
        assert_eq!(s.total, 3);
        assert_eq!(s.scored, 1);
        assert_eq!(s.unscored, 2);
    }

    #[test]
    fn test_save_and_reload() {
        let m = mem();
        let f = [100; FACTOR_DIM];
        m.store(Cell::new(1, "保存テスト").turn(1).mode(0o744).price(80).features(f)).unwrap();

        let tmp = "/tmp/mxbs_test_save.db";
        m.save_to(tmp).unwrap();

        let m2 = MxBS::open(tmp, MxBSConfig::default()).unwrap();
        let cell = m2.get(1).unwrap();
        assert_eq!(cell.text, "保存テスト");
        assert_eq!(cell.features, f);

        let _ = std::fs::remove_file(tmp);
    }

    #[test]
    fn test_set_features_not_found() {
        let m = mem();
        assert!(matches!(m.set_features(999, [100; FACTOR_DIM]), Err(MxBSError::NotFound(999))));
    }
}
