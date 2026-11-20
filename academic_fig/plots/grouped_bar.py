# -*- coding: utf-8 -*-
"""grouped_bar —— 分组柱状图（同一批类别下的多方案 / 多年度对比）。"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from matplotlib.patches import Patch

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_labels, cat_color

#: 每组的填充透明度（低饱和：用 tint 混白，而不是 alpha 叠灰）
_FILL_ALPHA = 0.34
#: 第 2 组起加纹理：黑白打印也能区分
_HATCHES = ("", "///", "...", "\\\\\\")


def _as_group_matrix(groups: Any, n_cat_hint: int | None = None) -> dict[str, np.ndarray]:
    """把分组数据统一成 ``{组名: 一维数组}``（各组等长）。"""
    if isinstance(groups, Mapping):
        items = [(str(k), v) for k, v in groups.items()]
    elif isinstance(groups, (list, tuple)) and groups and isinstance(groups[0], (list, tuple)) \
            and len(groups[0]) == 2 and isinstance(groups[0][0], str):
        items = [(str(k), v) for k, v in groups]
    else:
        arr = np.asarray(groups, dtype=float)
        if arr.ndim == 1:
            items = [("Series 1", arr)]
        elif arr.ndim == 2:
            if n_cat_hint is None:
                rows_are_groups = arr.shape[0] <= arr.shape[1]
            elif arr.shape[1] == n_cat_hint:
                rows_are_groups = True
            elif arr.shape[0] == n_cat_hint:
                rows_are_groups = False
            else:
                raise ValueError(
                    f"grouped_bar(): groups 形状 {arr.shape} 与类别数 {n_cat_hint} 对不上"
                )
            items = ([(f"S{i + 1}", arr[i]) for i in range(arr.shape[0])] if rows_are_groups
                     else [(f"S{i + 1}", arr[:, i]) for i in range(arr.shape[1])])
        else:
            raise ValueError(f"grouped_bar(): groups 维度不支持（收到 {arr.ndim} 维）")
    if not items:
        raise ValueError("grouped_bar(): groups 为空；至少给一组数据")

    out: dict[str, np.ndarray] = {}
    for name, vals in items:
        out[name] = as_1d(vals, f"groups[{name!r}]", caller="grouped_bar")
    lens = {arr.size for arr in out.values()}
    if len(lens) != 1:
        detail = {k: int(v.size) for k, v in out.items()}
        raise ValueError(f"grouped_bar(): 各组长度不一致 {detail}")
    n_cat = lens.pop()
    if n_cat_hint is not None and n_cat != n_cat_hint:
        raise ValueError(f"grouped_bar(): groups 每组 {n_cat} 个值，与 labels 的 {n_cat_hint} 不一致")
    return out


def grouped_bar(ax=None, labels: Sequence[str] | None = None, groups: Any | None = None, *,
                data: Any | None = None, errors: Any | None = None,
                ylabel: str | None = None, xlabel: str | None = None,
                annotate: bool = False, annotate_fmt: str = "{:.2f}",
                width: float = 0.78, gap: float = 0.04, legend: bool = True,
                ylim: tuple[float, float] | None = None, hatch: bool = True):
    """画分组柱状图。

    **这张图要让读者看到什么**：同一批类别里，哪个方案/年度整体更高，
    以及差异是「普遍更高」还是「只在某一类上更高」。

    塌陷点提醒
    1. 组数超过 4 → 颜色+纹理都不够分，改用分面条形图；
    2. 每组都标数值 → 只标关键组或只标极值；
    3. 组内不留缝、外侧不留白 → 读者会把两组看成一整块。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时按期刊单栏尺寸新建。
    labels : sequence of str, optional
        类别名（横轴），``None`` 时用 1..n。
    groups : Mapping[str, sequence] | 2D array, optional
        组名 → 每类别的数值；二维数组按 ``(组, 类别)`` 解释。也可用 ``data=`` 字典。
    data : Mapping, optional
        ``{"labels": …, "groups": …, "errors": …}``（给了就覆盖同名参数）。
    errors : Mapping[str, sequence] | 2D array, optional
        与 ``groups`` 同形状的误差棒。
    ylabel, xlabel : str, optional
        轴标签。
    annotate : bool
        是否在柱顶标数值；默认关（每根柱都标数字是最典型的 AI 味）。
    width : float
        每组占用的横向宽度比例（0.3–1.0）。
    gap : float
        组内柱间距（相对单柱宽度）。
    legend : bool
        是否画图例。
    hatch : bool
        是否给第 2 组起加斜纹/点纹（黑白打印也能区分，不只靠颜色）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        labels = _base.pick(data, "labels", "categories", default=labels)
        groups = _base.pick(data, "groups", "values", default=groups)
        errors = _base.pick(data, "errors", "err", default=errors)
    if groups is None:
        raise ValueError("grouped_bar(): 缺少 groups；可用 grouped_bar(ax, labels, groups)")
    hint = len(labels) if labels is not None else None
    vals = _as_group_matrix(groups, hint)
    n_cat = next(iter(vals.values())).size
    names = as_labels(labels, n_cat, "labels", caller="grouped_bar")
    n_grp = len(vals)
    if not 0.3 <= float(width) <= 1.0:
        raise ValueError(f"grouped_bar(): width 应在 0.3–1.0（收到 {width}）")
    if not 0.0 <= float(gap) <= 0.5:
        raise ValueError(f"grouped_bar(): gap 应在 0–0.5（收到 {gap}）")

    err_map: dict[str, np.ndarray] | None = None
    if errors is not None:
        if isinstance(errors, Mapping) or (isinstance(errors, (list, tuple)) and errors
                                           and isinstance(errors[0], (list, tuple))
                                           and len(errors[0]) == 2
                                           and isinstance(errors[0][0], str)):
            err_map = _as_group_matrix(errors, n_cat)
            missing = sorted(set(vals) - set(err_map))
            if missing:
                raise ValueError(f"grouped_bar(): errors 缺少组 {missing}")
        else:
            err_arr = np.asarray(errors, dtype=float)
            if err_arr.shape != (n_grp, n_cat):
                raise ValueError(
                    f"grouped_bar(): errors 形状应为 {(n_grp, n_cat)}（收到 {err_arr.shape}）"
                )
            err_map = {k: err_arr[i] for i, k in enumerate(vals)}
        if np.any(np.stack(list(err_map.values())) < 0):
            raise ValueError("grouped_bar(): errors 含负值；误差棒长度必须 ≥0")

    bar_w = float(width) / n_grp
    base = np.arange(n_cat)
    offsets = (np.arange(n_grp) - (n_grp - 1) / 2.0) * bar_w * (1.0 + float(gap))
    handles = []
    containers = []
    for i, (name, arr) in enumerate(vals.items()):
        color = cat_color(i)
        hs = _HATCHES[i % len(_HATCHES)] if hatch else None
        kwargs = dict(width=bar_w * (1 - float(gap)), color=_pal.tint(color, _FILL_ALPHA),
                      edgecolor=color, linewidth=0.7, zorder=3, hatch=hs)
        if err_map is not None:
            kwargs.update(yerr=err_map[name], error_kw=dict(ecolor=_pal.GREY, elinewidth=0.8,
                                                            capsize=2.2, capthick=0.8))
        containers.append(ax.bar(base + offsets[i], arr, **kwargs))
        handles.append(Patch(facecolor=_pal.tint(color, _FILL_ALPHA), edgecolor=color,
                             linewidth=0.7, hatch=hs, label=str(name)))

    ax.set_xticks(base, names)
    _common.set_labels(ax, ylabel=ylabel)
    _common.set_labels(ax, xlabel=xlabel)
    if ylim is not None:
        lo, hi = float(ylim[0]), float(ylim[1])
        if hi <= lo:
            raise ValueError(f"grouped_bar(): ylim 上限必须大于下限（收到 {ylim}）")
        ax.set_ylim(lo, hi)
    if legend:
        # 分组柱通常顶满画框：先在上方留出图例带，再横向摆一行小色块，
        # 这样图例既不压柱体也不占右侧版面。
        top = 0.0
        for name, arr in vals.items():
            hi = float(np.max(arr))
            if err_map is not None:
                hi += float(np.max(err_map[name]))
            top = max(top, hi)
        if ylim is None and top > 0:
            ax.set_ylim(min(0.0, float(np.min(np.stack(list(vals.values()))))),
                        top * 1.22)
            loc, anchor = "upper left", (0.0, 1.0)
        else:
            loc, anchor = "lower left", (0.0, 1.015)
        _base.legend(ax, handles=handles, loc=loc, bbox_to_anchor=anchor,
                     ncol=min(len(handles), 4), handlelength=1.15, handleheight=0.85,
                     columnspacing=1.0, handletextpad=0.5, borderaxespad=0.0)

    if annotate:
        for i, arr in enumerate(vals.values()):
            for j, v in enumerate(arr):
                ax.annotate(annotate_fmt.format(v), xy=(base[j] + offsets[i], v),
                            xytext=(0, 2), textcoords="offset points",
                            ha="center", va="bottom",
                            fontsize=_typo.TEXT_SIZES["footnote"] - 1.0, color=_pal.INK_SOFT)
    _common.auto_rotate_x(ax)
    return ax


__all__ = ["grouped_bar"]