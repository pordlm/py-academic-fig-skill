# -*- coding: utf-8 -*-
"""line —— 多序列折线（趋势对比 + 置信带 + 阶梯/虚线基线）。

**这张图要让读者看到什么**：谁在上升、谁在饱和、拐点出现在哪里；
差异要靠**线型 + 标记 + 颜色**三重编码，黑白打印也不丢信息。

塌陷点提醒
1. 只靠颜色区分序列 → 打印成灰后全糊，必须配线型/标记；
2. 每点标数值 → 曲线会变成表格，只标拐点或终点；
3. 序列超过 5 条 → 改分面或只画均值+包络带。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_series_map, cat_color, check_len, style_ls, style_marker


def line(ax=None, x: Any | None = None, series: Any | None = None, *,
         data: Any | None = None, xlabel: str | None = None, ylabel: str | None = None,
         markers: bool = True, band: Any | None = None, legend: bool = True,
         xlim: tuple[float, float] | None = None, ylim: tuple[float, float] | None = None,
         lw: float = 1.05, label_suffix: str = "", step: bool = False,
         baseline: float | None = None, baseline_label: str | None = None):
    """画多序列折线图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    x : sequence of float, optional
        横坐标（与每条序列等长）。
    series : Mapping[str, sequence] | 2D array | sequence, optional
        多序列数据；二维数组按形状推断（行数少者为序列数）。
    data : Mapping, optional
        ``{"x": …, "series": …, "band": …}``（给了就覆盖同名参数）。
    xlabel, ylabel : str, optional
        轴标签。
    markers : bool
        是否打标记；默认按点数自动稀疏（最多约 8 个），不会糊成一片。
    band : Mapping[str, (lower, upper)], optional
        每条序列的置信带/误差带；极浅同色填充、不描边。
    legend : bool
        是否画图例（无框、自动挑角落）。
    step : bool
        阶梯折线（剂量/阈值/状态切换曲线）。
    baseline : float, optional
        虚线基线（参考结构/自设目标），不是拟合结果。
    baseline_label : str, optional
        基线标注文本，如 ``"自设目标 0.90"``。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        x = _base.pick(data, "x", "xs", "index", default=x)
        series = _base.pick(data, "series", "y", "values", default=series)
        band = _base.pick(data, "band", "ci", default=band)
    if x is None or series is None:
        raise ValueError("line(): 需要 x 与 series（或传 data={'x':…, 'series':…}）")

    xs = as_1d(x, "x", caller="line")
    if xs.size < 2:
        raise ValueError(f"line(): x 至少需要 2 个点（收到 {xs.size} 个）")
    data_map = as_series_map(series, xs.size, caller="line")

    band_map: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if band is not None:
        if not isinstance(band, Mapping):
            raise ValueError("line(): band 必须是 {序列名: (lower, upper)} 的映射")
        for name, pair in band.items():
            if name not in data_map:
                raise ValueError(f"line(): band 里的 {name!r} 不在 series 中"
                                 f"（可选：{list(data_map)}）")
            lo, hi = pair
            lo_a = as_1d(lo, f"band[{name!r}].lower", caller="line")
            hi_a = as_1d(hi, f"band[{name!r}].upper", caller="line")
            check_len(f"band[{name!r}] 下限", lo_a, xs.size, caller="line")
            check_len(f"band[{name!r}] 上限", hi_a, xs.size, caller="line")
            band_map[str(name)] = (lo_a, hi_a)

    if baseline is not None:
        ax.axhline(float(baseline), color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1.2)
        if baseline_label:
            ax.annotate(baseline_label, xy=(1.0, float(baseline)),
                        xycoords=("axes fraction", "data"), xytext=(-2, 3),
                        textcoords="offset points", ha="right", va="bottom",
                        fontsize=_typo.TEXT_SIZES["footnote"], color=_pal.GREY)

    mark_every = 1 if xs.size <= 9 else max(1, int(round(xs.size / 8)))
    for i, (name, ys) in enumerate(data_map.items()):
        color = cat_color(i)
        if name in band_map:
            _base.ci_band(ax, xs, band_map[name][0], band_map[name][1], color=color)
        drawstyle = "steps-post" if step else "default"
        ax.plot(
            xs, ys, color=color, lw=lw if i else lw + 0.1, ls=style_ls(i),
            marker=style_marker(i) if markers else None, ms=4.2,
            markevery=mark_every, mfc="white", mec=color, mew=0.9,
            drawstyle=drawstyle, label=f"{name}{label_suffix}", zorder=3 + i * 0.1,
        )

    _common.set_labels(ax, xlabel=xlabel)
    _common.set_labels(ax, ylabel=ylabel)
    if xlim is not None:
        ax.set_xlim(*map(float, xlim))
    if ylim is not None:
        lo, hi = float(ylim[0]), float(ylim[1])
        if hi <= lo:
            raise ValueError(f"line(): ylim 上限必须大于下限（收到 {ylim}）")
        ax.set_ylim(lo, hi)
    if legend:
        _base.legend(ax, ncol=1 if len(data_map) <= 4 else 2)
    return ax


__all__ = ["line"]