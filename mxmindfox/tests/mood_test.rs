use mxmindfox::*;
use mxbs::Cell;

fn make_preset() -> MoodPreset {
    MoodPreset::from_json(r#"{
        "name": "test",
        "version": "1.0",
        "axes": [
            {
                "name": "temperature",
                "positive_factors": [0],
                "negative_factors": [1],
                "default_value": 0.05,
                "clamp_min": 0.0,
                "clamp_max": 1.0
            },
            {
                "name": "trust",
                "positive_factors": [2],
                "negative_factors": [3],
                "default_value": 0.0,
                "clamp_min": -1.0,
                "clamp_max": 1.0
            }
        ],
        "archetype_baselines": {
            "analyst": {"temperature": 0.02},
            "impulsive": {"temperature": 0.20}
        }
    }"#).unwrap()
}

fn make_cell(features: [u8; 16]) -> Cell {
    Cell::new(1, "test").turn(1).features(features)
}

#[test]
fn mood_get_returns_value_when_set() {
    let mut m = Mood::new();
    m.set("trust", 0.5);
    assert_eq!(m.get("trust"), Some(0.5));
}

#[test]
fn mood_get_returns_none_when_unset() {
    let m = Mood::new();
    assert_eq!(m.get("trust"), None);
}

#[test]
fn mood_get_or_returns_default_when_unset() {
    let m = Mood::new();
    assert_eq!(m.get_or("trust", 0.0), 0.0);
}

#[test]
fn preset_from_json_roundtrip() {
    let p = make_preset();
    let json = p.to_json().unwrap();
    let p2 = MoodPreset::from_json(&json).unwrap();
    assert_eq!(p2.axes.len(), 2);
}

#[test]
fn preset_invalid_factor_index_fails() {
    let bad = r#"{
        "name": "t", "version": "1.0",
        "axes": [{"name":"x","positive_factors":[16],"negative_factors":[],
                  "default_value":0.0,"clamp_min":0.0,"clamp_max":1.0}]
    }"#;
    assert!(MoodPreset::from_json(bad).is_err());
}

#[test]
fn preset_invalid_clamp_range_fails() {
    let bad = r#"{
        "name": "t", "version": "1.0",
        "axes": [{"name":"x","positive_factors":[],"negative_factors":[],
                  "default_value":0.0,"clamp_min":1.0,"clamp_max":0.0}]
    }"#;
    assert!(MoodPreset::from_json(bad).is_err());
}

#[test]
fn compute_mood_empty_cells_returns_default() {
    let preset = make_preset();
    let mood = compute_mood(&[], &preset, None);
    assert_eq!(mood.get("temperature"), Some(0.05));
    assert_eq!(mood.get("trust"), Some(0.0));
}

#[test]
fn compute_mood_empty_cells_uses_archetype_baseline() {
    let preset = make_preset();
    let mood = compute_mood(&[], &preset, Some("impulsive"));
    assert_eq!(mood.get("temperature"), Some(0.20));
}

#[test]
fn compute_mood_unknown_archetype_falls_back_to_default() {
    let preset = make_preset();
    let mood = compute_mood(&[], &preset, Some("nonexistent"));
    assert_eq!(mood.get("temperature"), Some(0.05));
}

#[test]
fn compute_mood_positive_factor_increases_axis() {
    let preset = make_preset();
    let cell = make_cell([255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    let mood = compute_mood(&[cell], &preset, None);
    assert!(mood.get("temperature").unwrap() > 0.05);
}

#[test]
fn compute_mood_clamps_to_range() {
    let preset = make_preset();
    let cells: Vec<Cell> = (0..100).map(|_| make_cell([255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])).collect();
    let mood = compute_mood(&cells, &preset, None);
    assert!(mood.get("temperature").unwrap() <= 1.0);
}

#[test]
fn compute_mood_negative_factor_decreases_axis() {
    let preset = make_preset();
    let cell = make_cell([0, 0, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    let mood = compute_mood(&[cell], &preset, None);
    assert!(mood.get("trust").unwrap() < 0.0);
}

#[test]
fn compute_mood_multiple_cells_averaged() {
    let preset = make_preset();
    let mood_one = compute_mood(
        &[make_cell([255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])],
        &preset, None,
    );
    let mood_two = compute_mood(
        &[
            make_cell([255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
            make_cell([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        ],
        &preset, None,
    );
    assert!(mood_two.get("temperature").unwrap() < mood_one.get("temperature").unwrap());
}

#[test]
fn preset_axis_names() {
    let p = make_preset();
    let names = p.axis_names();
    assert!(names.contains(&"temperature"));
    assert!(names.contains(&"trust"));
}
