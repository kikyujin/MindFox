//! MxMindFox — Multi-agent mood & decision layer on MxBS.

pub mod error;
pub mod mood;
pub mod diplomacy;
pub mod threshold;
pub mod decision;
pub mod ffi;

pub use error::{MxmfError, MxmfResult};
pub use mood::{Mood, MoodAxis, MoodPreset, compute_mood};
pub use diplomacy::compute_diplomacy_toward;
pub use threshold::{ThresholdRule, adjust_threshold};

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
