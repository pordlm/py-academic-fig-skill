# -*- coding: utf-8 -*-
"""stacked_bar —— 堆叠柱（组成占比 / 累计贡献；只在「部分与整体」明确的场合用）。

**这张图要让读者看到什么**：总量在各成分间的分配，以及总量随时间/类别的变化。

塌陷点提醒
1. 成分超过 5 类还堆叠 → 中间类无法比较，改堆叠面积图或分面；
2. 用饱和彩虹配色 → 改用本包 tints（低饱和、同族明度递进）；
3. 不给总量或不给百分比 → 读者不知道分母是什么。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import _common
from . import base as _base
from ._common import as_1d, as_labels, check_len

#: 堆叠用的低饱和填充序列（同族明度递进，印刷也分得开）
def stack_colors(n: int) -> list[str]:
    """返回 n 个低饱和堆叠色（蓝→青灰→赭→砖红→苔绿→紫灰）。"""
    base = list(_pal.CATEGORICAL[:6])
    if n <= len(base):
        alphas = np.linspace(0.22, 0.75, n)
        return [_pal.tint(base[i % 6], float(a)) for i, a in enumerate(alphas)]
    return [_pal.CATEGORICAL[i % len(_pal.CATEGORICAL)] for i in range(n)]


def stacked_bar(ax=None, labels: Sequence[str] | None = None, stacks: Any | None = None, *,
                data: Any | None = None, normalize: bool = False,
                ylabel: str | None = None, xlabel: str | None = None,
                width: float = 0.66, legend: bool = True,
                totals: bool = False, total_fmt: str = "{:.0f}",
                edge: bool = True):
    """画堆叠柱状图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    labels : sequence of str, optional
        横轴类别名。
    stacks : Mapping[str, sequence] | 2D array, optional
        成分名 → 每类别数值；二维数组按 ``(成分, 类别)`` 解释。
    data : Mapping, optional
        ``{"labels": …, "stacks": …}``（给了就覆盖同名参数）。
    normalize : bool
        是否按列（每个类别）归一化到 100%——「占比」场景必须开。
    totals : bool
        是否在柱顶标总量（``normalize=True`` 时自动关闭）。
    legend : bool
        是否画图例（放柱外侧，不压数据）。
    edge : bool
        是否描 0.6pt 白边把相邻色块分开（同族色相近时必需）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        labels = _base.pick(data, "labels", "categories", default=labels)
        stacks = _base.pick(data, "stacks", "values", "groups", default=stacks)
    if stacks is None:
        raise ValueError("stacked_bar(): 缺少 stacks（成分 → 每类别数值）")

    if isinstance(stacks, Mapping):
        names = [str(k) for k in stacks]
        seqs = [as_1d(v, f"stacks[{k!r}]", caller="stacked_bar") for k, v in stacks.items()]
    else:
        arr = np.asarray(stacks, dtype=float)
        if arr.ndim != 2:
            raise ValueError(f"stacked_bar(): stacks 需要二维（或 Mapping），收到 {arr.ndim} 维")
        names = [f"成分{i + 1}" for i in range(arr.shape[0])]
        seqs = [arr[i] for i in range(arr.shape[0])]
    if not seqs:
        raise ValueError("stacked_bar(): stacks 为空")
    m = np.vstack(seqs)
    n_cat = m.shape[1]
    for i, s in enumerate(seqs):
        check_len(f"stacks[{names[i]!r}]", s, n_cat, caller="stacked_bar")
    if np.any(m < 0):
        raise ValueError("stacked_bar(): stacks 含负值；堆叠图只接受非负数据"
                         "（有正负请用 grouped_bar 或发散堆叠）")
    cats = as_labels(labels, n_cat, "labels", caller="stacked_bar")

    if normalize:
        col_sum = m.sum(axis=0, keepdims=True)
        if np.any(col_sum <= 0):
            raise ValueError("stacked_bar(): 存在总量为 0 的类别，无法归一化")
        plot_m = m / col_sum * 100.0
        if totals:
            totals = False
    else:
        plot_m = m

    colors = stack_colors(len(names))
    pos = np.arange(n_cat)
    bottom = np.zeros(n_cat)
    for i, name in enumerate(names):
        ax.bar(pos, plot_m[i], width=float(width), bottom=bottom, color=colors[i],
               edgecolor=_pal.PAPER if edge else "none", linewidth=0.6,
               label=name, zorder=3)
        bottom += plot_m[i]

    if totals:
        for x, tot in zip(pos, m.sum(axis=0)):
            ax.annotate(total_fmt.format(tot), xy=(x, tot), xytext=(0, 3),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=_typo.TEXT_SIZES["footnote"], color=_pal.INK_SOFT)

    ax.set_xticks(pos, cats)
    ax.set_ylabel((ylabel or ("占比（%）" if normalize else "数量")),
                  fontsize=_typo.TEXT_SIZES["label"])
    _common.set_labels(ax, xlabel=xlabel)
    top = float(plot_m.sum(axis=0).max())
    ax.set_ylim(0.0, top * (1.02 if normalize else 1.12))
    if legend:
        _base.legend(ax, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    _common.auto_rotate_x(ax)
    return ax


__all__ = ["stacked_bar", "stack_colors"]