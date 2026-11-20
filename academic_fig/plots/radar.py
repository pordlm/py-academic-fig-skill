# -*- coding: utf-8 -*-
"""radar —— 雷达图（多维指标轮廓；指标 3–8 个为宜，轴序必须在图注里说明）。"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_series_map, cat_color, style_ls, style_marker


def radar(ax=None, labels: Sequence[str] | None = None, series: Any | None = None, *,
          data: Any | None = None, fill: bool = False, rmax: float | None = None,
          tick_labels: bool = False, legend: bool = True, rotate: float = 0.0):
    """画雷达图（极坐标）。

    **这张图要让读者看到什么**：多个方案在若干指标上的「轮廓形状」差异
    （谁更均衡、谁在某一维特别突出），而不是精确数值。

    塌陷点提醒
    1. 指标 > 8 或各指标量纲不同却不归一 → 轮廓失去意义；
    2. 轴序随意排列 → 形状是人为的，图注必须给出轴序与归一化方式；
    3. 轮廓互相重叠（> 5 条）→ 改分面或只画 2–3 条。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        极坐标轴；``None`` 时新建一幅单栏图。传普通坐标轴会报错（需 ``projection="polar"``）。
    labels : sequence of str, optional
        指标名（3–8 个最易读）；轴从 12 点方向顺时针排。
    series : Mapping[str, sequence] | 2D array, optional
        每个方案在各指标上的得分，长度必须等于指标数。
    data : Mapping, optional
        ``{"labels": …, "series": …}``（给了就覆盖同名参数）。
    fill : bool
        是否给每条轮廓加极浅填充（多方案超过 3 条时建议关）。
    rmax : float, optional
        径向最大值；缺省取数据最大值并留 8% 余量。

    Returns
    -------
    matplotlib.axes.Axes
        极坐标轴。
    """
    if data is not None:
        labels = _base.pick(data, "labels", "indicators", default=labels)
        series = _base.pick(data, "series", "values", default=series)
    if labels is None or series is None:
        raise ValueError("radar(): 需要 labels 与 series（或传 data={...}）")
    if ax is None:
        from ..layout import paper_fig
        fig, _ = paper_fig("single")
        ax = fig.add_subplot(111, projection="polar")
    elif getattr(ax, "name", "") != "polar":
        raise ValueError("radar(): 传入的 ax 必须是极坐标轴"
                         "（ax = fig.add_subplot(111, projection='polar')）")
    names = [str(x) for x in labels]
    n = len(names)
    if n < 3:
        raise ValueError(f"radar(): 至少需要 3 个指标（收到 {n} 个）；2 个指标请用折线/柱图")
    if n > 8:
        raise ValueError(f"radar(): 指标 {n} 个太多了（最多 8 个），请合并同类指标")
    data = as_series_map(series, n, caller="radar")
    if len(data) > 6:
        raise ValueError(f"radar(): 方案 {len(data)} 条太多（最多 6 条），轮廓会糊在一起")

    ax.set_theta_offset(np.pi / 2.0 + float(rotate))
    ax.set_theta_direction(-1)

    angles = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    closed = np.append(angles, angles[0])
    vmax = float(rmax) if rmax is not None else float(max(np.max(v) for v in data.values())) * 1.08
    if vmax <= 0:
        raise ValueError("radar(): rmax 必须为正")

    ax.set_xticks(angles, names)
    ax.set_ylim(0.0, vmax)
    # 默认不画同心环：本风格「无网格」。只有显式要刻度时才补浅色环 + 径向数字，
    # 数字放在 180°（左侧水平方向），避免压在数据折线上。
    rings = np.linspace(0.0, vmax, 5)[1:-1]
    ax.set_yticks(rings if tick_labels else [])
    if tick_labels:
        ax.set_yticklabels([f"{v:.2f}".rstrip("0").rstrip(".") for v in rings],
                           fontsize=_typo.TEXT_SIZES["footnote"], color=_pal.GREY)
        ax.set_rlabel_position(180.0)
        ax.grid(color=_pal.GREY_LIGHT, lw=0.6, ls=(0, (2, 2)))
    else:
        ax.set_yticklabels([])
        ax.grid(False)
    ax.spines["polar"].set_color(_pal.INK)
    ax.spines["polar"].set_linewidth(0.8)
    ax.tick_params(axis="x", pad=4, labelsize=_typo.TEXT_SIZES["tick"], colors=_pal.INK)

    lines = []
    for i, (name, vals) in enumerate(data.items()):
        color = cat_color(i)
        closed_vals = np.append(vals, vals[0])
        if fill:
            ax.fill(closed, closed_vals, color=_pal.tint(color, 0.12), edgecolor="none", zorder=2)
        ln, = ax.plot(closed, closed_vals, color=color, lw=1.05, ls=style_ls(i),
                      marker=style_marker(i), ms=4.0, mfc="white", mec=color, mew=0.9,
                      label=str(name), zorder=3 + i * 0.1)
        lines.append(ln)
    if legend:
        _base.legend(ax, loc="upper left", bbox_to_anchor=(1.02, 1.02))
    return ax


__all__ = ["radar"]