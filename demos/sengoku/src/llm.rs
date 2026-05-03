use crate::types::*;
use serde::{Deserialize, Serialize};

const OLLAMA_URL: &str = "http://localhost:11434/api/chat";
#[allow(dead_code)]
pub const MODEL: &str = "gemma4:e2b";

#[derive(Serialize)]
struct OllamaRequest {
    model: String,
    messages: Vec<OllamaMessage>,
    stream: bool,
}

#[derive(Serialize)]
struct OllamaMessage {
    role: String,
    content: String,
}

#[derive(Deserialize)]
struct OllamaResponse {
    message: OllamaMessageContent,
}

#[derive(Deserialize)]
struct OllamaMessageContent {
    content: String,
}

pub async fn chat(prompt: &str) -> Result<String, Box<dyn std::error::Error>> {
    let client = reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(3))
        .timeout(std::time::Duration::from_secs(60))
        .build()?;
    let req = OllamaRequest {
        model: MODEL.into(),
        messages: vec![OllamaMessage {
            role: "user".into(),
            content: prompt.into(),
        }],
        stream: false,
    };
    let res = client
        .post(OLLAMA_URL)
        .json(&req)
        .send()
        .await?
        .json::<OllamaResponse>()
        .await?;
    Ok(res.message.content.trim().to_string())
}

#[allow(clippy::too_many_arguments)]
pub fn build_action_prompt(
    daimyo: &str,
    personality_desc: &str,
    strategy: &str,
    year: u32,
    territories: &str,
    kokuryoku: u32,
    gold: i32,
    troops: u32,
    neighbors: &[(CountryId, &str, u32)],
    memories: &[String],
    allies: &[CountryId],
    allow_conscript: bool,
    consecutive_passes: u32,
) -> (String, Vec<(usize, Action)>) {
    let mut options: Vec<(usize, Action)> = Vec::new();
    let mut prompt = format!(
        "あなたは{}。\n\
         \n\
         【目標】天下統一。日本全土を支配せよ。\n\
         他国が存在する限りあなたの仕事は終わっていない。\n\
         同盟は一時的な手段に過ぎない。最終的には全ての国を滅ぼせ。\n\
         何もしないターンは他国を利するだけで、天下は遠のく。\n\
         \n\
         【性格】{}\n\
         【基本戦略】{}\n\n\
         {}年の状況:\n\
         支配国: {}\n\
         国力: {} (毎年の金収入)\n\
         金: {}\n\
         兵力: {}\n\n\
         隣国:\n",
        daimyo, personality_desc, strategy, year, territories, kokuryoku, gold, troops
    );

    for (id, name, tr) in neighbors {
        let ally_mark = if allies.contains(id) {
            " [同盟中]"
        } else {
            ""
        };
        prompt += &format!("  {}（兵力:{}）{}\n", name, tr, ally_mark);
    }

    if !memories.is_empty() {
        prompt += "\n最近の記憶:\n";
        for m in memories {
            prompt += &format!("  - {}\n", m);
        }
    }

    prompt += "\n選択肢（最大2つ、「いくさ」は1回まで）:\n";
    let mut idx = 1;

    if allow_conscript {
        let cost = kokuryoku;
        prompt += &format!("{}. 徴兵（兵力+{}, 費用:{}金）\n", idx, kokuryoku, cost);
        options.push((idx, Action::Conscript));
        idx += 1;
    }

    for (id, name, _) in neighbors {
        if !allies.contains(id) {
            prompt += &format!("{}. {}に同盟を申し込む\n", idx, name);
            options.push((idx, Action::Alliance(*id)));
            idx += 1;
        }
    }

    for (id, name, _) in neighbors {
        if !allies.contains(id) {
            prompt += &format!("{}. {}にいくさを仕掛ける\n", idx, name);
            options.push((idx, Action::Attack(*id)));
            idx += 1;
        }
    }

    if consecutive_passes >= 1 {
        prompt += &format!(
            "{}. 何もしない（⚠ {}ターン連続で無行動。兵の士気が低下する）\n",
            idx,
            consecutive_passes + 1
        );
    } else {
        prompt += &format!("{}. 何もしない\n", idx);
    }
    options.push((idx, Action::Pass));

    prompt += "\n数字をカンマ区切りで答えよ（例: 1,5）。数字のみ回答。";

    (prompt, options)
}

#[allow(clippy::too_many_arguments)]
pub fn build_alliance_response_prompt(
    daimyo: &str,
    personality_desc: &str,
    strategy: &str,
    proposer_name: &str,
    my_troops: u32,
    my_gold: i32,
    proposer_troops: u32,
    memories: &[String],
) -> String {
    let mut prompt = format!(
        "あなたは{}。\n\
         \n\
         【目標】天下統一。日本全土を支配せよ。\n\
         他国が存在する限りあなたの仕事は終わっていない。\n\
         同盟は一時的な手段に過ぎない。最終的には全ての国を滅ぼせ。\n\
         \n\
         【性格】{}\n\
         【基本戦略】{}\n\n\
         {}があなたに同盟を申し込んでいる。\n\n\
         あなた: 兵力{}, 金{}\n\
         {}: 兵力{}\n",
        daimyo,
        personality_desc,
        strategy,
        proposer_name,
        my_troops,
        my_gold,
        proposer_name,
        proposer_troops
    );
    if !memories.is_empty() {
        prompt += "\n記憶:\n";
        for m in memories {
            prompt += &format!("  - {}\n", m);
        }
    }
    prompt += "\n1. 受ける\n2. 断る\n\n数字のみ回答。";
    prompt
}

pub fn parse_action_response(response: &str, max_option: usize) -> Vec<usize> {
    let nums: Vec<usize> = response
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == ',')
        .collect::<String>()
        .split(',')
        .filter_map(|s| s.trim().parse::<usize>().ok())
        .filter(|&n| n >= 1 && n <= max_option)
        .collect();

    if nums.is_empty() {
        vec![max_option]
    } else {
        nums.into_iter().take(2).collect()
    }
}

pub fn parse_alliance_response(response: &str) -> bool {
    response.trim().starts_with('1')
}

#[allow(dead_code)]
pub fn build_scoring_prompt(preset_json: &str, text: &str) -> String {
    let preset: serde_json::Value = serde_json::from_str(preset_json).unwrap();
    let axes = preset["axes"].as_array().unwrap();

    let mut prompt =
        "以下のテキストを16因子でスコアリングせよ。各因子は0〜255の整数。\n\n因子:\n".to_string();
    for ax in axes {
        let idx = ax["index"].as_u64().unwrap();
        let name = ax["name"].as_str().unwrap();
        let low = ax["low"].as_str().unwrap();
        let high = ax["high"].as_str().unwrap();
        prompt += &format!("{}. {} ({}=0, {}=255)\n", idx, name, low, high);
    }
    prompt += &format!("\nテキスト: 「{}」\n\n", text);
    prompt += "カンマ区切りの数値16個のみ回答。例: 128,50,200,100,80,60,40,30,100,150,90,70,128,180,60,100";
    prompt
}

pub fn parse_scores(response: &str) -> [u8; 16] {
    let mut features = [128u8; 16];
    let nums: Vec<u8> = response
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == ',')
        .collect::<String>()
        .split(',')
        .filter_map(|s| s.trim().parse::<u8>().ok())
        .collect();
    for (i, &v) in nums.iter().enumerate().take(16) {
        features[i] = v;
    }
    features
}

#[allow(dead_code)]
pub async fn score_text_with_llm(text: &str, preset_json: &str, _model: &str) -> [u8; 16] {
    let prompt = build_scoring_prompt(preset_json, text);
    match chat(&prompt).await {
        Ok(response) => parse_scores(&response),
        Err(_) => [128u8; 16],
    }
}

pub fn situation_vector(
    troops: u32,
    gold: i32,
    kokuryoku: u32,
    neighbors_max_troops: u32,
    personality: &Personality,
) -> [u8; 16] {
    let mut v = [128u8; 16];

    let threat = if troops == 0 {
        255
    } else {
        (255 * neighbors_max_troops / (troops + neighbors_max_troops)).min(255) as u8
    };
    v[11] = threat;
    v[13] = 255 - threat;
    v[10] = threat.saturating_sub(30);

    v[14] = match personality {
        Personality::Impulsive => 220,
        Personality::Leader => 180,
        Personality::Analyst => 100,
        Personality::Stubborn => 80,
    };

    v[8] = if gold > kokuryoku as i32 * 2 {
        200
    } else if gold > 0 {
        150
    } else {
        50
    };

    v
}

pub fn build_inner_voice_prompt(daimyo: &str, situation_summary: &str) -> String {
    format!(
        "あなたは{}。今年の出来事を受けて一言つぶやけ。20文字以内。\n\n{}\n\n回答:",
        daimyo, situation_summary
    )
}

pub fn build_batch_scoring_prompt(preset_json: &str, texts: &[(u64, String)]) -> String {
    let preset: serde_json::Value = serde_json::from_str(preset_json).unwrap();
    let axes = preset["axes"].as_array().unwrap();

    let mut prompt = String::from(
        "以下のテキスト群を16因子でスコアリングせよ。各因子は0〜255の整数。\n\n因子:\n",
    );
    for ax in axes {
        let idx = ax["index"].as_u64().unwrap();
        let name = ax["name"].as_str().unwrap();
        let low = ax["low"].as_str().unwrap();
        let high = ax["high"].as_str().unwrap();
        prompt += &format!("{}. {} ({}=0, {}=255)\n", idx, name, low, high);
    }

    prompt += "\nテキスト:\n";
    for (i, (_id, text)) in texts.iter().enumerate() {
        prompt += &format!("[{}] 「{}」\n", i + 1, text);
    }

    prompt += "\n各行に番号とカンマ区切り16数値で回答。他の文字は不要。\n";
    prompt += "1: 80,80,128,128,128,128,20,20,60,210,100,80,128,170,160,80\n";
    prompt += "2: 30,10,128,128,230,210,220,20,140,128,120,150,80,180,80,60\n";
    prompt += "のように。";

    prompt
}

pub fn parse_batch_scores(response: &str, expected_count: usize) -> Vec<[u8; 16]> {
    let mut results = Vec::new();

    for line in response.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }

        let scores_part = if let Some(pos) = line.find(':') {
            &line[pos + 1..]
        } else {
            line
        };

        let nums: Vec<u8> = scores_part
            .split(',')
            .filter_map(|s| s.trim().parse::<u8>().ok())
            .collect();

        if nums.len() >= 16 {
            let mut features = [128u8; 16];
            for (i, &v) in nums.iter().enumerate().take(16) {
                features[i] = v;
            }
            results.push(features);
        }
    }

    while results.len() < expected_count {
        results.push([128u8; 16]);
    }

    results
}

async fn batch_score_chunk(chunk: &[(u64, String)], preset_json: &str) -> Vec<(u64, [u8; 16])> {
    let prompt = build_batch_scoring_prompt(preset_json, chunk);
    match chat(&prompt).await {
        Ok(response) => {
            let scores = parse_batch_scores(&response, chunk.len());
            chunk
                .iter()
                .zip(scores)
                .map(|((id, _), f)| (*id, f))
                .collect()
        }
        Err(_) => chunk.iter().map(|(id, _)| (*id, [128u8; 16])).collect(),
    }
}

pub async fn batch_score(texts: &[(u64, String)], preset_json: &str) -> Vec<(u64, [u8; 16])> {
    let mut results = Vec::new();
    for chunk in texts.chunks(4) {
        let features_list = batch_score_chunk(chunk, preset_json).await;
        results.extend(features_list);
    }
    results
}

#[cfg(test)]
mod tests {
    use super::*;
    #[allow(unused_imports)]
    use crate::scenario::PRESET_JSON;

    #[test]
    fn test_parse_action_response() {
        assert_eq!(parse_action_response("1,5", 8), vec![1, 5]);
        assert_eq!(parse_action_response("abc", 8), vec![8]);
        assert_eq!(parse_action_response("1,2,3,4", 8), vec![1, 2]);
        assert_eq!(parse_action_response("0,9", 8), vec![8]);
    }

    #[test]
    fn test_parse_scores() {
        let r = parse_scores("128,50,200,100,80,60,40,30,100,150,90,70,128,180,60,100");
        assert_eq!(r[0], 128);
        assert_eq!(r[2], 200);
        assert_eq!(r[15], 100);
    }

    #[test]
    fn test_build_action_prompt() {
        let neighbors = vec![(3u32, "斉藤義竜", 38u32)];
        let (prompt, options) = build_action_prompt(
            "織田信長",
            "攻め気。兵力が隣国を上回っていれば迷わず攻撃する。",
            "最弱の斉藤を早期に併合せよ。",
            1560,
            "尾張",
            69,
            100,
            78,
            &neighbors,
            &[],
            &[],
            true,
            0,
        );
        assert!(prompt.contains("織田信長"));
        assert!(prompt.contains("【性格】"));
        assert!(prompt.contains("【基本戦略】"));
        assert!(prompt.contains("【目標】天下統一"));
        assert!(prompt.contains("1."));
        assert!(options.len() >= 3);
    }

    #[test]
    fn test_parse_batch_scores() {
        let response = "1: 80,80,128,128,128,128,20,20,60,210,100,80,128,170,160,80\n\
                         2: 30,10,128,128,230,210,220,20,140,128,120,150,80,180,80,60\n";
        let results = parse_batch_scores(response, 2);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0][0], 80);
        assert_eq!(results[1][0], 30);
        assert_eq!(results[1][4], 230);

        let partial = "1: 80,80,128,128,128,128,20,20,60,210,100,80,128,170,160,80\n";
        let results = parse_batch_scores(partial, 3);
        assert_eq!(results.len(), 3);
        assert_eq!(results[0][0], 80);
        assert_eq!(results[1], [128u8; 16]);
        assert_eq!(results[2], [128u8; 16]);
    }
}
