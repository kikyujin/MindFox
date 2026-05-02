use crate::{MxBSError, FACTOR_DIM};

#[derive(Debug, Clone)]
pub struct Axis {
    pub index: usize,
    pub name: String,
    pub low: String,
    pub high: String,
}

#[derive(Debug, Clone)]
pub struct Preset {
    pub name: String,
    pub axes: Vec<Axis>,
}

impl Preset {
    pub fn from_json(json_str: &str) -> Result<Self, MxBSError> {
        let v: serde_json::Value = serde_json::from_str(json_str)
            .map_err(|e| MxBSError::Io(format!("JSON parse error: {e}")))?;

        let name = v["name"].as_str()
            .ok_or_else(|| MxBSError::Io("missing 'name' field".into()))?
            .to_string();

        let axes_arr = v["axes"].as_array()
            .ok_or_else(|| MxBSError::Io("missing 'axes' array".into()))?;

        if axes_arr.len() != FACTOR_DIM {
            return Err(MxBSError::Io(format!("expected 16 axes, got {}", axes_arr.len())));
        }

        let mut axes = Vec::with_capacity(FACTOR_DIM);
        for ax in axes_arr {
            axes.push(Axis {
                index: ax["index"].as_u64()
                    .ok_or_else(|| MxBSError::Io("axis missing 'index'".into()))? as usize,
                name: ax["name"].as_str()
                    .ok_or_else(|| MxBSError::Io("axis missing 'name'".into()))?.to_string(),
                low: ax["low"].as_str()
                    .ok_or_else(|| MxBSError::Io("axis missing 'low'".into()))?.to_string(),
                high: ax["high"].as_str()
                    .ok_or_else(|| MxBSError::Io("axis missing 'high'".into()))?.to_string(),
            });
        }

        Ok(Self { name, axes })
    }

    pub fn from_file(path: &str) -> Result<Self, MxBSError> {
        let content = std::fs::read_to_string(path)
            .map_err(|e| MxBSError::Io(e.to_string()))?;
        Self::from_json(&content)
    }

    pub fn scoring_prompt(&self, text: &str) -> (String, String) {
        let mut axes_desc = String::new();
        let mut axes_names = Vec::new();
        for ax in &self.axes {
            axes_desc.push_str(&format!(
                "  {:2}: {} (0={}, 255={})\n", ax.index, ax.name, ax.low, ax.high
            ));
            axes_names.push(ax.name.as_str());
        }

        let system = format!(
            "あなたはテキスト分析エンジンです。\n\
             与えられたテキストを16因子でスコアリングし、JSON配列で返してください。\n\
             各因子は 0〜255 の整数。必ず16個の数値を返すこと。\n\n\
             因子一覧:\n{}\n\
             回答形式: [n0, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12, n13, n14, n15]\n\
             JSON配列のみ出力。説明不要。",
            axes_desc
        );

        let axes_list = axes_names.join(", ");
        let user = format!(
            "テキスト:\n{}\n\n\
             上記テキストを以下の16因子でスコアリング（0〜255）:\n{}\n\n\
             必ず16個の整数をJSON配列で回答:",
            text, axes_list
        );

        (system, user)
    }
}

pub fn parse_scores(response: &str) -> Option<[u8; FACTOR_DIM]> {
    let cleaned = response.trim()
        .replace("```json", "").replace("```", "");
    let cleaned = cleaned.trim();

    if let Some(arr) = extract_array(cleaned)
        && let Some(result) = normalize_to_16(&arr) {
        return Some(result);
    }

    let numbers: Vec<i32> = cleaned.split(|c: char| !c.is_ascii_digit() && c != '-')
        .filter_map(|s| s.parse::<i32>().ok())
        .filter(|&n| (0..=255).contains(&n))
        .collect();
    if numbers.len() >= 12 {
        return normalize_to_16(&numbers);
    }

    None
}

fn extract_array(s: &str) -> Option<Vec<i32>> {
    let start = s.find('[')?;
    let end = s[start..].find(']')? + start;
    let inner = &s[start + 1..end];
    let nums: Vec<i32> = inner.split(',')
        .filter_map(|part| part.trim().parse::<i32>().ok())
        .collect();
    if nums.len() >= 12 { Some(nums) } else { None }
}

fn normalize_to_16(arr: &[i32]) -> Option<[u8; FACTOR_DIM]> {
    if arr.len() < 12 || arr.len() > 18 {
        return None;
    }
    let mut result = [128u8; FACTOR_DIM];
    for (i, &v) in arr.iter().take(FACTOR_DIM).enumerate() {
        result[i] = v.clamp(0, 255) as u8;
    }
    Some(result)
}

pub fn default_scores() -> [u8; FACTOR_DIM] {
    [128u8; FACTOR_DIM]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_scores_clean_json() {
        let r = parse_scores("[100, 200, 50, 150, 80, 120, 90, 170, 60, 130, 40, 110, 70, 160, 30, 140]");
        assert!(r.is_some());
        let f = r.unwrap();
        assert_eq!(f[0], 100);
        assert_eq!(f[15], 140);
    }

    #[test]
    fn test_parse_scores_with_codeblock() {
        let r = parse_scores("```json\n[100, 200, 50, 150, 80, 120, 90, 170, 60, 130, 40, 110, 70, 160, 30, 140]\n```");
        assert!(r.is_some());
    }

    #[test]
    fn test_parse_scores_short_pads() {
        let r = parse_scores("[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]");
        assert!(r.is_some());
        let f = r.unwrap();
        assert_eq!(f[11], 120);
        assert_eq!(f[12], 128);
        assert_eq!(f[15], 128);
    }

    #[test]
    fn test_parse_scores_clamp() {
        let r = parse_scores("[300, -10, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128]");
        assert!(r.is_some());
        let f = r.unwrap();
        assert_eq!(f[0], 255);
        assert_eq!(f[1], 0);
    }

    #[test]
    fn test_parse_scores_too_few() {
        let r = parse_scores("[1, 2, 3]");
        assert!(r.is_none());
    }
}
