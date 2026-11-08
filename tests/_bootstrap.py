"""测试辅助：把 ``src/`` 加入导入路径。

仓库采用 ``src`` 布局（见 docs/design.md 第 12 节 I1），M1 不添加打包配置，
因此测试通过本模块在 ``python -m unittest discover -s tests`` 下直接导入 ``totk_frontend``。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
