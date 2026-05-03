//! MxMindFox — Multi-agent mood & decision layer on MxBS.

pub mod decision;
pub mod diplomacy;
pub mod error;
pub mod ffi;
pub mod mood;
pub mod threshold;

pub use diplomacy::compute_diplomacy_toward;
pub use error::{MxmfError, MxmfResult};
pub use mood::{Mood, MoodAxis, MoodPreset, compute_mood};
pub use threshold::{ThresholdRule, adjust_threshold};

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
