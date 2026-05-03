use std::ffi::{CStr, CString};
use std::ptr;

use mxmindfox::ffi::*;

fn load_test_preset() -> *mut std::ffi::c_void {
    let json = CString::new(
        r#"{
        "name": "test", "version": "1.0",
        "axes": [
            {"name":"temperature","positive_factors":[0],"negative_factors":[1],
             "default_value":0.05,"clamp_min":0.0,"clamp_max":1.0}
        ],
        "archetype_baselines": {"impulsive": {"temperature": 0.20}}
    }"#,
    )
    .unwrap();
    unsafe { mxmf_preset_load_json(json.as_ptr()) }
}

#[test]
fn null_preset_free_no_crash() {
    unsafe {
        mxmf_preset_free(ptr::null_mut());
    }
}

#[test]
fn null_json_returns_null() {
    let p = unsafe { mxmf_preset_load_json(ptr::null()) };
    assert!(p.is_null());
}

#[test]
fn invalid_json_returns_null() {
    let bad = CString::new("not json").unwrap();
    let p = unsafe { mxmf_preset_load_json(bad.as_ptr()) };
    assert!(p.is_null());
}

#[test]
fn preset_load_to_json_roundtrip() {
    let p = load_test_preset();
    assert!(!p.is_null());
    let json_ptr = unsafe { mxmf_preset_to_json(p) };
    assert!(!json_ptr.is_null());
    let json = unsafe { CStr::from_ptr(json_ptr) }.to_str().unwrap();
    assert!(json.contains("temperature"));
    unsafe {
        mxmf_str_free(json_ptr);
    }
    unsafe {
        mxmf_preset_free(p);
    }
}

#[test]
fn compute_mood_empty_cells_archetype_baseline() {
    let p = load_test_preset();
    let cells = CString::new("[]").unwrap();
    let arch = CString::new("impulsive").unwrap();
    let result_ptr = unsafe { mxmf_compute_mood(p, cells.as_ptr(), arch.as_ptr()) };
    assert!(!result_ptr.is_null());
    let result = unsafe { CStr::from_ptr(result_ptr) }.to_str().unwrap();
    assert!(result.contains("temperature"));
    assert!(result.contains("0.2"));
    unsafe {
        mxmf_str_free(result_ptr);
    }
    unsafe {
        mxmf_preset_free(p);
    }
}

#[test]
fn decision_remember_t0_deterministic() {
    assert_eq!(mxmf_decision_remember(0.5, 0.3, 0.0, 42), 1);
    assert_eq!(mxmf_decision_remember(0.2, 0.3, 0.0, 42), 0);
}

#[test]
fn decision_remember_same_seed_same_result() {
    let r1 = mxmf_decision_remember(0.3, 0.3, 0.1, 99);
    let r2 = mxmf_decision_remember(0.3, 0.3, 0.1, 99);
    assert_eq!(r1, r2);
}

#[test]
fn decision_sample_invalid_json_returns_neg1() {
    let bad = CString::new("not json").unwrap();
    let result = unsafe { mxmf_decision_sample(bad.as_ptr(), 0.5, 42) };
    assert_eq!(result, -1);
}

#[test]
fn decision_sample_empty_returns_neg1() {
    let empty = CString::new("[]").unwrap();
    let result = unsafe { mxmf_decision_sample(empty.as_ptr(), 0.5, 42) };
    assert_eq!(result, -1);
}

#[test]
fn decision_sample_t0_argmax() {
    let json = CString::new(
        r#"[{"index":0,"score":0.1},{"index":1,"score":0.9},{"index":2,"score":0.5}]"#,
    )
    .unwrap();
    let result = unsafe { mxmf_decision_sample(json.as_ptr(), 0.0, 42) };
    assert_eq!(result, 1);
}

#[test]
fn version_not_null() {
    let v = mxmf_version();
    assert!(!v.is_null());
    let s = unsafe { CStr::from_ptr(v) }.to_str().unwrap();
    assert!(s.starts_with("0.1"));
}

#[test]
fn null_str_free_no_crash() {
    unsafe {
        mxmf_str_free(ptr::null_mut());
    }
}
