"""環境依存パス — libmxbs 自動検出"""

import os
import platform


def get_libmxbs_path() -> str:
    path = os.environ.get("LIBMXBS_PATH")
    if path:
        return path
    ext = "dylib" if platform.system() == "Darwin" else "so"
    return os.path.join(
        os.path.dirname(__file__), "..", "..", "target", "release", f"libmxbs.{ext}"
    )
