use thiserror::Error;

#[derive(Debug, Error)]
pub enum MxmfError {
    #[error("JSON parse error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Invalid factor index {idx}: must be in 0..16")]
    InvalidFactorIndex { idx: usize },

    #[error("Invalid clamp range: min ({min}) > max ({max})")]
    InvalidClampRange { min: f32, max: f32 },

    #[error("Empty candidates for sample()")]
    EmptyCandidates,

    #[error("Invalid temperature: {0} (must be >= 0.0)")]
    InvalidTemperature(f32),

    #[error("Other: {0}")]
    Other(String),
}

pub type MxmfResult<T> = Result<T, MxmfError>;
