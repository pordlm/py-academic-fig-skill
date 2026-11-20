# -*- coding: utf-8 -*-
"""hist —— 直方图（含可选 KDE 曲线；单峰/双峰/长尾一眼可辨）。

**这张图要让读者看到什么**：分布形状、中心与尾部，以及（多组时）两组分布
是「整体平移」还是「形状不同」。

塌陷点提醒
1. 组距（bins）随手选 → 形状会骗人，图注必须写 bins 规则；
2. 用 count 比较样本量不同的两组 → 改 density 或归一化；
3. KDE 曲线用饱和色压住柱子 → KDE 只描边、不与柱同色块。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, check_len, style_ls


def kde(x: Any, grid: Any, bw: Any = "scott") -> np.ndarray:
    """一维高斯核密度估计（纯 numpy，不需要 scipy）。

    Parameters
    ----------
    x : sequence of float
        样本。
    grid : sequence of float
        评估点。
    bw : float | {"scott", "silverman"}
        带宽；``scott`` = ``1.06·σ·n^(-1/5)``。

    Returns
    -------
    ndarray
        与 ``grid`` 等长的密度值。
    """
    xs = as_1d(x, "x", caller="kde")
    g = as_1d(grid, "grid", caller="kde")
    if xs.size < 2:
        raise ValueError(f"kde(): 至少需要 2 个样本（收到 {xs.size} 个）")
    if g.size == 0:
        raise ValueError("kde(): grid 为空")
    sd = float(np.std(xs, ddof=1))
    if sd == 0:
        sd = 1e-9
    if bw == "scott":
        h = 1.06 * sd * xs.size ** (-1 / 5)
    elif bw == "silverman":
        h = 0.9 * sd * xs.size ** (-1 / 5)
    else:
        h = float(bw)
    if h <= 0:
        raise ValueError(f"kde(): bw 必须为正（收到 {h}）")
    z = (g[:, None] - xs[None, :]) / h
    return np.exp(-0.5 * z ** 2).sum(axis=1) / (xs.size * h * np.sqrt(2 * np.pi))


def hist(ax=None, data: Any | None = None, *, labels: Sequence[str] | None = None,
         bins: int | str = "auto", density: bool = True, kde_overlay: bool = True,
         xlabel: str | None = None, ylabel: str | None = None, rug: bool = False,
         alpha: float = 0.55, legend: bool = True, reference: float | None = None):
    """画直方图（可多组叠加 + KDE 曲线）。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    data : sequence of float | Mapping[str, sequence], optional
        单组样本，或 ``{组名: 样本}`` 多组。也接受 ``{"data": …, "labels": …}``。
    labels : sequence of str, optional
        组名（与组数一致）。
    bins : int | str
        分箱数或规则（``"auto"`` / ``"fd"`` / ``"sturges"``）。
    density : bool
        是否按密度归一（多组比较必须为 ``True``）。
    kde_overlay : bool
        是否叠 KDE 曲线（只描边，不与柱子同色块）。
    rug : bool
        是否在底部画样本地毯图（小样本时直观）。
    reference : float, optional
        参考/阈值竖线（细虚线，须在图注说明来源）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if isinstance(data, Mapping) and ("data" in data or "groups" in data):
        labels = data.get("labels", labels)  # type: ignore[union-attr]
        xlabel = data.get("xlabel", xlabel)  # type: ignore[union-attr]
        data = data.get("data", data.get("groups"))  # type: ignore[union-attr]
    if data is None:
        raise ValueError("hist(): 缺少 data（一维样本或 {组名: 样本}）")
    if isinstance(data, Mapping):
        names = [str(k) for k in data]
        samples = [as_1d(v, f"data[{k!r}]", caller="hist") for k, v in data.items()]
    else:
        samples = [as_1d(data, "data", caller="hist")]
        names = as_labels(labels, 1, "labels", caller="hist")
    for smp, nm in zip(samples, names):
        if smp.size == 0:
            raise ValueError(f"hist(): 组 {nm!r} 为空")
    if labels is not None and isinstance(data, Mapping):
        names = as_labels(labels, len(samples), "labels", caller="hist")
        check_len("labels", names, len(samples), caller="hist")

    all_vals = np.concatenate(samples)
    edges = np.histogram_bin_edges(all_vals, bins=bins)
    for i, (name, smp) in enumerate(zip(names, samples)):
        color = _pal.CATEGORICAL[i % len(_pal.CATEGORICAL)]
        ax.hist(smp, bins=edges, density=bool(density), histtype="stepfilled",
                color=_pal.tint(color, float(alpha)), edgecolor=color, linewidth=0.75,
                alpha=1.0, label=name if len(samples) > 1 else None, zorder=2 + i * 0.1)
        if kde_overlay:
            grid = np.linspace(float(edges[0]), float(edges[-1]), 240)
            dens = kde(smp, grid)
            if not density:
                dens = dens * smp.size * float(np.diff(edges).mean())
            ax.plot(grid, dens, color=color, lw=1.05, ls=style_ls(i), zorder=4 + i * 0.1)
        if rug:
            ax.plot(smp, np.full(smp.size, 0.0), "|", color=color, ms=5.0,
                    mew=0.8, alpha=0.8, zorder=1.5, clip_on=False)

    if reference is not None:
        ax.axvline(float(reference), color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1.2)

    _common.set_labels(ax, xlabel=xlabel)
    ax.set_ylabel(ylabel or ("概率密度" if density else "频数"),
                  fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylim(bottom=0.0)
    if legend and len(samples) > 1:
        _base.legend(ax)
    return ax


__all__ = ["hist", "kde"]