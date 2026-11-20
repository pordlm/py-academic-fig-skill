# -*- coding: utf-8 -*-
"""violin —— 小提琴图（分布形状对比；内嵌中位数与四分位，不画箱体边框）。"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, cat_color, check_len

#: 小提琴填充透明度（tint 混白，见 palette.tint）
_FILL_ALPHA = 0.22


def _as_groups(data: Any) -> dict[str, np.ndarray]:
    """把分布数据统一成 ``{组名: 一维样本}``。"""
    if isinstance(data, Mapping):
        items = list(data.items())
    elif isinstance(data, (list, tuple)) and data and isinstance(data[0], (list, tuple, np.ndarray)):
        items = [(f"G{i + 1}", v) for i, v in enumerate(data)]
    else:
        arr = np.asarray(data, dtype=float)
        if arr.ndim == 1:
            items = [("G1", arr)]
        elif arr.ndim == 2:
            items = [(f"G{i + 1}", arr[i]) for i in range(arr.shape[0])]
        else:
            raise ValueError(f"violin(): data 维度不支持（收到 {arr.ndim} 维）")
    if not items:
        raise ValueError("violin(): data 为空；至少给一组样本")

    out: dict[str, np.ndarray] = {}
    for name, vals in items:
        arr = as_1d(vals, f"data[{name!r}]", caller="violin", min_len=2)
        if arr.size < 2:
            raise ValueError(f"violin(): data[{name!r}] 只有 {arr.size} 个样本，画不出分布")
        out[str(name)] = arr
    return out


def violin(ax=None, data: Any | None = None, *, labels: Sequence[str] | None = None,
           ylabel: str | None = None, xlabel: str | None = None,
           show_points: bool = False, show_median: bool = True,
           widths: float = 0.62, showmeans: bool = False, points_size: float = 6.0):
    """画小提琴图（默认叠抖动散点，看得见真实样本）。

    **这张图要让读者看到什么**：分布形状（单峰/双峰/长尾）与离散度差异，
    而不只是「组间中位数差一点」。

    塌陷点提醒
    1. 每组样本 < 5 却画小提琴 → 形状是核密度虚构的，改散点+中位线；
    2. 只有小提琴没有中位数/四分位 → 读者读不出中心与离散；
    3. 组数 > 6 或宽度过胖 → 改横向或分面。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    data : Mapping[str, sequence] | sequence of sequences | 2D array, optional
        每组一组样本；组名缺省为 G1..Gn。也可传 ``{"data": …, "labels": …}``。
    labels : sequence of str, optional
        覆盖组名（长度必须与组数一致）。
    ylabel, xlabel : str, optional
        轴标签。
    show_points : bool
        是否叠一层抖动散点（样本少时看真实分布；样本多时关掉）。
    show_median : bool
        是否画中位数（实心短横）与四分位（细竖线）。
    widths : float
        小提琴最大宽度（0.2–1.0）。
    points_size : float
        抖动点面积。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if isinstance(data, Mapping) and ("data" in data or "groups" in data):
        labels = data.get("labels", labels)  # type: ignore[union-attr]
        ylabel = data.get("ylabel", ylabel)  # type: ignore[union-attr]
        data = data.get("data", data.get("groups"))  # type: ignore[union-attr]
    if data is None:
        raise ValueError("violin(): 缺少 data（每组一组样本）")
    groups = _as_groups(data)
    names = list(groups)
    if labels is not None:
        check_len("labels", list(labels), len(names), caller="violin")
        names = [str(x) for x in labels]
    if not 0.2 <= float(widths) <= 1.0:
        raise ValueError(f"violin(): widths 应在 0.2–1.0（收到 {widths}）")

    samples = [groups[k] for k in groups]
    positions = np.arange(1, len(samples) + 1)
    parts = ax.violinplot(samples, positions=positions, widths=float(widths),
                          showmeans=False, showmedians=False, showextrema=False,
                          points=120, bw_method=0.35 if min(s.size for s in samples) > 8 else None)

    medians = []
    rng = np.random.default_rng(20240517)  # 抖动固定种子：图可复现
    for i, (body, sample) in enumerate(zip(parts["bodies"], samples)):
        color = cat_color(i)
        body.set_facecolor(_pal.tint(color, _FILL_ALPHA))
        body.set_edgecolor(color)
        body.set_linewidth(0.8)
        body.set_alpha(1.0)
        q1, med, q3 = np.percentile(sample, [25, 50, 75])
        if show_median:
            ax.vlines(positions[i], q1, q3, color=color, lw=0.9, zorder=4)
            medians.append(ax.hlines(med, positions[i] - float(widths) * 0.22,
                                     positions[i] + float(widths) * 0.22,
                                     color=color, lw=1.6, zorder=5))
        if show_points:
            jitter = rng.uniform(-0.11, 0.11, size=sample.size)
            # 原始观测用小实心灰点：彩色空心圆压在浅色琴身上像气泡
            ax.scatter(positions[i] + jitter, sample, s=float(points_size),
                       color=_pal.INK_SOFT, linewidths=0.0, alpha=0.45, zorder=3)
    if showmeans:
        means = [float(np.mean(s)) for s in samples]
        ax.scatter(positions, means, marker="D", s=10, facecolors=_pal.PAPER,
                   edgecolors=_pal.INK, linewidths=0.7, zorder=6, label="均值")

    ax.set_xticks(positions, names)
    ax.set_xlim(0.4, len(samples) + 0.6)
    _common.set_labels(ax, ylabel=ylabel)
    _common.set_labels(ax, xlabel=xlabel)
    return ax


__all__ = ["violin"]