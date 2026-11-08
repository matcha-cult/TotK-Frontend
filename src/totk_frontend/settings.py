"""设置注册表：``totk.ini`` 中玩家可感知的键。

单一事实源是 ``docs/settings.md``（公开文档）。本模块逐项登记该文档键表中的：

- 所属节、值类型、默认值；
- 取值范围（``range_doc`` 与文档原文一致，供界面提示；结构化范围用于校验）；
- 中文标签与说明；
- 生效时机（``Effect``）与暴露级别（``Priority``）；
- 版本限制（如 ``fov``、``menu_cursor`` 仅 1.4.3）与可写性。

配套测试 ``tests/test_settings.py`` 会解析 ``docs/settings.md`` 与本注册表逐行核对，
因此修改文档键表时必须同步修改本文件。

未登记在注册表中的键（上游新增或玩家自定义）一律视为未知键：读取/写入时保留，但不展示为可编辑。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "BIND_KEYS",
    "BIND_NAMES",
    "ValueType",
    "Effect",
    "Priority",
    "EFFECT_LABELS",
    "SECTION_ORDER",
    "SECTION_LABELS",
    "Setting",
    "SETTINGS",
    "all_settings",
    "get_setting",
    "settings_in_section",
    "is_registered",
    "is_pattern_key",
]


class ValueType(Enum):
    """值的类型，决定校验方式。"""

    BOOL = "bool"  # 文档写作 0/1
    INTEGER = "integer"
    NUMBER = "number"
    ENUM = "enum"
    RESOLUTION = "resolution"  # WIDTHxHEIGHT
    TEXT = "text"
    KEYNAME = "keyname"  # 键名（如 lshift）
    BINDING = "binding"  # bind_* 的值：pad:<name>, key:<name> ... 或 none


class Effect(Enum):
    """生效时机。"""

    IMMEDIATE = "immediate"  # 即时
    RESTART = "restart"  # 重启
    MOVIE_START = "movie_start"  # 影片开始时
    FOCUS_CHANGE = "focus_change"  # 焦点切换时
    VERSION_DEPENDENT = "version_dependent"  # 即时/重启（版本相关）


EFFECT_LABELS = {
    Effect.IMMEDIATE: "立即生效",
    Effect.RESTART: "需重启",
    Effect.MOVIE_START: "影片开始时生效",
    Effect.FOCUS_CHANGE: "焦点切换时生效",
    Effect.VERSION_DEPENDENT: "立即生效/需重启（版本相关）",
}


class Priority(Enum):
    """暴露优先级（见 docs/settings.md 第 1 节）。"""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


SECTION_ORDER: tuple[str, ...] = (
    "frame rate",
    "display",
    "input",
    "audio",
    "language",
    "performance",
)

SECTION_LABELS = {
    "frame rate": "帧率",
    "display": "画面",
    "input": "输入",
    "audio": "声音",
    "language": "语言",
    "performance": "性能/诊断",
}

#: ``bind_*`` 的合法按键名（小写）。
#: 来源：docs/settings.md 第 4 节列出的手柄按钮，加上 totk.ini.example 中的摇杆方向键与 SHAKE。
#: 注意 ``[performance]`` 的 ``bind_skip`` 是优化开关，不是按键绑定；未知键一律保留但不校验。
BIND_BUTTON_NAMES: tuple[str, ...] = (
    "a", "b", "x", "y", "l", "r", "zl", "zr", "plus", "minus",
    "left", "up", "right", "down", "lclick", "rclick",
)
BIND_DIRECTION_NAMES: tuple[str, ...] = tuple(
    f"{stick}_{direction}"
    for stick in ("lstick", "rstick")
    for direction in ("left", "up", "right", "down")
)
BIND_NAMES: tuple[str, ...] = BIND_BUTTON_NAMES + BIND_DIRECTION_NAMES + ("shake",)
BIND_KEYS: tuple[str, ...] = tuple(f"bind_{name}" for name in BIND_NAMES)


@dataclass(frozen=True)
class Setting:
    """一个设置项的完整元数据。"""

    key: str
    section: str
    value_type: ValueType
    default: str | None
    label: str
    description: str
    effect: Effect
    priority: Priority
    range_doc: str = ""
    min_value: float | None = None
    max_value: float | None = None
    width_range: tuple[int, int] | None = None
    height_range: tuple[int, int] | None = None
    choices: tuple[str, ...] = ()
    extra_choices: tuple[str, ...] = ()
    allow_empty: bool = False
    writable: bool = True
    versions: tuple[str, ...] = ()
    is_pattern: bool = False
    doc_key: str = ""

    @property
    def label_with_key(self) -> str:
        return f"{self.label}（{self.key}）"

    @property
    def effect_label(self) -> str:
        return EFFECT_LABELS[self.effect]

    def supports_version(self, version: str | None) -> bool:
        """未声明版本限制的键对所有版本可用。"""
        if not self.versions or version is None:
            return True
        return version in self.versions


# ---------------------------------------------------------------------- 工厂


def _flag(
    section: str,
    key: str,
    default: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str = "0/1",
    versions: tuple[str, ...] = (),
    writable: bool = True,
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.BOOL,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        choices=("0", "1"),
        min_value=0,
        max_value=1,
        versions=versions,
        writable=writable,
    )


def _integer(
    section: str,
    key: str,
    default: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str,
    min_value: float | None = None,
    max_value: float | None = None,
    extra_choices: tuple[str, ...] = (),
    versions: tuple[str, ...] = (),
    writable: bool = True,
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.INTEGER,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        min_value=min_value,
        max_value=max_value,
        extra_choices=extra_choices,
        versions=versions,
        writable=writable,
    )


def _number(
    section: str,
    key: str,
    default: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str,
    min_value: float | None = None,
    max_value: float | None = None,
    extra_choices: tuple[str, ...] = (),
    versions: tuple[str, ...] = (),
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.NUMBER,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        min_value=min_value,
        max_value=max_value,
        extra_choices=extra_choices,
        versions=versions,
    )


def _enum(
    section: str,
    key: str,
    default: str | None,
    choices: tuple[str, ...],
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str,
    versions: tuple[str, ...] = (),
    allow_empty: bool = False,
    writable: bool = True,
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.ENUM,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        choices=choices,
        versions=versions,
        allow_empty=allow_empty,
        writable=writable,
    )


def _text(
    section: str,
    key: str,
    default: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str = "",
    allow_empty: bool = False,
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.TEXT,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        allow_empty=allow_empty,
    )


def _keyname(
    section: str,
    key: str,
    default: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str = "键名",
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.KEYNAME,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
    )


def _resolution(
    section: str,
    key: str,
    default: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str,
    width_range: tuple[int, int],
    height_range: tuple[int, int],
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.RESOLUTION,
        default=default,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        width_range=width_range,
        height_range=height_range,
    )


def _binding_pattern(
    section: str,
    key: str,
    label: str,
    description: str,
    effect: Effect,
    priority: Priority,
    *,
    range_doc: str,
    doc_key: str,
) -> Setting:
    return Setting(
        key=key,
        section=section,
        value_type=ValueType.BINDING,
        default=None,
        label=label,
        description=description,
        effect=effect,
        priority=priority,
        range_doc=range_doc,
        writable=False,
        is_pattern=True,
        doc_key=doc_key,
    )


# ---------------------------------------------------------------------- 注册表

_FRAME_RATE = "frame rate"
_DISPLAY = "display"
_INPUT = "input"
_AUDIO = "audio"
_LANGUAGE = "language"
_PERFORMANCE = "performance"

_IMMEDIATE = Effect.IMMEDIATE
_RESTART = Effect.RESTART
_P0 = Priority.P0
_P1 = Priority.P1
_P2 = Priority.P2

SETTINGS: tuple[Setting, ...] = (
    # ------------------------------------------------------------ [frame rate]
    _integer(
        _FRAME_RATE, "fps_limit", "60", "帧率上限",
        "帧率上限；高于 60 属实验性", _IMMEDIATE, _P0,
        range_doc="30/40/45/60/90/120/144、30–240 的整数、`display`",
        min_value=30, max_value=240, extra_choices=("display",),
    ),
    _flag(
        _FRAME_RATE, "realtime", "1", "游戏速度跟随真实时钟",
        "游戏速度跟随真实时钟；`fps_limit>60` 时必须为 1", _IMMEDIATE, _P0,
    ),
    _flag(
        _FRAME_RATE, "frame_queue", "0", "帧队列",
        "帧队列，减少掉帧、增加最多一帧延迟", _IMMEDIATE, _P1,
    ),
    _flag(
        _FRAME_RATE, "highfps_fix", "1", "高帧率物理修复",
        "高帧率下物理弹跳修复", _IMMEDIATE, _P1,
    ),
    # -------------------------------------------------------------- [display]
    _enum(
        _DISPLAY, "device_profile", "auto", ("auto", "desktop", "deck"),
        "设备配置", "Steam Deck 上改默认值", _RESTART, _P2,
        range_doc="`auto`/`desktop`/`deck`",
    ),
    _enum(
        _DISPLAY, "vk_present", "mailbox", ("mailbox", "fifo", "immediate"),
        "呈现模式", "呈现模式；`immediate` 会撕裂", _RESTART, _P1,
        range_doc="`mailbox`/`fifo`/`immediate`",
    ),
    _resolution(
        _DISPLAY, "window_size", "1920x1080", "窗口尺寸",
        "窗口客户区像素；F11 切换全屏并写回", _IMMEDIATE, _P0,
        range_doc="640x360–7680x4320", width_range=(640, 7680), height_range=(360, 4320),
    ),
    _flag(
        _DISPLAY, "fullscreen", "0", "无边框全屏", "无边框全屏", _IMMEDIATE, _P0,
    ),
    _resolution(
        _DISPLAY, "output_res", "1920x1080", "绘制分辨率",
        "游戏绘制分辨率；非 16:9 需安装器预先准备 UI 布局", _RESTART, _P0,
        range_doc="1280x720–7680x4320", width_range=(1280, 7680), height_range=(720, 4320),
    ),
    _integer(
        _DISPLAY, "render_scale", "game", "3D 渲染缩放",
        "3D 场景分辨率；>100 为超采样", _RESTART, _P1,
        range_doc="`game` 或 25–400（%）", min_value=25, max_value=400,
        extra_choices=("game",),
    ),
    _enum(
        _DISPLAY, "upscaler", "fsr", ("fsr", "bilinear"),
        "缩放方式", "窗口大于输出分辨率时的缩放方式", _IMMEDIATE, _P0,
        range_doc="`fsr`/`bilinear`",
    ),
    _integer(
        _DISPLAY, "sharpness", "80", "FSR 锐化", "FSR 锐化", _IMMEDIATE, _P1,
        range_doc="0–100", min_value=0, max_value=100,
    ),
    _enum(
        _DISPLAY, "aspect", "fit", ("fit", "stretch"),
        "画面形状适配", "窗口形状与输出不一致时的处理", _IMMEDIATE, _P1,
        range_doc="`fit`/`stretch`",
    ),
    _enum(
        _DISPLAY, "movie_aspect", "keep", ("keep", "stretch"),
        "影片形状", "预渲染影片的形状", Effect.MOVIE_START, _P2,
        range_doc="`keep`/`stretch`",
    ),
    _integer(
        _DISPLAY, "fov", "100", "视野（FOV）",
        "视野；仅 1.4.3", _IMMEDIATE, _P1,
        range_doc="70–140（%）", min_value=70, max_value=140,
        versions=("1.4.3",),
    ),
    _enum(
        _DISPLAY, "aniso", "game", ("game", "2", "4", "8", "16"),
        "各向异性过滤", "各向异性过滤", _RESTART, _P1,
        range_doc="`game`/2/4/8/16",
    ),
    _enum(
        _DISPLAY, "shadow_res", "game", ("game", "256", "512", "768", "1024", "1536", "2048"),
        "阴影贴图尺寸", "太阳阴影贴图尺寸", _RESTART, _P1,
        range_doc="`game`/256/512/768/1024/1536/2048",
    ),
    _integer(
        _DISPLAY, "shadow_scale", "1", "阴影贴图放大倍数",
        "阴影贴图放大倍数", _RESTART, _P1,
        range_doc="1–4", min_value=1, max_value=4,
    ),
    _integer(
        _DISPLAY, "shadow_range", "100", "阴影级联范围",
        "阴影级联范围", _RESTART, _P2,
        range_doc="50–400（%）", min_value=50, max_value=400,
    ),
    _integer(
        _DISPLAY, "contact_shadows", "0", "屏幕空间接触阴影",
        "屏幕空间接触阴影", _RESTART, _P1,
        range_doc="0–100（%）", min_value=0, max_value=100,
    ),
    _integer(
        _DISPLAY, "pcss", "0", "软阴影（PCSS）",
        "软阴影（PCSS）", _RESTART, _P2,
        range_doc="0–200", min_value=0, max_value=200,
    ),
    _enum(
        _DISPLAY, "color_preset", "default", ("default", "vivid", "clarity", "custom"),
        "调色预设", "调色预设", _IMMEDIATE, _P1,
        range_doc="`default`/`vivid`/`clarity`/`custom`",
    ),
    _integer(
        _DISPLAY, "color_brightness", "0", "亮度",
        "亮度（%）", _IMMEDIATE, _P2,
        range_doc="-30–30", min_value=-30, max_value=30,
    ),
    _integer(
        _DISPLAY, "color_contrast", "100", "对比度",
        "对比度", _IMMEDIATE, _P2,
        range_doc="70–150（%）", min_value=70, max_value=150,
    ),
    _integer(
        _DISPLAY, "color_saturation", "100", "饱和度",
        "饱和度", _IMMEDIATE, _P2,
        range_doc="50–200（%）", min_value=50, max_value=200,
    ),
    _number(
        _DISPLAY, "color_gamma", "1", "伽马", "伽马", _IMMEDIATE, _P2,
        range_doc="0.8–1.2", min_value=0.8, max_value=1.2,
    ),
    _flag(
        _DISPLAY, "hdr", "0", "HDR10 输出", "HDR10 输出", _RESTART, _P1,
    ),
    _integer(
        _DISPLAY, "hdr_peak_nits", "1000", "HDR 峰值亮度",
        "HDR 亮度", _IMMEDIATE, _P2, range_doc="—",
    ),
    _integer(
        _DISPLAY, "hdr_game_nits", "203", "HDR 画面白点",
        "HDR 亮度", _IMMEDIATE, _P2, range_doc="—",
    ),
    _integer(
        _DISPLAY, "hdr_ui_nits", "203", "HDR 界面亮度",
        "HDR 亮度", _IMMEDIATE, _P2, range_doc="—",
    ),
    _flag(
        _DISPLAY, "dlaa", "0", "英伟达 DLSS / DLAA",
        "NVIDIA DLSS / DLAA（RTX）", _RESTART, _P2,
    ),
    _enum(
        _DISPLAY, "dlss", "dlaa", ("dlaa", "quality", "balanced", "performance", "ultra_performance"),
        "DLSS 模式", "DLSS 模式", Effect.VERSION_DEPENDENT, _P2,
        range_doc="`dlaa`/`quality`/`balanced`/`performance`/`ultra_performance`",
    ),
    _enum(
        _DISPLAY, "dlss_preset", "default",
        ("default", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m"),
        "DLSS 模型", "DLSS 模型", _IMMEDIATE, _P2,
        range_doc="`default`/`k`/`j`/a–m",
    ),
    _flag(
        _DISPLAY, "fxaa", "1", "游戏自带 FXAA", "游戏自带 FXAA", _IMMEDIATE, _P2,
    ),
    _enum(
        _DISPLAY, "perf_overlay", "off", ("off", "fps", "full"),
        "性能覆盖层", "性能覆盖层（F10）", _IMMEDIATE, _P2,
        range_doc="`off`/`fps`/`full`",
    ),
    _flag(
        _DISPLAY, "assume_focus", "1", "失焦时继续运行",
        "失焦时是否继续运行", Effect.FOCUS_CHANGE, _P2,
    ),
    _integer(
        _DISPLAY, "gpu_index", "0", "GPU 序号", "选择 GPU", _RESTART, _P2,
        range_doc="—", min_value=0,
    ),
    _text(
        _DISPLAY, "gpu_name", "", "GPU 名称", "选择 GPU", _RESTART, _P2,
        range_doc="—", allow_empty=True,
    ),
    # ---------------------------------------------------------------- [input]
    _flag(_INPUT, "motion", "1", "体感", "体感", _IMMEDIATE, _P0),
    _flag(_INPUT, "rumble", "1", "震动", "震动", _IMMEDIATE, _P0),
    _integer(
        _INPUT, "rumble_strength", "130", "震动强度", "震动强度", _IMMEDIATE, _P1,
        range_doc="0–300（%）", min_value=0, max_value=300,
    ),
    _number(
        _INPUT, "rumble_curve", "0.6", "震动曲线", "震动曲线", _IMMEDIATE, _P2,
        range_doc="0.2–1.5", min_value=0.2, max_value=1.5,
    ),
    _flag(_INPUT, "rumble_triggers", "0", "Xbox 扳机震动", "Xbox 扳机震动", _IMMEDIATE, _P2),
    _enum(
        _INPUT, "pad_layout", "auto", ("auto", "nintendo", "xbox"),
        "面键布局", "哪个面键是 Switch A", _IMMEDIATE, _P0,
        range_doc="`auto`/`nintendo`/`xbox`",
    ),
    _enum(
        _INPUT, "prompts", "nintendo", ("nintendo", "xbox", "pc"),
        "按钮提示风格", "按钮提示风格；需重启；非 16:9 时回退游戏原生", _RESTART, _P0,
        range_doc="`nintendo`/`xbox`/`pc`",
    ),
    _integer(
        _INPUT, "stick_deadzone", "8", "摇杆死区", "摇杆死区", _IMMEDIATE, _P0,
        range_doc="0–50（%）", min_value=0, max_value=50,
    ),
    _integer(
        _INPUT, "lstick_deadzone", "8", "左摇杆死区", "单摇杆死区", _IMMEDIATE, _P1,
        range_doc="0–50", min_value=0, max_value=50,
    ),
    _integer(
        _INPUT, "rstick_deadzone", "8", "右摇杆死区", "单摇杆死区", _IMMEDIATE, _P1,
        range_doc="0–50", min_value=0, max_value=50,
    ),
    _number(
        _INPUT, "stick_sens", "1", "右摇杆相机速度", "右摇杆相机速度", _RESTART, _P1,
        range_doc="0.1–3", min_value=0.1, max_value=3,
    ),
    _enum(
        _INPUT, "mouse_mode", "direct", ("direct", "stick"),
        "鼠标相机模式", "鼠标相机模式；1.1.0 为摇杆模拟", _IMMEDIATE, _P0,
        range_doc="`direct`/`stick`",
    ),
    _flag(
        _INPUT, "menu_cursor", "1", "鼠标操作游戏菜单",
        "鼠标操作游戏原生菜单；仅 1.4.3", _IMMEDIATE, _P0,
        versions=("1.4.3",),
    ),
    _number(
        _INPUT, "mouse_sens", "1", "鼠标相机灵敏度",
        "鼠标相机灵敏度（1 ≈ 0.08°/计数）；0 关闭鼠标相机", _IMMEDIATE, _P0,
        range_doc="0–10", min_value=0, max_value=10,
    ),
    _number(
        _INPUT, "mouse_aim_scale", "1", "拉弓时鼠标灵敏度",
        "拉弓时鼠标灵敏度倍率", _IMMEDIATE, _P1,
        range_doc="0.1–3", min_value=0.1, max_value=3,
    ),
    _keyname(
        _INPUT, "walk_key", "lshift", "走路按键",
        "键盘走路（按住减速）", _IMMEDIATE, _P2,
        range_doc="键名",
    ),
    _number(
        _INPUT, "walk_scale", "0.51", "走路减速倍率",
        "键盘走路（按住减速）", _IMMEDIATE, _P2,
        range_doc="0.2–0.9", min_value=0.2, max_value=0.9,
    ),
    _binding_pattern(
        _INPUT, "bind_*", "按键绑定",
        "改键；F1 菜单也会写这些行", _IMMEDIATE, _P0,
        range_doc="`pad:<name>, key:<name>, ...` 或 `none`",
        doc_key="bind_<A|B|X|Y|L|R|ZL|ZR|PLUS|MINUS|LEFT|UP|RIGHT|DOWN|LCLICK|RCLICK>",
    ),
    # ---------------------------------------------------------------- [audio]
    _text(
        _AUDIO, "audio", "default", "音频设备", "音频设备", _RESTART, _P1,
        range_doc="设备名或 `none`", allow_empty=True,
    ),
    _integer(
        _AUDIO, "audio_prefill_ms", "20", "音频预缓冲",
        "输出预缓冲", _RESTART, _P2,
        range_doc="0–500", min_value=0, max_value=500,
    ),
    _integer(
        _AUDIO, "volume", "100", "音量",
        "音量（叠加游戏内音量）", _IMMEDIATE, _P0,
        range_doc="0–100（%）", min_value=0, max_value=100,
    ),
    _enum(
        _AUDIO, "audio_channels", "stereo", ("stereo", "5.1", "auto"),
        "声道", "声道", _RESTART, _P1,
        range_doc="`stereo`/`5.1`/`auto`",
    ),
    # ------------------------------------------------------------- [language]
    _text(
        _LANGUAGE, "locale", "en-US", "游戏语言（地区）",
        "游戏语言（Windows locale 或 Switch 代码）", _RESTART, _P1,
    ),
    _text(
        _LANGUAGE, "lang", "en-US", "游戏语言（Switch 代码）",
        "游戏语言（Windows locale 或 Switch 代码）", _RESTART, _P1,
    ),
    _enum(
        _LANGUAGE, "operation_mode", "docked", ("docked", "handheld"),
        "掌机/底座模式", "掌机/底座模式", _RESTART, _P2,
        range_doc="",
    ),
    _enum(
        _LANGUAGE, "menu_lang", None, ("en", "ru", "pt-BR", "zh-Hans"),
        "设置菜单语言", "设置菜单与覆盖层语言（en/ru/pt-BR/zh-Hans）", _IMMEDIATE, _P2,
        range_doc="", allow_empty=True,
    ),
    # ---------------------------------------------------------- [performance]
    _flag(
        _PERFORMANCE, "free_cores", "0", "解除虚拟核心上限（排障）",
        "仅排障用；设为 1 会让游戏启动即崩（已知问题），永远不要写入 1", _RESTART, _P2,
    ),
    _flag(
        _PERFORMANCE, "replay_async", "0", "异步重放 NVN 提交（排障）",
        "在独立线程重放 NVN 提交，最多落后一帧；仅排障/性能测试用，默认关闭", _RESTART, _P2,
    ),
)

_BY_KEY: dict[str, Setting] = {setting.key.lower(): setting for setting in SETTINGS if not setting.is_pattern}
_PATTERNS: tuple[Setting, ...] = tuple(setting for setting in SETTINGS if setting.is_pattern)


_PATTERN_REGEX: dict[str, re.Pattern[str]] = {
    "bind_*": re.compile(r"^(?:" + "|".join(re.escape(key) for key in BIND_KEYS) + r")$")
}


def all_settings() -> tuple[Setting, ...]:
    """按文档顺序返回全部设置项。"""
    return SETTINGS


def get_setting(key: str, section: str | None = None) -> Setting | None:
    """按（大小写不敏感的）键名查找设置项；可选按节过滤。"""
    if not isinstance(key, str):
        raise TypeError("key 必须是字符串")
    normalized = key.strip().lower()
    setting = _BY_KEY.get(normalized)
    if setting is None:
        for pattern_setting in _PATTERNS:
            if _PATTERN_REGEX[pattern_setting.key].match(normalized):
                setting = pattern_setting
                break
    if setting is None:
        return None
    if section is not None and setting.section != section.strip().lower():
        return None
    return setting


def settings_in_section(section: str) -> tuple[Setting, ...]:
    """返回某节的全部设置项（文档顺序）。"""
    normalized = section.strip().lower()
    return tuple(setting for setting in SETTINGS if setting.section == normalized)


def is_registered(key: str, section: str | None = None) -> bool:
    return get_setting(key, section) is not None


def is_pattern_key(key: str) -> bool:
    """该键是否由模式项（如 ``bind_*``）覆盖。"""
    setting = get_setting(key)
    return setting is not None and setting.is_pattern
