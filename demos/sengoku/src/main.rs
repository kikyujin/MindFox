mod engine;
mod llm;
mod memory;
mod scenario;
mod types;

use rand::Rng;
use scenario::*;
use std::collections::HashMap;
use types::*;

impl GameState {
    fn new(defs_vec: &[CountryDef], adjacency: HashMap<CountryId, Vec<CountryId>>) -> Self {
        let mut defs = HashMap::new();
        let mut countries = HashMap::new();
        for d in defs_vec {
            countries.insert(
                d.id,
                CountryState {
                    id: d.id,
                    gold: d.initial_gold as i32,
                    troops: d.initial_troops,
                    territories: vec![d.id],
                    alive: true,
                    allies: std::collections::HashSet::new(),
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
            adjacency,
            player_id: PLAYER_COUNTRY,
            turn_log: Vec::new(),
        }
    }
}

fn display_status(state: &GameState) {
    println!("\n【国勢】");
    let mut ids: Vec<CountryId> = state.countries.keys().cloned().collect();
    ids.sort();
    for id in ids {
        let cs = &state.countries[&id];
        if !cs.alive {
            continue;
        }
        let def = &state.defs[&id];
        let koku: u32 = cs
            .territories
            .iter()
            .map(|tid| state.defs[tid].base_kokuryoku)
            .sum();
        let terr_names: Vec<&str> = cs
            .territories
            .iter()
            .map(|tid| state.defs[tid].name.as_str())
            .collect();
        let player_mark = if id == state.player_id {
            "  ← あなた"
        } else {
            ""
        };
        println!(
            "  {:10} | {:16} | 国力:{:<3} 金:{:<4} 兵力:{:<4}{}",
            def.daimyo,
            terr_names.join(", "),
            koku,
            cs.gold,
            cs.troops,
            player_mark
        );
    }
}

fn display_final_ranking(state: &GameState) {
    println!("\n【最終順位】");
    let mut ranking: Vec<(CountryId, u32)> = state
        .countries
        .iter()
        .filter(|(_, cs)| cs.alive)
        .map(|(&id, cs)| (id, cs.troops + cs.territories.len() as u32 * 100))
        .collect();
    ranking.sort_by_key(|b| std::cmp::Reverse(b.1));
    for (i, (id, score)) in ranking.iter().enumerate() {
        println!("  {}. {} (スコア:{})", i + 1, state.defs[id].daimyo, score);
    }
}

fn register_world_cells(mxbs: &mxbs::MxBS, reg: &mxbs::AgentRegistry, defs: &[CountryDef]) {
    for (i, d) in defs.iter().enumerate() {
        let text = format!(
            "{}は国力{}の国である。大名は{}。",
            d.name, d.base_kokuryoku, d.daimyo
        );
        let owner = reg.owner_id(memory::AGENT_GM).unwrap();
        mxbs.store(
            mxbs::Cell::new(owner, &text)
                .turn(0)
                .group_bits(reg.all_bits())
                .mode(0o444)
                .price(255)
                .features(memory::WORLD_FEATURES[i]),
        )
        .unwrap();
    }
}

fn get_alive_neighbors(state: &GameState, id: CountryId) -> Vec<(CountryId, &str, u32)> {
    state
        .adjacency
        .get(&id)
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter(|&&nid| state.countries.get(&nid).is_some_and(|c| c.alive))
        .map(|&nid| {
            (
                nid,
                state.defs[&nid].daimyo.as_str(),
                state.countries[&nid].troops,
            )
        })
        .collect()
}

async fn decide_action(
    state: &GameState,
    id: CountryId,
    mxbs: &mxbs::MxBS,
    reg: &mxbs::AgentRegistry,
) -> TurnActions {
    let cs = &state.countries[&id];
    let def = &state.defs[&id];
    let neighbors = get_alive_neighbors(state, id);
    let koku: u32 = cs
        .territories
        .iter()
        .map(|tid| state.defs[tid].base_kokuryoku)
        .sum();

    if neighbors.is_empty() {
        return TurnActions {
            country_id: id,
            actions: vec![Action::Conscript],
        };
    }

    // Mood算出（MxBS記憶から）
    let slug = memory::country_slug(id);
    let mood = memory::get_agent_mood(mxbs, reg, slug, state.turn);

    // === 強制ロジック ===

    if let Some(target) = engine::killable_target(state, id) {
        println!(
            "  {} → {}を確殺（兵力{}で一撃）",
            def.daimyo, state.defs[&target].daimyo, state.countries[&target].troops
        );
        return TurnActions {
            country_id: id,
            actions: vec![Action::Attack(target)],
        };
    }

    if let Some(target) = engine::free_target(state, id) {
        println!(
            "  {} → {}に無血進軍（兵力0）",
            def.daimyo, state.defs[&target].daimyo
        );
        return TurnActions {
            country_id: id,
            actions: vec![Action::Attack(target)],
        };
    }

    if engine::is_desperate(cs, koku)
        && let Some(target) = engine::weakest_neighbor(state, id)
    {
        println!(
            "  {} → 追い詰められ{}に決死の突撃！",
            def.daimyo, state.defs[&target].daimyo
        );
        return TurnActions {
            country_id: id,
            actions: vec![Action::Attack(target)],
        };
    }

    // 4. 性格別の強制攻撃（覇気ルール + Mood補正）
    if let Some(target) = engine::forced_attack_target(state, id, &mood) {
        let target_name = &state.defs[&target].daimyo;
        println!(
            "  {} → {}を攻める好機！（兵力差で優勢, 覇気:{:.2}）",
            def.daimyo, target_name, mood.aggression
        );
        let mut actions = vec![Action::Attack(target)];
        if engine::can_afford_conscript(cs, koku) {
            actions.push(Action::Conscript);
        }
        return TurnActions {
            country_id: id,
            actions,
        };
    }

    let allow_conscript = engine::can_afford_conscript(cs, koku);

    // === LLM に判断を投げる ===

    let max_neighbor_troops = neighbors.iter().map(|(_, _, t)| *t).max().unwrap_or(0);
    let query = llm::situation_vector(
        cs.troops,
        cs.gold,
        koku,
        max_neighbor_troops,
        &def.personality,
    );
    let memories = memory::get_memories_for_agent(mxbs, reg, slug, query, state.turn);
    let mem_slice: Vec<String> = memories.into_iter().take(5).collect();

    let terr_names: Vec<&str> = cs
        .territories
        .iter()
        .map(|tid| state.defs[tid].name.as_str())
        .collect();
    let allies_vec: Vec<CountryId> = cs.allies.iter().cloned().collect();

    let (prompt, options) = llm::build_action_prompt(
        &def.daimyo,
        scenario::personality_desc(&def.personality),
        &def.strategy,
        state.year,
        &terr_names.join(", "),
        koku,
        cs.gold,
        cs.troops,
        &neighbors,
        &mem_slice,
        &allies_vec,
        allow_conscript,
        cs.consecutive_passes,
    );

    print!("  {} 行動中...", def.daimyo);
    use std::io::Write;
    std::io::stdout().flush().ok();

    match llm::chat(&prompt).await {
        Ok(response) => {
            println!(" OK");
            let indices = llm::parse_action_response(&response, options.len());
            let mut actions: Vec<Action> = Vec::new();
            let mut has_attack = false;
            for idx in indices {
                if let Some((_, action)) = options.iter().find(|(i, _)| *i == idx) {
                    match action {
                        Action::Attack(_) if has_attack => continue,
                        Action::Attack(_) => {
                            has_attack = true;
                        }
                        _ => {}
                    }
                    actions.push(action.clone());
                }
            }
            TurnActions {
                country_id: id,
                actions,
            }
        }
        Err(e) => {
            println!(" [LLM失敗: {} → ランダム行動]", e);
            random_action(id, &neighbors, koku, cs)
        }
    }
}

fn random_action(
    id: CountryId,
    neighbors: &[(CountryId, &str, u32)],
    _kokuryoku: u32,
    _cs: &CountryState,
) -> TurnActions {
    let mut rng = rand::thread_rng();
    let mut actions = Vec::new();

    let roll: u32 = rng.gen_range(0..100);
    if roll < 40 {
        actions.push(Action::Conscript);
    } else if roll < 60 && !neighbors.is_empty() {
        let target = neighbors[rng.gen_range(0..neighbors.len())].0;
        actions.push(Action::Alliance(target));
    } else if roll < 90 && !neighbors.is_empty() {
        let target = neighbors[rng.gen_range(0..neighbors.len())].0;
        actions.push(Action::Attack(target));
    } else {
        actions.push(Action::Pass);
    }

    if actions.len() < 2 && rng.gen_bool(0.3) {
        actions.push(Action::Conscript);
    }

    TurnActions {
        country_id: id,
        actions,
    }
}

async fn collect_all_actions(
    state: &GameState,
    mxbs: &mxbs::MxBS,
    reg: &mxbs::AgentRegistry,
) -> Vec<TurnActions> {
    let mut all = Vec::new();
    let mut ids: Vec<CountryId> = state
        .countries
        .keys()
        .filter(|id| state.countries[id].alive)
        .cloned()
        .collect();
    ids.sort();
    println!("\n【意思決定フェイズ】");
    for id in ids {
        let ta = decide_action(state, id, mxbs, reg).await;
        all.push(ta);
    }
    all
}

fn process_conscriptions(state: &mut GameState, all_actions: &[TurnActions]) {
    for ta in all_actions {
        for action in &ta.actions {
            if let Action::Conscript = action {
                let koku: u32 = state.countries[&ta.country_id]
                    .territories
                    .iter()
                    .map(|tid| state.defs[tid].base_kokuryoku)
                    .sum();
                let cs = state.countries.get_mut(&ta.country_id).unwrap();
                engine::conscript(cs, koku);
            }
        }
    }
}

async fn process_alliance_proposals(
    state: &GameState,
    all_actions: &[TurnActions],
    mxbs: &mxbs::MxBS,
    reg: &mxbs::AgentRegistry,
) -> Vec<(CountryId, CountryId, bool)> {
    let mut raw: Vec<(CountryId, CountryId)> = Vec::new();
    let mut attack_targets: HashMap<CountryId, Vec<CountryId>> = HashMap::new();
    for ta in all_actions {
        for action in &ta.actions {
            match action {
                Action::Alliance(target) if state.countries[target].alive => {
                    raw.push((ta.country_id, *target));
                }
                Action::Attack(target) => {
                    attack_targets
                        .entry(ta.country_id)
                        .or_default()
                        .push(*target);
                }
                _ => {}
            }
        }
    }

    let mut results = Vec::new();
    let mut handled = std::collections::HashSet::new();

    for &(a, b) in &raw {
        if handled.contains(&a) && handled.contains(&b) {
            continue;
        }
        if raw.contains(&(b, a)) && !handled.contains(&a) && !handled.contains(&b) {
            let a_name = &state.defs[&a].daimyo;
            let b_name = &state.defs[&b].daimyo;
            println!(
                "  {}と{}が相互に同盟を申し込み → 自動成立！",
                a_name, b_name
            );
            results.push((a, b, true));
            handled.insert(a);
            handled.insert(b);
            continue;
        }
        if handled.contains(&a) {
            continue;
        }

        // Step A: 受諾側が提案側を攻撃予定 → 自動拒否
        if attack_targets
            .get(&b)
            .is_some_and(|targets| targets.contains(&a))
        {
            let from_name = &state.defs[&a].daimyo;
            let to_name = &state.defs[&b].daimyo;
            println!(
                "  → {}は{}への攻撃を準備中のため同盟を拒否",
                to_name, from_name
            );
            results.push((a, b, false));
            continue;
        }

        // Moodベースの自動拒否（信頼度 < 0.3）
        let trust_toward_proposer = memory::compute_diplomacy_toward(
            mxbs,
            reg,
            memory::country_slug(b),
            memory::country_slug(a),
            state.turn,
        );
        if trust_toward_proposer < 0.3 {
            let from_name = &state.defs[&a].daimyo;
            let to_name = &state.defs[&b].daimyo;
            println!(
                "  → {}は{}を信用できず同盟を拒否（信頼度:{:.2}）",
                to_name, from_name, trust_toward_proposer
            );
            results.push((a, b, false));
            continue;
        }

        let from_def = &state.defs[&a];
        let to_def = &state.defs[&b];
        let to_cs = &state.countries[&b];
        let from_cs = &state.countries[&a];

        let slug = memory::country_slug(b);
        let query = [128u8; 16];
        let memories = memory::get_memories_for_agent(mxbs, reg, slug, query, state.turn);
        let mem_slice: Vec<String> = memories.into_iter().take(3).collect();

        let prompt = llm::build_alliance_response_prompt(
            &to_def.daimyo,
            scenario::personality_desc(&to_def.personality),
            &to_def.strategy,
            &from_def.daimyo,
            to_cs.troops,
            to_cs.gold,
            from_cs.troops,
            &mem_slice,
        );

        print!(
            "  {} 同盟判断中（{}からの申込）...",
            to_def.daimyo, from_def.daimyo
        );
        std::io::Write::flush(&mut std::io::stdout()).ok();

        let accepted = match llm::chat(&prompt).await {
            Ok(response) => {
                println!(" OK");
                llm::parse_alliance_response(&response)
            }
            Err(e) => {
                println!(" [LLM失敗: {} → ランダム判定]", e);
                rand::thread_rng().gen_bool(0.4)
            }
        };
        results.push((a, b, accepted));
    }
    results
}

fn collect_attacks(all_actions: &[TurnActions]) -> Vec<(CountryId, CountryId)> {
    let mut attacks = Vec::new();
    for ta in all_actions {
        for action in &ta.actions {
            if let Action::Attack(target) = action {
                attacks.push((ta.country_id, *target));
            }
        }
    }
    attacks
}

fn report_and_store_results(
    state: &mut GameState,
    all_actions: &[TurnActions],
    proposals: &[(CountryId, CountryId, bool)],
    battles: &[BattleResult],
    mxbs: &mxbs::MxBS,
    reg: &mxbs::AgentRegistry,
) {
    println!("\n【行動】");
    for ta in all_actions {
        let def = &state.defs[&ta.country_id];
        let action_strs: Vec<String> = ta
            .actions
            .iter()
            .map(|a| match a {
                Action::Conscript => "徴兵".to_string(),
                Action::Alliance(t) => format!("{}に同盟を申し込む", state.defs[t].daimyo),
                Action::Attack(t) => format!("{}にいくさ", state.defs[t].daimyo),
                Action::Pass => "何もしない".to_string(),
            })
            .collect();
        println!("  {:10} → {}", def.daimyo, action_strs.join(" + "));

        for action in &ta.actions {
            if let Action::Conscript = action {
                let text = format!("{}が徴兵を行った", def.daimyo);
                memory::store_event_scored(
                    mxbs,
                    reg,
                    state.turn,
                    memory::country_slug(ta.country_id),
                    &text,
                    40,
                    0o744,
                    memory::EventType::Conscript,
                );
            }
        }
    }

    for &(from, to, accepted) in proposals {
        let from_name = &state.defs[&from].daimyo;
        let to_name = &state.defs[&to].daimyo;
        if accepted {
            println!("  → {}と{}の同盟成立！", from_name, to_name);
            let text = format!("{}と{}が同盟を結んだ", from_name, to_name);
            memory::store_alliance_event(
                mxbs,
                reg,
                state.turn,
                memory::country_slug(from),
                memory::country_slug(to),
                &text,
                80,
                memory::EventType::AllianceFormed,
            );
        } else {
            println!("  → {}が{}の同盟を断った", to_name, from_name);
            let text = format!("{}が{}の同盟を断った", to_name, from_name);
            memory::store_alliance_event(
                mxbs,
                reg,
                state.turn,
                memory::country_slug(from),
                memory::country_slug(to),
                &text,
                60,
                memory::EventType::AllianceRejected,
            );
        }
    }

    if !battles.is_empty() {
        for r in battles {
            let att_name = &state.defs[&r.attacker].daimyo;
            let def_name = &state.defs[&r.defender].daimyo;
            if r.is_wild {
                println!(
                    "  ⚔ {}と{}が野戦！ {}側損失:{}, {}側損失:{}",
                    att_name, def_name, att_name, r.att_losses, def_name, r.def_losses
                );
            } else {
                println!(
                    "  ⚔ {}が{}に侵攻！ 攻撃側損失:{}, 防御側損失:{}",
                    att_name, def_name, r.att_losses, r.def_losses
                );
            }

            let att_troops_before = state.countries[&r.attacker].troops + r.att_losses;
            let def_troops_before = state.countries[&r.defender].troops + r.def_losses;
            let att_won = r.conqueror == Some(r.attacker)
                || (r.conquered.is_none() && r.att_losses < r.def_losses);
            let def_won = r.conqueror == Some(r.defender)
                || (r.conquered.is_none() && r.def_losses < r.att_losses);
            let att_loss_ratio = if att_troops_before > 0 {
                r.att_losses as f32 / att_troops_before as f32
            } else {
                1.0
            };
            let def_loss_ratio = if def_troops_before > 0 {
                r.def_losses as f32 / def_troops_before as f32
            } else {
                1.0
            };

            let text = format!(
                "{}が{}と戦い、{}は兵{}を失い、{}は兵{}を失った",
                att_name, def_name, att_name, r.att_losses, def_name, r.def_losses
            );
            memory::store_event_scored(
                mxbs,
                reg,
                state.turn,
                memory::country_slug(r.attacker),
                &text,
                100,
                0o744,
                memory::EventType::BattleAttacker {
                    won: att_won,
                    loss_ratio: att_loss_ratio,
                },
            );
            memory::store_event_scored(
                mxbs,
                reg,
                state.turn,
                memory::country_slug(r.defender),
                &text,
                100,
                0o744,
                memory::EventType::BattleDefender {
                    won: def_won,
                    loss_ratio: def_loss_ratio,
                },
            );

            if let (Some(conqueror), Some(conquered)) = (r.conqueror, r.conquered) {
                let winner = &state.defs[&conqueror].daimyo;
                let loser = &state.defs[&conquered].daimyo;
                let loser_land = &state.defs[&conquered].name;
                println!(
                    "  💀 {}が滅亡！{}は{}の支配下に。",
                    loser, loser_land, winner
                );
                let text_win = format!(
                    "{}が{}を滅ぼし、{}を支配下に置いた",
                    winner, loser, loser_land
                );
                memory::store_event_scored(
                    mxbs,
                    reg,
                    state.turn,
                    memory::country_slug(conqueror),
                    &text_win,
                    200,
                    0o744,
                    memory::EventType::Conquered,
                );
                let text_lose = format!("{}は滅亡した", loser);
                memory::store_event_scored(
                    mxbs,
                    reg,
                    state.turn,
                    memory::country_slug(conquered),
                    &text_lose,
                    200,
                    0o744,
                    memory::EventType::Eliminated,
                );
            }
        }
    }
}

async fn generate_inner_voices(
    state: &GameState,
    all_actions: &[TurnActions],
    mxbs: &mxbs::MxBS,
    reg: &mxbs::AgentRegistry,
) {
    println!("\n【内心フェイズ】");
    for ta in all_actions {
        if !state.countries[&ta.country_id].alive {
            continue;
        }
        let def = &state.defs[&ta.country_id];
        let cs = &state.countries[&ta.country_id];
        let mood =
            memory::get_agent_mood(mxbs, reg, memory::country_slug(ta.country_id), state.turn);
        let mood_hint = if mood.desperation > 0.7 {
            "あなたは追い詰められている。焦りと恐怖が支配している。"
        } else if mood.aggression > 0.7 {
            "あなたは勝利に酔っている。もっと領土が欲しい。"
        } else if mood.confidence > 0.7 {
            "あなたは絶好調。天下は近い。"
        } else if mood.confidence < 0.3 {
            "あなたは弱気だ。周囲の強国に怯えている。"
        } else {
            "冷静に状況を分析している。"
        };
        let summary = format!(
            "兵力:{}, 金:{}, 領土数:{}\n気分: {}",
            cs.troops,
            cs.gold,
            cs.territories.len(),
            mood_hint
        );
        let prompt = llm::build_inner_voice_prompt(&def.daimyo, &summary);
        print!("  {} 内心...", def.daimyo);
        std::io::Write::flush(&mut std::io::stdout()).ok();
        match llm::chat(&prompt).await {
            Ok(voice) => {
                println!(" 「{}」", voice);
                let slug = memory::country_slug(ta.country_id);
                memory::store_event(mxbs, reg, state.turn, slug, &voice, 70, 0o700);
            }
            Err(e) => {
                println!(" [LLM失敗: {} → スキップ]", e);
            }
        }
    }
}

#[tokio::main]
async fn main() {
    println!("=== 戦国SIM — MxBS デモ ===\n");

    let defs_vec = create_countries();
    let adjacency = create_adjacency();
    let (mxbs, reg) = memory::init_memory();
    let mut state = GameState::new(&defs_vec, adjacency);

    register_world_cells(&mxbs, &reg, &defs_vec);

    loop {
        state.turn += 1;
        state.year = START_YEAR + state.turn - 1;
        state.turn_log.clear();

        println!("\n{}", "=".repeat(50));
        println!("  {}年（ターン{}）", state.year, state.turn);
        println!("{}", "=".repeat(50));

        let defs_clone = state.defs.clone();
        engine::process_economy(&mut state, &defs_clone);
        display_status(&state);

        // Moodログ表示
        println!("\n【気分】");
        let mut alive_ids: Vec<CountryId> = state
            .countries
            .keys()
            .filter(|id| state.countries[id].alive)
            .cloned()
            .collect();
        alive_ids.sort();
        for &aid in &alive_ids {
            let slug = memory::country_slug(aid);
            let mood = memory::get_agent_mood(&mxbs, &reg, slug, state.turn);
            let def = &state.defs[&aid];
            println!(
                "  {:10} | 覇気:{:.2} 焦燥:{:.2} 自信:{:.2} 外交:{:.2}",
                def.daimyo, mood.aggression, mood.desperation, mood.confidence, mood.diplomacy
            );
        }

        let all_actions = collect_all_actions(&state, &mxbs, &reg).await;

        process_conscriptions(&mut state, &all_actions);

        let proposals = process_alliance_proposals(&state, &all_actions, &mxbs, &reg).await;
        engine::resolve_alliances(&mut state, &proposals);

        let attacks = collect_attacks(&all_actions);
        let battles = engine::resolve_battles(&mut state, &attacks);

        report_and_store_results(&mut state, &all_actions, &proposals, &battles, &mxbs, &reg);

        for r in &battles {
            if let (Some(conqueror), Some(conquered)) = (r.conqueror, r.conquered) {
                engine::update_adjacency(&mut state.adjacency, conqueror, conquered);
            }
        }

        // Step C: 連続パスペナルティ
        let defs_ref = state.defs.clone();
        for ta in &all_actions {
            if let Some(cs) = state.countries.get_mut(&ta.country_id) {
                if !cs.alive {
                    continue;
                }
                engine::update_pass_count(cs, &ta.actions);
                let daimyo_name = &defs_ref[&ta.country_id].daimyo;
                engine::apply_pass_penalty(cs, daimyo_name);
            }
        }

        generate_inner_voices(&state, &all_actions, &mxbs, &reg).await;

        println!("\n【記憶スコアリング】");
        memory::score_all_pending(&mxbs, PRESET_JSON).await;

        match engine::check_game_end(&state) {
            engine::GameEnd::PlayerDead => {
                println!("\n💀 {}は滅亡した…", state.defs[&state.player_id].daimyo);
                break;
            }
            engine::GameEnd::PlayerWon => {
                println!("\n🏯 {}が天下統一！", state.defs[&state.player_id].daimyo);
                break;
            }
            engine::GameEnd::MaxTurns => {
                println!("\n⏰ {}ターンが経過。天下は定まらず。", MAX_TURNS);
                display_final_ranking(&state);
                break;
            }
            engine::GameEnd::NotYet => {}
        }
    }

    mxbs.save_to("sengoku_save.db").unwrap();
    println!("\nセーブ完了: sengoku_save.db");

    let stats = mxbs.stats().unwrap();
    println!("記憶セル数: {}", stats.total);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_game_state_init() {
        let defs_vec = create_countries();
        let adjacency = create_adjacency();
        let state = GameState::new(&defs_vec, adjacency);
        assert_eq!(state.countries.len(), 5);
        assert!(state.countries.values().all(|c| c.alive));
        assert_eq!(state.player_id, 5);
        assert_eq!(state.countries[&5].troops, 78);
        assert_eq!(state.countries[&5].gold, 100);
    }

    #[tokio::test]
    async fn test_full_turn_no_llm() {
        let defs_vec = create_countries();
        let adjacency = create_adjacency();
        let (mxbs, reg) = memory::init_memory();
        let mut state = GameState::new(&defs_vec, adjacency);
        register_world_cells(&mxbs, &reg, &defs_vec);

        state.turn = 1;
        state.year = START_YEAR;

        let defs_clone = state.defs.clone();
        engine::process_economy(&mut state, &defs_clone);

        let all_actions = collect_all_actions(&state, &mxbs, &reg).await;
        process_conscriptions(&mut state, &all_actions);
        let proposals = process_alliance_proposals(&state, &all_actions, &mxbs, &reg).await;
        engine::resolve_alliances(&mut state, &proposals);
        let attacks = collect_attacks(&all_actions);
        let battles = engine::resolve_battles(&mut state, &attacks);
        report_and_store_results(&mut state, &all_actions, &proposals, &battles, &mxbs, &reg);

        assert!(state.countries.values().any(|c| c.alive));
    }
}
