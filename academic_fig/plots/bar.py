# -*- coding: utf-8 -*-
"""bar —— 单序列柱状图（类别对比；只强调 1–2 根关键柱，可加误差棒与显著性括号）。

**这张图要让读者看到什么**：哪一类明显更高/更低，以及被强调的那一两根柱为什么重要。

塌陷点提醒
1. 每根柱都标数值 → 数值淹没有比较，改标极值或关键项；
2. 纵轴不从 0 起 → 差异被放大，属视觉误导（本函数默认贴 0）；
3. 用饱和色/渐变填充 → 降到灰蓝底 + 单一强调色。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_bool_mask, as_labels, check_len

#: 普通柱的填充（低饱和灰蓝，靠白纸衬托而不是靠饱和色喊话）
BAR_FILL = _pal.tint(_pal.SLATE, 0.26)
#: 强调柱的填充（实心蓝，与正文强调色一致）
BAR_EMPHASIS = _pal.BLUE


def bar(ax=None, labels: Sequence[str] | None = None, values: Any | None = None, *,
        data: Any | None = None, errors: Any | None = None, highlight: Any | None = None,
        ylabel: str | None = None, xlabel: str | None = None, horizontal: bool = False,
        annotate: Any | None = None, annotate_fmt: str = "{:.2f}",
        color: str | None = None, emphasis_color: str | None = None,
        width: float = 0.55, ylim: tuple[float, float] | None = None,
        brackets: Sequence[Any] | None = None, baseline0: bool = True):
    """画单序列柱状图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时按期刊单栏尺寸新建（返回的 ``ax`` 里可取 ``ax.figure``）。
    labels : sequence of str, optional
        类别名；``None`` 时用 1..n。
    values : sequence of float, optional
        每个类别的数值。也可以整包传 ``data=`` 字典：``{"labels": …, "values": …}``。
    data : Mapping | sequence, optional
        数据字典（``labels`` / ``values`` / ``errors``）；给了就覆盖同名参数。
    errors : sequence of float, optional
        误差棒（标准差/CI），长度必须一致；不接受负数。
    highlight : sequence of int | sequence of bool, optional
        要强调的柱，其余保持灰蓝；一张图只强调 1–2 根。
    ylabel, xlabel : str, optional
        轴标签；中文标签不要含 ``$...$``。
    horizontal : bool
        ``True`` 时横向条形（类别名长时用）。
    annotate : bool | sequence, optional
        **只标关键柱的数值**；默认关。
    width : float
        柱宽（占类目间距的比例），默认 0.55（ARCH §3 允许 0.4–0.6）。
    brackets : sequence of (i, j, y, label), optional
        显著性括号：第 i 与第 j 根柱之间、高度 y、文本 label。
    baseline0 : bool
        是否把数值轴拉到包含 0（默认是；柱图不从 0 起会放大差异）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴（``fig = ax.figure``）。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        labels = _base.pick(data, "labels", "categories", default=labels)
        values = _base.pick(data, "values", "value", default=values)
        errors = _base.pick(data, "errors", "err", default=errors)
    if values is None:
        raise ValueError("bar(): 缺少 values；可用 bar(ax, labels, values) 或 bar(data={...})")

    vals = as_1d(values, "values", caller="bar")
    names = as_labels(labels, vals.size, "labels", caller="bar")
    n = vals.size
    if errors is not None:
        err = as_1d(errors, "errors", caller="bar")
        check_len("errors", err, n, caller="bar")
        if np.any(err < 0):
            raise ValueError("bar(): errors 含负值；误差棒长度必须 ≥0")
    else:
        err = None
    if not 0.05 <= float(width) <= 1.0:
        raise ValueError(f"bar(): width 应在 0.05–1.0（收到 {width}）")

    mask = np.zeros(n, dtype=bool)
    if highlight is not None:
        mask = as_bool_mask(highlight, n, "highlight", caller="bar")
    fill = color or BAR_FILL
    emph = emphasis_color or BAR_EMPHASIS
    colors = [emph if m else fill for m in mask]

    pos = np.arange(n)
    kwargs = dict(color=colors, linewidth=0.6, edgecolor=_pal.INK_SOFT, zorder=3)
    if err is not None:
        kwargs.update(error_kw=dict(ecolor=_pal.GREY, elinewidth=0.8,
                                    capsize=2.4, capthick=0.8))
    if horizontal:
        bars = ax.barh(pos, vals, height=float(width),
                       xerr=err if err is not None else None, **kwargs)
        ax.set_yticks(pos, names)
        _common.set_labels(ax, xlabel=ylabel)
        _common.set_labels(ax, ylabel=xlabel)
        ax.invert_yaxis()
    else:
        bars = ax.bar(pos, vals, width=float(width),
                      yerr=err if err is not None else None, **kwargs)
        ax.set_xticks(pos, names)
        _common.set_labels(ax, ylabel=ylabel)
        _common.set_labels(ax, xlabel=xlabel)

    if ylim is not None:
        lo, hi = float(ylim[0]), float(ylim[1])
        if hi <= lo:
            raise ValueError(f"bar(): ylim 上限必须大于下限（收到 {ylim}）")
        (ax.set_xlim if horizontal else ax.set_ylim)(lo, hi)
    elif baseline0:
        lo = min(0.0, float(np.min(vals)))
        hi = float(np.max(vals)) + (float(np.max(err)) if err is not None else 0.0)
        span = (hi - lo) or 1.0
        (ax.set_xlim if horizontal else ax.set_ylim)(lo, hi + 0.08 * span)

    if annotate is not None:
        if isinstance(annotate, bool):
            show = np.ones(n, dtype=bool) if annotate else np.zeros(n, dtype=bool)
        else:
            show = as_bool_mask(annotate, n, "annotate", caller="bar")
        # 横向时高度是 x 轴，annotate_bar 的语义按 (位置, 值) 对齐
        _base.annotate_bar(ax, pos[show], vals[show], fmt=annotate_fmt, horizontal=horizontal)

    if brackets:
        span = abs(float(np.max(vals) - np.min(vals))) or 1.0
        h = 0.035 * span
        tops: list[float] = []
        for item in brackets:
            if len(item) == 3:
                i, j, label = item
                y = float(max(vals[i], vals[j])) + 0.12 * span
            else:
                i, j, y, label = item
            _base.significant(ax, pos[int(i)], pos[int(j)], float(y), str(label), h=h)
            tops.append(float(y) + h + 0.14 * span)  # 括号顶 + 星号留白（粗估）
        # 括号/星号不能顶到画框上：把上界抬到最高括号之上。星号高度随字号变化，
        # 所以按实际文字包围盒换算成数据坐标，粗估值只作兜底。
        if tops:
            need = max(tops)
            try:
                fig = ax.figure
                fig.canvas.draw()
                rend = fig.canvas.get_renderer()
                star_top = max(t.get_window_extent(rend).y1 for t in ax.texts)
                inv = ax.transData.inverted()
                pad_px = 3.0 * float(fig.dpi) / 72.0  # 星号上方留 3pt 呼吸
                need = max(need, float(inv.transform((0.0, star_top + pad_px))[1]))
            except Exception:  # 无 renderer（如某些交互后端）时退回粗估
                pass
            lo_hi = ax.get_xlim() if horizontal else ax.get_ylim()
            lo, hi = float(lo_hi[0]), float(lo_hi[1])
            if need > hi:
                if horizontal:
                    ax.set_xlim(lo, need)
                else:
                    ax.set_ylim(lo, need)
    _common.auto_rotate_x(ax)
    return ax


__all__ = ["bar", "BAR_FILL", "BAR_EMPHASIS"]