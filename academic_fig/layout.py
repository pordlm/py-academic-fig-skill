# -*- coding: utf-8 -*-
"""layout.py —— 期刊尺寸、面板网格、panel 标号与自动折行的图注。

尺寸口径（与 ``docs/ARCH.md`` §3 一致）：

* 单栏 ``SINGLE = 3.35 in``（≈85 mm），双栏 ``DOUBLE = 7.0 in``（≈178 mm）。
* 宽高比保持在 0.6–2.6；超出的版式应当改，而不是硬压。

``footnote`` 把 B 包 ``footnote_wrapped`` 的折行逻辑搬了过来，但修掉了它
「为每个字符调一次 ``fig.text(...).get_window_extent()``」的性能坑：这里只用一个
临时 ``Text``、二分查找行尾、并按字符串缓存实测宽度。
"""
from __future__ import annotations

import re
import warnings
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np

from . import palette as _pal
from . import style as _style
from . import typography as _typo

#: 单栏宽（inch）
SINGLE: float = 3.35
#: 双栏宽（inch）
DOUBLE: float = 7.0
#: 名称 → 宽度
WIDTHS: dict[str, float] = {"single": SINGLE, "double": DOUBLE}
#: 画布宽高比上限：横向多面板（ncols≥2）缺省高度按它反算，留出 0.25 余量给
#: ``checks.ASPECT_RANGE`` 的上限 2.6（R-12：1×4 双栏曾得到 5.6 的宽高比）。
MAX_FIG_ASPECT: float = 2.35
#: 从画布高度到「落盘高度」的损耗补偿（inch）。``save()`` 的 tight 裁切只会吃掉
#: 上下留白，实测双栏 1×4 画布 2.98in → PNG 2.87in（掉 0.11in）；若把画布高度卡在
#: ``w / MAX_FIG_ASPECT`` 正上方，落盘宽高比会回到 2.44，仍高于 MAX_FIG_ASPECT。
#: 这里留 0.16in 余量，让落盘后的宽高比真的 ≤ 2.35（R2-01：1.85in 的推荐值曾让
#: 4 面板图判废，7.00×2.04in、宽高比 3.43）。
CROP_ALLOWANCE: float = 0.16
#: 轴宽占画布宽的比例低于它，就认为「轴被刻意缩窄了」（polar/单正方形图），
#: 图注改按画布宽折行（R-18：否则会折成一根 6 行的窄柱）
NARROW_AXES_FRAC: float = 0.85

#: 折行时允许的断行位置（标点后断开最自然）
_BREAK_AFTER = "，。；：、,.;:!?！？）)]}】》」』 "
#: 不允许出现在行首的字符
_NO_LINE_START = "，。；：、,.;:!?！？）)]}】》」』"


def _width_inches(width: float | str) -> float:
    if isinstance(width, str):
        try:
            return WIDTHS[width.lower()]
        except KeyError:
            raise ValueError(
                f"paper_fig(): width 只接受 'single' / 'double' 或英寸数值，收到 {width!r}"
            ) from None
    width = float(width)
    if width <= 0:
        raise ValueError(f"paper_fig(): width 必须为正（收到 {width}）")
    return width


def paper_fig(width: str | float = "single", height: float | None = None,
              ncols: int = 1, nrows: int = 1, wspace: float | None = None,
              hspace: float | None = None, sharex: bool = False, sharey: bool = False,
              panel_aspect: float = 0.68, margins: tuple[float, float, float, float] | None = None,
              squeeze: bool = True, subplot_kw: dict | None = None):
    """创建期刊尺寸的画布与坐标轴（白底、细框、刻度朝内）。

    Parameters
    ----------
    width : {"single", "double"} or float
        ``"single"`` = 3.35 in，``"double"`` = 7.0 in；也可直接给英寸数值。
    height : float, optional
        画布高度（inch）。缺省按 ``panel_aspect`` 与行数推算，再留出标题/图注空间。
        显式给出的值若让宽高比超过 ``MAX_FIG_ASPECT``（2.35），会被自动抬到合规值
        并发一条 ``UserWarning``（落盘会被 ``checks`` 判 error 的尺寸不留给用户）。
    ncols, nrows : int
        面板行列数。
    wspace, hspace : float, optional
        面板间距（相对宽度/高度），默认 0.32 / 0.42。
    sharex, sharey : bool
        是否共享坐标轴（多面板对比同一量纲时用）。
    panel_aspect : float
        单个面板的「高/宽」，默认 0.68（数据图常用比例）。
    margins : tuple, optional
        ``(left, bottom, right, top)``，默认 ``(0.115, 0.17, 0.975, 0.90)``。
    squeeze : bool
        单面板返回 ``ax``，单行/单列返回一维数组（与 ``plt.subplots`` 一致）。

    Returns
    -------
    (matplotlib.figure.Figure, matplotlib.axes.Axes | numpy.ndarray)
    """
    if nrows < 1 or ncols < 1:
        raise ValueError(f"paper_fig(): nrows/ncols 必须 ≥1（收到 {nrows}×{ncols}）")
    # 漏写 apply_theme() 时自动兜底（只提示一次）：否则字号/字体全是 matplotlib
    # 默认值，中文字符在 PNG 里直接变成豆腐块，而错误要等到肉眼看图才被发现。
    _style._ensure_theme("paper_fig()")
    w = _width_inches(width)
    usable = w * 0.80
    panel_w = usable / ncols
    # 落盘后宽高比要 ≤ MAX_FIG_ASPECT，画布高度至少要有这么多（含 tight 裁切补偿）
    min_h = w / MAX_FIG_ASPECT + CROP_ALLOWANCE
    if height is None:
        height = nrows * panel_w * float(panel_aspect) + max(0, nrows - 1) * 0.10 + 0.30
        if ncols >= 2:
            # 横向多面板（1×2、1×4）按 panel_aspect 推算会太矮：双栏 1×4 只有 1.25in 高，
            # 宽高比 5.6 —— 会被自家 check 判 error（R-12）。这里给一个宽高比上限
            # MAX_FIG_ASPECT，把高度抬到「刚好不被判废」的最小值。
            height = max(height, min_h)
    else:
        given = float(height)
        if given <= 0:
            raise ValueError(f"paper_fig(): height 必须为正（收到 {height}）")
        if w / given > MAX_FIG_ASPECT:
            # R2-01：用户给了会被自家 check 判废的 height（7.0/1.85 = 3.78），
            # 工具把他救回来，而不是让 save()/check 事后骂他。
            warnings.warn(
                f"paper_fig(): height={given:g} 让画布宽高比变成 {w / given:.2f}，"
                f"超过上限 {MAX_FIG_ASPECT:g}（落盘后会被 check 判 error）。"
                f"已自动从 {given:.2f}in 抬到 {min_h:.2f}in"
                f"（= {w:g}/{MAX_FIG_ASPECT:g} + {CROP_ALLOWANCE:g}in 裁切补偿）。"
                "要更矮只能减少面板列数或换 single 宽度。",
                stacklevel=2,
            )
            height = min_h
    height = float(height)
    if height <= 0:
        raise ValueError(f"paper_fig(): height 必须为正（收到 {height}）")

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(w, height),
                             squeeze=False, sharex=sharex, sharey=sharey,
                             subplot_kw=subplot_kw)
    fig.patch.set_facecolor(_pal.PAPER)
    left, bottom, right, top = margins or (0.115, 0.17, 0.975, 0.90)
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top,
                        wspace=0.32 if wspace is None else wspace,
                        hspace=0.42 if hspace is None else hspace)
    for ax in np.asarray(axes, dtype=object).ravel():
        _style.axes(ax)

    if not squeeze:
        return fig, axes
    if nrows == 1 and ncols == 1:
        return fig, axes[0][0]
    if nrows == 1:
        return fig, axes[0]
    if ncols == 1:
        return fig, axes[:, 0]
    return fig, axes


def _panel_label(index: int) -> str:
    """0 → (a), 25 → (z), 26 → (aa)。"""
    letters = ""
    n = index
    while True:
        letters = chr(ord("a") + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return f"({letters})"


def grid_axes(fig, nrows: int, ncols: int, panel_labels: bool = True,
              margins: tuple[float, float, float, float] = (0.08, 0.10, 0.98, 0.94),
              wspace: float = 0.30, hspace: float = 0.40, **subplot_kwargs):
    """在已有画布上铺一组等大小面板，并可选地打上 ``(a)`` / ``(b)`` 标号。

    与 :func:`paper_fig` 的区别：画布已经存在（例如手工调过尺寸或要混排极坐标轴），
    这里只负责建子图 + 套风格 + 打标号。

    Returns
    -------
    numpy.ndarray
        形状 ``(nrows, ncols)`` 的 axes 数组（恒为二维，便于按行列索引）。
    """
    if nrows < 1 or ncols < 1:
        raise ValueError(f"grid_axes(): nrows/ncols 必须 ≥1（收到 {nrows}×{ncols}）")
    left, bottom, right, top = margins
    gs = fig.add_gridspec(nrows, ncols, left=left, right=right, bottom=bottom,
                          top=top, wspace=wspace, hspace=hspace)
    axes = np.empty((nrows, ncols), dtype=object)
    for r in range(nrows):
        for c in range(ncols):
            ax = fig.add_subplot(gs[r, c], **subplot_kwargs)
            _style.axes(ax)
            if panel_labels:
                panel(ax, label=_panel_label(r * ncols + c))
            axes[r, c] = ax
    return axes


def panel_note(ax, text: str, y: float = -0.22, fontsize: float | None = 8.5,
               color: str | None = None, **kwargs):
    """单行面板注记（放子图下方，不进绘图区），说明该面板的符号或关键数值。"""
    return ax.text(0.5, y, text, transform=ax.transAxes, ha="center", va="top",
                   fontsize=fontsize if fontsize is not None else _typo.TEXT_SIZES["footnote"],
                   color=color or _pal.INK_SOFT, **kwargs)


def panel(ax, label: str = "(a)", title: str | None = None, xlabel: str | None = None,
          ylabel: str | None = None, *, title_loc: str = "left",
          label_sep: str = " ", fontsize: float | None = None, box: bool = True,
          equal: bool = False, **kwargs):
    """统一子图外观：``(a) 标题``、轴标签，并套一次坐标轴风格（幂等）。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        目标坐标轴。
    label : str
        面板标号，如 ``"(a)"``；``""`` 或 ``None`` 表示不打标号。
    title : str, optional
        子图标题（11pt、不加粗，按 ``docs/ARCH.md`` §3）。
    xlabel, ylabel : str, optional
        轴标签（10pt）。中文标签不要含 ``$...$``。
    title_loc : {"left", "center"}
        标题对齐；默认左对齐，读起来更像论文面板。
    box, equal : bool
        转发给 :func:`academic_fig.style.axes`。

    Returns
    -------
    matplotlib.axes.Axes
    """
    _style.axes(ax, box=box, equal=equal)
    head = ""
    if label and title:
        head = f"{label}{label_sep}{title}"
    elif label:
        head = str(label)
    elif title:
        head = str(title)
    if head:
        ax.set_title(head, loc=title_loc,
                     fontsize=fontsize if fontsize is not None else _typo.TEXT_SIZES["title"],
                     fontweight="normal", color=_pal.INK, pad=6.0)
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontsize=_typo.TEXT_SIZES["label"], color=_pal.INK)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=_typo.TEXT_SIZES["label"], color=_pal.INK)
    return ax


_ASCII_TOKEN = set("0123456789abcdefghijklmnopqrstuvwxyz"
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ._%<>/=+-×")


def _splits_token(prev: str, nxt: str) -> bool:
    """断行会不会把一个英文词/数字/公式（如 ``p<0.01``、``3.35in``）劈成两半。"""
    return prev in _ASCII_TOKEN and nxt in _ASCII_TOKEN


_OPEN_BRACKET = "（(【[《"
_CLOSE_BRACKET = "）)】]》"


def _unclosed_bracket(paragraph: str, start: int, end: int) -> int:
    """``[start, end)`` 里最后一个没配平的左括号位置；配平则返回 -1。

    图注里 ``（示例数据，为演示版式而构造）`` 这种短括注被劈成「（示例数据，」+
    「虚构）」很难看——宁可把整段括注挪到下一行。
    """
    stack: list[int] = []
    for i in range(start, min(end, len(paragraph))):
        ch = paragraph[i]
        if ch in _OPEN_BRACKET:
            stack.append(i)
        elif ch in _CLOSE_BRACKET and stack:
            stack.pop()
    return stack[-1] if stack else -1


def _wrap_text(text: str, probe, maxw: float, cache: dict[str, float]) -> list[str]:
    """按实测像素宽度折行（二分找行尾；先按标点断，再保证英文词/数字不断开）。"""

    def width_of(s: str) -> float:
        if s not in cache:
            probe.set_text(s)
            cache[s] = float(probe.get_window_extent(_wrap_text.renderer).width)  # type: ignore[attr-defined]
        return cache[s]

    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        if width_of(paragraph) <= maxw:
            lines.append(paragraph)
            continue
        start = 0
        n = len(paragraph)
        while start < n:
            remaining = paragraph[start:]
            if width_of(remaining) <= maxw:
                lines.append(remaining)
                break
            lo, hi = start + 1, n
            while lo < hi:  # 找最长的能放下的前缀 [start, lo)
                mid = (lo + hi + 1) // 2
                if width_of(paragraph[start:mid]) <= maxw:
                    lo = mid
                else:
                    hi = mid - 1
            end = max(lo, start + 1)
            # 不要把英文词/数字/公式（p<0.01、3.35in）劈成两半
            while end - start > 1 and end < n and _splits_token(paragraph[end - 1], paragraph[end]):
                end -= 1
            window = max(start, end - 10)
            for j in range(end, window, -1):
                if paragraph[j - 1] in _BREAK_AFTER:
                    end = j
                    break
            while end < n and paragraph[end] in _NO_LINE_START:
                end += 1
            # 别把括注劈成「（示例数据，」+「虚构）」：行尾落在括号内时退回括号前
            idx = _unclosed_bracket(paragraph, start, end)
            if idx - start >= 8:
                end = idx
            chunk = paragraph[start:end].strip()
            if chunk:
                lines.append(chunk)
            start = end
    return lines


def _below_axes_inches(fig, renderer) -> float:
    """坐标轴下方被刻度标签 + 轴标签占掉的高度（inch），取所有面板的最大值。"""
    best = 0.0
    dpi = float(fig.dpi)
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        try:
            tight = ax.get_tightbbox(renderer)
            box = ax.get_window_extent(renderer)
        except Exception:  # 极坐标/自定义轴偶尔没有 tightbbox
            continue
        if tight is None:
            continue
        best = max(best, float(box.y0 - tight.y0) / dpi)
    return best


def _lowest_artwork_in(fig, renderer) -> float:
    """整幅图所有可见图元的最低点（inch，相对画布底边）。

    图注要落在它下面：刻度标签、轴标签、以及 km 风险人数表这类
    ``annotation_clip=False`` 画在轴外的标注都算数。
    """
    dpi = float(fig.dpi)
    low = float(fig.get_size_inches()[1]) * dpi
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        bb = ax.get_tightbbox(renderer)
        if bb is not None:
            low = min(low, float(bb.y0))
    for t in fig.texts:
        if not t.get_visible():
            continue
        try:
            low = min(low, float(t.get_window_extent(renderer).y0))
        except Exception:
            pass
    return low / dpi


def _axes_span_frac(fig) -> tuple[float, float] | None:
    """所有可见子图框的水平范围（figure fraction）：``(最左, 最右)``。

    图注按这段宽度折行、从左边框起排，读起来才像「图的说明」而不是海报副标题；
    左右边界跟着坐标轴走，``bbox_inches='tight'`` 裁切后也不会左右跳动。
    """
    lefts: list[float] = []
    rights: list[float] = []
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        pos = ax.get_position()
        lefts.append(float(pos.x0))
        rights.append(float(pos.x1))
    if not lefts:
        return None
    return min(lefts), max(rights)


def footnote(fig, text: str, y: float | None = None, fontsize: float | None = None,
             color: str | None = None, xmax_frac: float = 0.97,
             linespacing: float = 1.45, ha: str = "left", va: str = "bottom",
             x: float | None = None, gap_in: float = 0.07,
             width_in: float | None = None):
    """底部整幅图注：按坐标轴宽度自动折行，并**为图注留出专属底边**。

    图注必须写清**数据来源 + 口径**；示意量要标「示意，非真实值」，判定线要标
    「自设目标，非官方指标」。长图注如果不折行，``bbox_inches="tight"`` 会把 PNG
    撑成上万像素宽——所以这里默认折行。

    排版默认**左对齐到「轴左边框 → 轴右边框」**：三段式的长图注左对齐才好读，
    居中的多行像海报副标题；左右边界跟着坐标轴走，导出裁切后也不会左右跳。
    想要居中/右对齐就传 ``ha="center"`` / ``ha="right"``。

    与 B 包「直接把字贴在 y=0.006」的做法不同：本实现先量出刻度标签/轴标签已经
    占掉的高度，再算图注需要几行；底边不够时**把画布长高**（绘图区尺寸保持不变），
    因此图注永远不会压在刻度或横轴标题上。

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        整幅图。
    text : str
        图注；不要为空（空图注视为违反交付规范，直接 ``ValueError``）。
    y : float, optional
        图注底边位置（figure 坐标，0=底部）；缺省贴着画布底边。
    fontsize : float, optional
        默认 8.5pt；如果图窄、字多，可传 7.2。
    xmax_frac : float
        ``ha="center"`` 时允许占用的画布宽度比例（默认 0.97）。
    ha : {"left", "center", "right"}
        水平对齐，默认 ``"left"``（左边界对齐轴左边框）。
    x : float, optional
        图注起点的 figure 坐标；缺省时 ``left`` 取轴左边框、``right`` 取轴右边框、
        ``center`` 取 0.5。
    gap_in : float
        图注与上方刻度/轴标签之间的空隙（inch）。
    width_in : float, optional
        图注折行宽度（inch）。缺省时的规则：
        ① 轴几乎铺满画布（≥85% 画布宽）→ 贴着「轴左边框 → 轴右边框」折行；
        ② 轴被人为缩窄（如 polar 雷达图 ``set_position``）→ 回落到画布宽度并居中，
           不会折成一根窄柱（R-18）。
        想完全自己控就显式传这个参数。

    Returns
    -------
    matplotlib.text.Text
        图注 artist（需要改字/改色可继续操作）。
    """
    if not text or not str(text).strip():
        raise ValueError("footnote(): 图注不能为空；必须写清数据来源与口径")
    text = str(text).strip()
    if not 0.1 <= float(xmax_frac) <= 1.0:
        raise ValueError(f"footnote(): xmax_frac 必须在 0.1~1.0（收到 {xmax_frac}）")
    if ha not in ("left", "center", "right"):
        raise ValueError(f"footnote(): ha 只能是 left/center/right（收到 {ha!r}）")
    fs = float(fontsize if fontsize is not None else _typo.TEXT_SIZES["footnote"])

    # 折行宽度与起点：默认跟着坐标轴左右边框走；轴被缩窄时回落到画布宽（见 _axes_span_frac）
    w_in = float(fig.get_figwidth())
    dpi = float(fig.dpi)
    canvas_maxw = float(xmax_frac) * w_in * dpi
    span = _axes_span_frac(fig)
    if width_in is not None:
        maxw = max(float(width_in) * dpi, 1.0)
        if x is None:
            x = 0.5 if ha == "center" else (span[0] if ha == "left" and span else
                                            span[1] if ha == "right" and span else 0.5)
    elif span is not None:
        left_f, right_f = span
        span_w = max((right_f - left_f) * w_in * dpi, 1.0)
        if span_w >= NARROW_AXES_FRAC * canvas_maxw:
            maxw = span_w
            if x is None:
                x = left_f if ha == "left" else (right_f if ha == "right" else 0.5)
        else:
            # 轴被缩窄（盲测 fig03 的 polar 雷达图折成 6 行窄柱）：按画布宽折行，
            # 并以轴的中线为基准摆位，读起来仍是「整幅图的说明」。
            maxw = canvas_maxw
            if x is None:
                half = 0.5 * maxw / (w_in * dpi)
                cx = 0.5 * (left_f + right_f)
                x = max(0.0, cx - half) if ha == "left" else (
                    min(1.0, cx + half) if ha == "right" else cx)
    else:
        maxw = canvas_maxw
        if x is None:
            x = 0.5

    # 画一次拿到真实几何与 renderer（只画一次，不是每个字符都 draw）
    try:
        fig.canvas.draw()
    except Exception:
        pass
    renderer = getattr(fig.canvas, "renderer", None) or _style._renderer(fig)
    if renderer is None:  # 极端情况：后端不可用，退化成单行
        return fig.text(x, y if y is not None else 0.006, text, ha=ha, va=va,
                        fontsize=fs, color=color or _pal.INK_SOFT, linespacing=linespacing)

    probe = fig.text(0.5, 0.0, "", fontsize=fs, family=_typo.font_stack())
    _wrap_text.renderer = renderer  # type: ignore[attr-defined]
    lines = _wrap_text(text, probe, maxw, {})
    probe.remove()

    # 给图注留出专属底边：不够就长高画布（绘图区尺寸不变），而不是压在刻度上
    block_in = len(lines) * fs * float(linespacing) / 72.0
    deco_in = _below_axes_inches(fig, renderer)
    need_in = deco_in + float(gap_in) + block_in
    h_in = float(fig.get_size_inches()[1])
    pars = fig.subplotpars
    bottom, top = float(pars.bottom), float(pars.top)
    if bottom * h_in + 1e-6 < need_in and top > 0.25:
        axes_h = (top - bottom) * h_in
        new_h = (axes_h + need_in) / top
        delta_in = need_in - bottom * h_in  # 画布底部需要多出来的空间
        fig.set_size_inches(w_in, new_h, forward=True)
        # 不能用 subplots_adjust：它会按 SubplotSpec 重排，抹掉渲染器自己
        # set_position 过的版面（例如 km 的风险人数表）。按 inch 平移每一块 axes。
        for ax in fig.axes:
            pos = ax.get_position()
            ax.set_position([pos.x0,
                             (pos.y0 * h_in + delta_in) / new_h,
                             pos.width,
                             pos.height * h_in / new_h])
        # 画布坐标系的文字（如 km 的风险人数表）也要按 inch 跟着上移，
        # 否则它会在更高的画布里往下漂、重新压住刻度。
        for txt in fig.texts:
            tx, ty = txt.get_position()
            txt.set_position((tx, (ty * h_in + delta_in) / new_h))
        h_in = new_h

    # 长高之后重新量一遍：图注顶边要压在所有图元最低点之下（否则会叠在风险人数表上）
    y_eff, va_eff = 0.02 / max(h_in, 1e-6), va
    if y is None:
        try:
            fig.canvas.draw()
            rend2 = getattr(fig.canvas, "renderer", None) or _style._renderer(fig)
        except Exception:
            rend2 = None
        h_in = float(fig.get_size_inches()[1])
        if rend2 is not None:
            low_in = _lowest_artwork_in(fig, rend2)
            y_eff = max(low_in - float(gap_in), 0.0) / max(h_in, 1e-6)
            va_eff = "top"
    else:
        y_eff = float(y)
    artist = fig.text(x, y_eff, "\n".join(lines), ha=ha, va=va_eff,
                      fontsize=fs, color=color or _pal.INK_SOFT,
                      linespacing=linespacing)
    return artist


def footnote_wrapped(fig, text: str, y: float = 0.006, fontsize: float = 7.2, **kwargs):
    """B 包旧名：窄画布专用的折行图注（默认 7.2pt）。"""
    return footnote(fig, text, y=y, fontsize=fontsize, **kwargs)


#: 兼容 B 包 ``panel_result``：关键结果放子图下方
panel_result = panel_note


__all__ = [
    "DOUBLE",
    "SINGLE",
    "WIDTHS",
    "footnote",
    "footnote_wrapped",
    "grid_axes",
    "panel",
    "panel_note",
    "panel_result",
    "paper_fig",
    "square",
]

# layout.square 与 style.square 是同一个实现（ARCH §4 的旧名映射）
square = _style.square