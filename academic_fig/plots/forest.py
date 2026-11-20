# -*- coding: utf-8 -*-
"""forest —— 森林图（多研究/多组效应量 + 95% CI + 合并效应菱形）。

**这张图要让读者看到什么**：各项估计的方向是否一致、置信区间是否跨过无效线，
以及合并后的效应量落在哪（菱形）。

塌陷点提醒
1. 不画无效线（0 或 1）→ 读者无法判断「有没有效应」；
2. CI 宽度不按权重的画 → 权重信息丢失，至少要把 n 或权重写进标签；
3. 横轴刻度在 0 附近却用对数尺度（OR/RR）→ 必须标 log 轴或直接说明。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.patches import Polygon

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_1d, as_labels, check_len


def forest(ax=None, labels: Sequence[str] | None = None, estimates: Any | None = None, *,
           data: Any | None = None, lower: Any | None = None, upper: Any | None = None,
           pooled: tuple[float, float, float] | None = None,
           null: float = 0.0, xlabel: str | None = None, weights: Any | None = None,
           log_scale: bool = False, table: bool = True, fmt: str = "{:.2f}"):
    """画森林图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    labels : sequence of str, optional
        每行研究/组的名字（建议含 n 或权重）。
    estimates : sequence of float, optional
        点估计；也可用 ``data={"labels":…, "estimates":…, "lower":…, "upper":…}``。
    data : Mapping, optional
        数据字典（``labels`` / ``estimates`` / ``lower`` / ``upper`` / ``pooled``）。
    lower, upper : sequence of float, optional
        95% 置信区间下/上限，长度须与估计一致。
    pooled : (est, lo, hi), optional
        合并效应：画成菱形，并在右侧写数值。
    null : float
        无效线位置（均值差/相关系数用 0；OR/RR/HR 用 1）。
    weights : sequence of float, optional
        每个估计的权重（决定方块大小，如样本量或方差倒数）。
    log_scale : bool
        是否对数横轴（OR/RR/HR 常用；此时 null 必须 > 0）。
    table : bool
        是否在右侧列出「估计 [下限, 上限]」文本列（论文里通常需要）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        labels = _base.pick(data, "labels", "studies", default=labels)
        estimates = _base.pick(data, "estimates", "est", default=estimates)
        lower = _base.pick(data, "lower", "lo", default=lower)
        upper = _base.pick(data, "upper", "hi", default=upper)
        pooled = _base.pick(data, "pooled", default=pooled)
        weights = _base.pick(data, "weights", "n", default=weights)
    if estimates is None or lower is None or upper is None:
        raise ValueError("forest(): 需要 estimates / lower / upper（或 data={...}）")
    est = as_1d(estimates, "estimates", caller="forest")
    lo = as_1d(lower, "lower", caller="forest")
    hi = as_1d(upper, "upper", caller="forest")
    k = est.size
    if k == 0:
        raise ValueError("forest(): 估计为空")
    check_len("lower", lo, k, caller="forest")
    check_len("upper", hi, k, caller="forest")
    if np.any(hi < lo):
        raise ValueError("forest(): 存在上限小于下限的行")
    if np.any(est < lo) or np.any(est > hi):
        raise ValueError("forest(): 点估计必须落在 [lower, upper] 内")
    names = as_labels(labels, k, "labels", caller="forest")
    if log_scale and float(null) <= 0:
        raise ValueError("forest(): log_scale=True 时 null 必须为正（OR/RR 用 1）")

    w = None
    if weights is not None:
        w = as_1d(weights, "weights", caller="forest")
        check_len("weights", w, k, caller="forest")
        if np.any(w < 0):
            raise ValueError("forest(): weights 不能为负")
        wmax = float(np.max(w)) or 1.0
        sizes = 18.0 + 46.0 * (w / wmax)
    else:
        sizes = np.full(k, 34.0)

    ypos = np.arange(k)[::-1]
    for i in range(k):
        y = ypos[i]
        ax.plot([lo[i], hi[i]], [y, y], color=_pal.INK_SOFT, lw=0.9, zorder=3,
                solid_capstyle="butt")
        ax.plot([lo[i], lo[i]], [y - 0.12, y + 0.12], color=_pal.INK_SOFT, lw=0.8, zorder=3)
        ax.plot([hi[i], hi[i]], [y - 0.12, y + 0.12], color=_pal.INK_SOFT, lw=0.8, zorder=3)
        ax.scatter([est[i]], [y], s=float(sizes[i]), marker="s", color=_pal.BLUE,
                   edgecolors="white", linewidths=0.6, zorder=4)

    ax.axvline(float(null), color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1.2)
    ax.set_yticks(ypos, names)
    ax.set_ylim(-0.8, k - 0.2)
    if log_scale:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel or "效应量（95% CI）", fontsize=_typo.TEXT_SIZES["label"])

    if pooled is not None:
        if len(pooled) != 3:
            raise ValueError("forest(): pooled 需要 (est, lower, upper) 三个值")
        p_est, p_lo, p_hi = (float(v) for v in pooled)
        if not p_lo <= p_est <= p_hi:
            raise ValueError("forest(): pooled 的 est 必须落在其 CI 内")
        y = -0.55
        ax.add_patch(Polygon([[p_lo, y], [p_est, y + 0.16], [p_hi, y], [p_est, y - 0.16]],
                             closed=True, facecolor=_pal.tint(_pal.BLUE, 0.62),
                             edgecolor=_pal.INK, lw=0.6, zorder=5))
        ax.annotate(f"合并 {fmt.format(p_est)} [{fmt.format(p_lo)}, {fmt.format(p_hi)}]",
                    xy=(p_hi, y), xytext=(10, 0), textcoords="offset points",
                    va="center", ha="left", fontsize=_typo.TEXT_SIZES["footnote"],
                    color=_pal.INK)
        ax.set_ylim(min(-0.95, y - 0.4), k - 0.2)

    if table:
        # 右侧数值列要占 ~20% 图宽：先把绘图区右边界收进来，别让数字贴在画框上
        pos = ax.get_position()
        if pos.x1 > 0.80:
            ax.set_position([pos.x0, pos.y0,
                             max(0.80 - pos.x0, 0.30), pos.height])
        for i in range(k):
            ax.annotate(f"{fmt.format(est[i])} [{fmt.format(lo[i])}, {fmt.format(hi[i])}]",
                        xy=(1.02, ypos[i]), xycoords=("axes fraction", "data"),
                        va="center", ha="left", fontsize=_typo.TEXT_SIZES["footnote"],
                        color=_pal.INK_SOFT, annotation_clip=False)
    return ax


__all__ = ["forest"]