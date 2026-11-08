# 交接提示词

> 用途：把本仓库交给下一个代理/协作者时，**整段复制**即可。保持自包含、无时间估计、无本机路径。

---

你是 TotK Frontend 项目的实现代理。请先只读，不要立刻改代码。

## 你的目标

在现有仓库 **TotK-Frontend** 中，按 `docs/plan.md` 的里程碑推进，先完成 **M3（CLI）**。本项目是 TotK Recomp 的启动器/配置前台，不重编译、不模拟、不改游戏文件。

## 开始前必读（按顺序）

1. `AGENTS.md` —— 仓库硬性规则（文档分级、禁止时间估计、提交规范、红线）。
2. `docs/DOC-POLICY.md` —— `docs/` 可公开可提交，`private/` 仅本地不提交。
3. `docs/plan.md` —— 里程碑与退出标准、决策记录 D1–D5。
4. `docs/tracking.md` —— 唯一任务事实源；开工前把对应任务改为 `DOING`。
5. `docs/design.md` —— 架构、写入安全模型（第 7 节）、M1 约定（第 12 节）、核心库接口（第 13 节）、M2 约定（第 14 节）。
6. `docs/settings.md` —— `totk.ini` 键表、范围、生效时机、第 8 节跨字段规则、第 9 节预设。

## 当前状态

- M0（脚手架与文档）、M1（核心库，含独立审查修正）、M2（预设与 `doctor`）已完成，验收记录见 `docs/tracking.md`。
- 已有模块：`src/totk_frontend/{ini,settings,validate,presets,doctor}.py`；
  `tests/` 全部为无头测试（`tests/_bootstrap.py` 负责把 `src/` 加入导入路径）；
  `tools/coverage_check.py` 统计语句覆盖率（阈值 90%，测试失败时同样返回非 0）。
- 尚未有 CLI 入口：M3 需要新增 `src/totk_frontend/cli.py` 与 `src/totk_frontend/__main__.py`，使 `python -m totk_frontend ...` 可用。
- 写 `totk.ini` 一律走 `ini.write_ini`；预设差异/回滚用 `presets.plan_preset`/`apply_preset`/`revert_plan`；诊断用 `doctor.diagnose`/`format_report`。

## 下一步任务（M3）

| ID | 任务 | 验收 |
|---|---|---|
| M3-T1 | 命令框架与 `detect` | 每个命令有 `--help`；`detect` 只读检测安装目录标记（`totk.exe`/`totk`、`totk.ini`、`totk-install.json`、`exefs/`、`romfs/`），缺项可解释；M5 再扩展版本与引导 |
| M3-T2 | `list` / `get` / `set` / `unset` | 读写结果正确；未知键按未知处理（保留、不校验）；`set` 走安全写入并回读校验 |
| M3-T3 | `preset` / `apply` / `backup` / `restore` | `--dry-run` 输出差异预览；应用只改差异集；备份/恢复可用且失败可回滚 |
| M3-T4 | `launch` / `log` / `version` | 不启动游戏也能测试；`launch` 只按记录路径启动 `totk.exe`，不修改游戏文件 |

## 技术栈与约定

- Python 3.11+，**仅标准库**（CLI 用 `argparse`）；GUI 只在 M4 引入 `tkinter`，且必须可选。
- 包名 `totk_frontend`，源码在 `src/totk_frontend/`；测试放 `tests/`，沿用无头方式。
- 纯逻辑必须可无头运行与测试；不得依赖 Windows 特有 API（路径用 `pathlib`）。
- 写文件必须：先备份（同目录 `totk.ini.bak-<时间戳>`）→ 写临时文件 → `os.replace` → 回读校验；保留未知键、注释、空行与顺序。
- 退出码约定建议在 `docs/design.md` 记录（例如 0 成功、1 用户可修正错误、2 用法错误）；错误信息用简体中文、可操作。
- 无游戏/无 `totk.ini` 的机器上，命令不得崩溃，应给出明确提示。
- 不引入第三方运行时依赖；确需引入先写决策记录。
- 代码注释与文档用简体中文；标识符用英文；测试数据必须是手写合成样本，不含游戏数据。

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
3. 运行过的验证命令与结果；
4. 未解决的问题（如有）与建议的下一步（对应 `docs/plan.md` 的下一里程碑）；
5. 确认 `git status` 干净、`private/` 未入库、无时间估计。

---

（提示词结束）
