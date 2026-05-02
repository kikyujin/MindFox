use std::collections::HashMap;
use serde::{Serialize, Deserialize};

use crate::error::{MxmfError, MxmfResult};

const FACTOR_DIM: usize = 16;

/// Mood: a flexible bag of named axes.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Mood {
    pub axes: HashMap<String, f32>,
}

impl Mood {
    pub fn new() -> Self { Self::default() }

    pub fn get(&self, axis: &str) -> Option<f32> {
        self.axes.get(axis).copied()
    }

    pub fn get_or(&self, axis: &str, default: f32) -> f32 {
        self.axes.get(axis).copied().unwrap_or(default)
    }

    pub fn set(&mut self, axis: &str, value: f32) {
        self.axes.insert(axis.to_string(), value);
    }

    pub fn from_baseline(baseline: &HashMap<String, f32>) -> Self {
        Self { axes: baseline.clone() }
    }
}

/// Definition of a single mood axis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MoodAxis {
    pub name: String,
    pub positive_factors: Vec<usize>,
    pub negative_factors: Vec<usize>,
    pub default_value: f32,
    pub clamp_min: f32,
    pub clamp_max: f32,
}

impl MoodAxis {
    pub fn validate(&self) -> MxmfResult<()> {
        for &i in &self.positive_factors {
            if i >= FACTOR_DIM {
                return Err(MxmfError::InvalidFactorIndex { idx: i });
            }
        }
        for &i in &self.negative_factors {
            if i >= FACTOR_DIM {
                return Err(MxmfError::InvalidFactorIndex { idx: i });
            }
        }
        if self.clamp_min > self.clamp_max {
            return Err(MxmfError::InvalidClampRange {
                min: self.clamp_min,
                max: self.clamp_max,
            });
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MoodPreset {
    pub name: String,
    pub version: String,
    pub axes: Vec<MoodAxis>,
    #[serde(default)]
    pub archetype_baselines: HashMap<String, HashMap<String, f32>>,
}

impl MoodPreset {
    pub fn from_json(json: &str) -> MxmfResult<Self> {
        let preset: Self = serde_json::from_str(json)?;
        for axis in &preset.axes {
            axis.validate()?;
        }
        Ok(preset)
    }

    pub fn to_json(&self) -> MxmfResult<String> {
        Ok(serde_json::to_string_pretty(self)?)
    }

    pub fn axis_names(&self) -> Vec<&str> {
        self.axes.iter().map(|a| a.name.as_str()).collect()
    }

    pub fn baseline_for(&self, archetype: &str) -> Option<&HashMap<String, f32>> {
        self.archetype_baselines.get(archetype)
    }
}

/// Compute mood from recent memory cells.
pub fn compute_mood(
    cells: &[mxbs::Cell],
    preset: &MoodPreset,
    archetype: Option<&str>,
) -> Mood {
    let mut mood = Mood::new();
    let baseline = archetype.and_then(|a| preset.baseline_for(a));

    for axis in &preset.axes {
        let base = baseline
            .and_then(|b| b.get(&axis.name).copied())
            .unwrap_or(axis.default_value);

        let value = if cells.is_empty() {
            base
        } else {
            let mut sum_pos: u64 = 0;
            let mut sum_neg: u64 = 0;
            for cell in cells {
                for &i in &axis.positive_factors {
                    sum_pos += cell.features[i] as u64;
                }
                for &i in &axis.negative_factors {
                    sum_neg += cell.features[i] as u64;
                }
            }
            let n = cells.len() as f32;
            let delta = (sum_pos as f32 - sum_neg as f32) / n / 255.0;
            (base + delta).clamp(axis.clamp_min, axis.clamp_max)
        };

        mood.set(&axis.name, value);
    }

    mood
}
