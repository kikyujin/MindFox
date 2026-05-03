use std::ffi::{CStr, CString};

#[test]
fn test_ffi_open_close() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());
        assert!(!handle.is_null());
        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_open_with_config() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let config = CString::new(r#"{"half_life":16}"#).unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), config.as_ptr());
        assert!(!handle.is_null());
        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_store_and_search() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());
        assert!(!handle.is_null());

        let text = CString::new("test memory").unwrap();
        let meta = CString::new("{}").unwrap();
        let features: [u8; 16] = [
            200, 100, 50, 150, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110,
        ];

        let cell_id = mxbs::ffi::mxbs_store(
            handle,
            1,
            1,
            1,
            0x01,
            0o744,
            100,
            features.as_ptr(),
            text.as_ptr(),
            meta.as_ptr(),
        );
        assert!(cell_id > 0);

        let query: [u8; 16] = [
            200, 100, 50, 150, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110,
        ];
        let result_ptr = mxbs::ffi::mxbs_search(handle, query.as_ptr(), 1, 0x01, 1, 5);
        assert!(!result_ptr.is_null());

        let result_str = CStr::from_ptr(result_ptr).to_str().unwrap();
        assert!(result_str.contains("test memory"));
        mxbs::ffi::mxbs_free_string(result_ptr);

        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_get_and_delete() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());

        let text = CString::new("to be deleted").unwrap();
        let meta = CString::new("{}").unwrap();
        let features: [u8; 16] = [100; 16];

        let cell_id = mxbs::ffi::mxbs_store(
            handle,
            1,
            1,
            1,
            0x01,
            0o744,
            100,
            features.as_ptr(),
            text.as_ptr(),
            meta.as_ptr(),
        );

        let get_ptr = mxbs::ffi::mxbs_get(handle, cell_id);
        assert!(!get_ptr.is_null());
        let get_str = CStr::from_ptr(get_ptr).to_str().unwrap();
        assert!(get_str.contains("to be deleted"));
        mxbs::ffi::mxbs_free_string(get_ptr);

        let ok = mxbs::ffi::mxbs_delete(handle, cell_id, 1, 0x01);
        assert_eq!(ok, 1);

        let gone = mxbs::ffi::mxbs_get(handle, cell_id);
        assert!(gone.is_null());

        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_stats() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());

        let stats_ptr = mxbs::ffi::mxbs_stats(handle);
        assert!(!stats_ptr.is_null());
        let stats_str = CStr::from_ptr(stats_ptr).to_str().unwrap();
        assert!(stats_str.contains("\"total\":0"));
        mxbs::ffi::mxbs_free_string(stats_ptr);

        let text = CString::new("cell").unwrap();
        let meta = CString::new("{}").unwrap();
        mxbs::ffi::mxbs_store(
            handle,
            1,
            1,
            1,
            0,
            0o744,
            100,
            std::ptr::null(),
            text.as_ptr(),
            meta.as_ptr(),
        );

        let stats_ptr2 = mxbs::ffi::mxbs_stats(handle);
        let stats_str2 = CStr::from_ptr(stats_ptr2).to_str().unwrap();
        assert!(stats_str2.contains("\"total\":1"));
        assert!(stats_str2.contains("\"unscored\":1"));
        mxbs::ffi::mxbs_free_string(stats_ptr2);

        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_deferred_scoring() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());

        let text = CString::new("unscored cell").unwrap();
        let meta = CString::new("{}").unwrap();
        let cell_id = mxbs::ffi::mxbs_store(
            handle,
            1,
            1,
            1,
            0x01,
            0o744,
            100,
            std::ptr::null(),
            text.as_ptr(),
            meta.as_ptr(),
        );
        assert!(cell_id > 0);

        let unscored_ptr = mxbs::ffi::mxbs_get_unscored(handle);
        assert!(!unscored_ptr.is_null());
        let unscored_str = CStr::from_ptr(unscored_ptr).to_str().unwrap();
        assert!(unscored_str.contains("unscored cell"));
        mxbs::ffi::mxbs_free_string(unscored_ptr);

        let features: [u8; 16] = [100; 16];
        let ok = mxbs::ffi::mxbs_set_features(handle, cell_id, features.as_ptr());
        assert_eq!(ok, 1);

        let unscored_ptr2 = mxbs::ffi::mxbs_get_unscored(handle);
        let unscored_str2 = CStr::from_ptr(unscored_ptr2).to_str().unwrap();
        assert_eq!(unscored_str2, "[]");
        mxbs::ffi::mxbs_free_string(unscored_ptr2);

        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_reinforce() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());

        let text = CString::new("important").unwrap();
        let meta = CString::new("{}").unwrap();
        let features: [u8; 16] = [100; 16];
        let cell_id = mxbs::ffi::mxbs_store(
            handle,
            1,
            1,
            1,
            0,
            0o744,
            100,
            features.as_ptr(),
            text.as_ptr(),
            meta.as_ptr(),
        );

        let ok = mxbs::ffi::mxbs_reinforce(handle, cell_id, 5.0);
        assert_eq!(ok, 1);

        let bad = mxbs::ffi::mxbs_reinforce(handle, cell_id, 11.0);
        assert_eq!(bad, 0);

        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_dream() {
    unsafe {
        let path = CString::new(":memory:").unwrap();
        let handle = mxbs::ffi::mxbs_open(path.as_ptr(), std::ptr::null());

        let text = CString::new("old memory").unwrap();
        let meta = CString::new("{}").unwrap();
        let features: [u8; 16] = [100; 16];
        mxbs::ffi::mxbs_store(
            handle,
            1,
            1,
            1,
            0x01,
            0o744,
            200,
            features.as_ptr(),
            text.as_ptr(),
            meta.as_ptr(),
        );

        let dream_ptr = mxbs::ffi::mxbs_dream(handle, 1, 0x01, 20, 5);
        assert!(!dream_ptr.is_null());
        let dream_str = CStr::from_ptr(dream_ptr).to_str().unwrap();
        assert!(dream_str.contains("old memory"));
        mxbs::ffi::mxbs_free_string(dream_ptr);

        mxbs::ffi::mxbs_close(handle);
    }
}

#[test]
fn test_ffi_null_handle_safety() {
    unsafe {
        assert_eq!(
            mxbs::ffi::mxbs_store(
                std::ptr::null_mut(),
                1,
                1,
                1,
                0,
                0o744,
                100,
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
            ),
            0
        );
        assert!(
            mxbs::ffi::mxbs_search(std::ptr::null_mut(), std::ptr::null(), 1, 0, 1, 5,).is_null()
        );
        assert!(mxbs::ffi::mxbs_stats(std::ptr::null_mut()).is_null());
        mxbs::ffi::mxbs_close(std::ptr::null_mut());
        mxbs::ffi::mxbs_free_string(std::ptr::null());
    }
}
