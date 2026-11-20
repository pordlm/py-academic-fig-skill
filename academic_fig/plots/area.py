# -*- coding: utf-8 -*-
"""area —— 面积图（单序列趋势 / 堆叠组成随时间变化）。

**这张图要让读者看到什么**：量的累积与结构变化（谁在变厚、谁在变薄），
以及总量曲线的拐点。

塌陷点提醒
1. 用面积图比较 3 条以上独立序列 → 互相遮挡，改折线；
2. 堆叠顺序随意 → 图注要写清堆叠顺序与是否归一化；
3. 填成饱和实色 → 用 tint 浅填充 + 上沿描边，保持「墨线」感。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_series_map, check_len, style_ls, style_marker


def area(ax=None, x: Any | None = None, series: Any | None = None, *,
         data: Any | None = None, stacked: bool = False, normalize: bool = False,
         xlabel: str | None = None, ylabel: str | None = None,
         legend: bool = True, alpha: float = 0.20, markers: bool = False,
         xlim: tuple[float, float] | None = None, ylim: tuple[float, float] | None = None):
    """画面积图（可堆叠）。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    x : sequence of float, optional
        横坐标（通常为时间），与每条序列等长。
    series : Mapping[str, sequence] | 2D array, optional
        序列名 → 数值；二维数组按 ``(序列, 点)`` 解释。
    data : Mapping, optional
        ``{"x": …, "series": …}``（给了就覆盖同名参数）。
    stacked : bool
        是否堆叠（组成随时间变化时开）。
    normalize : bool
        堆叠时是否归一化到 100%（占比演化）。
    alpha : float
        填充透明度（0.08–0.4；太深会盖住下一条的描边）。
    markers : bool
        是否在数据点打标记（点数 ≤ 12 时才有意义）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        x = _base.pick(data, "x", "xs", "time", default=x)
        series = _base.pick(data, "series", "values", default=series)
    if x is None or series is None:
        raise ValueError("area(): 需要 x 与 series（或传 data={'x':…, 'series':…}）")
    xs = as_1d(x, "x", caller="area")
    if xs.size < 2:
        raise ValueError(f"area(): x 至少需要 2 个点（收到 {xs.size} 个）")
    s_map = as_series_map(series, xs.size, caller="area")
    for name, ys in s_map.items():
        check_len(f"series[{name!r}]", ys, xs.size, caller="area")

    if not 0.0 < float(alpha) < 1.0:
        raise ValueError(f"area(): alpha 应在 (0,1)（收到 {alpha}）")

    names = list(s_map)
    if stacked:
        M = np.vstack([s_map[nm] for nm in names])
        if np.any(M < 0):
            raise ValueError("area(): stacked=True 时序列不能含负值（有正负请改折线/发散堆叠）")
        if normalize:
            col = M.sum(axis=0, keepdims=True)
            if np.any(col <= 0):
                raise ValueError("area(): 存在总量为 0 的时刻，无法归一化")
            M = M / col * 100.0
        cum = np.zeros(xs.size)
        for i, name in enumerate(names):
            lo = cum.copy()
            hi = cum + M[i]
            ax.fill_between(xs, lo, hi, color=_pal.tint(_pal.CATEGORICAL[i % 6], float(alpha)),
                            edgecolor="none", zorder=2 + i * 0.1)
            ax.plot(xs, hi, color=_pal.CATEGORICAL[i % len(_pal.CATEGORICAL)], lw=1.0,
                    ls=style_ls(i), marker=style_marker(i) if markers else None, ms=3.6,
                    zorder=3 + i * 0.1, label=name)
            cum = hi
        ax.set_ylim(0.0, 100.0 if normalize else float(cum.max()) * 1.06)
    else:
        for i, name in enumerate(names):
            ys = s_map[name]
            ax.fill_between(xs, 0.0, ys, color=_pal.tint(_pal.CATEGORICAL[i % 6], float(alpha)),
                            edgecolor="none", zorder=2 + i * 0.1)
            ax.plot(xs, ys, color=_pal.CATEGORICAL[i % len(_pal.CATEGORICAL)], lw=1.05,
                    ls=style_ls(i), marker=style_marker(i) if markers else None, ms=3.6,
                    zorder=3 + i * 0.1, label=name)

    ax.set_ylabel(ylabel or ("占比（%）" if (stacked and normalize) else ""),
                  fontsize=_typo.TEXT_SIZES["label"])
    _common.set_labels(ax, xlabel=xlabel)
    if xlim is not None:
        ax.set_xlim(*map(float, xlim))
    if ylim is not None:
        lo, hi = float(ylim[0]), float(ylim[1])
        if hi <= lo:
            raise ValueError(f"area(): ylim 上限必须大于下限（收到 {ylim}）")
        ax.set_ylim(lo, hi)
    # 面积图铺满画框、没有空角，图例又不能出框（单栏 3.35in 宽度不能涨）：
    # 在顶部抬出一条留白带，图例横排放在这条带里，既不压数据也不撞 panel 标题。
    if legend:
        lo, hi = ax.get_ylim()
        if ylim is None:
            keep = [float(t) for t in ax.get_yticks() if t <= hi + 1e-9]
            ax.set_ylim(lo, hi + (hi - lo) * 0.20)
            if keep:  # 留白带里不出现「120」这种超出数据的刻度
                ax.set_yticks(keep)
        _base.legend(ax, loc="upper left", bbox_to_anchor=(0.0, 1.0),
                     ncol=min(len(names), 4), handlelength=1.15, handleheight=0.85,
                     columnspacing=1.0, handletextpad=0.5, borderaxespad=0.0)
    _common.auto_rotate_x(ax)
    return ax


__all__ = ["area"]