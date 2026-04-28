use std::collections::{HashMap, HashSet};

pub type CountryId = u32;

#[derive(Debug, Clone)]
pub enum Personality {
    Leader,
    Analyst,
    Stubborn,
    Impulsive,
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct CountryDef {
    pub id: CountryId,
    pub name: String,
    pub name_kana: String,
    pub daimyo: String,
    pub personality: Personality,
    pub base_kokuryoku: u32,
    pub initial_gold: u32,
    pub initial_troops: u32,
    pub strategy: String,
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct CountryState {
    pub id: CountryId,
    pub gold: i32,
    pub troops: u32,
    pub territories: Vec<CountryId>,
    pub alive: bool,
    pub allies: HashSet<CountryId>,
    pub consecutive_passes: u32,
}

#[derive(Debug, Clone)]
pub struct Mood {
    pub aggression: f32,
    pub desperation: f32,
    pub confidence: f32,
    pub diplomacy: f32,
}

impl Default for Mood {
    fn default() -> Self {
        Mood { aggression: 0.5, desperation: 0.5, confidence: 0.5, diplomacy: 0.5 }
    }
}

#[derive(Debug, Clone)]
pub enum Action {
    Conscript,
    Alliance(CountryId),
    Attack(CountryId),
    Pass,
}

#[derive(Debug, Clone)]
pub struct TurnActions {
    pub country_id: CountryId,
    pub actions: Vec<Action>,
}

#[derive(Debug, Clone)]
pub struct BattleResult {
    pub attacker: CountryId,
    pub defender: CountryId,
    pub is_wild: bool,
    pub att_losses: u32,
    pub def_losses: u32,
    pub conquered: Option<CountryId>,
    pub conqueror: Option<CountryId>,
}

#[derive(Debug)]
pub struct GameState {
    pub turn: u32,
    pub year: u32,
    pub countries: HashMap<CountryId, CountryState>,
    pub defs: HashMap<CountryId, CountryDef>,
    pub adjacency: HashMap<CountryId, Vec<CountryId>>,
    pub player_id: CountryId,
    pub turn_log: Vec<String>,
}
