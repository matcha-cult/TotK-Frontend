# `totk.ini` 设置参考（settings）

> 来源：TotK Recomp 仓库的 `totk.ini.example` 与 `docs/controls.md`（公开文档，2026-11 核对）。键名大小写不敏感；未出现或被注释的行表示默认值；同名键以最后一个生效。TotK Recomp 版本更新可能增删键，注册表以本文件为准并随版本维护。

## 1. 暴露优先级

| 级别 | 含义 |
|---|---|
| **P0** | 启动器首屏/常用页必须暴露 |
| **P1** | 进阶页暴露（默认折叠） |
| **P2** | 只读展示或完全不暴露（高级/诊断/实验项） |

“生效”列：`即时` = 游戏运行中改动立即生效；`重启` = 下次启动生效。

## 2. `[frame rate]` 帧率

| 键 | 默认 | 范围/取值 | 说明 | 生效 | 级别 |
|---|---|---|---|---|---|
| `fps_limit` | `60` | 30/40/45/60/90/120/144、30–240 的整数、`display` | 帧率上限；高于 60 属实验性 | 即时 | P0 |
| `realtime` | `1` | 0/1 | 游戏速度跟随真实时钟；`fps_limit>60` 时必须为 1 | 即时 | P0 |
| `frame_queue` | `0` | 0/1 | 帧队列，减少掉帧、增加最多一帧延迟 | 即时 | P1 |
| `highfps_fix` | `1` | 0/1 | 高帧率下物理弹跳修复 | 即时 | P1 |

## 3. `[display]` 画面

| 键 | 默认 | 范围/取值 | 说明 | 生效 | 级别 |
|---|---|---|---|---|---|
| `device_profile` | `auto` | `auto`/`desktop`/`deck` | Steam Deck 上改默认值 | 重启 | P2 |
| `vk_present` | `mailbox` | `mailbox`/`fifo`/`immediate` | 呈现模式；`immediate` 会撕裂 | 重启 | P1 |
| `window_size` | `1920x1080` | 640x360–7680x4320 | 窗口客户区像素；F11 切换全屏并写回 | 即时 | P0 |
| `fullscreen` | `0` | 0/1 | 无边框全屏 | 即时 | P0 |
| `output_res` | `1920x1080` | 1280x720–7680x4320 | 游戏绘制分辨率；非 16:9 需安装器预先准备 UI 布局 | 重启 | P0 |
| `render_scale` | `game` | `game` 或 25–400（%） | 3D 场景分辨率；>100 为超采样 | 重启 | P1 |
| `upscaler` | `fsr` | `fsr`/`bilinear` | 窗口大于输出分辨率时的缩放方式 | 即时 | P0 |
| `sharpness` | `80` | 0–100 | FSR 锐化 | 即时 | P1 |
| `aspect` | `fit` | `fit`/`stretch` | 窗口形状与输出不一致时的处理 | 即时 | P1 |
| `movie_aspect` | `keep` | `keep`/`stretch` | 预渲染影片的形状 | 影片开始时 | P2 |
| `fov` | `100` | 70–140（%） | 视野；**仅 1.4.3** | 即时 | P1 |
| `aniso` | `game` | `game`/2/4/8/16 | 各向异性过滤 | 重启 | P1 |
| `shadow_res` | `game` | `game`/256/512/768/1024/1536/2048 | 太阳阴影贴图尺寸 | 重启 | P1 |
| `shadow_scale` | `1` | 1–4 | 阴影贴图放大倍数 | 重启 | P1 |
| `shadow_range` | `100` | 50–400（%） | 阴影级联范围 | 重启 | P2 |
| `contact_shadows` | `0` | 0–100（%） | 屏幕空间接触阴影 | 重启 | P1 |
| `pcss` | `0` | 0–200 | 软阴影（PCSS） | 重启 | P2 |
| `color_preset` | `default` | `default`/`vivid`/`clarity`/`custom` | 调色预设 | 即时 | P1 |
| `color_brightness` | `0` | -30–30 | 亮度（%） | 即时 | P2 |
| `color_contrast` | `100` | 70–150（%） | 对比度 | 即时 | P2 |
| `color_saturation` | `100` | 50–200（%） | 饱和度 | 即时 | P2 |
| `color_gamma` | `1` | 0.8–1.2 | 伽马 | 即时 | P2 |
| `hdr` | `0` | 0/1 | HDR10 输出 | 重启 | P1 |
| `hdr_peak_nits` / `hdr_game_nits` / `hdr_ui_nits` | `1000` / `203` / `203` | — | HDR 亮度 | 即时 | P2 |
| `dlaa` | `0` | 0/1 | NVIDIA DLSS / DLAA（RTX） | 重启 | P2 |
| `dlss` | `dlaa` | `dlaa`/`quality`/`balanced`/`performance`/`ultra_performance` | DLSS 模式 | 即时/重启（版本相关） | P2 |
| `dlss_preset` | `default` | `default`/`k`/`j`/a–m | DLSS 模型 | 即时 | P2 |
| `fxaa` | `1` | 0/1 | 游戏自带 FXAA | 即时 | P2 |
| `perf_overlay` | `off` | `off`/`fps`/`full` | 性能覆盖层（F10） | 即时 | P2 |
| `assume_focus` | `1` | 0/1 | 失焦时是否继续运行 | 焦点切换时 | P2 |
| `gpu_index` / `gpu_name` | `0` / 空 | — | 选择 GPU | 重启 | P2 |

## 4. `[input]` 输入与鼠标

| 键 | 默认 | 范围/取值 | 说明 | 生效 | 级别 |
|---|---|---|---|---|---|
| `motion` | `1` | 0/1 | 体感 | 即时 | P0 |
| `rumble` | `1` | 0/1 | 震动 | 即时 | P0 |
| `rumble_strength` | `130` | 0–300（%） | 震动强度 | 即时 | P1 |
| `rumble_curve` | `0.6` | 0.2–1.5 | 震动曲线 | 即时 | P2 |
| `rumble_triggers` | `0` | 0/1 | Xbox 扳机震动 | 即时 | P2 |
| `pad_layout` | `auto` | `auto`/`nintendo`/`xbox` | 哪个面键是 Switch A | 即时 | P0 |
| `prompts` | `nintendo` | `nintendo`/`xbox`/`pc` | 按钮提示风格；**需重启**；非 16:9 时回退游戏原生 | 重启 | P0 |
| `stick_deadzone` | `8` | 0–50（%） | 摇杆死区 | 即时 | P0 |
| `lstick_deadzone` / `rstick_deadzone` | 同 `stick_deadzone` | 0–50 | 单摇杆死区 | 即时 | P1 |
| `stick_sens` | `1` | 0.1–3 | 右摇杆相机速度 | 重启 | P1 |
| `mouse_mode` | `direct` | `direct`/`stick` | 鼠标相机模式；1.1.0 为摇杆模拟 | 即时 | P0 |
| `menu_cursor` | `1` | 0/1 | 鼠标操作游戏原生菜单；**仅 1.4.3** | 即时 | P0 |
| `mouse_sens` | `1` | 0–10 | 鼠标相机灵敏度（1 ≈ 0.08°/计数）；0 关闭鼠标相机 | 即时 | P0 |
| `mouse_aim_scale` | `1` | 0.1–3 | 拉弓时鼠标灵敏度倍率 | 即时 | P1 |
| `walk_key` / `walk_scale` | `lshift` / `0.51` | 键名 / 0.2–0.9 | 键盘走路（按住减速） | 即时 | P2 |
| `bind_<A\|B\|X\|Y\|L\|R\|ZL\|ZR\|PLUS\|MINUS\|LEFT\|UP\|RIGHT\|DOWN\|LCLICK\|RCLICK>` | 见键表 | `pad:<name>, key:<name>, ...` 或 `none` | 改键；F1 菜单也会写这些行 | 即时 | P0（只读/由 F1 管理，启动器可展示） |

## 5. `[audio]` 声音

| 键 | 默认 | 范围/取值 | 说明 | 生效 | 级别 |
|---|---|---|---|---|---|
| `audio` | `default` | 设备名或 `none` | 音频设备 | 重启 | P1 |
| `audio_prefill_ms` | `20` | 0–500 | 输出预缓冲 | 重启 | P2 |
| `volume` | `100` | 0–100（%） | 音量（叠加游戏内音量） | 即时 | P0 |
| `audio_channels` | `stereo` | `stereo`/`5.1`/`auto` | 声道 | 重启 | P1 |

## 6. `[language]` 语言

| 键 | 默认 | 说明 | 生效 | 级别 |
|---|---|---|---|---|
| `locale` / `lang` | `en-US` | 游戏语言（Windows locale 或 Switch 代码） | 重启 | P1 |
| `operation_mode` | `docked` | 掌机/底座模式 | 重启 | P2 |
| `menu_lang` | 系统语言 | 设置菜单与覆盖层语言（en/ru/pt-BR/zh-Hans） | 即时 | P2 |

## 7. `[performance]` 与 `[diagnostics]`（P2，默认不暴露）

这些键面向测试与排障，`totk.ini.example` 明确说明“仅调试用”。启动器只在“高级”页只读展示，或完全不展示。**特别警告**：`free_cores` 设为 1 会让游戏启动即崩（已知问题），永远不要写入 1。

## 8. 跨字段校验规则（`doctor` 必须覆盖）

| 规则 | 级别 | 建议 |
|---|---|---|
| `fps_limit > 60` 且 `realtime = 0` | 错误 | 改为 `realtime = 1` 或把帧率降到 ≤60 |
| `free_cores = 1` | 错误 | 改回 0 |
| `mouse_sens = 0` 但期望鼠标相机 | 警告 | 提高灵敏度或说明 0 会关闭鼠标相机 |
| `prompts ∈ {xbox, pc}` 且 `output_res` 非 16:9 | 警告 | 提示提示图样式会回退游戏原生 |
| `pad_layout` 与 `prompts` 组合与本机手柄不符 | 提示 | 仅提示，不自动改 |
| `window_size` 超出显示器范围 | 警告 | 提示可能无法显示 |
| `upscaler = fsr` 且 `sharpness = 0` | 提示 | 可能偏软 |
| 同一键出现多次 | 警告 | 只有最后一个生效，建议清理 |

## 9. 预设（M2 定义，此处为约束）

| 预设 | 目标 | 必须包含 | 禁止包含 |
|---|---|---|---|
| `savage-wind` | 键鼠优先、Savage Wind 风格 | `prompts=pc`、`mouse_mode=direct`、`menu_cursor=1`（1.4.3）、`fps_limit=60`、`realtime=1`、`sharpness=80` | `free_cores=1`、`mouse_sens=0` |
| `controller` | 手柄优先 | `prompts=nintendo`、`pad_layout=auto`、`motion=1`、`rumble=1` | 同上 |
| `performance` | 低配/流畅 | `fps_limit=60`、`aniso=game`、`shadow_scale=1`、`render_scale=game`、`replay_async=1` | 同上 |
| `quality` | 画质优先 | `render_scale=100`、`aniso=16`、`shadow_scale=2`、`pcss=50`、`contact_shadows=50` | 同上 |

预设只修改注册表中存在且已声明的键；应用前必须 `--dry-run` 预览。
