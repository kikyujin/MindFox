use crate::mood::Mood;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThresholdRule {
    pub mood_axis: String,
    pub coefficient: f32,
}

/// Adjust a base threshold using mood-driven rules.
pub fn adjust_threshold(base_threshold: f32, mood: &Mood, rules: &[ThresholdRule]) -> f32 {
    let delta: f32 = rules
        .iter()
        .map(|r| mood.get_or(&r.mood_axis, 0.0) * r.coefficient)
        .sum();
    base_threshold + delta
}
