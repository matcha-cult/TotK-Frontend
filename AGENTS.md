# 仓库协作规则（AGENTS.md）

本文件约束所有在本仓库工作的协作者与 AI 代理。更上层的通用约定（工作区 `AGENTS.md`、README 双语规范）同时适用。

## 1. 目标与边界

- 本项目是 TotK Recomp 的**启动器与配置前台**，不修改游戏本体、不重编译、不做模拟。
- 一切游戏数据（游戏文件、密钥、固件、`exefs/`、`romfs/`、生成的 C、`totk.exe`、存档、日志、截图）**不得进入仓库**。
- 不写“如何获取游戏文件 / 密钥 / 固件”的说明。

## 2. 文档规则

- **语言**：文档以简体中文为主；根目录 `README` 必须同时提供 `README.md`（中文）与 `README.en.md`（英文），两者章节结构一致，并在顶部互相链接。其他层级若新增 README，同样遵守双语文档规范。
- **分级**（硬性要求）：
  - `docs/`：可公开、可提交的文档。
  - `private/`：仅本地、**不提交**（`.gitignore` 已忽略）。本机路径、测试记录、未验证推测、临时笔记一律放这里。
  - 判定标准与提交前检查见 [docs/DOC-POLICY.md](docs/DOC-POLICY.md)。
- **禁止时间估计**：计划、跟踪、设计、提交信息、交接提示词中**不得写具体工期/日期预估**（如“x 天/周/月”“预计某月完成”）。进度以阶段、依赖和验收标准表达。
- **参考项目**：引用外部项目必须写明名称、链接、许可证与“参考了什么”，不得复制其代码；见 [docs/references.md](docs/references.md)。

## 3. 计划与跟踪

- 唯一计划：[docs/plan.md](docs/plan.md)；唯一任务跟踪：[docs/tracking.md](docs/tracking.md)。
- 任何实现工作开始前，必须在 `docs/tracking.md` 中存在对应任务（ID 形如 `M1-T2`），并处于 `DOING`。
- 任务完成时更新状态、产物与验收记录；一次提交对应一组相关任务。
- 里程碑通过条件写在 `docs/plan.md`，未满足不得进入下一里程碑。

## 4. 提交规范

- 提交信息用**陈述句**，说明“做了什么/为什么”，不加 `feat:`、`fix:` 之类前缀。
- 一次提交只做一件事；格式化与功能改动分开。
- 提交前运行：单元测试（若已建立）、`python -m compileall`（若已有代码）、以及 [docs/DOC-POLICY.md](docs/DOC-POLICY.md) 的敏感信息检查。
- 不提交 `private/`、构建产物、虚拟环境、缓存。

## 5. 代码规范（随 M1 建立后细化）

- 默认技术栈：Python 3.11+，仅标准库；GUI 使用标准库 `tkinter`（可选依赖，无头环境可只用 CLI）。
- 不引入第三方运行时依赖；确需引入时先写入 `docs/plan.md` 的决策记录并说明许可证。
- 纯逻辑（ini 解析/写入、设置模型、预设、校验、安装检测）必须可在无 GUI 环境下测试。
- 写文件必须：先备份、原子替换（临时文件 + `os.replace`）、保留未知键与注释、只改目标行。

## 6. 参考代码的使用

- Savage Wind Recomp、TotK Recomp、LAS Recomp、MacNativeGames、Ryujinx 均为 MIT：可以参考其**行为与文档**，复制代码必须保留版权头并在 [docs/references.md](docs/references.md) 登记。
- UltraTears 等许可证未确认的项目：只读其公开文档，不复制代码。
- 任何参考都不得引入游戏数据或派生数据。

## 7. 交付与交接

- 交接提示词见 [docs/handoff-prompt.md](docs/handoff-prompt.md)，保持其自包含、可直接复制给下一个代理。
- 交接前必须：更新 `docs/tracking.md`、确认 `git status` 干净、`private/` 未入库、文档无时间估计。
