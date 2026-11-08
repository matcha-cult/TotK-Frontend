"""TotK Frontend 核心库。

本包只包含纯逻辑，不依赖 GUI 与 Windows 特有 API，可在无头环境运行与测试。

模块划分（见 docs/design.md 第 5、12 节）：

- :mod:`totk_frontend.ini`：``totk.ini`` 的解析与安全写入；
- :mod:`totk_frontend.settings`：设置注册表（类型、范围、默认值、中文标签、生效时机、暴露级别）；
- :mod:`totk_frontend.validate`：单键校验与跨字段规则。

入口与打包在后续里程碑（M3 CLI、M6 打包）引入。
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
