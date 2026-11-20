# -*- coding: utf-8 -*-
"""plots.base —— 给「所有图」（包括本包没覆盖的图型）兜底用的风格原语。

这一层是风格的最后一道闸：**任何手写 matplotlib 代码**，只要在结束前过一遍
:func:`styled_ax`，出来就是「白纸 + 墨线 + 低饱和强调色」的论文插图。因此这些函数
必须 **幂等、无副作用、不依赖全局状态**，可以重复调用。

导出清单::

    ensure_ax(ax=None, ...)      # 传 ax 就用它；不传就按期刊尺寸新建一个
    styled_ax(ax)                # 四边 0.8pt 墨框、刻度朝内 3.5pt、9pt 刻度标签
    legend(ax, ...)              # frameon=False、9pt、labelspacing=0.35、自动择位
    equal_aspect(ax)             # 等比例（空间图必须）
    zero_line(ax)                # 过零基线（细实线，不是网格）
    annotate_point / annotate_bar# 只标关键点，不标全部
    significant(ax, x1, x2, y)   # 显著性括号（带星号）
    ci_band(ax, x, lo, hi)       # 置信带（极浅填充、无描边）
    regression(ax, x, y)         # 回归线 + 95% 带 + R²（不引入 scipy）
    pick(data, *keys)            # 数据字典解包（兼容 dict / array / None）
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import style as _style
from .. import typography as _typo


# ------------------------------------------------------------------ 画布 / 坐标轴
def ensure_ax(ax=None, *, width: str | float = "single", height: float | None = None,
              nrows: int = 1, ncols: int = 1, index: int = 0, equal: bool = False,
              box: bool = True):
    """拿到一个已套风格的坐标轴：有 ``ax`` 就用它，没有就按期刊尺寸新建。

    Parameters
    ----------
    ax : matplotlib.axes.Axes | array of Axes | None
        传入的轴；若是数组（``paper_fig`` 多面板返回值）取第 ``index`` 个。
    width : {"single", "double"} or float
        新建时的画布宽度。
    height : float, optional
        新建时的画布高度。
    index : int
        ``ax`` 是数组时取哪一个（按 C 顺序展平）。
    equal : bool
        是否等比例。

    Returns
    -------
    matplotlib.axes.Axes
    """
    if ax is None:
        from ..layout import paper_fig
        fig, axes = paper_fig(width, height=height, nrows=nrows, ncols=ncols)
        ax = axes if np.ndim(axes) == 0 else np.ravel(np.asarray(axes, dtype=object))[index]
    elif isinstance(ax, np.ndarray):
        ax = np.ravel(ax)[index]
    elif isinstance(ax, (list, tuple)):
        ax = np.ravel(np.asarray(ax, dtype=object))[index]
    _style.axes(ax, box=box, equal=equal)
    return ax


def styled_ax(ax, **kwargs):
    """对现成坐标轴套统一风格（幂等）；``kwargs`` 转发给 :func:`academic_fig.style.axes`。"""
    return _style.axes(ax, **kwargs)


def equal_aspect(ax):
    """等比例坐标轴（空间/几何图必须；防止「看上去差一点」的失真）。"""
    ax.set_aspect("equal", adjustable="box")
    return ax


def zero_line(ax, axis: str = "y", **kwargs):
    """过零基线：细实线，颜色比数据浅一档（不是网格线）。"""
    axis = str(axis).lower()
    if axis not in ("x", "y", "both"):
        raise ValueError(f"zero_line(): axis 只支持 'x'/'y'/'both'（收到 {axis!r}）")
    color = kwargs.pop("color", _pal.GREY)
    if axis in ("y", "both"):
        ax.axhline(0.0, color=color, lw=0.8, zorder=1.1, **kwargs)
    if axis in ("x", "both"):
        ax.axvline(0.0, color=color, lw=0.8, zorder=1.1, **kwargs)
    return ax


def legend(ax, loc: str = "auto", **kwargs):
    """统一图例：无框、9pt、labelspacing 0.35、自动挑不压数据的角落。"""
    kwargs.setdefault("fontsize", _typo.TEXT_SIZES["legend"])
    kwargs.setdefault("labelspacing", 0.35)
    kwargs.setdefault("frameon", False)
    return _style.legend(ax, loc, **kwargs)


# ------------------------------------------------------------------ 数据解包
def pick(data: Any, *keys: str, default: Any = None) -> Any:
    """从 ``data`` 里按顺序取第一个存在的键（数据字典解包的统一入口）。"""
    if data is None:
        return default
    if isinstance(data, Mapping):
        for k in keys:
            if k in data:
                return data[k]
        return default
    return data if len(keys) <= 1 else default


# ------------------------------------------------------------------ 标注
def annotate_point(ax, x: float, y: float, text: str | None = None, *,
                   xytext: tuple[float, float] = (8, 6), arrow: bool = False,
                   color: str | None = None, fontsize: float | None = None,
                   ha: str = "left", va: str = "bottom", mark: bool = False):
    """只给关键点加标注（``mark=True`` 同时画空心圈强调）。"""
    return _style.annotate_point(ax, x, y, text, xytext=xytext, arrow=arrow,
                                 color=color, fontsize=fontsize, ha=ha, va=va, mark=mark)


def annotate_bar(ax, xs: Sequence[float], ys: Sequence[float],
                 texts: Sequence[str] | None = None, *, fmt: str = "{:.2f}",
                 horizontal: bool = False, color: str | None = None,
                 fontsize: float | None = None):
    """在**选定**的柱顶标数值（不要对每根柱都调用）。"""
    xs_a = np.ravel(np.asarray(xs, dtype=float))
    ys_a = np.ravel(np.asarray(ys, dtype=float))
    if xs_a.size != ys_a.size:
        raise ValueError(f"annotate_bar(): xs({xs_a.size}) 与 ys({ys_a.size}) 长度不一致")
    if texts is not None and len(texts) != ys_a.size:
        raise ValueError(f"annotate_bar(): texts({len(texts)}) 与 ys({ys_a.size}) 长度不一致")
    color = color or _pal.INK
    size = fontsize if fontsize is not None else _typo.TEXT_SIZES["footnote"]
    for i, (x, y) in enumerate(zip(xs_a, ys_a)):
        txt = texts[i] if texts is not None else fmt.format(y)
        if horizontal:
            ax.annotate(txt, xy=(x, y), xytext=(4, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=size, color=color, zorder=6)
        else:
            ax.annotate(txt, xy=(x, y), xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=size, color=color, zorder=6)
    return ax


def significant(ax, x1: float, x2: float, y: float, label: str = "*", *,
                h: float = 0.02, color: str | None = None, lw: float = 0.7,
                fontsize: float | None = None, text_offset: float = 2.0):
    """显著性括号：两根柱之间的折线括号 + 星号（``*/**/***`` 或 ``n.s.``）。

    Parameters
    ----------
    x1, x2 : float
        两组的位置（类别坐标）。
    y : float
        括号底部高度（数据坐标）；括号向上抬 ``h``。
    label : str
        标记文本，``"*"`` / ``"**"`` / ``"***"`` / ``"n.s."``。
    h : float
        括号高度（数据坐标的绝对量，不是比例）。
    """
    color = color or _pal.GREY
    x1, x2, y = float(x1), float(x2), float(y)
    if x2 == x1:
        raise ValueError("significant(): x1 与 x2 不能相同")
    lo, hi = (x1, x2) if x1 < x2 else (x2, x1)
    ax.plot([lo, lo, hi, hi], [y, y + float(h), y + float(h), y],
            color=color, lw=lw, solid_capstyle="butt", zorder=5, clip_on=False)
    ax.annotate(label, xy=((lo + hi) / 2.0, y + float(h)), xytext=(0, float(text_offset)),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=fontsize if fontsize is not None else _typo.TEXT_SIZES["footnote"],
                color=_pal.INK, zorder=6)
    return ax


# ------------------------------------------------------------------ 带 / 回归
def ci_band(ax, x: Any, lo: Any, hi: Any, *, color: str | None = None,
            alpha: float = 0.13, label: str | None = None):
    """置信带/误差带：极浅填充 + 无描边（``tint`` 混白，不用 alpha 叠灰）。"""
    xs = np.ravel(np.asarray(x, dtype=float))
    lo_a = np.ravel(np.asarray(lo, dtype=float))
    hi_a = np.ravel(np.asarray(hi, dtype=float))
    if not (xs.size == lo_a.size == hi_a.size):
        raise ValueError(
            f"ci_band(): 长度不一致 x={xs.size}, lo={lo_a.size}, hi={hi_a.size}"
        )
    if np.any(hi_a < lo_a):
        raise ValueError("ci_band(): upper 存在小于 lower 的点")
    base = color or _pal.BLUE
    return ax.fill_between(xs, lo_a, hi_a, color=_pal.tint(base, alpha),
                           edgecolor="none", zorder=1.5, label=label)


def regression(ax, x: Any, y: Any, *, color: str | None = None, band: bool = True,
               label: str | None = None, annotate: bool = True,
               text_xy: tuple[float, float] | None = None, lw: float = 1.05):
    """画 OLS 回归线（可选 95% 均值置信带）并标注 ``R²`` / ``n``。

    只用 numpy 的最小二乘，不做显著性检验（需要 p 值时请自己算好再 ``annotate``）。

    Returns
    -------
    dict
        ``{"slope": float, "intercept": float, "r2": float, "line": Line2D}``。
    """
    xs = np.ravel(np.asarray(x, dtype=float))
    ys = np.ravel(np.asarray(y, dtype=float))
    if xs.size != ys.size:
        raise ValueError(f"regression(): x({xs.size}) 与 y({ys.size}) 长度不一致")
    if xs.size < 3:
        raise ValueError(f"regression(): 至少 3 个点才画回归线（收到 {xs.size} 个）")
    ok = np.isfinite(xs) & np.isfinite(ys)
    xs, ys = xs[ok], ys[ok]
    color = color or _pal.BLUE

    A = np.column_stack([xs, np.ones_like(xs)])
    coef, *_ = np.linalg.lstsq(A, ys, rcond=None)
    slope, intercept = float(coef[0]), float(coef[1])
    resid = ys - (slope * xs + intercept)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((ys - ys.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    grid = np.linspace(float(xs.min()), float(xs.max()), 120)
    # 角标已经写了 R²/n 时，图例再带一次就是重复信息：只留「拟合线」。
    default_label = "拟合线" if annotate else f"拟合线（R²={r2:.2f}）"
    line, = ax.plot(grid, slope * grid + intercept, color=color, lw=lw,
                    label=label or default_label, zorder=4)

    if band and xs.size > 4:
        n = xs.size
        dof = max(1, n - 2)
        s_err = np.sqrt(ss_res / dof)
        xbar = float(xs.mean())
        sxx = float(np.sum((xs - xbar) ** 2))
        if sxx > 0:
            # 95% t 分位近似（n>30 用 1.96，小样本用粗查表值）
            t_val = 1.96 if dof > 30 else float({1: 12.7, 2: 4.3, 3: 3.18, 4: 2.78,
                                                 5: 2.57, 6: 2.45, 8: 2.31, 10: 2.23,
                                                 15: 2.13, 20: 2.09, 30: 2.04}.get(dof, 2.0))
            se = s_err * np.sqrt(1.0 / n + (grid - xbar) ** 2 / sxx)
            ax.fill_between(grid, slope * grid + intercept - t_val * se,
                            slope * grid + intercept + t_val * se,
                            color=_pal.tint(color, 0.14), edgecolor="none", zorder=2)
    if annotate:
        # R²/n 要落在「点最少」的角落：先四个角各数一遍点，再挑最空的放。
        # 这样图例（同样按占用择优）会自动去另一个角，两者不叠。
        if text_xy is None:
            text_xy, ha, va = free_corner(ax, xs, ys)
        else:
            ha = "left" if text_xy[0] < 0.5 else "right"
            va = "bottom" if text_xy[1] < 0.5 else "top"
        ax.annotate(f"R²={r2:.2f}\nn={xs.size}", xy=text_xy, xycoords="axes fraction",
                    ha=ha, va=va, fontsize=_typo.TEXT_SIZES["footnote"],
                    color=_pal.INK_SOFT, zorder=6)
    return {"slope": slope, "intercept": intercept, "r2": r2, "line": line}


def free_corner(ax, x: Any | None = None, y: Any | None = None, *,
                box: tuple[float, float] = (0.38, 0.22)
                ) -> tuple[tuple[float, float], str, str]:
    """挑画框里最空的角，供注释（R²、解释方差、n）落位。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        目标坐标轴。
    x, y : sequence of float, optional
        数据点坐标；给了才按点密度挑角，不给就按已有文字挑角。
    box : (float, float)
        角部取样框的宽高（axes fraction），默认 (0.38, 0.22)。

    Returns
    -------
    ((fx, fy), ha, va)
        角点在 axes fraction 下的坐标，以及配套的 ha/va。

    Notes
    -----
    四个角各数一遍「落进角框的点 + 与角框相交的已有文字」，取最少的那个；
    平手时按 (左下, 右下, 左上, 右上) 的顺序取，行为可复现。
    """
    cand = {"lb": (0.03, 0.04), "rb": (0.97, 0.04),
            "lt": (0.03, 0.96), "rt": (0.97, 0.96)}
    counts = {k: 0 for k in cand}
    if x is not None and y is not None:
        xa = np.asarray(x, dtype=float).ravel()
        ya = np.asarray(y, dtype=float).ravel()
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        fx = (xa - x0) / ((x1 - x0) or 1.0)
        fy = (ya - y0) / ((y1 - y0) or 1.0)
        bw, bh = float(box[0]), float(box[1])
        masks = {"lb": (fx < bw) & (fy < bh), "rb": (fx > 1 - bw) & (fy < bh),
                 "lt": (fx < bw) & (fy > 1 - bh), "rt": (fx > 1 - bw) & (fy > 1 - bh)}
        for k, m in masks.items():
            counts[k] += int(np.sum(m))
    try:
        rend = ax.figure.canvas.get_renderer()
    except Exception:
        rend = None
    if rend is not None:
        ab = ax.get_window_extent(rend)
        for txt in getattr(ax, "texts", []):
            if not txt.get_visible() or not txt.get_text():
                continue
            try:
                tb = txt.get_window_extent(rend)
            except Exception:
                continue
            cx = (tb.x0 + tb.x1) / 2.0 / max(ab.width, 1.0)
            cy = (tb.y0 + tb.y1) / 2.0 / max(ab.height, 1.0)
            for k, (fx0, fy0) in cand.items():
                if abs(cx - fx0) < box[0] / 2.0 and abs(cy - fy0) < box[1] / 2.0:
                    counts[k] += 2
    order = {"lb": 0, "rb": 1, "lt": 2, "rt": 3}
    best = min(cand, key=lambda k: (counts[k], order[k]))
    bx, by = cand[best]
    ha = "left" if bx < 0.5 else "right"
    va = "bottom" if by < 0.5 else "top"
    return (bx, by), ha, va


def label_points(ax, xs, ys, texts, *, fontsize: float | None = None,
                 color: str | None = None, gap_px: float = 1.5,
                 max_tries: int = 8) -> list:
    """给若干点标名字，并自动换个方向躲开已有的字与点。

    从「右上 → 左上 → 右下 → 左下 → 正上 → 正下 → 右 → 左」依次试位，
    任何一次落到画框外或与已放好的标签相交就换下一个；全都不行才退回第一个位置。
    标签多了照样会挤，但不会再出现「四个基因名糊成一团」。

    Returns
    -------
    list[matplotlib.text.Text]
        实际放下的注释对象。
    """
    xs = np.ravel(np.asarray(xs, dtype=float))
    ys = np.ravel(np.asarray(ys, dtype=float))
    if xs.size != ys.size:
        raise ValueError(f"label_points(): x({xs.size}) 与 y({ys.size}) 长度不一致")
    texts = [str(t) for t in texts]
    if len(texts) != xs.size:
        raise ValueError(f"label_points(): texts({len(texts)}) 与点数({xs.size}) 不一致")
    size = fontsize if fontsize is not None else _typo.TEXT_SIZES["footnote"] - 0.5
    ink = color or _pal.INK

    fig = ax.figure
    try:
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
        axes_box = ax.get_window_extent(rend)
    except Exception:  # noqa: BLE001 - 没有渲染器时退回固定偏移
        rend, axes_box = None, None

    candidates = [(5, 3, "left", "bottom"), (-5, 3, "right", "bottom"),
                  (5, -3, "left", "top"), (-5, -3, "right", "top"),
                  (0, 7, "center", "bottom"), (0, -7, "center", "top"),
                  (9, 0, "left", "center"), (-9, 0, "right", "center")][:max_tries]
    taken: list = []
    placed: list = []
    # 先用点自己占位，避免标签压到别的点
    if rend is not None:
        for x, y in zip(xs, ys):
            px, py = ax.transData.transform((x, y))
            taken.append((px - gap_px, py - gap_px, px + gap_px, py + gap_px))

    def _hits(b) -> bool:
        for tb in taken:
            if b[0] < tb[2] and b[2] > tb[0] and b[1] < tb[3] and b[3] > tb[1]:
                return True
        return False

    for i, (x, y) in enumerate(zip(xs, ys)):
        chosen = None
        for dx, dy, ha, va in candidates:
            txt = ax.annotate(texts[i], xy=(x, y), xytext=(dx, dy),
                              textcoords="offset points", ha=ha, va=va,
                              fontsize=size, color=ink, zorder=6)
            if rend is None:
                chosen = txt
                break
            tb = txt.get_window_extent(rend).expanded(1.0, 1.0)
            inside = (tb.x0 >= axes_box.x0 - 1 and tb.x1 <= axes_box.x1 + 1
                      and tb.y0 >= axes_box.y0 - 1 and tb.y1 <= axes_box.y1 + 1)
            if inside and not _hits((tb.x0, tb.y0, tb.x1, tb.y1)):
                chosen = txt
                break
            txt.remove()
        if chosen is None:  # 八个方向都不行：退回右上角，至少方向一致
            dx, dy, ha, va = candidates[0]
            chosen = ax.annotate(texts[i], xy=(x, y), xytext=(dx, dy),
                                 textcoords="offset points", ha=ha, va=va,
                                 fontsize=size, color=ink, zorder=6)
        if rend is not None:
            tb = chosen.get_window_extent(rend)
            taken.append((tb.x0 - 1, tb.y0 - 1, tb.x1 + 1, tb.y1 + 1))
        placed.append(chosen)
    return placed


__all__ = [
    "annotate_bar",
    "free_corner",
    "label_points",
    "annotate_point",
    "ci_band",
    "ensure_ax",
    "equal_aspect",
    "legend",
    "pick",
    "regression",
    "significant",
    "styled_ax",
    "zero_line",
]