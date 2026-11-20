# -*- coding: utf-8 -*-
"""pca —— PCA 降维得分图（SVD 实现，95% 置信椭圆，可选双标图箭头）。

**这张图要让读者看到什么**：样本在主成分平面上是否分得开、组间距离与组内离散
（椭圆重叠程度），以及哪几个原始变量主导了这个分离（双标图）。

塌陷点提醒
1. 不写解释方差比例 → 读者不知道这两轴代表多少信息；
2. 不同量纲的变量直接 PCA → 被量纲最大的变量支配（本函数默认逐列 z-score）；
3. 只画点不画椭圆/凸包 → 组间是否真有差异看不出来。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.patches import Ellipse

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_bool_mask, as_labels, as_matrix, cat_color, style_marker

#: 95% 置信椭圆的卡方分位（2 自由度）
_CHI2_95 = 5.991


def _ellipse_axes(points: np.ndarray) -> tuple[float, float, float, float, float]:
    """返回 (中心x, 中心y, 宽, 高, 角度)，宽高为 95% 置信椭圆轴长。"""
    if points.shape[0] < 4:
        # 三点估出的协方差几乎是退化的，卡方椭圆会变成一条穿出画框的长条；
        # 与其画错，不如不画。
        return 0.0, 0.0, 0.0, 0.0, 0.0
    cov = np.cov(points, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    vals = np.clip(vals, 0.0, None)
    angle = float(np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0])))
    width = 2.0 * float(np.sqrt(_CHI2_95 * vals[0]))
    height = 2.0 * float(np.sqrt(_CHI2_95 * vals[1])) if vals.size > 1 else width
    cx, cy = points.mean(axis=0)
    return float(cx), float(cy), width, height, angle


def pca(ax=None, matrix: Any | None = None, *, data: Any | None = None,
        groups: Any | None = None, labels: Sequence[str] | None = None,
        ellipse: bool = True, scale: bool = True, biplot: bool = False,
        feature_names: Sequence[str] | None = None, annotate: bool = False,
        legend: bool = True, s: float = 24.0):
    """画 PCA 得分图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    matrix : 2D array, optional
        样本 × 变量矩阵（``n_samples × n_features``），不接受 NaN。
    data : Mapping, optional
        ``{"matrix": …, "groups": …, "labels": …}``（给了就覆盖同名参数）。
    groups : Mapping[str, mask] | sequence of str, optional
        分组（掩码或等长标签序列）；每组画一个 95% 椭圆。
    labels : sequence of str, optional
        样本标签（与样本数等长），用于 ``annotate`` 时取用。
    ellipse : bool
        是否画 95% 置信椭圆（组内样本 ≥3 时）。
    scale : bool
        是否逐变量 z-score（默认是；量纲不同时必须开）。
    biplot : bool
        是否叠加变量载荷箭头（变量数建议 ≤ 8）。
    feature_names : sequence of str, optional
        变量名（双标图箭头标注）；缺省用 V1..Vp。
    annotate : bool
        是否标注解释方差百分比（强烈建议保留）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        matrix = _base.pick(data, "matrix", "X", default=matrix)
        groups = _base.pick(data, "groups", "labels", default=groups)
        labels = _base.pick(data, "sample_labels", default=labels)
    if matrix is None:
        raise ValueError("pca(): 缺少 matrix（样本 × 变量）")
    X = as_matrix(matrix, "matrix", caller="pca").astype(float)
    n, p = X.shape
    if n < 3:
        raise ValueError(f"pca(): 至少需要 3 个样本（收到 {n} 个）")
    if p < 2:
        raise ValueError(f"pca(): 至少需要 2 个变量（收到 {p} 个）")

    if scale:
        sd = X.std(axis=0, ddof=1)
        sd[sd == 0] = 1.0
        Xc = (X - X.mean(axis=0)) / sd
    else:
        Xc = X - X.mean(axis=0)

    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    scores = U * S
    var = S ** 2
    ratio = var / var.sum() if var.sum() > 0 else np.zeros_like(var)
    ev = ratio[:2] * 100.0
    if ev.size < 2:
        ev = np.pad(ev, (0, 2 - ev.size))

    if groups is not None:
        if isinstance(groups, Mapping):
            masks = {str(k): as_bool_mask(v, n, f"groups[{k!r}]", caller="pca")
                     for k, v in groups.items()}
        else:
            arr = np.asarray(groups)
            if arr.ndim != 1 or arr.size != n:
                raise ValueError(f"pca(): groups 需要与样本数 {n} 等长的标签序列")
            masks = {name: np.asarray([str(v) == name for v in arr], dtype=bool)
                     for name in dict.fromkeys(str(v) for v in arr)}
        for i, (name, mask) in enumerate(masks.items()):
            color = cat_color(i)
            ax.scatter(scores[mask, 0], scores[mask, 1], s=float(s), color=color,
                       marker=style_marker(i), edgecolors="white", linewidths=0.5,
                       alpha=0.92, zorder=3, label=f"{name}（n={int(mask.sum())}）")
            if ellipse and mask.sum() >= 4:
                cx, cy, w, h, ang = _ellipse_axes(scores[mask, :2])
                ax.add_patch(Ellipse((cx, cy), w, h, angle=ang, facecolor="none",
                                     edgecolor=color, lw=0.9, ls=(0, (4, 3)), zorder=2))
    else:
        ax.scatter(scores[:, 0], scores[:, 1], s=float(s), color=_pal.BLUE,
                   edgecolors="white", linewidths=0.5, alpha=0.92, zorder=3)

    if biplot:
        if feature_names is None:
            raise ValueError("pca(): 双标图必须给 feature_names（没有名字的箭头读不出含义）")
        names = as_labels(feature_names, p, "feature_names", caller="pca")
        loads = Vt[:2].T  # p × 2
        reach = float(np.max(np.abs(scores[:, :2]))) or 1.0
        scale_f = 0.75 * reach / (float(np.max(np.abs(loads))) or 1.0)
        tips = loads * scale_f
        for j in range(p):
            tx, ty = float(tips[j, 0]), float(tips[j, 1])
            ax.annotate("", xy=(tx, ty), xytext=(0, 0),
                        arrowprops=dict(arrowstyle="-|>", color=_pal.INK_SOFT,
                                        lw=0.85, alpha=0.75, shrinkA=0.0,
                                        shrinkB=0.0, mutation_scale=6.5))
            # 名字沿箭头方向甩到端点外侧：中心附近的箭头端点容易挤在一起
            norm = float(np.hypot(tx, ty)) or 1.0
            off = (5.0 * tx / norm, 5.0 * ty / norm)
            ha = "left" if off[0] >= 0 else "right"
            va = "bottom" if off[1] >= 0 else "top"
            ax.annotate(names[j], xy=(tx, ty), xytext=off, textcoords="offset points",
                        ha=ha, va=va, fontsize=_typo.TEXT_SIZES["footnote"],
                        color=_pal.INK_SOFT, zorder=5)

    if biplot:
        # 箭头端点常落在得分范围之外：把视野撑到能看见箭头和名字（再留 8% 余量）
        ax.update_datalim(np.vstack([[0.0, 0.0], np.asarray(tips, dtype=float)]))
        ax.autoscale_view()
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        padx, pady = (x1 - x0) * 0.08, (y1 - y0) * 0.08
        ax.set_xlim(x0 - padx, x1 + padx)
        ax.set_ylim(y0 - pady, y1 + pady)
    ax.axhline(0.0, color=_pal.GREY_LIGHT, lw=0.8, zorder=1.1)
    ax.axvline(0.0, color=_pal.GREY_LIGHT, lw=0.8, zorder=1.1)
    ax.set_xlabel(f"PC1（{ev[0]:.1f}%）", fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylabel(f"PC2（{ev[1]:.1f}%）", fontsize=_typo.TEXT_SIZES["label"])
    if annotate:
        xy, ha, va = _base.free_corner(ax, scores[:, 0], scores[:, 1])
        ax.annotate(f"累计解释方差 {ev[0] + ev[1]:.1f}%", xy=xy, xycoords="axes fraction",
                    ha=ha, va=va, fontsize=_typo.TEXT_SIZES["footnote"],
                    color=_pal.INK_SOFT)
    if legend and groups is not None:
        _base.legend(ax, markerscale=1.2)
    return ax


__all__ = ["pca"]