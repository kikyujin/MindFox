"""YamAMVA Python Bridge — ctypes wrapper for libyamamva.dylib/.so"""
import ctypes
import json
import platform
from pathlib import Path
from typing import Optional


class FfiElement(ctypes.Structure):
    _fields_ = [
        ("key", ctypes.c_char_p),
        ("label", ctypes.c_char_p),
        ("extra_json", ctypes.c_char_p),
    ]


class FfiArgs(ctypes.Structure):
    _fields_ = [
        ("node_type", ctypes.c_char_p),
        ("node_json", ctypes.c_char_p),
        ("element_count", ctypes.c_uint32),
        ("elements", ctypes.POINTER(FfiElement)),
        ("result", ctypes.c_char_p),
    ]


YAMAMVA_END = -1
YAMAMVA_PASS = 0
YAMAMVA_BLOCKING = 1


class YamamvaBridge:
    """Python wrapper for the YamAMVA C API."""

    def __init__(self, yaml_str: str, lib_path: Optional[str] = None):
        if lib_path is None:
            lib_path = self._find_library()

        self._lib = ctypes.cdll.LoadLibrary(lib_path)
        self._setup_signatures()

        yaml_bytes = yaml_str.encode("utf-8")
        self._handle = self._lib.yamamva_load(yaml_bytes, len(yaml_bytes))
        if not self._handle:
            raise RuntimeError("yamamva_load failed")

        self._args = FfiArgs()
        self._result_buf = None

    END = YAMAMVA_END

    def _find_library(self) -> str:
        system = platform.system()
        name = "libyamamva.dylib" if system == "Darwin" else "libyamamva.so"

        candidates = [
            Path.home() / "work" / "YAMAMVA" / "target" / "release" / name,
            Path.home() / "work" / "YAMAMVA" / "target" / "debug" / name,
            Path(__file__).parent.parent.parent / "YAMAMVA" / "target" / "release" / name,
            Path(name),
        ]
        for p in candidates:
            if p.exists():
                return str(p)

        raise FileNotFoundError(f"Cannot find {name}. Build YAMAMVA with: cargo build --release")

    def _setup_signatures(self):
        L = self._lib

        L.yamamva_load.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        L.yamamva_load.restype = ctypes.c_void_p

        L.yamamva_register.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32, ctypes.c_int32,
        ]
        L.yamamva_register.restype = None

        L.yamamva_exec.argtypes = [ctypes.c_void_p, ctypes.POINTER(FfiArgs)]
        L.yamamva_exec.restype = ctypes.c_int32

        L.yamamva_get_state.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        L.yamamva_get_state.restype = ctypes.c_void_p

        L.yamamva_set_state.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
        ]
        L.yamamva_set_state.restype = None

        L.yamamva_meta.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        L.yamamva_meta.restype = ctypes.c_void_p

        L.yamamva_save.argtypes = [ctypes.c_void_p]
        L.yamamva_save.restype = ctypes.c_void_p

        L.yamamva_free.argtypes = [ctypes.c_void_p]
        L.yamamva_free.restype = None

        L.yamamva_free_string.argtypes = [ctypes.c_void_p]
        L.yamamva_free_string.restype = None

    def _read_and_free(self, ptr):
        if not ptr:
            return None
        s = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self._lib.yamamva_free_string(ptr)
        return s

    def register(self, node_type: str, command_id: int,
                 blocking: bool = False):
        flags = YAMAMVA_BLOCKING if blocking else YAMAMVA_PASS
        self._lib.yamamva_register(
            self._handle, node_type.encode("utf-8"), command_id, flags,
        )

    def exec(self) -> tuple[int, dict]:
        cmd = self._lib.yamamva_exec(self._handle, ctypes.byref(self._args))

        if cmd == YAMAMVA_END:
            return YAMAMVA_END, {}

        node_type = (self._args.node_type.decode("utf-8")
                     if self._args.node_type else "")
        node_json_str = (self._args.node_json.decode("utf-8")
                         if self._args.node_json else "{}")
        node_json = json.loads(node_json_str) if node_json_str else {}

        elements = []
        for i in range(self._args.element_count):
            el = self._args.elements[i]
            elements.append({
                "key": el.key.decode("utf-8") if el.key else "",
                "label": el.label.decode("utf-8") if el.label else "",
                "extra": json.loads(
                    el.extra_json.decode("utf-8") if el.extra_json else "{}",
                ),
            })

        return cmd, {
            "node_type": node_type,
            "node_json": node_json,
            "elements": elements,
        }

    def set_result(self, result: str):
        self._result_buf = ctypes.c_char_p(result.encode("utf-8"))
        self._args.result = self._result_buf

    def get_state(self, key: str):
        ptr = self._lib.yamamva_get_state(
            self._handle, key.encode("utf-8"),
        )
        raw = self._read_and_free(ptr)
        if raw is None:
            return None
        return json.loads(raw)

    def set_state(self, key: str, value):
        val_json = json.dumps(value).encode("utf-8")
        self._lib.yamamva_set_state(
            self._handle, key.encode("utf-8"), val_json,
        )

    def meta(self, section: str) -> dict:
        ptr = self._lib.yamamva_meta(
            self._handle, section.encode("utf-8"),
        )
        raw = self._read_and_free(ptr)
        if raw is None:
            return {}
        return json.loads(raw)

    def save(self) -> str:
        ptr = self._lib.yamamva_save(self._handle)
        return self._read_and_free(ptr) or "{}"

    def close(self):
        if self._handle:
            self._lib.yamamva_free(self._handle)
            self._handle = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
