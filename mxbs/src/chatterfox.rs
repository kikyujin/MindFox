use std::collections::HashSet;

use crate::{FACTOR_DIM, MxBS, MxBSError, SearchResult, cosine_similarity};

#[derive(Debug, serde::Serialize)]
pub struct ChatterFoxResult {
    pub cell_id: u64,
    pub text: String,
    pub meta: String,
    pub depth: usize,
    pub is_fallback: bool,
}

fn pick_random(candidates: &[&SearchResult], seed: u64, depth: usize) -> usize {
    if candidates.len() <= 1 {
        return 0;
    }
    let mixed = seed
        .wrapping_mul(6364136223846793005)
        .wrapping_add(depth as u64)
        .wrapping_mul(1442695040888963407);
    (mixed as usize) % candidates.len()
}

pub fn cascade_search(
    db: &MxBS,
    word_features: &[[u8; FACTOR_DIM]],
    lines_owner: u32,
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
    exclude_ids: &[u64],
    threshold: f32,
    top_k: usize,
    seed: u64,
) -> Result<ChatterFoxResult, MxBSError> {
    let exclude_set: HashSet<u64> = exclude_ids.iter().copied().collect();

    let effective_seed = if seed == 0 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(42)
    } else {
        seed
    };

    for depth in (1..=word_features.len()).rev() {
        let query_words = &word_features[..depth];

        let candidates = db
            .search(query_words[0], viewer_id, viewer_groups)
            .owner(lines_owner)
            .current_turn(current_turn)
            .limit(top_k)
            .exec()
            .unwrap_or_default();

        let filtered: Vec<&SearchResult> = candidates
            .iter()
            .filter(|c| c.features != [0u8; FACTOR_DIM])
            .filter(|c| cosine_similarity(&c.features, &query_words[0]) >= threshold)
            .filter(|c| {
                query_words[1..]
                    .iter()
                    .all(|wf| cosine_similarity(&c.features, wf) >= threshold)
            })
            .filter(|c| !exclude_set.contains(&c.id))
            .collect();

        if !filtered.is_empty() {
            let idx = pick_random(&filtered, effective_seed, depth);
            let pick = filtered[idx];
            return Ok(ChatterFoxResult {
                cell_id: pick.id,
                text: pick.text.clone(),
                meta: pick.meta.clone(),
                depth,
                is_fallback: false,
            });
        }
    }

    Ok(ChatterFoxResult {
        cell_id: 0,
        text: String::new(),
        meta: String::new(),
        depth: 0,
        is_fallback: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Cell, MxBSConfig};

    fn config() -> MxBSConfig {
        MxBSConfig { half_life: 80 }
    }

    fn feat(vals: &[(usize, u8)]) -> [u8; 16] {
        let mut f = [0u8; 16];
        for &(i, v) in vals {
            f[i] = v;
        }
        f
    }

    #[test]
    fn test_single_word_hit() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let f_snack_ask = feat(&[(0, 200), (6, 200)]);
        let id = db
            .store(
                Cell::new(100, "おやつの話")
                    .features(f_snack_ask)
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255),
            )
            .unwrap();

        let word_snack = feat(&[(0, 220)]);
        let r = cascade_search(&db, &[word_snack], 100, 1, 0xFF, 1, &[], 0.35, 20, 42).unwrap();
        assert_eq!(r.cell_id, id);
        assert_eq!(r.depth, 1);
        assert!(!r.is_fallback);
    }

    #[test]
    fn test_cascade_2words() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let f_snack_ask = feat(&[(0, 200), (6, 200)]);
        let f_snack_time = feat(&[(0, 200), (1, 200)]);
        let f_time_ask = feat(&[(1, 200), (6, 200)]);

        let id_a = db
            .store(
                Cell::new(100, "おやつ聞く")
                    .features(f_snack_ask)
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255),
            )
            .unwrap();
        db.store(
            Cell::new(100, "おやつ時間")
                .features(f_snack_time)
                .group_bits(0xFF)
                .mode(0o744)
                .price(255),
        )
        .unwrap();
        db.store(
            Cell::new(100, "時間聞く")
                .features(f_time_ask)
                .group_bits(0xFF)
                .mode(0o744)
                .price(255),
        )
        .unwrap();

        let word_snack = feat(&[(0, 220)]);
        let word_ask = feat(&[(6, 220)]);
        let r =
            cascade_search(&db, &[word_snack, word_ask], 100, 1, 0xFF, 1, &[], 0.35, 20, 42)
                .unwrap();
        assert_eq!(r.cell_id, id_a);
        assert_eq!(r.depth, 2);
        assert!(!r.is_fallback);
    }

    #[test]
    fn test_cascade_3words() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let f_all = feat(&[(0, 200), (1, 200), (6, 200)]);
        let f_snack_time = feat(&[(0, 200), (1, 200)]);

        let id_all = db
            .store(
                Cell::new(100, "完全一致")
                    .features(f_all)
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255),
            )
            .unwrap();
        db.store(
            Cell::new(100, "部分一致")
                .features(f_snack_time)
                .group_bits(0xFF)
                .mode(0o744)
                .price(255),
        )
        .unwrap();

        let w1 = feat(&[(0, 220)]);
        let w2 = feat(&[(1, 220)]);
        let w3 = feat(&[(6, 220)]);
        let r =
            cascade_search(&db, &[w1, w2, w3], 100, 1, 0xFF, 1, &[], 0.35, 20, 42).unwrap();
        assert_eq!(r.cell_id, id_all);
        assert_eq!(r.depth, 3);
    }

    #[test]
    fn test_backtrack() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let f_snack = feat(&[(0, 200)]);
        let id = db
            .store(
                Cell::new(100, "おやつだけ")
                    .features(f_snack)
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255),
            )
            .unwrap();

        let w_snack = feat(&[(0, 220)]);
        let w_evidence = feat(&[(4, 220)]);
        let w_alibi = feat(&[(5, 220)]);
        let r = cascade_search(
            &db,
            &[w_snack, w_evidence, w_alibi],
            100, 1, 0xFF, 1, &[], 0.35, 20, 42,
        )
        .unwrap();
        assert_eq!(r.cell_id, id);
        assert_eq!(r.depth, 1);
        assert!(!r.is_fallback);
    }

    #[test]
    fn test_full_fallback() {
        let db = MxBS::open(":memory:", config()).unwrap();
        db.store(
            Cell::new(100, "おやつの話")
                .features(feat(&[(0, 200)]))
                .group_bits(0xFF)
                .mode(0o744)
                .price(255),
        )
        .unwrap();

        let w_unrelated = feat(&[(14, 220), (15, 220)]);
        let r =
            cascade_search(&db, &[w_unrelated], 100, 1, 0xFF, 1, &[], 0.35, 20, 42).unwrap();
        assert!(r.is_fallback);
        assert_eq!(r.cell_id, 0);
        assert_eq!(r.depth, 0);
    }

    #[test]
    fn test_exclude_ids() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let f = feat(&[(0, 200), (6, 200)]);
        let id1 = db
            .store(
                Cell::new(100, "セリフA")
                    .features(f)
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255),
            )
            .unwrap();
        let id2 = db
            .store(
                Cell::new(100, "セリフB")
                    .features(f)
                    .group_bits(0xFF)
                    .mode(0o744)
                    .price(255),
            )
            .unwrap();

        let w = feat(&[(0, 220)]);
        let r =
            cascade_search(&db, &[w], 100, 1, 0xFF, 1, &[id1, id2], 0.35, 20, 42).unwrap();
        assert!(r.is_fallback);
    }

    #[test]
    fn test_empty_db() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let w = feat(&[(0, 220)]);
        let r = cascade_search(&db, &[w], 100, 1, 0xFF, 1, &[], 0.35, 20, 42).unwrap();
        assert!(r.is_fallback);
        assert_eq!(r.depth, 0);
    }

    #[test]
    fn test_acl_respected() {
        let db = MxBS::open(":memory:", config()).unwrap();
        let f = feat(&[(0, 200)]);
        db.store(
            Cell::new(100, "秘密のセリフ")
                .features(f)
                .group_bits(0x00)
                .mode(0o700)
                .price(255),
        )
        .unwrap();

        let w = feat(&[(0, 220)]);
        let r = cascade_search(&db, &[w], 100, 1, 0xFF, 1, &[], 0.35, 20, 42).unwrap();
        assert!(r.is_fallback);
    }
}
