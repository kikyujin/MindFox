use crate::mood::{MoodPreset, compute_mood};

/// Compute trust toward a counterpart from filtered cells.
pub fn compute_diplomacy_toward(
    cells_about_counterpart: &[mxbs::Cell],
    preset: &MoodPreset,
    archetype: Option<&str>,
) -> f32 {
    let mood = compute_mood(cells_about_counterpart, preset, archetype);
    mood.get_or("trust", 0.0)
}
