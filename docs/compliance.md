# 合规与版权（compliance）

## 1. 游戏数据红线

本仓库**永远不包含**：

- 游戏本体、更新、DLC 的镜像（`*.nsp`、`*.xci`、`*.nsz`、`*.xcz`、`*.nca`）；
- 密钥（`prod.keys`、`title.keys`）、固件、票据（`*.tik`、`*.cert`）；
- `exefs/`、`romfs/` 及由游戏代码生成的 C、`totk.exe`、`swgame.*` 等派生文件；
- 存档、日志、截图、录屏。

工具运行时只读写**玩家本机**的 TotK Recomp 安装目录，且只写 `totk.ini` 及其备份；本仓库不提供任何获取上述文件的途径或说明。

## 2. 参考代码

- 只参考公开文档与行为；复制 MIT/BSD 代码必须保留版权头，并在 [references.md](references.md) 与 `THIRD_PARTY_NOTICES.md` 登记。
- 许可证未确认的项目（如 UltraTears）不复制代码。
- 不复制参考项目中与游戏相关的常量表、地址、补丁、生成的代码。

## 3. 商标与免责

- 本项目为独立同人工具，与 Nintendo 无关联、未获其认可或赞助。
- *The Legend of Zelda*、*Tears of the Kingdom*、*Nintendo Switch* 为任天堂商标。
- “Savage Wind”“TotK Recomp”等名称属于各自项目作者；本项目只引用，不冒充。

## 4. 分发注意

- 发布包只含本项目代码与文档，不含游戏数据与派生数据。
- 发布前运行 [DOC-POLICY.md](DOC-POLICY.md) 的检查清单与 M6 发布检查单。
- 许可证确定前（决策 D3），不对外声称任何授权。

## 5. 隐私

- 不在公开文档中写入本机路径、用户名、密钥信息。
- 本机信息放 `private/`（不入库）。
- 若用户提交日志/截图求助，先提示其清理路径与账号信息。
