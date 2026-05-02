import ctypes
import json
import os
from pathlib import Path


class PresetHandle:
    def __init__(self, bridge, handle):
        self._bridge = bridge
        self.handle = handle

    def __del__(self):
        if self.handle:
            self._bridge.lib.mxmf_preset_free(self.handle)
            self.handle = None


class MxMindFox:
    def __init__(self, lib_path=None):
        if lib_path is None:
            lib_path = os.environ.get(
                "MXMINDFOX_LIB",
                str(Path(__file__).resolve().parent.parent.parent
                    / "target" / "release" / "libmxmindfox.dylib"),
            )
        self.lib = ctypes.CDLL(lib_path)
        self._setup()

    def _setup(self):
        L = self.lib

        L.mxmf_version.argtypes = []
        L.mxmf_version.restype = ctypes.c_char_p

        L.mxmf_str_free.argtypes = [ctypes.c_void_p]
        L.mxmf_str_free.restype = None

        L.mxmf_preset_load_json.argtypes = [ctypes.c_char_p]
        L.mxmf_preset_load_json.restype = ctypes.c_void_p

        L.mxmf_preset_free.argtypes = [ctypes.c_void_p]
        L.mxmf_preset_free.restype = None

        L.mxmf_preset_to_json.argtypes = [ctypes.c_void_p]
        L.mxmf_preset_to_json.restype = ctypes.c_void_p

        L.mxmf_compute_mood.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
        ]
        L.mxmf_compute_mood.restype = ctypes.c_void_p

        L.mxmf_compute_diplomacy_toward.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
        ]
        L.mxmf_compute_diplomacy_toward.restype = ctypes.c_float

        L.mxmf_adjust_threshold.argtypes = [
            ctypes.c_float, ctypes.c_char_p, ctypes.c_char_p,
        ]
        L.mxmf_adjust_threshold.restype = ctypes.c_float

        L.mxmf_decision_remember.argtypes = [
            ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_uint64,
        ]
        L.mxmf_decision_remember.restype = ctypes.c_int

        L.mxmf_decision_sample.argtypes = [
            ctypes.c_char_p, ctypes.c_float, ctypes.c_uint64,
        ]
        L.mxmf_decision_sample.restype = ctypes.c_int

    def version(self):
        return self.lib.mxmf_version().decode()

    def load_preset(self, preset_dict):
        j = json.dumps(preset_dict).encode()
        handle = self.lib.mxmf_preset_load_json(j)
        if not handle:
            raise RuntimeError("preset load failed")
        return PresetHandle(self, handle)

    def compute_mood(self, preset, cells, archetype=None):
        cells_json = json.dumps(cells).encode()
        arch = archetype.encode() if archetype else None
        ptr = self.lib.mxmf_compute_mood(preset.handle, cells_json, arch)
        if not ptr:
            raise RuntimeError("compute_mood failed")
        try:
            return json.loads(ctypes.string_at(ptr).decode())
        finally:
            self.lib.mxmf_str_free(ptr)

    def compute_diplomacy_toward(self, preset, cells, archetype=None):
        cells_json = json.dumps(cells).encode()
        arch = archetype.encode() if archetype else None
        return self.lib.mxmf_compute_diplomacy_toward(
            preset.handle, cells_json, arch,
        )

    def adjust_threshold(self, base, mood, rules):
        mood_json = json.dumps(mood).encode()
        rules_json = json.dumps(rules).encode()
        return self.lib.mxmf_adjust_threshold(base, mood_json, rules_json)

    def decision_remember(self, score, threshold, temperature, seed):
        return self.lib.mxmf_decision_remember(
            score, threshold, temperature, seed,
        ) == 1

    def decision_sample(self, candidates, temperature, seed):
        j = json.dumps(candidates).encode()
        result = self.lib.mxmf_decision_sample(j, temperature, seed)
        if result < 0:
            raise RuntimeError("decision_sample failed")
        return result
