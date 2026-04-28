use mxbs::{MxBS, MxBSConfig, Cell, AgentRegistry, FACTOR_DIM};
use crate::types::CountryId;

pub const AGENT_GM: &str = "gm";

pub enum EventType {
    Conscript,
    AllianceFormed,
    AllianceRejected,
    BattleAttacker { won: bool, loss_ratio: f32 },
    BattleDefender { won: bool, loss_ratio: f32 },
    Conquered,
    Eliminated,
}

pub fn event_features(event: EventType) -> [u8; 16] {
    match event {
        EventType::Conscript => [
            80, 80, 128, 128,  128, 128, 10, 20,
            60, 210, 100, 80,  128, 170, 160, 80
        ],
        EventType::AllianceFormed => [
            30, 10, 128, 128,  230, 210, 220, 20,
            140, 128, 120, 150,  80, 180, 80, 60
        ],
        EventType::AllianceRejected => [
            40, 10, 128, 128,  40, 40, 80, 20,
            128, 128, 80, 100,  60, 120, 60, 40
        ],
        EventType::BattleAttacker { won, loss_ratio } => {
            let result = if won { 200 } else { 60 };
            let confidence = if won { 220 } else { 50 };
            let force = (128.0 * (1.0 - loss_ratio * 2.0)).clamp(0.0, 255.0) as u8;
            let threat = if won { 40 } else { (100.0 + loss_ratio * 155.0).min(255.0) as u8 };
            [
                220, 190, result, if won { 180 } else { 100 },
                20, 30, 10, 30,
                70, force, 190, threat,
                if won { 200 } else { 40 }, confidence, 200, 180
            ]
        },
        EventType::BattleDefender { won, loss_ratio } => {
            let result = if won { 200 } else { 50 };
            let confidence = if won { 200 } else { 30 };
            let force = (128.0 * (1.0 - loss_ratio * 2.0)).clamp(0.0, 255.0) as u8;
            let threat = if won { 60 } else { (150.0 + loss_ratio * 105.0).min(255.0) as u8 };
            [
                40, 180, result, if won { 128 } else { 80 },
                20, 30, 10, 20,
                80, force, 220, threat,
                if won { 180 } else { 20 }, confidence, 80, 160
            ]
        },
        EventType::Conquered => [
            230, 220, 240, 240,  10, 20, 10, 30,
            60, 50, 240, 20,  240, 250, 250, 250
        ],
        EventType::Eliminated => [
            20, 20, 20, 20,  10, 10, 10, 10,
            20, 10, 250, 250,  10, 10, 10, 250
        ],
    }
}

pub const WORLD_FEATURES: [[u8; 16]; 5] = [
    // ID1 今川（遠江駿河）: 中規模、名門leader
    [40, 20, 128, 128, 128, 128, 20, 20, 140, 128, 60, 80, 100, 160, 140, 60],
    // ID2 徳川（三河）: 大国寄り、慎重analyst
    [30, 20, 128, 128, 128, 128, 20, 20, 160, 128, 40, 50, 120, 170, 100, 60],
    // ID3 斉藤（美濃）: 弱小、stubborn
    [30, 20, 128, 128, 128, 128, 20, 20, 80, 128, 120, 160, 60, 80, 60, 80],
    // ID4 武田（甲斐信濃）: 強国、leader
    [50, 30, 128, 128, 128, 128, 20, 20, 150, 128, 60, 60, 140, 190, 180, 60],
    // ID5 織田（尾張）: 強国、impulsive
    [70, 30, 128, 128, 128, 128, 20, 20, 170, 128, 80, 50, 180, 200, 220, 80],
];

pub fn init_memory() -> (MxBS, AgentRegistry) {
    let mxbs = MxBS::open(":memory:", MxBSConfig { half_life: 8 }).unwrap();
    let mut reg = AgentRegistry::new();

    reg.register(AGENT_GM, "天の声").unwrap();
    reg.register("imagawa", "今川義元").unwrap();
    reg.register("tokugawa", "徳川家康").unwrap();
    reg.register("saito", "斉藤義竜").unwrap();
    reg.register("takeda", "武田信玄").unwrap();
    reg.register("oda", "織田信長").unwrap();

    (mxbs, reg)
}

pub fn country_slug(id: CountryId) -> &'static str {
    match id {
        1 => "imagawa",
        2 => "tokugawa",
        3 => "saito",
        4 => "takeda",
        5 => "oda",
        _ => panic!("invalid country id"),
    }
}

pub fn store_event(
    mxbs: &MxBS,
    reg: &AgentRegistry,
    turn: u32,
    owner_slug: &str,
    text: &str,
    price: u8,
    mode: u16,
) -> u64 {
    store_event_with_features(mxbs, reg, turn, owner_slug, text, price, mode, [0u8; FACTOR_DIM])
}

pub fn store_event_scored(
    mxbs: &MxBS,
    reg: &AgentRegistry,
    turn: u32,
    owner_slug: &str,
    text: &str,
    price: u8,
    mode: u16,
    event: EventType,
) -> u64 {
    store_event_with_features(mxbs, reg, turn, owner_slug, text, price, mode, event_features(event))
}

fn store_event_with_features(
    mxbs: &MxBS,
    reg: &AgentRegistry,
    turn: u32,
    owner_slug: &str,
    text: &str,
    price: u8,
    mode: u16,
    features: [u8; FACTOR_DIM],
) -> u64 {
    if mode == 0o744 {
        reg.store_public(mxbs, turn, owner_slug, text, features, price).unwrap()
    } else {
        reg.store_private(mxbs, turn, owner_slug, text, features, price).unwrap()
    }
}

pub fn store_alliance_event(
    mxbs: &MxBS,
    reg: &AgentRegistry,
    turn: u32,
    from_slug: &str,
    to_slug: &str,
    text: &str,
    price: u8,
    event: EventType,
) -> u64 {
    let owner = reg.owner_id(from_slug).unwrap();
    let from_bit = reg.bit(from_slug).unwrap();
    let to_bit = reg.bit(to_slug).unwrap();
    mxbs.store(
        Cell::new(owner, text)
            .turn(turn)
            .group_bits(from_bit | to_bit)
            .mode(0o740)
            .price(price)
            .features(event_features(event))
    ).unwrap()
}

pub fn get_memories_for_agent(
    mxbs: &MxBS,
    reg: &AgentRegistry,
    slug: &str,
    query_features: [u8; FACTOR_DIM],
    current_turn: u32,
) -> Vec<String> {
    let results = reg.search(mxbs, slug, query_features, current_turn).unwrap();
    results.iter().map(|r| r.text.clone()).collect()
}

pub async fn score_all_pending(
    mxbs: &MxBS,
    preset_json: &str,
) {
    let unscored = mxbs.get_unscored().unwrap();
    if unscored.is_empty() {
        println!("  スコアリング不要（全件ルールベース処理済み）");
        return;
    }
    println!("  inner_voice {}件をLLMスコアリング...", unscored.len());

    let texts: Vec<(u64, String)> = unscored.iter()
        .map(|c| (c.id, c.text.clone()))
        .collect();

    let batch_count = (texts.len() + 3) / 4;
    println!("  スコアリング中（{}件, {}バッチ）", texts.len(), batch_count);
    let phase_start = std::time::Instant::now();

    let mut batch_idx = 0;
    for chunk in texts.chunks(4) {
        batch_idx += 1;
        let t0 = std::time::Instant::now();
        let chunk_vec: Vec<(u64, String)> = chunk.to_vec();
        let scored = crate::llm::batch_score(&chunk_vec, preset_json).await;
        let elapsed = t0.elapsed();
        println!("    バッチ{} ({}件) ... {:.1}秒", batch_idx, chunk.len(), elapsed.as_secs_f64());
        for (cell_id, features) in scored {
            if let Err(e) = mxbs.set_features(cell_id, features) {
                eprintln!("    set_features error for cell {}: {}", cell_id, e);
            }
        }
    }

    let total = phase_start.elapsed();
    println!("  完了（{}件, 合計{:.1}秒, 平均{:.2}秒/件）",
        texts.len(), total.as_secs_f64(), total.as_secs_f64() / texts.len() as f64);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_init_memory() {
        let (_mxbs, reg) = init_memory();
        assert_eq!(reg.count(), 6);
    }

    #[test]
    fn test_store_and_search() {
        let (mxbs, reg) = init_memory();
        store_event_scored(&mxbs, &reg, 1, "oda", "織田が徴兵を行った", 40, 0o744, EventType::Conscript);
        let query = event_features(EventType::Conscript);
        let results = get_memories_for_agent(&mxbs, &reg, "oda", query, 1);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0], "織田が徴兵を行った");
    }

    #[test]
    fn test_private_invisible() {
        let (mxbs, reg) = init_memory();
        store_event_scored(&mxbs, &reg, 1, "oda", "内心の声", 70, 0o700, EventType::Conscript);
        let query = event_features(EventType::Conscript);
        let oda_results = get_memories_for_agent(&mxbs, &reg, "oda", query, 1);
        assert_eq!(oda_results.len(), 1);
        let takeda_results = get_memories_for_agent(&mxbs, &reg, "takeda", query, 1);
        assert_eq!(takeda_results.len(), 0);
    }

    #[test]
    fn test_alliance_event_visibility() {
        let (mxbs, reg) = init_memory();
        store_alliance_event(&mxbs, &reg, 1, "tokugawa", "imagawa", "徳川と今川が同盟", 80, EventType::AllianceFormed);
        let query = event_features(EventType::AllianceFormed);
        let toku = get_memories_for_agent(&mxbs, &reg, "tokugawa", query, 1);
        assert_eq!(toku.len(), 1);
        let ima = get_memories_for_agent(&mxbs, &reg, "imagawa", query, 1);
        assert_eq!(ima.len(), 1);
        let oda = get_memories_for_agent(&mxbs, &reg, "oda", query, 1);
        assert_eq!(oda.len(), 0);
    }

    #[test]
    fn test_event_features_conscript() {
        let f = event_features(EventType::Conscript);
        assert_eq!(f[9], 210);
        assert_eq!(f[4], 128);
    }

    #[test]
    fn test_event_features_battle_attacker_won() {
        let f = event_features(EventType::BattleAttacker { won: true, loss_ratio: 0.2 });
        assert!(f[2] > 150);
        assert!(f[13] > 150);
    }

    #[test]
    fn test_event_features_battle_defender_lost() {
        let f = event_features(EventType::BattleDefender { won: false, loss_ratio: 0.8 });
        assert!(f[2] < 80);
        assert!(f[11] > 200);
    }
}
