# 任务跟踪（tracking）

> 唯一事实源。计划见 [plan.md](plan.md)。所有实现工作开始前，对应任务必须是 `DOING`；完成时更新状态、产物与验收记录。

## 1. 状态定义

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `TODO` | 未开始 | 计划已列出 |
| `DOING` | 进行中 | 已有负责人且有明确产物 |
| `BLOCKED` | 受阻 | 写明阻塞原因与解除条件 |
| `REVIEW` | 待验证 | 产物已就绪，等待测试/评审 |
| `DONE` | 完成 | 退出标准全部满足，验收记录已填 |

## 2. 里程碑状态

| 里程碑 | 状态 | 进入下一阶段的条件 |
|---|---|---|
| M0 | `DONE` | 全部 M0 任务 `DONE`，初始提交已推送 |
| M1 | `DONE` | M0 完成；独立审查修正（`M1-T6`）已完成 |
| M2 | `DONE` | M1 完成；全部 M2 任务 `DONE` |
| M3 | `DOING` | M2 完成 |
| M4 | `TODO` | M3 完成 |
| M5 | `TODO` | M3 完成（可与 M4 并行，但写作用域不得重叠） |
| M6 | `TODO` | M4、M5 完成 |

## 3. 任务表

### M0 脚手架与规范

| ID | 任务 | 状态 | 产物 | 验收记录 |
|---|---|---|---|---|
| M0-T1 | 建立目录结构与文档分级（`docs/`、`private/`、忽略规则） | `DONE` | 目录、`.gitignore` | `git check-ignore private/` 通过；`private/` 不在索引 |
| M0-T2 | 双语 README（中文/英文，互链、结构一致） | `DONE` | `README.md`、`README.en.md` | 两文件存在且互链 |
| M0-T3 | 仓库协作规则 | `DONE` | `AGENTS.md` | 含分级、禁时间估计、提交规范 |
| M0-T4 | 文档体系（分级/设计/计划/跟踪/设置/参考/合规/交接） | `DONE` | `docs/*.md` | 逐份核对：无时间估计、无本机路径、参考项目已登记 |
| M0-T5 | git 跟踪与初始提交 | `DONE` | 提交记录、`origin/main` | `git status` 干净、`private/` 未入库、`main` 跟踪 `origin/main` |

### M1 核心库

| ID | 任务 | 状态 | 产物 | 验收 |
|---|---|---|---|---|
| M1-T1 | `totk.ini` 解析器（节/键/注释/保序/大小写不敏感） | `DONE` | `src/totk_frontend/ini.py` | `tests/test_ini_parse.py`、`tests/test_ini_edit.py` 通过；覆盖保序、注释/空行/未知行保留、大小写不敏感、重复键后者生效、CRLF/BOM/无末尾换行 |
| M1-T2 | 写入器（备份、原子写、只改目标行、回滚） | `DONE` | 同上 | `tests/test_ini_write.py` 通过；覆盖备份命名与重名、原子替换、只改目标行、回读校验、失败回滚、只读目录、中文路径、临时文件清理；公开示例 `totk.ini.example` 的临时副本核对：仅目标行变化、其余字节一致 |
| M1-T3 | 设置注册表（类型/范围/默认/中文标签/生效时机/暴露级别） | `DONE` | `src/totk_frontend/settings.py` | `tests/test_settings.py` 解析 `docs/settings.md` 键表逐项核对通过：节的归属、默认值、范围文本、生效时机、暴露级别、中文标签一致；`bind_*` 以模式项登记；`free_cores`、`replay_async` 作为文档第 7/9 节引用键登记 |
| M1-T4 | 校验器（单键 + 跨字段规则） | `DONE` | `src/totk_frontend/validate.py` | `tests/test_validate.py` 通过：覆盖布尔/整数/小数/枚举/分辨率/键名/绑定/文本的单键校验，以及第 8 节全部 8 条跨字段规则、版本限制与未知键忽略 |
| M1-T5 | 单元测试与测试数据（不含游戏数据） | `DONE` | `tests/`、`tools/coverage_check.py` | `python -m unittest discover -s tests -v` 全部用例通过、`python -m compileall src` 通过；`python tools/coverage_check.py` 语句覆盖率 99.07%（阈值 90%）；测试数据为手写合成样本，不含游戏数据；CRLF/BOM/无末尾换行在测试运行时生成 |
| M1-T6 | 独立审查修正（写入拼接、`bind_*` 模式、校验健壮性、测试与文档同步） | `DONE` | `src/totk_frontend/`、`tests/`、`tools/coverage_check.py`、相关文档 | 修复无末尾换行时新键拼接（补换行并加回归测试）；`bind_*` 收紧为文档与公开示例枚举的按键名，`bind_skip` 按未知键保留；整数校验不再转 `float`（防超大整数 `OverflowError`）；跨节同名键计入重复；绑定语法收紧；覆盖率工具在测试失败时退出非 0；POSIX 专属测试加平台守卫；结构化范围与文档范围文本互相校验；155 个用例通过、`compileall` 通过、语句覆盖率 99.07% |

### M2 预设与诊断

| ID | 任务 | 状态 | 产物 | 验收 |
|---|---|---|---|---|
| M2-T1 | 预设定义（Savage Wind 风格 / 手柄 / 性能 / 画质） | `DONE` | `src/totk_frontend/presets.py` | `tests/test_presets.py` 通过：4 个预设与 `settings.md` 第 9 节“必须包含”一致；全部键已注册、值通过单键校验、无 `free_cores=1`/`mouse_sens=0`；`menu_cursor` 标注仅 1.4.3 |
| M2-T2 | 预设应用、dry-run、回滚 | `DONE` | 同上 | `tests/test_presets.py` 通过：`plan_preset` 只给差异集且不改文档（dry-run）；`apply_preset` 只改目标键、幂等；版本过滤生效；`revert_plan` 恢复原值并移除新增键（应用时新建的空节头保留，与 I5 一致）；经 `write_ini` 落盘后可回滚到原字节；`format_plan` 输出可读预览 |
| M2-T3 | `doctor` 诊断规则 | `DONE` | `src/totk_frontend/doctor.py` | `tests/test_doctor.py` 通过：规则表与 `settings.md` 第 8 节 8 条规则一一对应且每条可触发；未知键只汇总不校验；重复键、版本限制、严重级别排序均有覆盖；`format_report` 输出中文建议与结论；诊断只读 |

### M3 CLI

| ID | 任务 | 状态 | 产物 | 验收 |
|---|---|---|---|---|
| M3-T1 | 命令框架与 `detect` | `DONE` | `src/totk_frontend/cli.py`、`__main__.py`、`install.py` | `tests/test_cli.py`、`tests/test_install.py` 通过：`python -m totk_frontend` 可用，13 个命令均有 `--help`；`detect` 打印每个标记存在/缺失，无安装目录或标记不全时退出码 1 且不崩溃 |
| M3-T2 | `list/get/set/unset` | `DONE` | 同上 | 测试通过：读写结果与默认值正确、键名大小写不敏感、缺 `totk.ini` 时读默认值、非法值/未知键退出码 1 且不写盘、`set` 可新建文件、`unset` 移除激活行并恢复默认 |
| M3-T3 | `preset/apply/backup/restore` | `DONE` | 同上 | 测试通过：`--dry-run` 不写盘并输出差异预览；`apply` 只写差异集且幂等；`backup` 命名符合约定；`restore` 恢复前备份当前文件并可恢复原字节；无效备份报错 |
| M3-T4 | `launch/log/version` | `DONE` | 同上 | 测试通过：`launch --dry-run` 只打印命令，另用假 `totk` 脚本验证真实启动路径；`log` 支持 `--tail`/`--path`/自动探测并处理缺失与读取失败；`version` 输出注册表信息；全程不启动真实游戏 |

### M4 GUI

| ID | 任务 | 状态 | 产物 | 验收 |
|---|---|---|---|---|
| M4-T1 | 窗口骨架、安装目录栏、状态栏 | `TODO` | `gui.py` | 无 tkinter 时提示 |
| M4-T2 | 画面/声音/控制/鼠标/高级/日志页 | `TODO` | 同上 | 注册表驱动 |
| M4-T3 | 预设、保存、恢复默认、备份、启动按钮 | `TODO` | 同上 | 与 CLI 一致 |

### M5 安装检测与引导

| ID | 任务 | 状态 | 产物 | 验收 |
|---|---|---|---|---|
| M5-T1 | 检测规则与结果模型 | `TODO` | `install.py` | 缺失项可解释 |
| M5-T2 | 首次引导页 | `TODO` | `gui`/`cli` | 不改动任何游戏文件 |
| M5-T3 | 版本感知（1.1.0/1.2.1/1.4.3 差异） | `TODO` | 键表标注 | 差异键有说明 |

### M6 打包与发布

| ID | 任务 | 状态 | 产物 | 验收 |
|---|---|---|---|---|
| M6-T1 | 打包（Windows 优先，Linux 评估） | `TODO` | 构建脚本 | 干净机器可运行 |
| M6-T2 | 发布检查单 | `TODO` | `docs/release-checklist.md` | 逐项通过 |
| M6-T3 | 许可证与第三方声明 | `TODO` | `LICENSE`、`THIRD_PARTY_NOTICES.md` | D3 已决 |

## 4. 更新规则

1. 开始任务：状态改 `DOING`，填写负责人（提交者/代理标识）。
2. 受阻：改 `BLOCKED` 并写原因与解除条件。
3. 完成：改 `DONE` 并填写验收记录（测试命令/结果摘要）。
4. 一次提交只更新与本次改动相关的任务行。
5. 里程碑状态只在 `plan.md` 的退出标准全部满足时更新。

## 5. 完成定义（DoD）

- 代码：可无头测试，测试通过；无新增第三方运行时依赖（除非有决策记录）。
- 文档：相关文档同步更新；公开/私有分级正确；无时间估计。
- 提交：只含相关改动；`private/` 未入库；提交信息为陈述句。
