use std::ffi::{c_char, c_int, CStr, CString};
use std::panic;
use std::ptr;

use crate::{Cell, MxBS, MxBSConfig};

pub type MxBSHandle = MxBS;

fn to_json_cstring<T: serde::Serialize>(val: &T) -> *const c_char {
    match serde_json::to_string(val) {
        Ok(json) => match CString::new(json) {
            Ok(cs) => cs.into_raw() as *const c_char,
            Err(_) => ptr::null(),
        },
        Err(_) => ptr::null(),
    }
}

unsafe fn cstr_to_str<'a>(p: *const c_char) -> Option<&'a str> {
    if p.is_null() {
        return None;
    }
    unsafe { CStr::from_ptr(p) }.to_str().ok()
}

unsafe fn features_from_ptr(p: *const u8) -> [u8; 16] {
    if p.is_null() {
        [0u8; 16]
    } else {
        let slice = unsafe { std::slice::from_raw_parts(p, 16) };
        let mut arr = [0u8; 16];
        arr.copy_from_slice(slice);
        arr
    }
}

// ---------- Lifecycle ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_open(
    db_path: *const c_char,
    config_json: *const c_char,
) -> *mut MxBSHandle {
    let result = panic::catch_unwind(|| {
        let path = unsafe { cstr_to_str(db_path) }?;
        let config: MxBSConfig = if config_json.is_null() {
            MxBSConfig::default()
        } else {
            let json_str = unsafe { cstr_to_str(config_json) }?;
            serde_json::from_str(json_str).ok()?
        };
        MxBS::open(path, config).ok()
    });
    match result {
        Ok(Some(mxbs)) => Box::into_raw(Box::new(mxbs)),
        _ => ptr::null_mut(),
    }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_close(handle: *mut MxBSHandle) {
    if !handle.is_null() {
        unsafe { drop(Box::from_raw(handle)) };
    }
}

// ---------- Store ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_store(
    h: *mut MxBSHandle,
    owner: u32,
    from: u32,
    turn: u32,
    group_bits: u64,
    mode: u16,
    price: u8,
    features: *const u8,
    text: *const c_char,
    meta: *const c_char,
) -> u64 {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let text_str = unsafe { cstr_to_str(text) }.unwrap_or("");
        let meta_str = unsafe { cstr_to_str(meta) }.unwrap_or("{}");
        let feat = unsafe { features_from_ptr(features) };

        let mut cell = Cell::new(owner, text_str)
            .from(from)
            .turn(turn)
            .group_bits(group_bits)
            .mode(mode)
            .price(price);

        if feat.iter().any(|&b| b != 0) {
            cell = cell.features(feat);
        }

        if meta_str != "{}" {
            cell = cell.meta(meta_str);
        }

        mxbs.store(cell).unwrap_or(0)
    }));
    result.unwrap_or(0)
}

// ---------- Deferred Scoring ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_get_unscored(h: *mut MxBSHandle) -> *const c_char {
    if h.is_null() {
        return ptr::null();
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let unscored = mxbs.get_unscored().unwrap_or_default();
        to_json_cstring(&unscored)
    }));
    result.unwrap_or(ptr::null())
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_set_features(
    h: *mut MxBSHandle,
    cell_id: u64,
    features: *const u8,
) -> c_int {
    if h.is_null() || features.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let feat = unsafe { features_from_ptr(features) };
        match mxbs.set_features(cell_id, feat) {
            Ok(()) => 1,
            Err(_) => 0,
        }
    }));
    result.unwrap_or(0)
}

// ---------- Search ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_search(
    h: *mut MxBSHandle,
    query_features: *const u8,
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
    limit: c_int,
) -> *const c_char {
    if h.is_null() {
        return ptr::null();
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let query = unsafe { features_from_ptr(query_features) };
        let results = mxbs
            .search(query, viewer_id, viewer_groups)
            .current_turn(current_turn)
            .limit(limit as usize)
            .exec()
            .unwrap_or_default();
        to_json_cstring(&results)
    }));
    result.unwrap_or(ptr::null())
}

// ---------- Dream ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_dream(
    h: *mut MxBSHandle,
    viewer_id: u32,
    viewer_groups: u64,
    current_turn: u32,
    limit: c_int,
) -> *const c_char {
    if h.is_null() {
        return ptr::null();
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let results = mxbs
            .dream(viewer_id, viewer_groups)
            .current_turn(current_turn)
            .limit(limit as usize)
            .exec()
            .unwrap_or_default();
        to_json_cstring(&results)
    }));
    result.unwrap_or(ptr::null())
}

// ---------- Inspire ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_inspire(
    h: *mut MxBSHandle,
    cell_id: u64,
    limit: c_int,
    viewer_id: u32,
    viewer_groups: u64,
) -> *const c_char {
    if h.is_null() {
        return ptr::null();
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let results = mxbs
            .inspire(cell_id)
            .limit(limit as usize)
            .viewer(viewer_id, viewer_groups)
            .exec()
            .unwrap_or_default();
        to_json_cstring(&results)
    }));
    result.unwrap_or(ptr::null())
}

// ---------- Reinforce ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_reinforce(
    h: *mut MxBSHandle,
    cell_id: u64,
    importance: f32,
) -> c_int {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        match mxbs.reinforce(cell_id, importance) {
            Ok(()) => 1,
            Err(_) => 0,
        }
    }));
    result.unwrap_or(0)
}

// ---------- Field Updates ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_update_group_bits(
    h: *mut MxBSHandle,
    cell_id: u64,
    new_group_bits: u64,
    requester: u32,
    req_groups: u64,
) -> c_int {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        match mxbs.update_group_bits(cell_id, new_group_bits, requester, req_groups) {
            Ok(true) => 1,
            _ => 0,
        }
    }));
    result.unwrap_or(0)
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_update_mode(
    h: *mut MxBSHandle,
    cell_id: u64,
    new_mode: u16,
    requester: u32,
    req_groups: u64,
) -> c_int {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        match mxbs.update_mode(cell_id, new_mode, requester, req_groups) {
            Ok(true) => 1,
            _ => 0,
        }
    }));
    result.unwrap_or(0)
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_update_meta(
    h: *mut MxBSHandle,
    cell_id: u64,
    new_meta: *const c_char,
    requester: u32,
    req_groups: u64,
) -> c_int {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let meta_str = unsafe { cstr_to_str(new_meta) }.unwrap_or("{}");
        match mxbs.update_meta(cell_id, meta_str, requester, req_groups) {
            Ok(true) => 1,
            _ => 0,
        }
    }));
    result.unwrap_or(0)
}

// ---------- Get / Delete ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_get(h: *mut MxBSHandle, cell_id: u64) -> *const c_char {
    if h.is_null() {
        return ptr::null();
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        match mxbs.get(cell_id) {
            Ok(cell) => to_json_cstring(&cell),
            Err(_) => ptr::null(),
        }
    }));
    result.unwrap_or(ptr::null())
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_delete(
    h: *mut MxBSHandle,
    cell_id: u64,
    requester: u32,
    req_groups: u64,
) -> c_int {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        match mxbs.delete(cell_id, requester, req_groups) {
            Ok(true) => 1,
            _ => 0,
        }
    }));
    result.unwrap_or(0)
}

// ---------- Save ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_save(h: *mut MxBSHandle, dest_path: *const c_char) -> c_int {
    if h.is_null() {
        return 0;
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        let path = match unsafe { cstr_to_str(dest_path) } {
            Some(p) => p,
            None => return 0,
        };
        match mxbs.save_to(path) {
            Ok(()) => 1,
            Err(_) => 0,
        }
    }));
    result.unwrap_or(0)
}

// ---------- Stats ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_stats(h: *mut MxBSHandle) -> *const c_char {
    if h.is_null() {
        return ptr::null();
    }
    let result = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let mxbs = unsafe { &*h };
        match mxbs.stats() {
            Ok(stats) => to_json_cstring(&stats),
            Err(_) => ptr::null(),
        }
    }));
    result.unwrap_or(ptr::null())
}

// ---------- Free ----------

#[unsafe(no_mangle)]
pub unsafe extern "C" fn mxbs_free_string(s: *const c_char) {
    if !s.is_null() {
        unsafe { drop(CString::from_raw(s as *mut c_char)) };
    }
}
