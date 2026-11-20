# -*- coding: utf-8 -*-
"""scatter —— 散点图（主体分布 + 高亮分组 + 可选回归线与置信带）。

**这张图要让读者看到什么**：两量的关系方向与离散程度，以及被单独强调的那组点
（离群/关键样本）偏离整体到哪里。

塌陷点提醒
1. 点太大太实 → 重叠成色块，降面积、留白边、必要时调 alpha；
2. 每个点都标 ID → 只标本图要讨论的 1–3 个点；
3. 强行画回归线却不给 R²/n → 读者无法判断这条线是否可信。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_bool_mask, check_len, style_marker

#: 背景点云（其它样本/对照）——必须退后，不与主体争视觉
_BG_COLOR = _pal.GREY_LIGHT


def _group_masks(groups: Any, n: int) -> dict[str, np.ndarray]:
    """把 groups 统一成 ``{组名: 布尔掩码}``。"""
    if isinstance(groups, Mapping):
        masks = {str(k): as_bool_mask(v, n, f"groups[{k!r}]", caller="scatter")
                 for k, v in groups.items()}
    else:
        arr = np.asarray(groups)
        if arr.ndim != 1:
            raise ValueError(f"scatter(): groups 需要一维标签序列（收到 {arr.ndim} 维）")
        check_len("groups", arr, n, caller="scatter")
        masks = {name: np.asarray([str(v) == name for v in arr], dtype=bool)
                 for name in dict.fromkeys(str(v) for v in arr)}
    if not masks:
        raise ValueError("scatter(): groups 为空")
    return masks


def scatter(ax=None, x: Any | None = None, y: Any | None = None, *,
            data: Any | None = None, background: Any | None = None,
            groups: Any | None = None, highlight: Any | None = None, s: float = 22.0,
            xlabel: str | None = None, ylabel: str | None = None, legend: bool = True,
            equal: bool = False, annotate: Any | None = None,
            annotate_offset: tuple[float, float] = (6, 5), alpha: float = 0.9,
            labels: Sequence[str] | None = None, fit: bool = False,
            fit_band: bool = True):
    """画散点图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    x, y : sequence of float, optional
        散点坐标，长度必须一致；也可用 ``data={"x":…, "y":…}``。
    data : Mapping, optional
        数据字典（``x`` / ``y`` / ``background`` / ``groups``）。
    background : (sequence, sequence) | Mapping[str, (seq, seq)], optional
        背景点云（对照/全体样本），浅灰小点。
    groups : Mapping[str, mask] | sequence of str, optional
        分组：掩码/下标映射，或与点等长的组名序列。默认单色（蓝）。
    highlight : mask, optional
        要强调的点（下标或布尔掩码）；其余点退成浅灰。
    s : float
        点面积（默认 22，约 4.7pt 直径）。
    annotate : sequence of int, optional
        只给这几个点加文字标注。
    labels : sequence of str, optional
        与点等长的标签，供 ``annotate`` 使用。
    fit : bool
        是否叠 OLS 回归线（并标 R²/n）；置信带由 ``fit_band`` 控制。
    equal : bool
        是否等比例（空间/几何散点必须）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        x = _base.pick(data, "x", default=x)
        y = _base.pick(data, "y", default=y)
        background = _base.pick(data, "background", default=background)
        groups = _base.pick(data, "groups", "labels", default=groups)
    if x is None or y is None:
        raise ValueError("scatter(): 需要 x 与 y（或传 data={'x':…, 'y':…}）")

    xs = as_1d(x, "x", caller="scatter")
    ys = as_1d(y, "y", caller="scatter")
    check_len("y", ys, xs.size, caller="scatter")
    if xs.size < 2:
        raise ValueError(f"scatter(): 至少需要 2 个点（收到 {xs.size} 个）")
    if float(s) <= 0:
        raise ValueError(f"scatter(): s 必须为正（收到 {s}）")

    if background is not None:
        bg_items = (background.items() if isinstance(background, Mapping)
                    else [(None, background)])
        for name, pair in bg_items:
            bx, by = pair
            bx_a = as_1d(bx, "background.x", caller="scatter")
            by_a = as_1d(by, "background.y", caller="scatter")
            check_len("background.y", by_a, bx_a.size, caller="scatter")
            ax.scatter(bx_a, by_a, s=float(s) * 0.55, color=_BG_COLOR, linewidths=0,
                       alpha=0.85, zorder=1, rasterized=True,
                       label=str(name) if name else None)

    if groups is not None:
        masks = _group_masks(groups, xs.size)
        for i, (name, mask) in enumerate(masks.items()):
            color = _pal.CATEGORICAL[i % len(_pal.CATEGORICAL)]
            ax.scatter(xs[mask], ys[mask], s=float(s), color=color, marker=style_marker(i),
                       linewidths=0.5, edgecolors="white", alpha=float(alpha), zorder=3,
                       label=str(name))
    elif highlight is not None:
        hi = as_bool_mask(highlight, xs.size, "highlight", caller="scatter")
        rest = ~hi
        if rest.any():
            ax.scatter(xs[rest], ys[rest], s=float(s) * 0.9, color=_pal.GREY_LIGHT,
                       linewidths=0, alpha=0.9, zorder=2, label="其余样本")
        ax.scatter(xs[hi], ys[hi], s=float(s) * 1.25, color=_pal.HIGHLIGHT,
                   linewidths=0.5, edgecolors="white", alpha=1.0, zorder=4,
                   label="关键样本")
    else:
        ax.scatter(xs, ys, s=float(s), color=_pal.BLUE, linewidths=0.5,
                   edgecolors="white", alpha=float(alpha), zorder=3)

    if fit:
        _base.regression(ax, xs, ys, band=fit_band)

    if annotate is not None:
        for i in [int(v) for v in np.ravel(np.asarray(annotate))]:
            if not 0 <= i < xs.size:
                raise ValueError(f"scatter(): annotate 下标 {i} 越界（0..{xs.size - 1}）")
            txt = str(labels[i]) if labels is not None and i < len(labels) else f"#{i + 1}"
            _base.annotate_point(ax, xs[i], ys[i], txt, xytext=annotate_offset,
                                 color=_pal.INK_SOFT)

    _common.set_labels(ax, xlabel=xlabel)
    _common.set_labels(ax, ylabel=ylabel)
    if equal:
        _base.equal_aspect(ax)
    if legend:
        _base.legend(ax, markerscale=1.15)
    return ax


__all__ = ["scatter"]