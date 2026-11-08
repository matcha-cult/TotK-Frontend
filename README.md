# TotK Frontend

[English](README.en.md)

> 状态：**M3 已完成**。核心库（`totk.ini` 解析/写入、设置注册表、校验）、预设与 `doctor` 诊断、命令行工具已就绪并有单元测试；后续里程碑见 [docs/plan.md](docs/plan.md)。

TotK Frontend 是为 [TotK Recomp](https://github.com/valentderah/totk-pc-recomp)（《塞尔达传说：王国之泪》的静态重编译 PC 移植）准备的 **PC 化启动器与配置前台**。产品形态参考 [Savage Wind Recomp](https://github.com/Revivedx/SavageWindRecomp)（BotW 的同类项目）的 Configuration 界面：在进入游戏前完成启动、画面 / 声音 / 控制 / 鼠标设置、预设管理、游戏文件引导与日志查看，让玩家尽量不必手改 `totk.ini`。

## 这不是什么

- **不是模拟器，也不是 TotK 的重编译器**：游戏本体仍由 TotK Recomp 构建与运行，本项目只管理它的配置与启动流程。
- **不包含、不请求、不生成任何任天堂游戏文件、密钥、固件或重编译产物**。
- **不是游戏内原生菜单的改造**：把 PC 设置画进游戏自己的菜单属于单独的后续议题（见 [docs/plan.md](docs/plan.md) 的“非目标”）。

## 文档分级（重要）

本仓库的文档分两类，**必须放在不同目录**：

| 目录 | 级别 | 是否提交 | 内容 |
|---|---|---|---|
| `docs/` | 可公开、可提交 | 是 | 设计、计划、跟踪、设置参考、参考项目、合规 |
| `private/` | 仅本地 | **否**（已被 `.gitignore` 忽略） | 本机路径、测试记录、未验证推测、临时笔记 |

判定标准与提交前检查清单见 [docs/DOC-POLICY.md](docs/DOC-POLICY.md)。提交前请确认 `git status` 中不出现 `private/`。

## 目录结构

```text
.
├── README.md / README.en.md   # 双语说明（工作区规范要求）
├── AGENTS.md                  # 仓库协作与 AI 代理规则
├── src/totk_frontend/         # 核心库与 CLI（ini、设置注册表、校验、预设、诊断、命令行）
├── tests/                     # 无头单元测试与手写合成测试数据
├── tools/coverage_check.py    # 语句覆盖率检查（仅标准库）
├── tools/check_env.py         # 环境自检（Python/tkinter/仓库布局）
├── docs/                      # 公开文档（可提交）
│   ├── DOC-POLICY.md           # 文档分级与提交检查
│   ├── design.md               # 产品与技术设计
│   ├── plan.md                 # 开发计划（阶段 / 里程碑，不写时间估计）
│   ├── tracking.md             # 任务跟踪（唯一事实源）
│   ├── settings.md             # totk.ini 设置参考
│   ├── references.md           # 参考项目与来源
│   ├── compliance.md           # 合规与版权
│   └── handoff-prompt.md       # 交接提示词（可复用）
└── private/                    # 仅本地（被忽略，不提交）
```

## 当前进度

- M0：脚手架与规范 —— 已完成
- M1：核心库（`totk.ini` 解析/写入、设置注册表、校验、单元测试）—— 已完成
- M2：预设系统与 `doctor` 诊断 —— 已完成
- M3：命令行工具（detect/list/get/set/preset/doctor/launch/log 等）—— 已完成
- M5：安装检测与版本感知 —— 进行中（检测与版本感知已完成，引导页待做）
- M4 起：GUI、安装引导、打包（详见 [docs/plan.md](docs/plan.md)）

## 参考项目

本项目在**产品形态、设置语义与文档组织**上参考下列项目；不复制其代码，许可证与引用方式见 [docs/references.md](docs/references.md)。

- [Savage Wind Recomp](https://github.com/Revivedx/SavageWindRecomp)（MIT）——启动器 / Configuration 的产品形态与 PC 设置项
- [TotK Recomp](https://github.com/valentderah/totk-pc-recomp)（MIT）——`totk.ini` 设置模型、安装目录结构与启动方式
- [MacNativeGames](https://github.com/ly05010419/MacNativeGames)（MIT）——TotK 原生层背景资料
- [LAS Recomp](https://github.com/peiikai/LASRecomp)（MIT）——技术谱系与运行时思路
- [UltraTears](https://github.com/kuraeow/ultratears)——`exefs/`、`romfs/` 输入目录参考（许可证以仓库为准）
- [Ryujinx](https://github.com/Ryujinx/Ryujinx)（MIT）——仅背景资料（着色器翻译器），本项目不使用其代码

## 合规

- 不做盗版协助：仓库内不出现游戏文件、密钥、固件、生成的游戏代码、存档、日志、截图。
- 只读取玩家本机的 TotK Recomp 安装目录，只写 `totk.ini` 及其备份。
- 免责声明：本项目与 Nintendo 无关；*The Legend of Zelda*、*Tears of the Kingdom* 为任天堂商标。

## 许可证

**待定**（见 [docs/plan.md](docs/plan.md) 未决问题 D3）。在确定之前，仓库内容不视为已授予任何许可。
