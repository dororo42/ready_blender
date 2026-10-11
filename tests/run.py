# -*- coding: utf-8 -*-
"""轻量测试运行器。

优先走 pytest(与 CI `pytest tests -q` 同一断言、同一事实源);
环境无 pytest 时退化为直接调用各 test_*.py 的 test_* 函数。
不再复制 core 断言(旧版内联 t1~t10 与 test_core.py 双轨漂移,已移除)。
"""
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)


def main() -> int:
    sys.path.insert(0, _ROOT)
    try:
        import pytest
        return pytest.main(["-q", _HERE])
    except ImportError:
        pass
    # 无 pytest 的退化路径:逐模块调用 test_* 函数
    import importlib
    failed = 0
    for fn in sorted(os.listdir(_HERE)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        try:
            mod = importlib.import_module("tests." + fn[:-3])
        except Exception:
            traceback.print_exc()
            failed += 1
            continue
        for name in sorted(dir(mod)):
            if name.startswith("test_") and callable(getattr(mod, name)):
                try:
                    getattr(mod, name)()
                except Exception:
                    traceback.print_exc()
                    failed += 1
                    print(f"[FAIL] {fn}::{name}")
                else:
                    print(f"[PASS] {fn}::{name}")
    print(f"\n{failed} failed" if failed else "\nall passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
