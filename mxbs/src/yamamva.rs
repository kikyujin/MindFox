use std::collections::{HashMap, HashSet};

use crate::{FACTOR_DIM, MxBS, MxBSError};

pub struct MxYamAMVAState {
    flags: HashSet<String>,
    keyword_cells: HashMap<String, u64>,
}

impl Default for MxYamAMVAState {
    fn default() -> Self {
        Self::new()
    }
}

impl MxYamAMVAState {
    pub fn new() -> Self {
        Self {
            flags: HashSet::new(),
            keyword_cells: HashMap::new(),
        }
    }

    pub fn has_flag(&self, name: &str) -> bool {
        self.flags.contains(name)
    }

    pub fn add_flag(&mut self, name: &str) {
        self.flags.insert(name.to_string());
    }

    pub fn flag_count(&self) -> usize {
        self.flags.len()
    }

    pub fn flags(&self) -> &HashSet<String> {
        &self.flags
    }
}

pub fn keyword_gate(state: &MxYamAMVAState, check_keywords: &[String]) -> f32 {
    if check_keywords.is_empty() {
        return 1.0;
    }
    let matched = check_keywords.iter().filter(|k| state.has_flag(k)).count();
    matched as f32 / check_keywords.len() as f32
}

pub fn keyword_grant(
    state: &mut MxYamAMVAState,
    db: &MxBS,
    grant_names: &[String],
    player_id: u32,
    player_groups: u64,
) -> Vec<String> {
    let mut newly_granted = Vec::new();
    for name in grant_names {
        if !state.has_flag(name) {
            state.add_flag(name);
            if let Some(&cell_id) = state.keyword_cells.get(name.as_str()) {
                let _ = db.update_mode(cell_id, 0o744, player_id, player_groups);
            }
            newly_granted.push(name.clone());
        }
    }
    newly_granted
}

pub fn prepare_chatterfox_lines(
    state: &MxYamAMVAState,
    db: &MxBS,
    npc_owner: u32,
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
) -> Result<Vec<u64>, MxBSError> {
    let all_lines = db
        .search([0u8; FACTOR_DIM], viewer_id, viewer_groups)
        .owner(npc_owner)
        .current_turn(current_turn)
        .limit(200)
        .exec()?;

    Ok(all_lines
        .into_iter()
        .filter(|r| {
            let requires = parse_requires(&r.meta);
            requires.iter().all(|req| state.has_flag(req))
        })
        .map(|r| r.id)
        .collect())
}

pub fn process_grants(
    state: &mut MxYamAMVAState,
    db: &MxBS,
    meta_json: &str,
    player_id: u32,
    player_groups: u64,
) -> Vec<String> {
    let grant_names = parse_grants(meta_json);
    keyword_grant(state, db, &grant_names, player_id, player_groups)
}

pub fn load_keywords(
    state: &mut MxYamAMVAState,
    db: &MxBS,
    player_id: u32,
    player_groups: u64,
    current_turn: u32,
) -> Result<usize, MxBSError> {
    let all_cells = db
        .search([0u8; FACTOR_DIM], player_id, player_groups)
        .owner(player_id)
        .current_turn(current_turn)
        .limit(500)
        .exec()?;

    let mut count = 0;
    for cell in &all_cells {
        let meta: serde_json::Value = match serde_json::from_str(&cell.meta) {
            Ok(v) => v,
            Err(_) => continue,
        };
        if meta.get("type").and_then(|v| v.as_str()) != Some("keyword") {
            continue;
        }
        let grant_name = meta
            .get("grant_name")
            .and_then(|v| v.as_str())
            .map(String::from)
            .or_else(|| {
                meta.get("word_id")
                    .and_then(|v| v.as_str())
                    .map(String::from)
            });

        let is_initial = meta
            .get("initial")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        if let Some(name) = grant_name {
            state.keyword_cells.insert(name.clone(), cell.id);
            if is_initial {
                state.add_flag(&name);
            }
            count += 1;
        }
    }
    Ok(count)
}

fn parse_requires(meta_json: &str) -> Vec<String> {
    serde_json::from_str::<serde_json::Value>(meta_json)
        .ok()
        .and_then(|v| v.get("requires")?.as_array().cloned())
        .map(|arr| {
            arr.into_iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default()
}

fn parse_grants(meta_json: &str) -> Vec<String> {
    serde_json::from_str::<serde_json::Value>(meta_json)
        .ok()
        .and_then(|v| v.get("grants")?.as_array().cloned())
        .map(|arr| {
            arr.into_iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Cell, MxBSConfig};

    fn config() -> MxBSConfig {
        MxBSConfig { half_life: 80 }
    }

    fn s(v: &str) -> String {
        v.to_string()
    }

    #[test]
    fn test_keyword_gate_partial() {
        let mut state = MxYamAMVAState::new();
        state.add_flag("包み紙");
        state.add_flag("ティルが怪しい");
        state.add_flag("犯行は1時以降");

        let check = vec![
            s("包み紙"),
            s("ティルが怪しい"),
            s("犯行は1時以降"),
            s("高級チョコレート"),
            s("足音がティルに似ている"),
        ];
        let rate = keyword_gate(&state, &check);
        assert!((rate - 0.6).abs() < 0.01);
    }

    #[test]
    fn test_keyword_gate_empty() {
        let state = MxYamAMVAState::new();
        assert_eq!(keyword_gate(&state, &[]), 1.0);
    }

    #[test]
    fn test_keyword_grant_basic() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let mut state = MxYamAMVAState::new();

        let newly = keyword_grant(&mut state, &db, &[s("ガサゴソ音"), s("プリン")], 1, 0xFF);
        assert_eq!(newly.len(), 2);
        assert!(state.has_flag("ガサゴソ音"));
        assert!(state.has_flag("プリン"));
    }

    #[test]
    fn test_keyword_grant_duplicate() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let mut state = MxYamAMVAState::new();

        let first = keyword_grant(&mut state, &db, &[s("ガサゴソ音")], 1, 0xFF);
        assert_eq!(first.len(), 1);

        let second = keyword_grant(&mut state, &db, &[s("ガサゴソ音")], 1, 0xFF);
        assert_eq!(second.len(), 0);
    }

    #[test]
    fn test_prepare_lines_requires_filter() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let mut state = MxYamAMVAState::new();

        let id_free = db
            .store(
                Cell::new(100, "自由セリフ")
                    .features([200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255)
                    .meta(r#"{"requires":[]}"#),
            )
            .unwrap();

        let id_locked = db
            .store(
                Cell::new(100, "要件付きセリフ")
                    .features([0, 200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255)
                    .meta(r#"{"requires":["包み紙"]}"#),
            )
            .unwrap();

        let lines = prepare_chatterfox_lines(&state, &db, 100, 1, 0xFF, 0).unwrap();
        assert!(lines.contains(&id_free));
        assert!(!lines.contains(&id_locked));

        state.add_flag("包み紙");
        let lines2 = prepare_chatterfox_lines(&state, &db, 100, 1, 0xFF, 0).unwrap();
        assert!(lines2.contains(&id_free));
        assert!(lines2.contains(&id_locked));
    }

    #[test]
    fn test_process_grants_from_meta() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let mut state = MxYamAMVAState::new();

        let meta = r#"{"grants":["ガサゴソ音","プリン"],"requires":[]}"#;
        let newly = process_grants(&mut state, &db, meta, 1, 0xFF);
        assert_eq!(newly, vec!["ガサゴソ音", "プリン"]);
        assert!(state.has_flag("ガサゴソ音"));
    }

    #[test]
    fn test_process_grants_empty() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let mut state = MxYamAMVAState::new();

        let meta = r#"{"grants":[],"requires":[]}"#;
        let newly = process_grants(&mut state, &db, meta, 1, 0xFF);
        assert!(newly.is_empty());
    }

    #[test]
    fn test_load_keywords_from_baked_db() {
        let db = MxBS::open(":memory:", config()).unwrap();

        db.store(
            Cell::new(1, "おやつ")
                .features([220, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                .group_bits(0xFF)
                .mode(0o744)
                .price(255)
                .meta(r#"{"type":"keyword","word_id":"w_oyatsu","initial":true}"#),
        )
        .unwrap();

        let gettable_id = db
            .store(
                Cell::new(1, "ガサゴソ音")
                    .features([0, 150, 80, 0, 180, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0])
                    .group_bits(0x00)
                    .mode(0o700)
                    .price(255)
                    .meta(r#"{"type":"keyword","word_id":"w_gasagoso","grant_name":"ガサゴソ音","initial":false}"#),
            )
            .unwrap();

        let mut state = MxYamAMVAState::new();
        let count = load_keywords(&mut state, &db, 1, 0xFF, 0).unwrap();

        assert_eq!(count, 2);
        assert!(state.has_flag("w_oyatsu"));
        assert!(!state.has_flag("ガサゴソ音"));
        assert_eq!(state.keyword_cells.get("ガサゴソ音"), Some(&gettable_id));
    }

    #[test]
    fn test_keyword_grant_updates_mode() {
        let db = MxBS::open(":memory:", config()).unwrap();

        let cell_id = db
            .store(
                Cell::new(1, "ガサゴソ音")
                    .features([0, 150, 80, 0, 180, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0])
                    .group_bits(0x00)
                    .mode(0o700)
                    .price(255)
                    .meta(r#"{"type":"keyword","grant_name":"ガサゴソ音","initial":false}"#),
            )
            .unwrap();

        let mut state = MxYamAMVAState::new();
        state.keyword_cells.insert(s("ガサゴソ音"), cell_id);

        let cell_before = db.get(cell_id).unwrap();
        assert_eq!(cell_before.mode, 0o700);

        keyword_grant(&mut state, &db, &[s("ガサゴソ音")], 1, 0xFF);

        let cell_after = db.get(cell_id).unwrap();
        assert_eq!(cell_after.mode, 0o744);
        assert!(state.has_flag("ガサゴソ音"));
    }
}
