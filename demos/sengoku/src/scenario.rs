use crate::types::*;
use std::collections::HashMap;

pub const MAX_TURNS: u32 = 30;
pub const START_YEAR: u32 = 1560;
pub const PLAYER_COUNTRY: CountryId = 5;

pub const MAINTENANCE_DIVISOR: u32 = 2;
pub const CONSCRIPT_COST_RATIO: u32 = 1;
pub const CONSCRIPT_GAIN_RATIO: u32 = 1;

#[allow(dead_code)]
pub const DEFENSE_BUFF_NUM: u32 = 3;
#[allow(dead_code)]
pub const DEFENSE_BUFF_DEN: u32 = 2;
pub const INVASION_ATT_LOSS_NUM: u32 = 45;
pub const INVASION_ATT_LOSS_DEN: u32 = 100;
pub const INVASION_DEF_LOSS_NUM: u32 = 30;
pub const INVASION_DEF_LOSS_DEN: u32 = 100;
pub const WILD_LOSS_NUM: u32 = 50;
pub const WILD_LOSS_DEN: u32 = 100;

pub fn personality_desc(p: &Personality) -> &'static str {
    match p {
        Personality::Leader => "\
戦略家。有利な状況では積極的に攻め、不利なら同盟で時間を稼ぐ。\
隣国との力関係を常に計算している。",

        Personality::Analyst => "\
慎重派。準備が十分に整うまで動かない。\
兵力で相手を大きく上回るまでは徴兵と蓄財を優先する。\
ただし同盟の申し込みには利害が合えば応じる。",

        Personality::Stubborn => "\
意地っ張りだが愚かではない。\
自国より強い相手からの同盟は生き残りのために受け入れる。\
弱い相手には強気で、同盟より攻撃を選ぶ。",

        Personality::Impulsive => "\
攻め気。兵力が隣国を上回っていれば迷わず攻撃する。\
待つのが苦手で、徴兵だけのターンを嫌う。\
勝てる戦があるなら必ず仕掛ける。",
    }
}

pub fn create_countries() -> Vec<CountryDef> {
    vec![
        CountryDef {
            id: 1,
            name: "遠江駿河".into(),
            name_kana: "とおとうみするが".into(),
            daimyo: "今川義元".into(),
            personality: Personality::Leader,
            base_kokuryoku: 55,
            initial_gold: 68,
            initial_troops: 73,
            strategy: "\
隣国は徳川と武田の2国のみ。どちらも強国で単独では勝てない。\
片方と同盟を組み、もう片方を叩くのが基本戦略。\
徳川と武田が争えば漁夫の利を得られる。\
孤立は死を意味する。常にどちらかとは同盟を維持せよ。".into(),
        },
        CountryDef {
            id: 2,
            name: "三河".into(),
            name_kana: "みかわ".into(),
            daimyo: "徳川家康".into(),
            personality: Personality::Analyst,
            base_kokuryoku: 73,
            initial_gold: 69,
            initial_troops: 71,
            strategy: "\
4国と隣接する中央の要衝。全方位から攻められるリスクがある。\
序盤は蓄財と徴兵に専念し、周囲が消耗するのを待て。\
弱った国があれば確実に仕留める。\
同盟は自国を守るために使い、不要なら断れ。\
最大の脅威が誰かを常に見極めよ。".into(),
        },
        CountryDef {
            id: 3,
            name: "美濃".into(),
            name_kana: "みの".into(),
            daimyo: "斉藤義竜".into(),
            personality: Personality::Stubborn,
            base_kokuryoku: 30,
            initial_gold: 29,
            initial_troops: 38,
            strategy: "\
国力30で最弱。単独では織田にも武田にも勝てない。\
生き残りが最優先。隣国からの同盟申し込みは基本的に受けよ。\
特に兵力で大きく上回る国からの同盟は断ってはならない。\
金が少ないので徴兵の機会は限られる。同盟の盾で時間を稼げ。\
強国同士が潰し合うのを待ち、隙を突いて生き延びよ。".into(),
        },
        CountryDef {
            id: 4,
            name: "甲斐信濃".into(),
            name_kana: "かいしなの".into(),
            daimyo: "武田信玄".into(),
            personality: Personality::Leader,
            base_kokuryoku: 62,
            initial_gold: 73,
            initial_troops: 72,
            strategy: "\
強国だが隣国も強い。今川・徳川・斉藤と3方向に隣接。\
まず弱い斉藤を狙うか、今川と同盟して南を固めるのが定石。\
徳川が成長する前に叩くか、同盟で封じるかの判断が鍵。\
兵力を温存しつつ確実に領土を広げよ。".into(),
        },
        CountryDef {
            id: 5,
            name: "尾張".into(),
            name_kana: "おわり".into(),
            daimyo: "織田信長".into(),
            personality: Personality::Impulsive,
            base_kokuryoku: 69,
            initial_gold: 100,
            initial_troops: 78,
            strategy: "\
金と兵力で最強だが隣国は徳川と斉藤の2国のみ。\
最弱の斉藤を早期に併合し、国力を拡大するのが天下への最短路。\
徳川とは同盟を組んで背後を安全にし、斉藤攻略に集中せよ。\
斉藤を取れば武田・今川との接点が増え、天下統一の道が開ける。\
兵力維持費に注意。攻めるなら早く、溜め込みすぎるな。".into(),
        },
    ]
}

pub fn create_adjacency() -> HashMap<CountryId, Vec<CountryId>> {
    let mut adj = HashMap::new();
    adj.insert(1, vec![2, 4]);
    adj.insert(2, vec![1, 3, 4, 5]);
    adj.insert(3, vec![2, 4, 5]);
    adj.insert(4, vec![1, 2, 3]);
    adj.insert(5, vec![2, 3]);
    adj
}

pub const PRESET_JSON: &str = r#"
{
  "name": "sengoku_lite",
  "version": "1.0",
  "axes": [
    {"index": 0,  "name": "aggression",        "low": "対話的",     "high": "攻撃的"},
    {"index": 1,  "name": "military_scale",     "low": "非軍事",     "high": "総力戦"},
    {"index": 2,  "name": "battle_result",      "low": "大敗",       "high": "大勝"},
    {"index": 3,  "name": "territorial_change",  "low": "領土喪失",   "high": "領土拡大"},
    {"index": 4,  "name": "cooperation",        "low": "敵対",       "high": "協力"},
    {"index": 5,  "name": "trust_change",       "low": "信頼低下",   "high": "信頼向上"},
    {"index": 6,  "name": "commitment",         "low": "口先だけ",   "high": "正式な約束"},
    {"index": 7,  "name": "deception",          "low": "誠実",       "high": "裏切り"},
    {"index": 8,  "name": "economic_impact",    "low": "大きな消耗", "high": "大きな蓄積"},
    {"index": 9,  "name": "force_change",       "low": "兵力激減",   "high": "兵力激増"},
    {"index": 10, "name": "urgency",            "low": "平時",       "high": "緊急事態"},
    {"index": 11, "name": "threat_to_self",     "low": "安全",       "high": "存亡の危機"},
    {"index": 12, "name": "opportunity",        "low": "八方塞がり", "high": "千載一遇"},
    {"index": 13, "name": "confidence",         "low": "動揺",       "high": "自信満々"},
    {"index": 14, "name": "ambition",           "low": "現状維持",   "high": "天下統一"},
    {"index": 15, "name": "power_shift",        "low": "均衡維持",   "high": "勢力図激変"}
  ]
}
"#;
