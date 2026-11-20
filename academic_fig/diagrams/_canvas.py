# -*- coding: utf-8 -*-
"""示意图共享画布：**1 数据单位 = 1 英寸**。

为什么要这样做
--------------
数据图关心「数值」，示意图关心「版面」。示意图的三条硬约束——层间距 ≥0.25in、
模块等高、文字不溢出框——本质都是**长度**问题，用数据坐标（0~1 或 0~12）根本
没法验。所以这里把画布做成一把尺子：

* ``paper_fig(width, height, margins=(0, 0, 1, 1))`` 让坐标轴铺满整幅画布；
* 再把 ``xlim``/``ylim`` 设成画布的英寸尺寸 ``(0, w) × (0, h)``。

于是坐标轴里 1 个单位正好 1 英寸：``gap = 0.30`` 就是 0.30in，``fontsize=9.5`` 的
一行字高就是 ``9.5/72`` 英寸。字号、内边距、间距全部可以用同一把尺子量。

文字处理
--------
不猜行高：**每一行都是一个独立的单行 Text**，行距（pitch）由本模块自己算，
所以 ``Text.get_window_extent()`` 量出来的就是真实占位。排版完成后由
:func:`check_box_overflow` 逐个复核，默认严格模式——溢出直接抛
:class:`TextOverflowError`，绝不带着错版出图。

颜色
----
一律取自 :mod:`academic_fig.palette`，本文件不出现任何十六进制色值。
"""
from __future__ import annotations

import json
import math
import os
import warnings
from pathlib import Path as _FsPath        # 与 matplotlib.path.Path 区分开

from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
from matplotlib.path import Path

from ..layout import footnote as _footnote
from ..layout import paper_fig
from .. import palette as _pal
from ..checks import (
    TextLineCollision,
    TextOverflowError,
    check_box_overflow,
    check_text_hits,
    register_box,
    register_link,
    seg_hits_rect,
)
from ..palette import BLUE, INK, PAPER, WASH
from ..typography import TEXT_SIZES

__all__ = [
    "SINGLE", "DOUBLE", "MIN_GAP", "MODULE_FS", "NOTE_FS", "BRANCH_FS", "TITLE_FS",
    "LINE_PITCH", "BOX_PAD", "SCENE_MARGINS", "CORNER_R", "CORNER_STYLE",
    "SHAFT_PT", "GAP_PAD_PT", "BORDER_BREAK", "gap_width_px",
    "TextOverflowError", "TextLineCollision", "Diagram",
    "Measure", "arrow", "border_gap", "check_box_overflow", "check_text_hits",
    "label", "line", "load_spec", "poly", "register_box", "register_link",
    "resolve_color", "rounded_box", "scene_axes", "square_fig", "seg_hits_rect",
    "stack_text", "text_block_height", "wrap_to_width",
]

SINGLE = 3.35           # 单栏英寸
DOUBLE = 7.0            # 双栏英寸
MIN_GAP = 0.25          # 层间距/横向间距下限（in）——ARCH §3 硬约束
MODULE_FS = 9.5         # 模块名（ARCH §3）
NOTE_FS = 8.5           # 模块说明 / 图注正文
BRANCH_FS = 8.0         # 分支标注 "是" / "否"
TITLE_FS = float(TEXT_SIZES.get("diagram_title", 12.0))   # 整幅标题（不加粗，12pt 封顶）
LINE_PITCH = 1.35       # 行距 = 字号 × 1.35
BOX_PAD = 0.02          # FancyBboxPatch 的 pad（ARCH §3：圆角 0.02）

CORNER_R = 0.055        # 折线拐角半径（in）：≤0.06in，全库统一走这一个值
CORNER_STYLE = "round"  # "round" 圆角 / "miter" 直角：全库统一走这一个开关
BORDER_LW = 0.8         # 层带/容器边框线宽（与 INK 0.8pt 一致）

# --------------------------------------------------------------------------- 穿框白口
# 白口只服务「0.9pt 轴线穿过 0.8pt 边框」这一件事，所以宽度由线宽推出来，不再写死。
# 箭头三角（mutation_scale=8）在 300dpi 下实测全宽 16px，但它永远落在**节点框边**上
# （层带内部），不会落到层带边框上——穿框处只有 3.8px 的轴。因此按「轴宽 + 抗锯齿
# 余量」取：半宽 = (0.9/2 + 0.8)/72 ≈ 0.0174in，总宽 ≈ 0.035in ≈ 10.4px@300dpi。
SHAFT_PT = 0.9          # 连线轴宽（pt）——ARCH §3
GAP_PAD_PT = 0.8        # 轴两侧各让出的余量（pt）
BORDER_BREAK = (SHAFT_PT / 2.0 + GAP_PAD_PT) / 72.0    # 白口半宽（in）


def gap_width_px(dpi: float = 300.0) -> float:
    """白口总宽换算成像素——报告与像素扫描共用这一个口径。"""
    return 2.0 * BORDER_BREAK * float(dpi)


#: 越界/压线两个异常类与两类复核函数都住在 :mod:`academic_fig.checks`
#: （与 :func:`academic_fig.checks.check_dir` 同构，见上面的 import）。


# --------------------------------------------------------------------------- 量字
def _estimate_width(text: str, fs: float) -> float:
    """renderer 不可用时的兜底估算：CJK 按 1.0em，ASCII 按 0.52em。"""
    em = float(fs) / 72.0
    w = 0.0
    for ch in str(text):
        w += em if ord(ch) > 0x2E80 else 0.52 * em
    return w


class Measure:
    """用真实 renderer 量文字宽度（inch）。

    matplotlib 的 ``get_text_width_height_descent`` 对多行串不可靠，所以只
    量单行；多行的行距由 :data:`LINE_PITCH` 自己算，见 :func:`stack_text`。
    """

    def __init__(self, fig):
        self.fig = fig
        self.dpi = float(fig.dpi) or 100.0
        self.renderer = None
        try:
            fig.canvas.draw()
        except Exception:                                    # pragma: no cover
            pass
        self.renderer = getattr(fig.canvas, "renderer", None)
        if self.renderer is None:
            try:
                self.renderer = fig.canvas.get_renderer()
            except Exception:                                # pragma: no cover
                self.renderer = None

    # -- 单行宽度 ----------------------------------------------------------
    def width(self, text: str, fs: float) -> float:
        widest = 0.0
        for ln in str(text).split("\n"):
            got = None
            if self.renderer is not None:
                try:
                    widest_px, _, _ = self.renderer.get_text_width_height_descent(
                        ln, FontProperties(size=float(fs)), False)
                    got = float(widest_px) / self.dpi
                except Exception:                            # pragma: no cover
                    got = None
            widest = max(widest, got if got is not None else _estimate_width(ln, fs))
        return widest

    # -- 行高 --------------------------------------------------------------
    @staticmethod
    def line_height(fs: float) -> float:
        return float(fs) / 72.0 * LINE_PITCH

    def block_height(self, lines, fs: float) -> float:
        n = max(1, len(list(lines)))
        return n * self.line_height(fs)


# --------------------------------------------------------------------------- 折行
def _is_cjk(ch: str) -> bool:
    return ord(ch) > 0x2E80


def wrap_to_width(measure: Measure, text: str, fs: float, max_w: float) -> list[str]:
    """把一行字折进 ``max_w`` 英寸：CJK 逐字断，ASCII 按空白断。

    已经是多行的文本逐行处理；折不开（单字就超宽）时抛 :class:`TextOverflowError`。
    """
    out: list[str] = []
    for para in str(text).split("\n"):
        if not para:
            out.append("")
            continue
        if measure.width(para, fs) <= max_w:
            out.append(para)
            continue
        buf, cur = [], ""
        for ch in para:
            cand = cur + ch
            if measure.width(cand, fs) <= max_w or not cur:
                if not cur and measure.width(ch, fs) > max_w:
                    raise TextOverflowError(
                        f"单个字符「{ch}」在 {fs}pt 下宽于可用宽度 {max_w:.3f}in；"
                        "请缩短文字或把图放宽（width='double'）")
                cur = cand
            else:
                buf.append(cur)
                cur = ch
        if cur:
            buf.append(cur)
        out.extend([b for b in buf if b] or [""])
    return out


# --------------------------------------------------------------------------- 画布
class Diagram:
    """一张示意图的画布：英寸坐标 + 量字器 + 图注。

    典型用法（各渲染器内部就是这样用的）::

        d = Diagram("double")
        ... 量字、算版面，得到画布高度 h ...
        d.size(h)
        ... 画 ...
        d.footnote("来源：…；口径：…")
        return d.ax
    """

    def __init__(self, width: str | float = "double", *, height: float = 3.0):
        if isinstance(width, str):
            self.w = {"single": SINGLE, "double": DOUBLE}[width]
        else:
            self.w = float(width)
        if not self.w > MIN_GAP:
            raise ValueError(f"Diagram(): 画布宽度必须 > {MIN_GAP}in，收到 {self.w}")
        self.fig, self.ax = paper_fig(self.w, height=float(height), margins=(0, 0, 1, 1))
        self.ax.axis("off")
        self.measure = Measure(self.fig)
        self.h = float(height)
        self.size(float(height))

    # -- 画布尺寸 ----------------------------------------------------------
    def size(self, height: float):
        """把画布定高；坐标轴始终铺满画布，保证 1 单位 = 1 英寸。"""
        h = float(height)
        if not h > 0.4:
            raise ValueError(f"Diagram.size(): 高度必须 > 0.4in，收到 {h}")
        self.fig.set_size_inches(self.w, h, forward=True)
        self.ax.set_position([0.0, 0.0, 1.0, 1.0])
        self.ax.set_xlim(0.0, self.w)
        self.ax.set_ylim(0.0, h)
        self.h = h
        return self

    # -- 标题 --------------------------------------------------------------
    def title(self, text: str, *, reserve: float = 0.30, fs: float = TITLE_FS) -> float:
        """画全幅标题，返回它占掉的高度（调用方据此扣掉顶部留白）。"""
        if not text:
            return 0.0
        self.ax.text(self.w / 2.0, self.h - 0.04, str(text), ha="center", va="top",
                     fontsize=fs, color=INK)
        return reserve

    # -- 图注 --------------------------------------------------------------
    def footnote(self, text: str | None, **kw):
        if not text:
            return None
        return _footnote(self.fig, str(text), **kw)


# --------------------------------------------------------------------------- 图元
def rounded_box(ax, x: float, y: float, w: float, h: float, *, fc=PAPER, ec=INK,
                lw: float = 0.8, ls="-", radius: float = 0.055, zorder: float = 2,
                alpha: float = 1.0):
    """圆角矩形。``pad=0.02``（ARCH §3 硬约束），外沿正好落在给定矩形上。

    ``FancyBboxPatch`` 的 ``pad`` 是把框**外扩**，所以这里先内缩 pad 再交给它，
    这样 ``(x, y, w, h)`` 就是最终可见的外沿——排版算出来的间隔才作数。
    """
    p = BOX_PAD
    bw, bh = max(w - 2 * p, 1e-3), max(h - 2 * p, 1e-3)
    r = float(min(radius, bw / 2.0, bh / 2.0))
    patch = FancyBboxPatch((x + p, y + p), bw, bh,
                           boxstyle=f"round,pad={p},rounding_size={r}",
                           facecolor=fc, edgecolor=ec, linewidth=float(lw),
                           linestyle=ls, mutation_aspect=1.0, zorder=zorder,
                           alpha=alpha)
    ax.add_patch(patch)
    return patch


def diamond(ax, cx: float, cy: float, w: float, h: float, *, fc=PAPER, ec=INK,
            lw: float = 0.8, zorder: float = 3):
    """判定菱形。"""
    pts = [(cx, cy + h / 2.0), (cx + w / 2.0, cy), (cx, cy - h / 2.0), (cx - w / 2.0, cy)]
    patch = Polygon(pts, closed=True, facecolor=fc, edgecolor=ec,
                    linewidth=float(lw), joinstyle="miter", zorder=zorder)
    ax.add_patch(patch)
    return patch


def capsule(ax, x: float, y: float, w: float, h: float, *, fc=WASH, ec=INK,
            lw: float = 0.8, zorder: float = 3):
    """开始/终止端点：极圆圆角（胶囊）矩形。"""
    p = BOX_PAD
    bw, bh = max(w - 2 * p, 1e-3), max(h - 2 * p, 1e-3)
    patch = FancyBboxPatch((x + p, y + p), bw, bh,
                           boxstyle=f"round,pad={p},rounding_size={min(bh / 2.0, 0.20)}",
                           facecolor=fc, edgecolor=ec, linewidth=float(lw),
                           mutation_aspect=1.0, zorder=zorder)
    ax.add_patch(patch)
    return patch


def _unit(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _dist(p0, p1):
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def rounded_path(pts, radius: float | None = None) -> Path:
    """把折线的直角拐角换成二次贝塞尔圆角（0.9pt 细线也不会显得生硬）。

    ``radius=None`` 时用 :data:`CORNER_R`；:data:`CORNER_STYLE` 为 ``"miter"``
    或显式传 ``radius=0`` 时退回纯直角折线。**所有连线都走这一个半径**，
    同一张图里不会出现「这段圆角、那段直角」的混排。
    """
    r = CORNER_R if radius is None else float(radius)
    pts = [(float(p[0]), float(p[1])) for p in pts]
    if len(pts) < 3 or r <= 0:
        return Path(pts, [Path.MOVETO] + [Path.LINETO] * (len(pts) - 1))
    verts, codes = [pts[0]], [Path.MOVETO]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = _unit(p0, p1), _unit(p1, p2)
        rr = min(r, 0.45 * _dist(p0, p1), 0.45 * _dist(p1, p2))
        if rr <= 1e-6:
            verts.append(p1)
            codes.append(Path.LINETO)
            continue
        a = (p1[0] - d1[0] * rr, p1[1] - d1[1] * rr)
        b = (p1[0] + d2[0] * rr, p1[1] + d2[1] * rr)
        verts.append(a)
        codes.append(Path.LINETO)
        verts.extend([p1, b])
        codes.extend([Path.CURVE3, Path.CURVE3])
    verts.append(pts[-1])
    codes.append(Path.LINETO)
    return Path(verts, codes)


def arrow(ax, pts, *, color=INK, lw: float = 0.9, ls="-", head: bool = True,
          radius: float | None = None, corner: str | None = None, zorder: float = 6,
          head_scale: float = 8.0, shrink: float = 0.0):
    """细箭头（ARCH §3：0.9pt、``-|>``、``mutation_scale=8``）。

    多段折线自动圆角；``corner="miter"``（或全局 :data:`CORNER_STYLE`）改直角；
    ``head=False`` 时只画线。拐角半径统一由 :data:`CORNER_R` 决定，调用方不必
    逐处传数字——同图混排就是这样避免的。
    """
    pts = [(float(p[0]), float(p[1])) for p in pts]
    if len(pts) < 2:
        raise ValueError("arrow(): 至少需要两个点")
    style = CORNER_STYLE if corner is None else str(corner).lower()
    r = 0.0 if style in ("miter", "sharp", "square", "right") else radius
    if head:
        ap = FancyArrowPatch(path=rounded_path(pts, r), arrowstyle="-|>",
                             mutation_scale=float(head_scale), linewidth=float(lw),
                             color=color, linestyle=ls, shrinkA=shrink,
                             shrinkB=shrink, joinstyle="miter", capstyle="butt",
                             zorder=zorder)
        ax.add_patch(ap)
        return ap
    ln, = ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color,
                  lw=float(lw), ls=ls, solid_capstyle="butt", solid_joinstyle="miter",
                  zorder=zorder)
    return ln


def line(ax, pts, *, color=INK, lw: float = 0.9, ls="-", zorder: float = 5):
    return arrow(ax, pts, color=color, lw=lw, ls=ls, head=False, zorder=zorder)


def poly(ax, pts, *, fc, ec, lw: float = 0.8, ls="-", zorder: float = 2,
         alpha: float = 1.0):
    patch = Polygon([(float(p[0]), float(p[1])) for p in pts], closed=True,
                    facecolor=fc, edgecolor=ec, linewidth=float(lw),
                    linestyle=ls, joinstyle="miter", zorder=zorder, alpha=alpha)
    ax.add_patch(patch)
    return patch


def label(ax, x: float, y: float, text: str, *, fs: float = NOTE_FS, color=INK,
          ha: str = "center", va: str = "center", bbox: bool = False,
          bbox_pad: float = 0.03, zorder: float = 8, rotation: float = 0.0,
          bbox_ec=None, bbox_alpha: float = 0.90):
    """单行标注。``bbox=True`` 时在字下垫一块白底，避免压在线上看不清。

    ``bbox_pad`` 默认 0.03in（≈2.2pt）：白底只把字兜住，不会把线挖出大豁口。
    标注优先「贴线侧、留 ≥2pt 空隙」，白底只是兜底，不是用来遮线的。
    """
    kw = {}
    if bbox:
        kw["bbox"] = dict(facecolor=PAPER, edgecolor=bbox_ec or "none",
                          linewidth=0.5, alpha=bbox_alpha, pad=bbox_pad)
    return ax.text(float(x), float(y), str(text), fontsize=float(fs), color=color,
                   ha=ha, va=va, rotation=rotation, zorder=zorder, **kw)


def stack_text(ax, cx: float, top: float, lines, fs: float, *, color=INK,
               ha: str = "center", zorder: float = 8, gap_after: float = 0.0):
    """把若干**单行**文字自上而下摞起来，返回 (最低 y, 总高)。

    逐行放置而不是给一个多行串，是为了让 ``get_window_extent()`` 量到的就是
    真实占位（matplotlib 的多行 extent 依赖 linespacing，不可靠）。
    """
    lines = [str(s) for s in lines if str(s) != ""]
    lh = fs / 72.0 * LINE_PITCH
    y = float(top)
    lowest = y
    for i, ln in enumerate(lines):
        center = y - lh / 2.0
        ax.text(float(cx), center, ln, fontsize=float(fs), color=color, ha=ha,
                va="center", zorder=zorder)
        lowest = center - lh / 2.0
        y = center - lh / 2.0 - (gap_after if i == len(lines) - 1 else 0.0)
    return y, len(lines) * lh


def text_block_height(lines, fs: float, *, n_gap: int = 0, gap: float = 0.03) -> float:
    n = max(1, len(list(lines)))
    return n * (fs / 72.0 * LINE_PITCH) + n_gap * gap


# --------------------------------------------------------------------------- 规格
def load_spec(obj) -> dict:
    """把「规格」统一成 dict：直接给 dict，或给 JSON 文件路径 / JSON 文本。

    五个示意图入口都过这一层，所以既能在脚本里内联字典，也能从
    ``examples/data/diagrams/*.json`` 读文件，还能把 JSON 字符串贴进来。
    """
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, (str, os.PathLike)):
        text = os.fspath(obj)
        if text.lstrip().startswith("{"):
            data = json.loads(text)
        else:
            p = _FsPath(text)
            if not p.is_file():
                raise FileNotFoundError(f"load_spec(): 规格文件不存在：{p}")
            data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("load_spec(): 规格 JSON 顶层必须是对象（dict）")
        return data
    raise TypeError(
        f"load_spec(): 规格只接受 dict 或 JSON 路径/文本，收到 {type(obj).__name__}")


# --------------------------------------------------------------------------- 场景画布
SCENE_MARGINS = (0.14, 0.17, 0.96, 0.91)   # 左侧留刻度、下侧留标签


def resolve_color(name, default=INK):
    """把规格里的颜色**名字**解析成 palette 里的颜色。

    规格只用名字（``"BLUE_T"`` / ``"CLAY"`` / ``"INK"``…），这样 JSON 里不会出现
    十六进制色值，改色板时全库一起变。
    """
    if name is None or name == "":
        return default
    if not isinstance(name, str):
        return name
    key = name.strip().upper()
    if key in ("NONE", "TRANSPARENT"):
        return "none"
    val = getattr(_pal, key, None)
    if val is None or not isinstance(val, str):
        raise ValueError(
            f"resolve_color(): 颜色名 {name!r} 不在 palette 里；"
            "可用 INK/INK_SOFT/GREY/GREY_LIGHT/PAPER/WASH/WASH_COOL/"
            "BLUE/CLAY/MOSS/OCHRE/SLATE/PLUM 及对应的 _T 浅色")
    return val


def square_fig(width: str | float, xr: float, yr: float, *,
               margins=SCENE_MARGINS):
    """按数据域长宽比定画布高度：``equal`` 下既不压字也不留白。"""
    w = {"single": SINGLE, "double": DOUBLE}.get(width, None) if isinstance(
        width, str) else float(width)
    if w is None:
        raise ValueError(f"square_fig(): width 只能是 'single'/'double'/数值，收到 {width!r}")
    # ``height=1.0`` 只是一个「先给我张画布」的占位值：下一行 delaxes、再下一行
    # 用数据域长宽比 set_size_inches，占位尺寸不留任何痕迹。它会命中 paper_fig 的
    # 宽高比兜底（3.35/1.0 = 3.35 > MAX_FIG_ASPECT）而发 UserWarning——那条告警对
    # 真实画布有意义，对这张随即被改尺寸的占位图只是噪音，还会盖住真警告
    # （每个 geometry 图都刷一条）。所以**只在这两行**局部静音；真实画布照旧走
    # paper_fig 的正常校验，上限一点没关。
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r"paper_fig\(\): height=.*超过上限", category=UserWarning)
        fig, placeholder = paper_fig(w, height=1.0, margins=(0, 0, 1, 1))
    fig.delaxes(placeholder)                 # 只留按英寸自己摆的轴
    ax_w = w * (margins[2] - margins[0])
    ax_h = ax_w * (yr / xr)
    fig.set_size_inches(w, ax_h / (margins[3] - margins[1]))
    fig.patch.set_facecolor(PAPER)
    return fig


def scene_axes(fig, *, margins=SCENE_MARGINS):
    """在 :func:`square_fig` 的画布上开一个铺满绘图区的轴（不放 placeholder）。"""
    m = margins
    ax = fig.add_axes([m[0], m[1], m[2] - m[0], m[3] - m[1]])
    ax.set_facecolor(PAPER)
    return ax


# --------------------------------------------------------------------------- 通线白口
def border_gap(ax, x: float, y: float, *, horizontal: bool = True,
               half: float = BORDER_BREAK, lw: float = 1.2, color=PAPER,
               zorder: float = 2.5):
    """在层带/容器边框上开一个白口，让连线是「穿过去」而不是「压在框线上」。

    ``horizontal=True``：被穿过的是**水平**边框（连线竖直穿过它），白口沿 x 铺开。
    ``half`` 是白口半宽（in），默认 :data:`BORDER_BREAK`（由 0.9pt 轴宽推出来，
    总宽 ≈10.4px@300dpi）——比轴宽多 0.8pt 余量，够吃掉抗锯齿；**不要**再传
    0.075 之类的固定值，那会得到 45px 的大口子，看起来像框线被橡皮擦断。

    同一条边框上的多个白口各自独立：若两处相距不到两倍口宽，说明布局本身太挤，
    直接 :class:`ValueError` 报出来，而不是把两个口子合并成一大段。完全重合的
    重复调用会被去重（同一条线穿同一处只画一次）。

    Returns
    -------
    Line2D | None
        白口那一小段 PAPER 线；重复调用返回 ``None``。
    """
    x, y, half = float(x), float(y), max(float(half), 0.004)
    reg = ax.__dict__.setdefault("_afg_gaps", [])
    for g in reg:
        if g["horizontal"] != bool(horizontal):
            continue
        same_line = abs(g["y"] - y) < 4e-3 if horizontal else abs(g["x"] - x) < 4e-3
        if not same_line:
            continue
        d = abs(g["x"] - x) if horizontal else abs(g["y"] - y)
        wide = g["half"] + half
        if d < 1e-6:                                   # 同一处重复穿线：去重
            return None
        if d < wide * 1.02:
            raise ValueError(
                f"border_gap(): 同一条边框上两处白口相距仅 {d:.3f}in，小于两倍口宽 "
                f"({wide:.3f}in)，会连成一段断口；请拉开连线落点或改走其它侧")
    reg.append(dict(horizontal=bool(horizontal), x=x, y=y, half=half))
    if horizontal:
        xs, ys = [x - half, x + half], [y, y]
    else:
        xs, ys = [x, x], [y - half, y + half]
    ln, = ax.plot(xs, ys, color=color, lw=float(lw), solid_capstyle="butt",
                  zorder=float(zorder))
    return ln
