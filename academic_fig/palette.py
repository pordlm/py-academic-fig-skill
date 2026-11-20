# -*- coding: utf-8 -*-
"""palette.py —— 论文插图配色契约（FROZEN / 冻结文件（改动需评审），成员只读）。

设计目标：**简单、高级、像框架图**，不是数据看板，也不是海报。
一句话：「白纸 + 墨线 + 两个低饱和强调色 + 一层暖白纸感」。

三条铁律（写进 SKILL.md，prompts 里必须逐字对齐这里的取值）：
1. 只用本文件里的颜色。不要 matplotlib 默认蓝橙红、不要 tab10、不要 jet。
2. 信息不能只靠颜色承载：颜色 + marker 形状 + 虚实 + 明度，四者至少两重冗余。
3. 大面积（>15% 画布）只用白/纸白/浅灰；强调色只出现在小面积与线条上。

色值口径：`#RRGGBB`，均已按 sRGB 手调，灰度打印后仍可区分（明度差 ≥ 12%）。
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------- 墨与纸
INK = "#1A1A1A"          # 主墨：坐标轴、主曲线、关键点、强调框外框
INK_SOFT = "#33383D"     # 次墨：正文文字、次要曲线
GREY = "#6E6E6E"         # 三级：参考结构、辅助线、非显著组
GREY_LIGHT = "#C9CCD1"   # 四级：散点背景、弱网格、不可行区域
PAPER = "#FFFFFF"        # 底色：纯白（默认 figure/axes facecolor）
WASH = "#F6F4F0"         # 纸白：框图默认填充、强调区极浅底
WASH_COOL = "#F2F4F6"    # 冷纸白：与 WASH 交替区分相邻模块

# ---------------------------------------------------------------- 强调色（低饱和、成对可用）
BLUE = "#2F5D8A"         # 主张量 / 推荐解 / 达标 / 正向
CLAY = "#A4442F"         # 违例 / 未达标 / 峰值 / 强调一
MOSS = "#3F6B52"         # 保证量 / 已覆盖 / 稳健分支
OCHRE = "#B08443"        # 次级强调 / 警告 / 对比基线
SLATE = "#5B6B7C"        # 中性强调（不想用蓝时）
PLUM = "#6E5068"         # 第五类（少量使用）

# 浅色底（框图填充、置信带、可行域）——都为 8%~12% 等效明度
BLUE_T = "#E9EFF4"
CLAY_T = "#F7EBE8"
MOSS_T = "#EAF0EC"
OCHRE_T = "#F7F1E5"
SLATE_T = "#EEF0F3"
PLUM_T = "#F2EDF1"

# ---------------------------------------------------------------- 语义角色（图里永远这样用）
GOOD = BLUE              # 满足约束 / 命中 / 提升
BAD = CLAY               # 违反约束 / 未命中 / 退化
BASE = GREY              # 基线 / 对照组 / 其余
TARGET = CLAY            # 阈值线 / 判定线（自主设定，不是官方指标！图注须写明）
HIGHLIGHT = OCHRE        # 单点强调（某一行/某一列/某个样本）
MUTED = GREY_LIGHT       # 背景样本 / 非显著

# ---------------------------------------------------------------- 分类序列（最多 6 类推荐）
CATEGORICAL = [BLUE, CLAY, MOSS, OCHRE, SLATE, PLUM]
CATEGORICAL_TINTS = [BLUE_T, CLAY_T, MOSS_T, OCHRE_T, SLATE_T, PLUM_T]
# 超过 6 类时：先想能不能合并/直接标注，再用扩展序列
CATEGORICAL_EXTENDED = CATEGORICAL + [
    "#7C8B99", "#8A7A6A", "#9AA79B", "#B9A88F",
    "#4A6B7C", "#8C5F55", "#5F7A6B", "#A08A5E",
]

# ---------------------------------------------------------------- 色图
# 连续量（热力图 / 场量 / 响应面）：明度单调、色盲友好、打印不失真
_CMAP_SEQ_STOPS = ["#F7F5F1", "#DCE6E4", "#A9C4C0", "#6E9AA0", "#3F7189", "#2F5D8A", "#16304A"]
# 有符号量（log2FC / z-score / 偏差）：以纸白为零点，蓝负红正
_CMAP_DIV_STOPS = [BLUE, "#FFFFFF", CLAY]
# 离散计数（覆盖次数 / 命中次数）：同色系深浅 + 顶端警示
_CMAP_DISC_STOPS = ["#F6F7F8", "#DCE4EA", "#B3C6D3", "#7F9DB3", "#4A7391", "#2F5D8A", "#1B3A56"]

CMAP_NOTE = "用 cmap_seq()/cmap_div()/cmap_disc()，不要用 matplotlib 自带色图。"


def _make(stops):
    """惰性构造 LinearSegmentedColormap（不 import matplotlib 也能 import 本模块）。"""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list("paper_" + str(abs(hash(tuple(stops))) % 10**8), stops)


def cmap_seq():
    """连续量：纸白 → 青灰 → 深蓝（明度单调）。"""
    return _make(_CMAP_SEQ_STOPS)


def cmap_seq_r():
    """连续量的反向（表达「越小越好」时用）。"""
    return cmap_seq().reversed()


def cmap_div():
    """有符号量：蓝（负）— 白（0）— 砖红（正）。"""
    return _make(_CMAP_DIV_STOPS)


def cmap_disc(n_bins: int | None = None):
    """离散计数：同色系阶梯；n_bins 给定时在已有停靠色间等距取样。"""
    stops = _CMAP_DISC_STOPS
    if n_bins is None:
        return _make(stops)
    pick = np.linspace(0, len(stops) - 1, max(2, n_bins))
    sub = [stops[int(round(i))] for i in pick]
    return _make(sub)


# ---------------------------------------------------------------- 工具
def categorical(n: int | None = None) -> list[str]:
    """取 n 个分类色；n 超过 6 才走扩展序列，超过 16 直接报错（提示改图）。"""
    if n is None:
        return list(CATEGORICAL)
    if n > len(CATEGORICAL_EXTENDED):
        raise ValueError(f"分类数 {n} 过多：请合并类目或改用直接标注，不要堆 16+ 种颜色")
    return list(CATEGORICAL_EXTENDED[:n])


def tint(color: str, alpha: float = 0.10) -> tuple[float, float, float]:
    """把强调色压成极浅填充（与白底混合），用于框图/置信带。"""
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (r + (1 - r) * (1 - alpha), g + (1 - g) * (1 - alpha), b + (1 - b) * (1 - alpha))


#: 命名方案：默认 paper-calm（简单高级）；journal-cns 仅供“套用某期刊既有风格”时切换
PALETTES = {
    "paper-calm": {
        "ink": INK, "grey": GREY, "paper": PAPER, "wash": WASH,
        "accents": [BLUE, CLAY, MOSS, OCHRE, SLATE, PLUM],
        "categorical": CATEGORICAL,
        "seq": _CMAP_SEQ_STOPS, "div": _CMAP_DIV_STOPS,
    },
    # journal-cns 迁移自 academic-figure-skill 的 Nature/Cell 基线，只作可选风格。
    # ⚠ 自检不覆盖这个方案：``checks._allowed_colors()`` 只收 paper-calm 的基色、``_T``
    # 浅色、``tint()`` 各档与色阶停靠色。用 ``apply_theme("journal-cns")`` 出的图跑
    # ``cli check`` 会把这里的 #2166AC / #B2182B 等报成「不在 palette 内」（color warning）。
    # 这不是 bug：该方案本就是「迁就某期刊既有配色」，与 paper-calm 的色值体系无关。
    "journal-cns": {
        "ink": "#222222", "grey": "#999999", "paper": "#FFFFFF", "wash": "#F7F7F7",
        "accents": ["#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666"],
        "categorical": ["#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666"],
        "seq": ["#F7FBFF", "#6BAED6", "#08306B"],
        "div": ["#2166AC", "#F7F7F7", "#B2182B"],
    },
}


def get_palette(name: str = "paper-calm") -> dict:
    try:
        return PALETTES[name]
    except KeyError:
        raise KeyError(f"未知配色方案 {name!r}；可选：{', '.join(PALETTES)}") from None