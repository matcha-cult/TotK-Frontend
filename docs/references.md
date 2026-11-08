# 参考项目与来源（references）

> 本项目参考下列项目的**公开文档与行为**，不复制其代码。复制任何代码前必须先在本文件登记（项目、文件、许可证、版权头），并在 `THIRD_PARTY_NOTICES.md` 中保留声明。

## 1. 直接参考

| 项目 | 链接 | 许可证 | 参考了什么 | 不复制什么 |
|---|---|---|---|---|
| Savage Wind Recomp | https://github.com/Revivedx/SavageWindRecomp | MIT | 产品形态（Configuration 启动器）、PC 设置项的组织方式、文档结构、站点/补丁思路的背景 | 代码、生成的游戏代码、游戏资源 |
| TotK Recomp | https://github.com/valentderah/totk-pc-recomp | MIT | `totk.ini` 的键名/语义/默认值、安装目录结构（`totk.exe`、`exefs/`、`romfs/`、`totk-install.json`）、启动方式、F1 菜单与 `totk.ini` 的关系 | 代码、构建产物、游戏数据 |
| MacNativeGames | https://github.com/ly05010419/MacNativeGames | MIT | TotK 原生层的背景资料（宿主层、NVN 前端、版本差异） | 代码、生成的代码、游戏数据 |
| LAS Recomp | https://github.com/peiikai/LASRecomp | MIT | 技术谱系与运行时思路背景 | 代码 |
| UltraTears | https://github.com/kuraeow/ultratears | 以仓库 `LICENSE` 为准（README 提及 GPL，未确认） | `exefs/`、`romfs/` 输入目录格式、启动器形态 | 代码（许可证未确认前不复制） |
| Ryujinx | https://github.com/Ryujinx/Ryujinx | MIT | 仅背景：TotK Recomp 借用了其着色器翻译器；本项目不涉及 | 代码 |

## 2. 文档与数据来源

| 来源 | 用途 | 备注 |
|---|---|---|
| TotK Recomp `totk.ini.example` | `settings.md` 的键名、默认值、范围 | 公开文档；版本更新可能变化 |
| TotK Recomp `docs/controls.md`、`docs/settings.md`、`docs/installer.md`、`docs/architecture.md` | 输入/安装/架构背景 | 公开文档 |
| Savage Wind Recomp `README.md`、`docs/SAVAGE-WIND.md` | 产品形态与版本机制参考 | 公开文档 |
| Nintendo Switchbrew（https://switchbrew.org） | 系统服务背景 | 仅背景 |

## 3. 版本记录

| 项目 | 核对时间 | 核对内容 |
|---|---|---|
| TotK Recomp | 2026-11 | `totk.ini.example` 的节/键；安装目录结构；1.1.0/1.2.1/1.4.3 版本差异 |
| Savage Wind Recomp | 2026-11 | Configuration 形态、`savagewind.ini` 与游戏内 Options 的关系 |

## 4. 命名与商标

- “Savage Wind” 属于其原作者；本项目只在文档中引用，不借用其名称作为产品名。
- “TotK Frontend” 为本项目暂定名，不代表任天堂或 TotK Recomp 团队。
- *The Legend of Zelda*、*Tears of the Kingdom* 为任天堂商标，本项目与任天堂无关联。
