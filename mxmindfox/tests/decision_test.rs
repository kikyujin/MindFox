use mxmindfox::decision::{remember, sample};
use rand::SeedableRng;
use rand::rngs::StdRng;

#[test]
fn remember_t0_deterministic_above_threshold() {
    let mut rng = StdRng::seed_from_u64(0);
    assert!(remember(0.5, 0.3, 0.0, &mut rng));
}

#[test]
fn remember_t0_deterministic_below_threshold() {
    let mut rng = StdRng::seed_from_u64(0);
    assert!(!remember(0.2, 0.3, 0.0, &mut rng));
}

#[test]
fn remember_t0_at_threshold() {
    let mut rng = StdRng::seed_from_u64(0);
    assert!(remember(0.3, 0.3, 0.0, &mut rng));
}

#[test]
fn remember_t_positive_yields_distribution() {
    let mut rng = StdRng::seed_from_u64(42);
    let mut hits = 0;
    for _ in 0..1000 {
        if remember(0.05, 0.30, 0.10, &mut rng) {
            hits += 1;
        }
    }
    assert!((30..=130).contains(&hits), "hits = {}", hits);
}

#[test]
fn remember_high_temperature_approaches_50_50() {
    let mut rng = StdRng::seed_from_u64(42);
    let mut hits = 0;
    for _ in 0..1000 {
        if remember(0.30, 0.30, 100.0, &mut rng) {
            hits += 1;
        }
    }
    assert!((400..=600).contains(&hits), "hits = {}", hits);
}

#[test]
fn sample_empty_returns_none() {
    let mut rng = StdRng::seed_from_u64(0);
    let cands: Vec<(&str, f32)> = vec![];
    assert!(sample(&cands, 0.5, &mut rng).is_none());
}

#[test]
fn sample_t0_argmax() {
    let mut rng = StdRng::seed_from_u64(0);
    let cands = vec![("a", 0.1), ("b", 0.9), ("c", 0.5)];
    assert_eq!(*sample(&cands, 0.0, &mut rng).unwrap(), "b");
}

#[test]
fn sample_t_low_concentrates_on_argmax() {
    let cands = vec![("a", 0.1), ("b", 0.9), ("c", 0.5)];
    let mut rng = StdRng::seed_from_u64(42);
    let mut b_count = 0;
    for _ in 0..1000 {
        if *sample(&cands, 0.05, &mut rng).unwrap() == "b" {
            b_count += 1;
        }
    }
    assert!(b_count > 950, "b_count = {}", b_count);
}

#[test]
fn sample_t_high_approaches_uniform() {
    let cands = vec![("a", 0.1), ("b", 0.9), ("c", 0.5)];
    let mut rng = StdRng::seed_from_u64(42);
    let mut counts = [0; 3];
    for _ in 0..3000 {
        let label = *sample(&cands, 100.0, &mut rng).unwrap();
        counts[match label {
            "a" => 0,
            "b" => 1,
            "c" => 2,
            _ => unreachable!(),
        }] += 1;
    }
    for c in counts {
        assert!((700..=1300).contains(&c), "counts = {:?}", counts);
    }
}

#[test]
fn remember_seed_reproducible() {
    let mut rng1 = StdRng::seed_from_u64(123);
    let mut rng2 = StdRng::seed_from_u64(123);
    let r1: Vec<bool> = (0..100)
        .map(|_| remember(0.3, 0.3, 0.1, &mut rng1))
        .collect();
    let r2: Vec<bool> = (0..100)
        .map(|_| remember(0.3, 0.3, 0.1, &mut rng2))
        .collect();
    assert_eq!(r1, r2);
}

#[test]
fn sample_seed_reproducible() {
    let cands = vec![("a", 0.1), ("b", 0.9), ("c", 0.5)];
    let mut rng1 = StdRng::seed_from_u64(456);
    let mut rng2 = StdRng::seed_from_u64(456);
    let r1: Vec<&str> = (0..50)
        .map(|_| *sample(&cands, 0.3, &mut rng1).unwrap())
        .collect();
    let r2: Vec<&str> = (0..50)
        .map(|_| *sample(&cands, 0.3, &mut rng2).unwrap())
        .collect();
    assert_eq!(r1, r2);
}
