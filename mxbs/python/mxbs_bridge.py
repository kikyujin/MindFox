"""MxBS Python Bridge — ctypes wrapper for libmxbs.dylib/.so"""
import ctypes
import json
import platform
from pathlib import Path
from typing import Optional


class MxBSBridge:
    """Python wrapper for the MxBS C API."""

    FACTOR_DIM = 16

    def __init__(self, db_path: str, half_life: int = 8, lib_path: Optional[str] = None):
        if lib_path is None:
            lib_path = self._find_library()

        self._lib = ctypes.cdll.LoadLibrary(lib_path)
        self._setup_signatures()

        config = json.dumps({"half_life": half_life})
        self._handle = self._lib.mxbs_open(
            db_path.encode("utf-8"),
            config.encode("utf-8"),
        )
        if not self._handle:
            raise RuntimeError(f"Failed to open MxBS database: {db_path}")

    def _find_library(self) -> str:
        system = platform.system()
        if system == "Darwin":
            name = "libmxbs.dylib"
        elif system == "Linux":
            name = "libmxbs.so"
        elif system == "Windows":
            name = "mxbs.dll"
        else:
            name = "libmxbs.so"

        candidates = [
            Path(__file__).parent.parent / "target" / "release" / name,
            Path(__file__).parent.parent / "target" / "debug" / name,
            # workspace root
            Path(__file__).parent.parent.parent / "target" / "release" / name,
            Path(__file__).parent.parent.parent / "target" / "debug" / name,
            Path(name),
        ]
        for p in candidates:
            if p.exists():
                return str(p)

        raise FileNotFoundError(
            f"Cannot find {name}. Build with: cargo build --release"
        )

    def _setup_signatures(self):
        L = self._lib

        # Lifecycle
        L.mxbs_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        L.mxbs_open.restype = ctypes.c_void_p

        L.mxbs_close.argtypes = [ctypes.c_void_p]
        L.mxbs_close.restype = None

        # Store
        L.mxbs_store.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint64, ctypes.c_uint16, ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_char_p, ctypes.c_char_p,
        ]
        L.mxbs_store.restype = ctypes.c_uint64

        # Deferred scoring
        L.mxbs_get_unscored.argtypes = [ctypes.c_void_p]
        L.mxbs_get_unscored.restype = ctypes.c_void_p

        L.mxbs_set_features.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_uint8),
        ]
        L.mxbs_set_features.restype = ctypes.c_int

        # Search
        L.mxbs_search.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_uint32, ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_int,
        ]
        L.mxbs_search.restype = ctypes.c_void_p

        # Dream
        L.mxbs_dream.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_int,
        ]
        L.mxbs_dream.restype = ctypes.c_void_p

        # Inspire
        L.mxbs_inspire.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int,
            ctypes.c_uint32, ctypes.c_uint64,
        ]
        L.mxbs_inspire.restype = ctypes.c_void_p

        # Reinforce
        L.mxbs_reinforce.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_float,
        ]
        L.mxbs_reinforce.restype = ctypes.c_int

        # Field updates
        L.mxbs_update_group_bits.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_uint64,
        ]
        L.mxbs_update_group_bits.restype = ctypes.c_int

        L.mxbs_update_mode.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint16,
            ctypes.c_uint32, ctypes.c_uint64,
        ]
        L.mxbs_update_mode.restype = ctypes.c_int

        L.mxbs_update_meta.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p,
            ctypes.c_uint32, ctypes.c_uint64,
        ]
        L.mxbs_update_meta.restype = ctypes.c_int

        # Get / Delete
        L.mxbs_get.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        L.mxbs_get.restype = ctypes.c_void_p

        L.mxbs_delete.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_uint64,
        ]
        L.mxbs_delete.restype = ctypes.c_int

        # Save
        L.mxbs_save.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        L.mxbs_save.restype = ctypes.c_int

        # Stats
        L.mxbs_stats.argtypes = [ctypes.c_void_p]
        L.mxbs_stats.restype = ctypes.c_void_p

        # Meta
        L.mxbs_meta_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        L.mxbs_meta_get.restype = ctypes.c_void_p

        L.mxbs_meta_set.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        L.mxbs_meta_set.restype = ctypes.c_int

        # Free
        L.mxbs_free_string.argtypes = [ctypes.c_void_p]
        L.mxbs_free_string.restype = None

    # ========== Helpers ==========

    def _features_arg(self, features: Optional[list]):
        if features is None:
            return ctypes.POINTER(ctypes.c_uint8)()
        arr = (ctypes.c_uint8 * 16)(*features)
        return ctypes.cast(arr, ctypes.POINTER(ctypes.c_uint8))

    def _parse_json(self, ptr):
        if not ptr:
            return None
        try:
            raw = ctypes.string_at(ptr)
            return json.loads(raw.decode("utf-8"))
        finally:
            self._lib.mxbs_free_string(ptr)

    # ========== Pythonic API ==========

    def store(self, owner: int, text: str, *,
              from_id: int = 0, turn: int = 0,
              group_bits: int = 0, mode: int = 0o744,
              price: int = 100,
              features: Optional[list] = None,
              meta: str = "{}") -> int:
        cell_id = self._lib.mxbs_store(
            self._handle,
            owner, from_id, turn,
            group_bits, mode, price,
            self._features_arg(features),
            text.encode("utf-8"),
            meta.encode("utf-8"),
        )
        if cell_id == 0:
            raise RuntimeError("mxbs_store failed")
        return cell_id

    def get(self, cell_id: int) -> Optional[dict]:
        ptr = self._lib.mxbs_get(self._handle, cell_id)
        return self._parse_json(ptr)

    def delete(self, cell_id: int, requester: int, req_groups: int) -> bool:
        return self._lib.mxbs_delete(
            self._handle, cell_id, requester, req_groups
        ) == 1

    def search(self, query_features: list, viewer_id: int, viewer_groups: int,
               current_turn: int, limit: int = 5) -> list:
        ptr = self._lib.mxbs_search(
            self._handle,
            self._features_arg(query_features),
            viewer_id, viewer_groups,
            current_turn, limit,
        )
        return self._parse_json(ptr) or []

    def dream(self, viewer_id: int, viewer_groups: int,
              current_turn: int, limit: int = 3) -> list:
        ptr = self._lib.mxbs_dream(
            self._handle,
            viewer_id, viewer_groups,
            current_turn, limit,
        )
        return self._parse_json(ptr) or []

    def inspire(self, cell_id: int, limit: int = 5,
                viewer_id: int = 0, viewer_groups: int = 0) -> list:
        ptr = self._lib.mxbs_inspire(
            self._handle, cell_id, limit,
            viewer_id, viewer_groups,
        )
        return self._parse_json(ptr) or []

    def reinforce(self, cell_id: int, importance: float) -> bool:
        return self._lib.mxbs_reinforce(
            self._handle, cell_id, importance
        ) == 1

    def get_unscored(self) -> list:
        ptr = self._lib.mxbs_get_unscored(self._handle)
        return self._parse_json(ptr) or []

    def set_features(self, cell_id: int, features: list) -> bool:
        return self._lib.mxbs_set_features(
            self._handle, cell_id, self._features_arg(features)
        ) == 1

    def update_group_bits(self, cell_id: int, new_group_bits: int,
                          requester: int, req_groups: int) -> bool:
        return self._lib.mxbs_update_group_bits(
            self._handle, cell_id, new_group_bits, requester, req_groups
        ) == 1

    def update_mode(self, cell_id: int, new_mode: int,
                    requester: int, req_groups: int) -> bool:
        return self._lib.mxbs_update_mode(
            self._handle, cell_id, new_mode, requester, req_groups
        ) == 1

    def update_meta(self, cell_id: int, new_meta: str,
                    requester: int, req_groups: int) -> bool:
        return self._lib.mxbs_update_meta(
            self._handle, cell_id, new_meta.encode("utf-8"),
            requester, req_groups
        ) == 1

    def meta_get(self, key: str) -> Optional[str]:
        ptr = self._lib.mxbs_meta_get(self._handle, key.encode("utf-8"))
        result = self._parse_json(ptr)
        if result is None:
            return None
        return result.get("value")

    def meta_set(self, key: str, value: str) -> None:
        ret = self._lib.mxbs_meta_set(
            self._handle, key.encode("utf-8"), value.encode("utf-8")
        )
        if ret != 1:
            raise RuntimeError(f"meta_set failed for key={key}")

    def save(self, dest_path: str) -> bool:
        return self._lib.mxbs_save(
            self._handle, dest_path.encode("utf-8")
        ) == 1

    def stats(self) -> dict:
        ptr = self._lib.mxbs_stats(self._handle)
        return self._parse_json(ptr) or {}

    def close(self):
        if self._handle:
            self._lib.mxbs_close(self._handle)
            self._handle = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
