use rand::Rng;

/// Bernoulli decision with temperature.
pub fn remember(
    score: f32,
    threshold: f32,
    temperature: f32,
    rng: &mut impl Rng,
) -> bool {
    if temperature <= 0.0 {
        return score >= threshold;
    }
    let logit = (score - threshold) / temperature;
    let p = 1.0 / (1.0 + (-logit).exp());
    rng.r#gen::<f32>() < p
}

/// Multinomial sample from candidates with temperature (softmax).
pub fn sample<'a, T>(
    candidates: &'a [(T, f32)],
    temperature: f32,
    rng: &mut impl Rng,
) -> Option<&'a T> {
    if candidates.is_empty() {
        return None;
    }

    if temperature <= 0.0 {
        return candidates.iter()
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(t, _)| t);
    }

    let scaled: Vec<f32> = candidates.iter().map(|(_, s)| s / temperature).collect();
    let max = scaled.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let exps: Vec<f32> = scaled.iter().map(|s| (s - max).exp()).collect();
    let sum: f32 = exps.iter().sum();

    let r: f32 = rng.r#gen();
    let mut acc = 0.0;
    for (i, &e) in exps.iter().enumerate() {
        acc += e / sum;
        if r < acc {
            return Some(&candidates[i].0);
        }
    }
    Some(&candidates.last().unwrap().0)
}
