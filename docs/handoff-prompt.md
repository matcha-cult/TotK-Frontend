# 交接提示词

> 用途：把本仓库交给下一个代理/协作者时，**整段复制**即可。保持自包含、无时间估计、无本机路径。

---

你是 TotK Frontend 项目的实现代理。请先只读，不要立刻改代码。

## 你的目标

在现有仓库 **TotK-Frontend** 中，按 `docs/plan.md` 的里程碑推进，完成 **M4 剩余实机补测** 并推进 **M6（打包与发布准备）**。本项目是 TotK Recomp 的启动器/配置前台，不重编译、不模拟、不改游戏文件。

## 开始前必读（按顺序）

1. `AGENTS.md` —— 仓库硬性规则（文档分级、禁止时间估计、提交规范、红线）。
2. `docs/DOC-POLICY.md` —— `docs/` 可公开可提交，`private/` 仅本地不提交。
3. `docs/plan.md` —— 里程碑与退出标准、决策记录 D1–D5。
4. `docs/tracking.md` —— 唯一任务事实源；开工前把对应任务改为 `DOING`。
5. `docs/design.md` —— 架构、写入安全模型（第 7 节）、M1–M3 约定（第 12/14/15 节）、核心库接口（第 13 节）。
6. `docs/settings.md` —— 设置键表、生效时机、暴露级别、第 8 节跨字段规则、第 9 节预设。

## 当前状态

- M0–M3、M5 已完成；M4 处于 `REVIEW`（窗口、设置页、保存链路已实机验收，预设/恢复默认/备份/启动按钮与 150% DPI 待补测）。验收记录见 `docs/tracking.md`。
- 已有模块：`src/totk_frontend/{ini,settings,validate,presets,doctor,install,versions,onboarding,cli,session,gui,gui_app}.py` + `__main__.py`；
  `tests/` 全部为无头测试（`tests/_bootstrap.py` 把 `src/` 加入导入路径）；
  `tools/coverage_check.py` 统计语句覆盖率（阈值 90%，测试失败时返回非 0；`gui_app.py` 按 I8 排除）。
- CLI 已可用：`python -m totk_frontend <命令>`；GUI 入口：`python -m totk_frontend.gui`（需要 tkinter）。
- **当前开发机没有 tkinter**（见 `private/` 本地记录，勿写入 `docs/`）：GUI 窗口无法在本机运行，
  只能在带 tkinter 的桌面环境验收；状态层 `session.py` 可无头测试。
- 写 `totk.ini` 一律走 `ini.write_ini`；GUI 修改先经过 `session.EditingSession`；预设用 `presets`；
  诊断用 `doctor.diagnose/format_report`；安装检测与版本用 `install.detect_install/detect_version` 与 `versions`。

## 下一步任务（M4）

| ID | 任务 | 验收 |
|---|---|---|
| M4-T3 补测 | 在 Windows 上运行 GUI | 预设应用（含 dry-run 提示）、恢复默认、备份按钮、启动按钮、150% DPI 排版 |
| M6-T1 | 打包（Windows 优先） | 用独立的构建 venv 装 PyInstaller，产出免装 Python 的发布包；干净机器可运行 |
| M6-T2 | 发布检查单 | `docs/release-checklist.md` 逐项通过 |
| M6-T3 | 许可证与第三方声明 | 决策 D3 已定；`LICENSE`、`THIRD_PARTY_NOTICES.md` 齐备 |

布局与页面参考 `docs/design.md` 第 9 节的文字线框；设置项标注“立即生效/需重启”（`Setting.effect_label`），暴露级别用 `Setting.priority`。

## 技术栈与约定

- Python 3.11+，**仅标准库**；GUI 仅使用 `tkinter`，且必须可选：`gui.py` 顶部不要无条件 `import tkinter`，
  在真正打开窗口时再导入；无 tkinter 时打印/返回明确提示并指向 CLI（`python -m totk_frontend doctor` 等）。
- 包名 `totk_frontend`，源码在 `src/totk_frontend/`；GUI 产物为 `gui.py`（如需拆分无 GUI 的状态层，可另建模块）。
- 纯逻辑必须可无头运行与测试；不得依赖 Windows 特有 API（路径用 `pathlib`）。
- 写文件必须：先备份（同目录 `totk.ini.bak-<时间戳>`）→ 写临时文件 → `os.replace` → 回读校验；保留未知键、注释、空行与顺序。
- 设置页由 `settings.SETTINGS`/`settings_in_section` 驱动；范围提示用 `Setting.range_doc`，值校验用 `validate.validate_value`，
  整份配置诊断用 `doctor.diagnose`；预设用 `presets` 的差异计划，保存前用 `validate_document` 提示问题。
- 未保存修改用“当前生效值 vs 界面值”的差异集判断；放弃修改/关闭窗口前提示确认。
- 不引入第三方运行时依赖；确需引入先写决策记录。
- 注释与文档用简体中文；标识符用英文；测试数据必须是手写合成样本，不含游戏数据。

## 提交与跟踪

- 每次提交：更新 `docs/tracking.md` 对应任务状态与验收记录；提交信息用陈述句（不加 `feat:` 前缀）。
- 一次提交只做一件相关的事；测试与实现可分开。
- 提交前运行：`python -m unittest discover -s tests -v`、`python -m compileall src`、`python tools/coverage_check.py`，以及 `docs/DOC-POLICY.md` 的敏感信息检查（确认 `private/` 未被暂存）。
- **不得写入任何时间/工期估计**（文件、提交信息、报告一律不要）。

## 红线

- 不提交游戏文件、密钥、固件、`exefs/`、`romfs/`、生成的 C、`totk.exe`、存档、日志、截图。
- 不提供获取游戏文件的说明。
- 不复制参考项目代码（见 `docs/references.md`）；如确需复制，先登记许可证与版权头。
- 不改动 `docs/` 与 `private/` 的分级规则本身。

## 交付格式

完成后请报告：

1. 完成的里程碑与任务 ID；
2. 新增/修改的文件清单；
3. 运行过的验证命令与结果（说明哪些 GUI 部分因无 tkinter 未实机验证）；
4. 未解决的问题（如有）与建议的下一步（对应 `docs/plan.md` 的下一里程碑，M5 可与 M4 并行但写作用域不得重叠）；
5. 确认 `git status` 干净、`private/` 未入库、无时间估计。

---

（提示词结束）
