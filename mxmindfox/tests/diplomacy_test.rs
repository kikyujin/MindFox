use mxbs::Cell;
use mxmindfox::*;

fn preset_with_trust() -> MoodPreset {
    MoodPreset::from_json(
        r#"{
        "name": "test", "version": "1.0",
        "axes": [
            {"name":"trust","positive_factors":[2],"negative_factors":[3],
             "default_value":0.0,"clamp_min":-1.0,"clamp_max":1.0}
        ],
        "archetype_baselines": {
            "friendly": {"trust": 0.3}
        }
    }"#,
    )
    .unwrap()
}

fn preset_no_trust() -> MoodPreset {
    MoodPreset::from_json(
        r#"{
        "name": "test", "version": "1.0",
        "axes": [
            {"name":"temperature","positive_factors":[0],"negative_factors":[],
             "default_value":0.05,"clamp_min":0.0,"clamp_max":1.0}
        ]
    }"#,
    )
    .unwrap()
}

fn make_cell(features: [u8; 16]) -> Cell {
    Cell::new(1, "test").turn(1).features(features)
}

#[test]
fn trust_empty_cells_returns_default() {
    assert!((compute_diplomacy_toward(&[], &preset_with_trust(), None) - 0.0).abs() < 1e-6);
}

#[test]
fn trust_no_trust_axis_returns_zero() {
    let cell = make_cell([255; 16]);
    assert!((compute_diplomacy_toward(&[cell], &preset_no_trust(), None) - 0.0).abs() < 1e-6);
}

#[test]
fn trust_positive_factors_increase() {
    let cell = make_cell([0, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    let trust = compute_diplomacy_toward(&[cell], &preset_with_trust(), None);
    assert!(trust > 0.0);
}

#[test]
fn trust_negative_factors_decrease() {
    let cell = make_cell([0, 0, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    let trust = compute_diplomacy_toward(&[cell], &preset_with_trust(), None);
    assert!(trust < 0.0);
}

#[test]
fn trust_archetype_baseline() {
    let trust = compute_diplomacy_toward(&[], &preset_with_trust(), Some("friendly"));
    assert!((trust - 0.3).abs() < 1e-6);
}
