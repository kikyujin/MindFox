use mxmindfox::*;

#[test]
fn single_rule() {
    let mut mood = Mood::new();
    mood.set("aggression", 0.8);
    let rules = vec![ThresholdRule { mood_axis: "aggression".into(), coefficient: -0.3 }];
    let adjusted = adjust_threshold(0.6, &mood, &rules);
    assert!((adjusted - (0.6 + 0.8 * -0.3)).abs() < 1e-6);
}

#[test]
fn multiple_rules() {
    let mut mood = Mood::new();
    mood.set("aggression", 0.8);
    mood.set("confidence", 0.5);
    let rules = vec![
        ThresholdRule { mood_axis: "aggression".into(), coefficient: -0.3 },
        ThresholdRule { mood_axis: "confidence".into(), coefficient: -0.1 },
    ];
    let adjusted = adjust_threshold(0.6, &mood, &rules);
    let expected = 0.6 + (0.8 * -0.3) + (0.5 * -0.1);
    assert!((adjusted - expected).abs() < 1e-6);
}

#[test]
fn missing_axis_treated_as_zero() {
    let mood = Mood::new();
    let rules = vec![ThresholdRule { mood_axis: "nonexistent".into(), coefficient: -0.3 }];
    let adjusted = adjust_threshold(0.6, &mood, &rules);
    assert!((adjusted - 0.6).abs() < 1e-6);
}

#[test]
fn zero_coefficient_no_effect() {
    let mut mood = Mood::new();
    mood.set("aggression", 0.8);
    let rules = vec![ThresholdRule { mood_axis: "aggression".into(), coefficient: 0.0 }];
    let adjusted = adjust_threshold(0.6, &mood, &rules);
    assert!((adjusted - 0.6).abs() < 1e-6);
}

#[test]
fn empty_rules_returns_base() {
    let mood = Mood::new();
    let adjusted = adjust_threshold(0.6, &mood, &[]);
    assert!((adjusted - 0.6).abs() < 1e-6);
}
