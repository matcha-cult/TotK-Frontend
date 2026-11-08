# 设计（design）

> 状态：M1 已完成；M0 的架构与契约不变，M1 的实现约定见第 12 节，核心库接口见第 13 节。实现细节在对应里程碑中细化，变更须同步 `plan.md` 与 `tracking.md`。

## 1. 背景

[TotK Recomp](https://github.com/valentderah/totk-pc-recomp) 把《王国之泪》静态重编译为原生 PC 程序，其设置存放在安装目录的 `totk.ini`，并有一个宿主侧的 `F1` 设置菜单。与 [Savage Wind Recomp](https://github.com/Revivedx/SavageWindRecomp) 的 *Savage Wind Configuration* 相比，它在**启动流程、设置发现性、键鼠/鼠标相机的手感入口**上更“工程化”：很多项只在 `totk.ini.example` 里以注释形式给出，玩家需要手动编辑文件。

本项目的目标不是替换 TotK Recomp，而是补上它缺少的**产品外壳**：

- 进入游戏前的统一入口（启动、设置、游戏文件、日志、退出）；
- 把 `totk.ini` 中与 PC 体验相关的键以可视化方式暴露；
- 提供“Savage Wind 风格”的预设（键鼠优先、鼠标相机直连、PC 按键提示等）；
- 降低误操作风险（备份、校验、只改目标键、保留未知内容）。

## 2. 目标（B1）

1. 检测 TotK Recomp 安装目录并识别其版本/更新版本。
2. 读写 `totk.ini`：解析、显示、修改、校验、备份、恢复。
3. 提供预设与“一键调到 Savage Wind 风格”。
4. 提供启动器：启动游戏、打开安装目录、查看/导出日志。
5. 提供 CLI 与 GUI 两种入口；核心逻辑在无 GUI 环境可测试。
6. 文档、跟踪、合规齐备，可交接。

## 3. 非目标

- 不实现 TotK 的静态重编译、运行时或渲染。
- 不修改 `totk.exe`、`exefs/`、`romfs/`、着色器缓存。
- 不把 PC 选项绘制进游戏原生菜单（属独立议题，未来另行评估）。
- 不提供、不下载、不生成任何游戏文件/密钥/固件。
- 不承诺跨版本兼容所有 TotK Recomp 版本；以文档标注的版本为准（当前：1.1.0 / 1.2.1 / 1.4.3，重点 1.4.3）。

## 4. 用户流程

```text
首次启动
  └─ 选择/自动检测安装目录（totk.exe、totk.ini、totk-install.json、exefs/、romfs/）
       ├─ 检测失败 → 显示缺少的标记文件与修复建议
       └─ 检测成功 → 读取 totk.ini（不存在则从模板生成）
            ├─ 选择预设（Savage Wind 风格 / 手柄 / 性能 / 画质 / 自定义）
            ├─ 逐页调整：画面 / 声音 / 控制 / 鼠标 / 高级
            ├─ 保存（备份旧文件 → 原子写入 → 校验回读）
            └─ 启动游戏 → 记录一次启动（日志路径、退出码）
日常使用
  └─ 启动器 → Play（读取上次目录）→ 游戏
```

## 5. 功能模块

| 模块 | 职责 | 不依赖 GUI |
|---|---|---|
| `ini` | 解析/序列化 `totk.ini`：保序、保留注释与未知键、大小写不敏感、节（section）归属 | 是 |
| `settings` | 设置注册表：键、节、类型、范围/枚举、默认值、中文标签、生效时机、暴露优先级 | 是 |
| `validate` | 单键校验 + 跨字段规则（如 `fps_limit>60` 与 `realtime`） | 是 |
| `presets` | 预设定义与应用（差异集），支持 dry-run 与回滚 | 是 |
| `install` | 安装目录检测、版本信息、日志定位、启动命令 | 是 |
| `cli` | `detect / list / get / set / preset / doctor / launch / log` | 是 |
| `gui` | tkinter 窗口：启动页、画面、声音、控制、鼠标、高级、日志、关于 | 仅此层 |

## 6. 技术选型（建议，待 M0 决策确认）

- **语言/运行时**：Python 3.11+，仅标准库。
- **GUI**：标准库 `tkinter`（Windows 官方 Python 自带；无显示环境时自动退回 CLI）。
- **打包**：后续用 PyInstaller 生成 Windows 单文件/目录（Linux AppImage 另行评估）。
- **理由**：与 TotK Recomp 安装器同为 Python 技术栈；零第三方依赖便于审计与分发；核心逻辑可无头测试。
- **备选**：C++/Dear ImGui（与游戏同栈、启动快，但构建与分发成本高，暂不采用）。

## 7. 写入安全模型（硬性）

1. 写入前：若 `totk.ini` 存在，复制为 `totk.ini.bak-YYYYmmdd-HHMMSS`（同目录）。
2. 只改动用户确认的键所在行；其余行（含注释、空行、未知键、顺序）逐字节保留。
3. 写入使用“临时文件 + `os.replace`”原子替换；编码 UTF-8，换行保持平台默认（Windows CRLF）或沿用原文件风格。
4. 写入后回读并校验目标键值；失败则用备份恢复并报错。
5. 永不删除文件；恢复默认 = 移除激活行（回到注释默认）而非删除整文件。

## 8. 与 TotK Recomp 的契约

- 安装目录判定标记：`totk.exe`（Windows）或 `totk`（Linux）、`totk.ini`、`totk-install.json`、`exefs/`、`romfs/`。
- `totk.ini` 语义：`[section]` 分组；`#`、`;` 起注释；键名大小写不敏感；**未出现或注释掉的行表示默认值**；同名键以最后一个生效。
- 生效时机：不同键分为“立即生效”与“下次启动生效”，必须在 UI 中标注；`prompts`、`pad_layout` 的部分效果需重启。
- 版本差异：`menu_cursor`（游戏菜单鼠标）、`fov`、`mouse_mode=direct` 等只对 1.4.3 完整可用；1.1.0 的鼠标为摇杆模拟。

## 9. 界面（文字线框）

```text
┌ TotK Frontend ──────────────────────────────┐
│ 安装目录: [D:\TotK Recomp        ] [浏览] [重新检测] │
│ 状态: 1.4.3 已安装 · 3 个设置与默认不同        │
├ 启动 │ 画面 │ 声音 │ 控制 │ 鼠标 │ 高级 │ 日志 ┤
│ 预设: [Savage Wind 风格 ▼] [应用] [另存为…]     │
│ ...设置控件...                                 │
├──────────────────────────────────────────────┤
│ [保存] [恢复默认] [备份] [启动游戏]             │
└──────────────────────────────────────────────┘
```

## 10. 验收标准（整体）

- 在无 TotK 安装的机器上，`doctor` 能给出明确缺失项，不崩溃。
- 对一份真实的 `totk.ini`，应用预设前后：目标键正确、其余行逐字节不变。
- 任何写操作失败都能回滚且不损坏原文件。
- CLI 与 GUI 的设置结果一致（同一核心库）。
- 文档齐全：公开/私有分级、参考项目、合规、跟踪、交接提示词。

## 11. 风险与未知

| 风险 | 影响 | 处置 |
|---|---|---|
| TotK Recomp 设置键随版本变化 | 设置表过期、误写 | 键表随版本维护；未知键一律保留、不展示为可编辑 |
| `totk.ini` 被游戏改写（注释丢失） | 我们的“保留注释”失效 | 接受；文档说明；写入前备份 |
| Windows 路径/编码差异 | 读写错误 | 统一用 `pathlib`；测试含中文路径与 CRLF |
| 无 tkinter 的环境 | GUI 不可用 | CLI 兜底；GUI 为可选 |
| 上游项目改名/迁移 | 文档链接失效 | 参考项目表标注版本日期，定期核对 |

## 12. M1 实现决定（记录）

M1 的目标是“不启动 GUI 也能安全读写 `totk.ini`”。以下约定在 M1 开始时确定，后续里程碑沿用；变更须同步本节与 `tracking.md`。

| 编号 | 决定 | 说明 |
|---|---|---|
| I1 | 包名 `totk_frontend`，源码位于 `src/totk_frontend/`；M1 不添加打包配置 | 测试由 `tests/_bootstrap.py` 把 `src/` 加入 `sys.path`；`pyproject.toml`/PyInstaller 留给 M6 |
| I2 | 模块依赖方向：`ini` ← `settings` ← `validate`；`settings` 不依赖 `ini` | 解析/写入不感知设置语义；校验层同时使用两者 |
| I3 | 编码 UTF-8（可带 BOM，原样保留）；换行逐行保留原文件风格，新增行沿用文件内的主流换行 | 不做 UTF-16 等转换；解码失败直接报错，避免静默损坏 |
| I4 | 写入只改目标键“最后一个生效行”；新增键插入该节最后一个键值行之后（该节没有键值行时插到节内最后一个非空行之后）；文件没有该节时在末尾新建 | 其余行（含注释、空行、未知键、顺序）逐字节保留 |
| I5 | `unset`（恢复默认）语义：移除该键的全部激活行，保留注释行；不删除节 | 对应第 7 节第 5 条 |
| I6 | 备份命名 `totk.ini.bak-YYYYmmdd-HHMMSS`（同目录）；同一秒内重名时追加 `-2`、`-3`… | 备份保留，不自动清理 |
| I7 | 回读校验：写入后重新读取字节并逐键核对本次改动；失败时用写入前的原内容原子恢复并报错；新建文件校验失败时删除本次新建的文件 | 备份在任何情况下都不删除 |
| I8 | 覆盖率阈值：`src/totk_frontend` 的语句覆盖率（AST 统计；多行语句按一条计）≥ 90%，用 `python tools/coverage_check.py` 测量（仅标准库） | M1 退出标准之一 |
| I9 | 校验结果模型：`Issue(severity, code, message, keys, suggestion)`；“错误/警告/提示”对应 `settings.md` 第 8 节的三级 | 校验只读，不自动改文件 |
| I10 | 模式键 `bind_*` 在注册表中按模式登记（P0、只读、由 F1 菜单写入）；未知键一律保留但不展示为可编辑 | 对应第 11 节风险处置 |

测试数据全部为手写合成样本，不含任何游戏数据；CRLF、BOM、无末尾换行等边界在测试运行时生成，避免换行归一化影响样本本身。

## 13. 核心库接口（M1 交付）

| 模块 | 公开接口 | 说明 |
|---|---|---|
| `ini` | `IniDocument`：`from_text`/`from_bytes`/`from_path`、`get`/`get_all`/`has`、`keys`/`sections`/`duplicates`、`set`/`unset`、`render`/`to_bytes` | 保序、保留注释与未知行；`set` 只改最后一个生效行，新增键插入目标节；`unset` 移除激活行、保留注释 |
| `ini` | `read_ini`、`write_ini`、`write_bytes_atomic`、`create_backup`、`WriteResult`、`IniParseError`/`IniWriteError` | 写入安全模型见第 7 节；`write_ini` 返回备份路径与“是否发生变化” |
| `settings` | `Setting`、`SETTINGS`、`get_setting`、`settings_in_section`、`ValueType`/`Effect`/`Priority`、`SECTION_ORDER`/`SECTION_LABELS` | 设置注册表，与 `settings.md` 逐项一致；`bind_*` 用模式项登记 |
| `validate` | `Issue`、`Severity`、`validate_value`、`validate_document`、`effective_value`、`parse_resolution`、`is_16_9` | 单键与跨字段校验；只读；依赖本机环境的两条规则需调用方传入检测结果 |

验证命令：`python -m unittest discover -s tests -v`、`python -m compileall src`、`python tools/coverage_check.py`
（语句覆盖率阈值 90%，M1 验收时为 99.32%）。M2 的 `presets` 只能使用注册表中的键，`doctor` 复用
`validate` 的稳定规则码（`rule.*`、`value.*`）。
