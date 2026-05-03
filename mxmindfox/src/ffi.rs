use std::ffi::{CStr, CString, c_char, c_int};
use std::ptr;

use rand::SeedableRng;
use rand::rngs::SmallRng;

use crate::decision::{remember, sample};
use crate::diplomacy::compute_diplomacy_toward;
use crate::mood::*;
use crate::threshold::{ThresholdRule, adjust_threshold};

unsafe fn cstr_to_str<'a>(p: *const c_char) -> Option<&'a str> {
    if p.is_null() {
        return None;
    }
    unsafe { CStr::from_ptr(p) }.to_str().ok()
}

fn str_to_cstr(s: String) -> *mut c_char {
    CString::new(s)
        .map(|c| c.into_raw())
        .unwrap_or(ptr::null_mut())
}

/// # Safety
/// `s` must be a pointer returned by a `mxmf_*` function or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_str_free(s: *mut c_char) {
    if s.is_null() {
        return;
    }
    unsafe {
        drop(CString::from_raw(s));
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn mxmf_version() -> *const c_char {
    static VERSION: &str = concat!(env!("CARGO_PKG_VERSION"), "\0");
    VERSION.as_ptr() as *const c_char
}

/// # Safety
/// `json` must be a valid C string or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_preset_load_json(json: *const c_char) -> *mut std::ffi::c_void {
    let s = match unsafe { cstr_to_str(json) } {
        Some(s) => s,
        None => return ptr::null_mut(),
    };
    match MoodPreset::from_json(s) {
        Ok(p) => Box::into_raw(Box::new(p)) as *mut std::ffi::c_void,
        Err(_) => ptr::null_mut(),
    }
}

/// # Safety
/// `p` must be a handle returned by `mxmf_preset_load_json` or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_preset_free(p: *mut std::ffi::c_void) {
    if p.is_null() {
        return;
    }
    unsafe {
        drop(Box::from_raw(p as *mut MoodPreset));
    }
}

/// # Safety
/// `p` must be a valid preset handle or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_preset_to_json(p: *const std::ffi::c_void) -> *mut c_char {
    if p.is_null() {
        return ptr::null_mut();
    }
    let preset = unsafe { &*(p as *const MoodPreset) };
    match preset.to_json() {
        Ok(s) => str_to_cstr(s),
        Err(_) => ptr::null_mut(),
    }
}

/// # Safety
/// All pointer arguments must be valid C strings or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_compute_mood(
    preset: *const std::ffi::c_void,
    cells_json: *const c_char,
    archetype: *const c_char,
) -> *mut c_char {
    if preset.is_null() {
        return ptr::null_mut();
    }
    let preset = unsafe { &*(preset as *const MoodPreset) };
    let cells_str = match unsafe { cstr_to_str(cells_json) } {
        Some(s) => s,
        None => return ptr::null_mut(),
    };
    let cells: Vec<mxbs::Cell> = match serde_json::from_str(cells_str) {
        Ok(v) => v,
        Err(_) => return ptr::null_mut(),
    };
    let archetype = unsafe { cstr_to_str(archetype) };
    let mood = compute_mood(&cells, preset, archetype);
    match serde_json::to_string(&mood) {
        Ok(s) => str_to_cstr(s),
        Err(_) => ptr::null_mut(),
    }
}

/// # Safety
/// All pointer arguments must be valid C strings or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_compute_diplomacy_toward(
    preset: *const std::ffi::c_void,
    cells_json: *const c_char,
    archetype: *const c_char,
) -> f32 {
    if preset.is_null() {
        return 0.0;
    }
    let preset = unsafe { &*(preset as *const MoodPreset) };
    let cells_str = match unsafe { cstr_to_str(cells_json) } {
        Some(s) => s,
        None => return 0.0,
    };
    let cells: Vec<mxbs::Cell> = match serde_json::from_str(cells_str) {
        Ok(v) => v,
        Err(_) => return 0.0,
    };
    let archetype = unsafe { cstr_to_str(archetype) };
    compute_diplomacy_toward(&cells, preset, archetype)
}

/// # Safety
/// All pointer arguments must be valid C strings or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_adjust_threshold(
    base: f32,
    mood_json: *const c_char,
    rules_json: *const c_char,
) -> f32 {
    let mood_str = match unsafe { cstr_to_str(mood_json) } {
        Some(s) => s,
        None => return base,
    };
    let mood: Mood = match serde_json::from_str(mood_str) {
        Ok(v) => v,
        Err(_) => return base,
    };
    let rules_str = match unsafe { cstr_to_str(rules_json) } {
        Some(s) => s,
        None => return base,
    };
    let rules: Vec<ThresholdRule> = match serde_json::from_str(rules_str) {
        Ok(v) => v,
        Err(_) => return base,
    };
    adjust_threshold(base, &mood, &rules)
}

#[unsafe(no_mangle)]
pub extern "C" fn mxmf_decision_remember(
    score: f32,
    threshold: f32,
    temperature: f32,
    seed: u64,
) -> c_int {
    let mut rng = SmallRng::seed_from_u64(seed);
    if remember(score, threshold, temperature, &mut rng) {
        1
    } else {
        0
    }
}

/// # Safety
/// `candidates_json` must be a valid C string or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxmf_decision_sample(
    candidates_json: *const c_char,
    temperature: f32,
    seed: u64,
) -> c_int {
    #[derive(serde::Deserialize)]
    struct Item {
        index: i32,
        score: f32,
    }

    let s = match unsafe { cstr_to_str(candidates_json) } {
        Some(s) => s,
        None => return -1,
    };
    let items: Vec<Item> = match serde_json::from_str(s) {
        Ok(v) => v,
        Err(_) => return -1,
    };
    if items.is_empty() {
        return -1;
    }
    let cands: Vec<(i32, f32)> = items.into_iter().map(|i| (i.index, i.score)).collect();

    let mut rng = SmallRng::seed_from_u64(seed);
    match sample(&cands, temperature, &mut rng) {
        Some(idx) => *idx,
        None => -1,
    }
}
