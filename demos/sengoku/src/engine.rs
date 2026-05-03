use crate::scenario::*;
use crate::types::*;
use std::collections::HashMap;

pub enum GameEnd {
    PlayerDead,
    PlayerWon,
    MaxTurns,
    NotYet,
}

pub fn process_economy(state: &mut GameState, defs: &HashMap<CountryId, CountryDef>) {
    for (_id, cs) in state.countries.iter_mut() {
        if !cs.alive {
            continue;
        }

        let income: u32 = cs
            .territories
            .iter()
            .map(|tid| defs[tid].base_kokuryoku)
            .sum();
        cs.gold += income as i32;

        let maintenance = cs.troops / MAINTENANCE_DIVISOR;
        cs.gold -= maintenance as i32;

        if cs.gold < 0 {
            let desert = (cs.gold.unsigned_abs()) * 2;
            cs.troops = cs.troops.saturating_sub(desert);
            cs.gold = 0;
        }
    }
}

pub fn conscript(cs: &mut CountryState, kokuryoku: u32) {
    let cost = kokuryoku * CONSCRIPT_COST_RATIO;
    let gain = kokuryoku * CONSCRIPT_GAIN_RATIO;
    cs.gold -= cost as i32;
    cs.troops += gain;
}

pub fn resolve_alliances(state: &mut GameState, proposals: &[(CountryId, CountryId, bool)]) {
    for cs in state.countries.values_mut() {
        cs.allies.clear();
    }
    for &(from, to, accepted) in proposals {
        if accepted {
            state.countries.get_mut(&from).unwrap().allies.insert(to);
            state.countries.get_mut(&to).unwrap().allies.insert(from);
        }
    }
}

pub fn resolve_battles(
    state: &mut GameState,
    attacks: &[(CountryId, CountryId)],
) -> Vec<BattleResult> {
    let mut results = Vec::new();

    let valid_attacks: Vec<(CountryId, CountryId)> = attacks
        .iter()
        .filter(|(a, d)| !state.countries[a].allies.contains(d))
        .cloned()
        .collect();

    let mut wild_pairs: Vec<(CountryId, CountryId)> = Vec::new();
    let mut invasion_attacks: Vec<(CountryId, CountryId)> = Vec::new();

    for &(a, d) in &valid_attacks {
        if valid_attacks.contains(&(d, a)) {
            if a < d && !wild_pairs.contains(&(a, d)) {
                wild_pairs.push((a, d));
            }
        } else {
            invasion_attacks.push((a, d));
        }
    }

    for (a, b) in &wild_pairs {
        let result = resolve_wild_battle(state, *a, *b);
        results.push(result);
    }

    for (a, d) in &invasion_attacks {
        if !state.countries[a].alive || !state.countries[d].alive {
            continue;
        }
        let result = resolve_invasion(state, *a, *d);
        results.push(result);
    }

    results
}

fn resolve_wild_battle(state: &mut GameState, a: CountryId, b: CountryId) -> BattleResult {
    let a_troops = state.countries[&a].troops;
    let b_troops = state.countries[&b].troops;

    let a_loss = b_troops * WILD_LOSS_NUM / WILD_LOSS_DEN;
    let b_loss = a_troops * WILD_LOSS_NUM / WILD_LOSS_DEN;

    let cs_a = state.countries.get_mut(&a).unwrap();
    cs_a.troops = cs_a.troops.saturating_sub(a_loss);
    let a_alive = cs_a.troops > 0;

    let cs_b = state.countries.get_mut(&b).unwrap();
    cs_b.troops = cs_b.troops.saturating_sub(b_loss);
    let b_alive = cs_b.troops > 0;

    let (conquered, conqueror) = match (a_alive, b_alive) {
        (true, false) => {
            conquer(state, a, b);
            (Some(b), Some(a))
        }
        (false, true) => {
            conquer(state, b, a);
            (Some(a), Some(b))
        }
        (false, false) => {
            conquer(state, b, a);
            (Some(a), Some(b))
        }
        _ => (None, None),
    };

    BattleResult {
        attacker: a,
        defender: b,
        is_wild: true,
        att_losses: a_loss,
        def_losses: b_loss,
        conquered,
        conqueror,
    }
}

fn resolve_invasion(state: &mut GameState, att: CountryId, def: CountryId) -> BattleResult {
    let a_troops = state.countries[&att].troops;
    let d_troops = state.countries[&def].troops;

    let a_loss = d_troops * INVASION_ATT_LOSS_NUM / INVASION_ATT_LOSS_DEN;
    let d_loss = a_troops * INVASION_DEF_LOSS_NUM / INVASION_DEF_LOSS_DEN;

    let new_a = a_troops.saturating_sub(a_loss);
    let new_d = d_troops.saturating_sub(d_loss);

    state.countries.get_mut(&att).unwrap().troops = new_a;
    state.countries.get_mut(&def).unwrap().troops = new_d;

    let (conquered, conqueror) = if new_d == 0 {
        conquer(state, att, def);
        (Some(def), Some(att))
    } else if new_a == 0 {
        conquer(state, def, att);
        (Some(att), Some(def))
    } else {
        (None, None)
    };

    BattleResult {
        attacker: att,
        defender: def,
        is_wild: false,
        att_losses: a_loss,
        def_losses: d_loss,
        conquered,
        conqueror,
    }
}

fn conquer(state: &mut GameState, winner: CountryId, loser: CountryId) {
    let loser_territories: Vec<CountryId> = state.countries[&loser].territories.clone();
    state
        .countries
        .get_mut(&winner)
        .unwrap()
        .territories
        .extend(loser_territories);
    let cs_loser = state.countries.get_mut(&loser).unwrap();
    cs_loser.alive = false;
    cs_loser.territories.clear();
    cs_loser.troops = 0;
}

pub fn update_adjacency(
    adjacency: &mut HashMap<CountryId, Vec<CountryId>>,
    winner: CountryId,
    loser: CountryId,
) {
    let loser_neighbors: Vec<CountryId> = adjacency
        .get(&loser)
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|&n| n != winner)
        .collect();

    let winner_adj = adjacency.entry(winner).or_default();
    for n in &loser_neighbors {
        if !winner_adj.contains(n) {
            winner_adj.push(*n);
        }
    }
    winner_adj.retain(|&n| n != loser);

    for (id, neighbors) in adjacency.iter_mut() {
        if *id == winner || *id == loser {
            continue;
        }
        for n in neighbors.iter_mut() {
            if *n == loser {
                *n = winner;
            }
        }
        neighbors.dedup();
    }

    adjacency.remove(&loser);
}

pub fn killable_target(state: &GameState, country_id: CountryId) -> Option<CountryId> {
    let my_troops = state.countries[&country_id].troops;
    let kill_power = my_troops * INVASION_DEF_LOSS_NUM / INVASION_DEF_LOSS_DEN;

    state
        .adjacency
        .get(&country_id)?
        .iter()
        .filter(|&&n| {
            let c = &state.countries[&n];
            c.alive
                && c.troops > 0
                && c.troops <= kill_power
                && !state.countries[&country_id].allies.contains(&n)
        })
        .min_by_key(|&&n| state.countries[&n].troops)
        .copied()
}

pub fn can_afford_conscript(cs: &CountryState, kokuryoku_total: u32) -> bool {
    let cost = kokuryoku_total as i32;
    let new_troops = cs.troops + kokuryoku_total;
    let new_gold = cs.gold - cost;
    let income = kokuryoku_total as i32;
    let maintenance = (new_troops / MAINTENANCE_DIVISOR) as i32;
    let next_gold = new_gold + income - maintenance;
    next_gold >= 0
}

pub fn is_desperate(cs: &CountryState, kokuryoku_total: u32) -> bool {
    let income = kokuryoku_total as i32;
    let maintenance = (cs.troops / MAINTENANCE_DIVISOR) as i32;
    cs.gold + income - maintenance < 0
}

pub fn weakest_neighbor(state: &GameState, country_id: CountryId) -> Option<CountryId> {
    state
        .adjacency
        .get(&country_id)?
        .iter()
        .filter(|&&n| state.countries.get(&n).is_some_and(|c| c.alive))
        .min_by_key(|&&n| state.countries[&n].troops)
        .copied()
}

pub fn free_target(state: &GameState, country_id: CountryId) -> Option<CountryId> {
    state
        .adjacency
        .get(&country_id)?
        .iter()
        .find(|&&n| {
            state
                .countries
                .get(&n)
                .is_some_and(|c| c.alive && c.troops == 0)
        })
        .copied()
}

pub fn update_pass_count(cs: &mut CountryState, actions: &[Action]) {
    let all_pass = actions.iter().all(|a| matches!(a, Action::Pass));
    if all_pass {
        cs.consecutive_passes += 1;
    } else {
        cs.consecutive_passes = 0;
    }
}

pub fn apply_pass_penalty(cs: &mut CountryState, daimyo_name: &str) {
    if cs.consecutive_passes >= 2 {
        let desert = cs.troops / 20;
        if desert > 0 {
            cs.troops = cs.troops.saturating_sub(desert);
            println!(
                "  ⚠ {}の兵{}が「戦わぬ主君に仕える意味なし」と脱走",
                daimyo_name, desert
            );
        }
    }
}

pub fn should_attack_target(
    personality: &Personality,
    my_troops: u32,
    target_troops: u32,
    consecutive_passes: u32,
    mood: &Mood,
) -> bool {
    if target_troops == 0 {
        return true;
    }

    let ratio = my_troops as f32 / target_troops as f32;

    let base_threshold = match personality {
        Personality::Impulsive => 1.2,
        Personality::Leader => 1.5,
        Personality::Analyst => 2.0,
        Personality::Stubborn => 2.5,
    };

    let mood_adjustment = (mood.aggression - 0.5) * 0.8
        + (mood.desperation - 0.5) * 0.6
        + (mood.confidence - 0.5) * 0.4;

    let pass_adjustment = consecutive_passes as f32 * 0.2;

    let adjusted = (base_threshold - mood_adjustment - pass_adjustment).max(1.0);
    ratio >= adjusted
}

pub fn forced_attack_target(
    state: &GameState,
    country_id: CountryId,
    mood: &Mood,
) -> Option<CountryId> {
    let cs = &state.countries[&country_id];
    let def = &state.defs[&country_id];

    state
        .adjacency
        .get(&country_id)?
        .iter()
        .filter(|&&n| {
            let nc = &state.countries[&n];
            nc.alive
                && !cs.allies.contains(&n)
                && should_attack_target(
                    &def.personality,
                    cs.troops,
                    nc.troops,
                    cs.consecutive_passes,
                    mood,
                )
        })
        .min_by_key(|&&n| state.countries[&n].troops)
        .copied()
}

pub fn check_game_end(state: &GameState) -> GameEnd {
    let player = &state.countries[&state.player_id];
    if !player.alive {
        return GameEnd::PlayerDead;
    }
    let alive_count = state.countries.values().filter(|c| c.alive).count();
    if alive_count == 1 {
        return GameEnd::PlayerWon;
    }
    if state.turn >= MAX_TURNS {
        return GameEnd::MaxTurns;
    }
    GameEnd::NotYet
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    fn make_test_state() -> GameState {
        let defs_vec = create_countries();
        let mut defs = HashMap::new();
        let mut countries = HashMap::new();
        for d in &defs_vec {
            countries.insert(
                d.id,
                CountryState {
                    id: d.id,
                    gold: d.initial_gold as i32,
                    troops: d.initial_troops,
                    territories: vec![d.id],
                    alive: true,
                    allies: HashSet::new(),
                    consecutive_passes: 0,
                },
            );
            defs.insert(d.id, d.clone());
        }
        GameState {
            turn: 0,
            year: START_YEAR,
            countries,
            defs,
            adjacency: create_adjacency(),
            player_id: PLAYER_COUNTRY,
            turn_log: Vec::new(),
        }
    }

    #[test]
    fn test_conscript() {
        let mut cs = CountryState {
            id: 5,
            gold: 100,
            troops: 78,
            territories: vec![5],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 0,
        };
        conscript(&mut cs, 69);
        assert_eq!(cs.troops, 78 + 69);
        assert_eq!(cs.gold, 100 - 69);
    }

    #[test]
    fn test_invasion_defender_wins() {
        let mut state = make_test_state();
        state.countries.get_mut(&3).unwrap().troops = 50;
        state.countries.get_mut(&5).unwrap().troops = 50;

        let results = resolve_battles(&mut state, &[(5, 3)]);
        assert_eq!(results.len(), 1);
        let r = &results[0];
        assert!(!r.is_wild);
        assert!(r.att_losses > r.def_losses);
        assert!(state.countries[&3].alive);
        assert!(state.countries[&5].alive);
    }

    #[test]
    fn test_invasion_attacker_conquers() {
        let mut state = make_test_state();
        state.countries.get_mut(&5).unwrap().troops = 200;
        state.countries.get_mut(&3).unwrap().troops = 10;

        let results = resolve_battles(&mut state, &[(5, 3)]);
        assert_eq!(results.len(), 1);
        assert!(!state.countries[&3].alive);
        assert_eq!(results[0].conquered, Some(3));
        assert_eq!(results[0].conqueror, Some(5));
        assert!(state.countries[&5].territories.contains(&3));
    }

    #[test]
    fn test_wild_battle() {
        let mut state = make_test_state();
        state.countries.get_mut(&1).unwrap().troops = 100;
        state.countries.get_mut(&2).unwrap().troops = 100;

        let results = resolve_battles(&mut state, &[(1, 2), (2, 1)]);
        assert_eq!(results.len(), 1);
        assert!(results[0].is_wild);
        assert_eq!(results[0].att_losses, 50);
        assert_eq!(results[0].def_losses, 50);
    }

    #[test]
    fn test_alliance_blocks_attack() {
        let mut state = make_test_state();
        resolve_alliances(&mut state, &[(1, 2, true)]);
        let results = resolve_battles(&mut state, &[(1, 2)]);
        assert!(results.is_empty());
    }

    #[test]
    fn test_economy_desertion() {
        let mut state = make_test_state();
        state.countries.get_mut(&3).unwrap().gold = -50;
        state.countries.get_mut(&3).unwrap().troops = 38;

        let defs = state.defs.clone();
        process_economy(&mut state, &defs);
        let cs = &state.countries[&3];
        assert_eq!(cs.gold, 0);
    }

    #[test]
    fn test_adjacency_update() {
        let mut adj = create_adjacency();
        update_adjacency(&mut adj, 5, 3);
        assert!(!adj.contains_key(&3));
        assert!(adj[&5].contains(&4));
        assert!(adj[&5].contains(&2));
        assert!(!adj[&5].contains(&3));
        assert!(adj[&4].contains(&5));
        assert!(!adj[&4].contains(&3));
    }

    #[test]
    fn test_can_afford_conscript() {
        let cs = CountryState {
            id: 5,
            gold: 100,
            troops: 50,
            territories: vec![5],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 0,
        };
        assert!(can_afford_conscript(&cs, 60));

        let cs = CountryState {
            id: 2,
            gold: 35,
            troops: 71,
            territories: vec![2],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 0,
        };
        assert!(!can_afford_conscript(&cs, 73));
    }

    #[test]
    fn test_is_desperate() {
        let cs = CountryState {
            id: 3,
            gold: 0,
            troops: 100,
            territories: vec![3],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 0,
        };
        assert!(is_desperate(&cs, 30));

        let cs = CountryState {
            id: 5,
            gold: 100,
            troops: 78,
            territories: vec![5],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 0,
        };
        assert!(!is_desperate(&cs, 69));
    }

    #[test]
    fn test_should_attack_impulsive() {
        let neutral = Mood::default();
        assert!(should_attack_target(
            &Personality::Impulsive,
            147,
            72,
            0,
            &neutral
        ));
    }

    #[test]
    fn test_should_attack_analyst_no() {
        let neutral = Mood::default();
        assert!(!should_attack_target(
            &Personality::Analyst,
            127,
            73,
            0,
            &neutral
        ));
    }

    #[test]
    fn test_should_attack_analyst_with_passes() {
        let neutral = Mood::default();
        assert!(should_attack_target(
            &Personality::Analyst,
            127,
            73,
            2,
            &neutral
        ));
    }

    #[test]
    fn test_mood_affects_attack_threshold() {
        let neutral = Mood::default();
        let aggressive = Mood {
            aggression: 0.9,
            desperation: 0.5,
            confidence: 0.8,
            diplomacy: 0.5,
        };
        assert!(!should_attack_target(
            &Personality::Analyst,
            127,
            73,
            0,
            &neutral
        ));
        assert!(should_attack_target(
            &Personality::Analyst,
            127,
            73,
            0,
            &aggressive
        ));
    }

    #[test]
    fn test_pass_penalty() {
        let mut cs = CountryState {
            id: 1,
            gold: 50,
            troops: 100,
            territories: vec![1],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 2,
        };
        apply_pass_penalty(&mut cs, "テスト");
        assert_eq!(cs.troops, 95);
    }

    #[test]
    fn test_update_pass_count() {
        let mut cs = CountryState {
            id: 1,
            gold: 50,
            troops: 100,
            territories: vec![1],
            alive: true,
            allies: HashSet::new(),
            consecutive_passes: 0,
        };
        update_pass_count(&mut cs, &[Action::Pass]);
        assert_eq!(cs.consecutive_passes, 1);
        update_pass_count(&mut cs, &[Action::Pass]);
        assert_eq!(cs.consecutive_passes, 2);
        update_pass_count(&mut cs, &[Action::Conscript]);
        assert_eq!(cs.consecutive_passes, 0);
    }
}
