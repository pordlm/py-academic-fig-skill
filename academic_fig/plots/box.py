# -*- coding: utf-8 -*-
"""box —— 箱线图（含散点/离群标注；比小提琴更「稳」，适合样本少或需报四分位）。

**这张图要让读者看到什么**：组间中位数差异、四分位离散程度与离群点，
以及每组真实样本的量级（叠散点后一目了然）。

塌陷点提醒
1. 每组只有 3–5 个样本 → 箱体是猜的，直接画散点 + 中位横线；
2. 不标样本量 n → 读者无法判断箱体的可信度；
3. 用彩色实心箱体 + 粗边 → 改白填充 + 墨线描边 + 一组低饱和强调色。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_labels, cat_color, check_len


def _as_groups(data: Any) -> list[np.ndarray]:
    if isinstance(data, Mapping):
        groups = []
        for name, vals in data.items():
            arr = as_1d(vals, f"data[{name!r}]", caller="box")
            if arr.size == 0:
                raise ValueError(f"box(): 组 {name!r} 为空")
            groups.append(arr)
        if not groups:
            raise ValueError("box(): data 为空映射")
        return groups
    arr = np.asarray(data, dtype=object)
    if arr.ndim == 1:
        if all(np.isscalar(v) for v in arr):
            raise ValueError("box(): 只给了一组数字；请传 {组名: 样本} 或二维序列")
        groups = [as_1d(v, f"data[{i}]", caller="box") for i, v in enumerate(arr)]
    elif arr.ndim == 2:
        groups = [as_1d(row, f"data[{i}]", caller="box") for i, row in enumerate(arr)]
    else:
        raise ValueError(f"box(): data 维度不支持（收到 {arr.ndim} 维）")
    for i, g in enumerate(groups):
        if g.size == 0:
            raise ValueError(f"box(): 第 {i} 组为空")
    return groups


def box(ax=None, data: Any | None = None, *, labels: Sequence[str] | None = None,
        ylabel: str | None = None, xlabel: str | None = None, show_points: bool = True,
        show_n: bool = True, widths: float = 0.5, jitter: float = 0.09,
        points_size: float = 5.0, showmeans: bool = False):
    """画箱线图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    data : Mapping[str, sequence] | sequence of sequences | 2D array, optional
        每组一组样本；也可传 ``{"data": …, "labels": …}``。
    labels : sequence of str, optional
        组名（长度须等于组数）。
    ylabel, xlabel : str, optional
        轴标签。
    show_points : bool
        是否叠抖动散点（透明小点，显真实样本）。
    show_n : bool
        是否在组名下写样本量 ``(n=…)``。
    widths : float
        箱体宽度（0.2–0.9）。
    jitter : float
        抖动幅度（相对组间距，0–0.25）。
    showmeans : bool
        是否用空心圈标均值（默认只画中位数）。

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
        raise ValueError("box(): 缺少 data（每组一组样本）")
    if isinstance(data, Mapping) and labels is None:
        # {组名: 样本} 是最常见的写法，键就是刻度名
        labels = [str(k) for k in data.keys()]
    groups = _as_groups(data)
    n_groups = len(groups)
    names = as_labels(labels, n_groups, "labels", caller="box")
    check_len("labels", names, n_groups, caller="box")
    if not 0.1 <= float(widths) <= 0.95:
        raise ValueError(f"box(): widths 应在 0.1–0.95（收到 {widths}）")
    if not 0.0 <= float(jitter) <= 0.3:
        raise ValueError(f"box(): jitter 应在 0–0.3（收到 {jitter}）")

    positions = np.arange(1, n_groups + 1)
    rng = np.random.default_rng(20240607)
    for i, (vals, pos, name) in enumerate(zip(groups, positions, names)):
        color = cat_color(i)
        ax.boxplot([vals], positions=[pos], widths=float(widths), patch_artist=True,
                   showfliers=False, showmeans=bool(showmeans), manage_ticks=False,
                   medianprops=dict(color=_pal.INK, lw=1.1),
                   boxprops=dict(facecolor="white", edgecolor=color, lw=0.9),
                   whiskerprops=dict(color=color, lw=0.8, ls=(0, (4, 2))),
                   capprops=dict(color=color, lw=0.8),
                   meanprops=dict(marker="o", markerfacecolor="white",
                                  markeredgecolor=_pal.INK, markersize=4.2))
        if show_points:
            jit = rng.uniform(-float(jitter), float(jitter), size=vals.size)
            ax.scatter(pos + jit, vals, s=float(points_size), color=_pal.tint(color, 0.55),
                       edgecolors="none", zorder=4, alpha=0.9)

    tick_labels = [f"{nm}\n(n={g.size})" if show_n else str(nm)
                   for nm, g in zip(names, groups)]
    ax.set_xticks(positions, tick_labels)
    ax.set_xlim(0.4, n_groups + 0.6)
    _common.set_labels(ax, ylabel=ylabel)
    _common.set_labels(ax, xlabel=xlabel)
    return ax


__all__ = ["box"]