# -*- coding: utf-8 -*-
"""lollipop —— 棒棒糖图（排序后的类别比较 / 点图 / 与基线的偏差）。

**这张图要让读者看到什么**：一串类别按大小排好后的相对位置，以及少数几项
明显高出（或低于）其余项——它比柱图更轻，适合类别多（10–20 个）的排序比较。

塌陷点提醒
1. 不排序却画棒棒糖 → 读不出结构，应该按值排序（``sort=True`` 默认）；
2. 每根都标数值 → 只标极值/关键项；
3. 基线不在 0（或不在要对比的参考值）→ 读者会把「偏差」读成「绝对量」。
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_bool_mask, as_labels, check_len


def lollipop(ax=None, labels: Sequence[str] | None = None, values: Any | None = None, *,
             data: Any | None = None, xlabel: str | None = None,
             ylabel: str | None = None, sort: bool = True, ascending: bool = False,
             highlight: Any | None = None, annotate: Any | None = None,
             annotate_fmt: str = "{:.2f}", baseline: float = 0.0,
             horizontal: bool = True, top: int | None = None):
    """画棒棒糖图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    labels : sequence of str, optional
        类别名。
    values : sequence of float, optional
        每个类别的数值；也可用 ``data={"labels":…, "values":…}``。
    data : Mapping, optional
        数据字典（``labels`` / ``values``）。
    sort : bool
        是否按值排序（强烈建议开）。
    ascending : bool
        ``sort=True`` 时的排序方向。
    highlight : sequence of int | sequence of str, optional
        要强调的项（下标、布尔掩码或类别名）。
    annotate : bool | sequence, optional
        只标关键项数值；默认关。
    baseline : float
        竖线起点（0 或参考值）。
    horizontal : bool
        是否横排（类别名长时用，默认横排）。
    top : int, optional
        只显示排序后的前 ``top`` 项（长列表时用）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        labels = _base.pick(data, "labels", "categories", default=labels)
        values = _base.pick(data, "values", "value", default=values)
    if values is None:
        raise ValueError("lollipop(): 缺少 values（或传 data={'values': …}）")
    vals = as_1d(values, "values", caller="lollipop")
    names = as_labels(labels, vals.size, "labels", caller="lollipop")
    check_len("labels", names, vals.size, caller="lollipop")
    if vals.size == 0:
        raise ValueError("lollipop(): 数据为空")

    order = np.argsort(vals) if ascending else np.argsort(-vals)
    if top is not None:
        if int(top) <= 0:
            raise ValueError(f"lollipop(): top 必须为正（收到 {top}）")
        order = order[: int(top)]
    vals_s = vals[order]
    names_s = [names[i] for i in order]

    mask = np.zeros(vals_s.size, dtype=bool)
    if highlight is not None:
        if isinstance(highlight, (list, tuple, np.ndarray)) and not np.issubdtype(
                np.asarray(highlight).dtype, np.bool_):
            arr = np.asarray(highlight)
            if np.issubdtype(arr.dtype, np.number) and arr.max(initial=-1) >= vals.size:
                raise ValueError(f"lollipop(): highlight 下标越界（0..{vals.size - 1}）")
            if np.issubdtype(arr.dtype, np.number):
                mask[arr.astype(int)] = True
            else:
                wanted = {str(v) for v in arr}
                mask = np.array([nm in wanted for nm in names_s], dtype=bool)
        else:
            mask = as_bool_mask(highlight, vals_s.size, "highlight", caller="lollipop")

    pos = np.arange(vals_s.size)
    base_line = float(baseline)
    for i, (y, v) in enumerate(zip(pos, vals_s)):
        color = _pal.HIGHLIGHT if mask[i] else _pal.SLATE
        if horizontal:
            ax.plot([base_line, v], [y, y], color=_pal.GREY_LIGHT, lw=0.9, zorder=2,
                    solid_capstyle="round")
            ax.plot([v], [y], marker="o", ms=5.2, color=_pal.BLUE if mask[i] else color,
                    mec="white", mew=0.6, zorder=3)
        else:
            ax.plot([y, y], [base_line, v], color=_pal.GREY_LIGHT, lw=0.9, zorder=2,
                    solid_capstyle="round")
            ax.plot([y], [v], marker="o", ms=5.2, color=_pal.BLUE if mask[i] else color,
                    mec="white", mew=0.6, zorder=3)

    if horizontal:
        ax.axvline(base_line, color=_pal.GREY, lw=0.8, zorder=1.1)
        ax.set_yticks(pos, names_s)
        ax.invert_yaxis()
        _common.set_labels(ax, xlabel=xlabel)
        _common.set_labels(ax, ylabel=ylabel)
        lo = min(base_line, float(vals_s.min()))
        hi = max(base_line, float(vals_s.max()))
        pad = (hi - lo) * 0.08 or 1.0
        ax.set_xlim(lo - (pad if base_line == lo else 0), hi + pad)
    else:
        ax.axhline(base_line, color=_pal.GREY, lw=0.8, zorder=1.1)
        ax.set_xticks(pos, names_s)
        ax.tick_params(axis="x", labelrotation=0)
        _common.set_labels(ax, ylabel=ylabel)
        _common.set_labels(ax, xlabel=xlabel)

    if annotate is not None:
        if isinstance(annotate, bool):
            show = np.ones(vals_s.size, dtype=bool) if annotate else np.zeros(vals_s.size, bool)
        else:
            show = as_bool_mask(annotate, vals_s.size, "annotate", caller="lollipop")
        _base.annotate_bar(ax, pos[show], vals_s[show], fmt=annotate_fmt, horizontal=horizontal)
    return ax


__all__ = ["lollipop"]