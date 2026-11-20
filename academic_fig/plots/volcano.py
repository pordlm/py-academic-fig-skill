# -*- coding: utf-8 -*-
"""volcano —— 火山图（差异表达/差异丰度：log2FC × −log10 p）。

**这张图要让读者看到什么**：哪些特征同时「变化大」且「显著」，
分左右两侧（上调/下调）成团，而不是均匀散布。

塌陷点提醒
1. 阈值不画出来 → 读者不知道哪些点算「显著」，必须画横竖虚线；
2. 标注所有显著点 → 只标效应量最大的 5–10 个；
3. 用 p 而非校正后 q 值 → 图注必须写清用哪个（p 还是 FDR）。
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_1d, check_len


def volcano(ax=None, log2fc: Any | None = None, pvalue: Any | None = None, *,
            data: Any | None = None, names: Sequence[str] | None = None,
            fc_thresh: float = 1.0, p_thresh: float = 0.05, top_n: int = 8,
            xlabel: str | None = None, ylabel: str | None = None,
            legend: bool = False, annotate: bool = False):
    """画火山图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    log2fc : sequence of float, optional
        对数倍数变化；也可用 ``data={"log2fc":…, "pvalue":…, "names":…}``。
    pvalue : sequence of float, optional
        显著性（原始 p 或校正 q），须在 (0, 1]；0 会用 1e-300 兜底。
    data : Mapping, optional
        数据字典（``log2fc`` / ``pvalue`` / ``names``）。
    names : sequence of str, optional
        特征名（用于标注 top 点）。
    fc_thresh : float
        倍数变化阈值（绝对值），默认 1（即 2 倍）。
    p_thresh : float
        显著性阈值，默认 0.05。
    top_n : int
        自动标注的显著点个数（按 |log2FC|·−log10 p 排序）；0 表示不标。
    annotate : bool
        是否强制标注 top 点（``top_n>0`` 时默认就会标）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        log2fc = _base.pick(data, "log2fc", "fc", "x", default=log2fc)
        pvalue = _base.pick(data, "pvalue", "p", "q", default=pvalue)
        names = _base.pick(data, "names", "genes", "labels", default=names)
    if log2fc is None or pvalue is None:
        raise ValueError("volcano(): 需要 log2fc 与 pvalue（或 data={...}）")
    fc = as_1d(log2fc, "log2fc", caller="volcano")
    p = as_1d(pvalue, "pvalue", caller="volcano")
    check_len("pvalue", p, fc.size, caller="volcano")
    if fc.size == 0:
        raise ValueError("volcano(): 数据为空")
    if np.any(p <= 0) or np.any(p > 1):
        raise ValueError("volcano(): pvalue 必须落在 (0, 1]；0 请先做下限截断")
    if fc_thresh < 0:
        raise ValueError(f"volcano(): fc_thresh 不能为负（收到 {fc_thresh}）")
    if not 0 < float(p_thresh) < 1:
        raise ValueError(f"volcano(): p_thresh 应在 (0,1)（收到 {p_thresh}）")

    y = -np.log10(p)
    up = (fc >= float(fc_thresh)) & (p <= float(p_thresh))
    down = (fc <= -float(fc_thresh)) & (p <= float(p_thresh))
    mid = ~(up | down)

    ax.scatter(fc[mid], y[mid], s=9, color=_pal.GREY_LIGHT, linewidths=0, zorder=2,
               label="不显著")
    ax.scatter(fc[down], y[down], s=14, color=_pal.BLUE, linewidths=0.3,
               edgecolors="white", zorder=3, label=f"下调（{int(down.sum())}）")
    ax.scatter(fc[up], y[up], s=14, color=_pal.CLAY, linewidths=0.3,
               edgecolors="white", zorder=3, label=f"上调（{int(up.sum())}）")

    ax.axhline(-np.log10(float(p_thresh)), color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1.2)
    for xs in (-float(fc_thresh), float(fc_thresh)):
        ax.axvline(xs, color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1.2)

    ax.set_xlabel(xlabel or "log₂ 倍数变化", fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylabel(ylabel or "−log₁₀ p", fontsize=_typo.TEXT_SIZES["label"])
    # 顶部的基因名要留出位置：上界抬 12%，左右各留 6%
    x_lo, x_hi = float(fc.min()), float(fc.max())
    x_pad = (x_hi - x_lo) * 0.06 or 0.2
    ax.set_xlim(x_lo - x_pad, x_hi + x_pad)
    ax.set_ylim(0.0, float(y.max()) * 1.12 if y.size else 1.0)

    if top_n and names is not None:
        names_a = np.asarray(list(names), dtype=object)
        if names_a.ndim != 1:
            raise ValueError("volcano(): names 必须是一维序列（每个点一个基因名）")
        check_len("names", names_a, fc.size, caller="volcano")
        score = np.where(up | down, np.abs(fc) * y, -np.inf)
        order = np.argsort(-score)[: int(top_n)]
        order = order[np.isfinite(score[order])]
        idx_list = [int(i) for i in order]
        # 名字互相避让：否则左侧一串下调基因会糊成一团
        _base.label_points(ax, fc[idx_list], y[idx_list],
                           [names_a[i] for i in idx_list])
    if legend:
        # 火山图的四角都有点：图例放框外上方，别和数据、基因名抢位置
        _base.legend(ax, loc="lower right", bbox_to_anchor=(1.0, 1.012),
                     ncol=3, handlelength=1.0, columnspacing=0.9, borderaxespad=0.0)
    return ax


__all__ = ["volcano"]