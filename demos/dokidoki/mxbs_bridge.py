"""MxBS Python Bridge for dokidoki — minimal ctypes wrapper"""
import ctypes
import json
from typing import Optional

from config import get_libmxbs_path


class MxBSBridge:
    FACTOR_DIM = 16

    def __init__(self, db_path: str, half_life: int = 8, lib_path: Optional[str] = None):
        if lib_path is None:
            lib_path = get_libmxbs_path()

        self._lib = ctypes.cdll.LoadLibrary(lib_path)
        self._setup_signatures()

        config = json.dumps({"half_life": half_life})
        self._handle = self._lib.mxbs_open(
            db_path.encode("utf-8"),
            config.encode("utf-8"),
        )
        if not self._handle:
            raise RuntimeError(f"Failed to open MxBS database: {db_path}")

    def _setup_signatures(self):
        L = self._lib

        L.mxbs_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        L.mxbs_open.restype = ctypes.c_void_p

        L.mxbs_close.argtypes = [ctypes.c_void_p]
        L.mxbs_close.restype = None

        L.mxbs_store.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint64, ctypes.c_uint16, ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_char_p, ctypes.c_char_p,
        ]
        L.mxbs_store.restype = ctypes.c_uint64

        L.mxbs_search.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_uint32, ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_int,
        ]
        L.mxbs_search.restype = ctypes.c_void_p

        L.mxbs_get.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        L.mxbs_get.restype = ctypes.c_void_p

        L.mxbs_reinforce.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_float,
        ]
        L.mxbs_reinforce.restype = ctypes.c_int

        L.mxbs_update_group_bits.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_uint32, ctypes.c_uint64,
        ]
        L.mxbs_update_group_bits.restype = ctypes.c_int

        L.mxbs_stats.argtypes = [ctypes.c_void_p]
        L.mxbs_stats.restype = ctypes.c_void_p

        L.mxbs_free_string.argtypes = [ctypes.c_void_p]
        L.mxbs_free_string.restype = None

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

    def search(self, query_features: list, viewer_id: int, viewer_groups: int,
               current_turn: int, limit: int = 5) -> list:
        ptr = self._lib.mxbs_search(
            self._handle,
            self._features_arg(query_features),
            viewer_id, viewer_groups,
            current_turn, limit,
        )
        return self._parse_json(ptr) or []

    def reinforce(self, cell_id: int, importance: float) -> bool:
        return self._lib.mxbs_reinforce(
            self._handle, cell_id, importance
        ) == 1

    def update_group_bits(self, cell_id: int, new_group_bits: int,
                          requester: int, req_groups: int) -> bool:
        return self._lib.mxbs_update_group_bits(
            self._handle, cell_id, new_group_bits, requester, req_groups
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
