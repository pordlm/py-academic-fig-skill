# -*- coding: utf-8 -*-
"""confusion —— 混淆矩阵（count 或按行归一化；单元格直接标数值）。

**这张图要让读者看到什么**：错误集中在哪些「真实类 → 预测类」的格子上，
而不是只看总体准确率。

塌陷点提醒
1. 只报总体准确率不给矩阵 → 掩盖了类别不平衡下的塌陷；
2. 不给颜色刻度和单位（count / %）→ 读者读不出强度；
3. 用彩虹色阶 → 改用单色 seq（本包默认），并让文字颜色随底色反转保证可读。
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_labels, as_matrix


def confusion(ax=None, matrix: Any | None = None, *, data: Any | None = None,
              labels: Sequence[str] | None = None, normalize: bool = False,
              cbar: bool = False, cbar_label: str | None = None,
              xlabel: str = "预测类别", ylabel: str = "真实类别",
              fmt: str | None = None, cmap: str = "seq",
              two_line: bool = False):
    """画混淆矩阵。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    matrix : 2D array, optional
        ``n_classes × n_classes`` 计数矩阵（行=真实，列=预测）。
    data : Mapping, optional
        ``{"matrix": …, "labels": …}``（给了就覆盖同名参数）。
    labels : sequence of str, optional
        类别名，长度须等于矩阵边长；缺省用 C1..Cn。
    normalize : bool
        是否按行归一化（显示 recall 分布，百分比，色阶 0–100%）。
    cbar : bool
        是否画 colorbar；默认关（矩阵小、数值已标出）。
    fmt : str, optional
        数值格式。``normalize=True`` 默认 ``"{:.0%}"``；否则默认 ``"{:.0f}"``
        （计数是整数，但统一走浮点格式，传 ``"{:d}"`` 会因 ``float`` 入参而报错）。
    cmap : {"seq", "div"}
        色阶；混淆矩阵一律建议 ``seq``（0 到最大值）。
    two_line : bool
        ``True`` 时每格标两行「计数 + 行占比」，一眼同时读到绝对量和该类召回率；
        与 ``normalize=True`` 互斥（已归一化就只标比例）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。

    Examples
    --------
    >>> afg.plots.confusion(ax, [[45, 5], [8, 42]], labels=["正常", "故障"], two_line=True)
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        matrix = _base.pick(data, "matrix", "cm", default=matrix)
        labels = _base.pick(data, "labels", "classes", default=labels)
    if matrix is None:
        raise ValueError("confusion(): 缺少 matrix（真实 × 预测 计数矩阵）")
    m = as_matrix(matrix, "matrix", caller="confusion")
    n_row, n_col = m.shape
    if n_row != n_col:
        raise ValueError(f"confusion(): 矩阵必须是方阵（收到 {n_row}×{n_col}）")
    n = n_row
    names = as_labels(labels, n, "labels", caller="confusion")
    if np.any(m < 0):
        raise ValueError("confusion(): 矩阵含负值；计数/比例都不能为负")
    if two_line and normalize:
        raise ValueError("confusion(): two_line 与 normalize 互斥——要么标「计数+占比」，"
                         "要么整格标比例")

    row_sum = m.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    ratio = m / row_sum
    if normalize:
        shown = ratio
        text_fmt = fmt or "{:.0%}"
        vmax = 1.0
    else:
        shown = m
        text_fmt = fmt or "{:.0f}"
        vmax = float(m.max()) or 1.0

    if cmap == "div":
        cm = _pal.cmap_div()
    else:
        # 论文插图里混淆矩阵只是「强度示意」，底色不该比正文更重：
        # 用纸色→低饱和蓝的浅色阶，最深也只到 52% 的蓝。
        from matplotlib.colors import LinearSegmentedColormap

        cm = LinearSegmentedColormap.from_list(
            "paper_blue",
            [_pal.PAPER,
             _pal.tint(_pal.BLUE, 0.10),
             _pal.tint(_pal.BLUE, 0.22),
             _pal.tint(_pal.BLUE, 0.36),
             _pal.tint(_pal.BLUE, 0.52)])
    mesh = ax.pcolormesh(np.arange(n + 1) - 0.5, np.arange(n + 1) - 0.5, shown,
                         cmap=cm, vmin=0.0, vmax=vmax,
                         edgecolors=_pal.PAPER, linewidth=0.8, shading="flat")
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks(np.arange(n), names)
    ax.set_yticks(np.arange(n), names)
    ax.tick_params(length=0)
    ax.set_xlabel(xlabel, fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylabel(ylabel, fontsize=_typo.TEXT_SIZES["label"])

    for i in range(n):
        for j in range(n):
            val = float(shown[i, j])
            if two_line:
                # 第一行计数、第二行该真实类的召回比例（小一号字，仍用 tick 字号免得糊）
                txt = "{:.0f}\n{:.0%}".format(val, float(ratio[i, j]))
            else:
                txt = text_fmt.format(val)
            # 浅色阶上墨色始终可读；只有全零格用浅灰，避免白底白字
            ax.text(j, i, txt, ha="center", va="center",
                    fontsize=_typo.TEXT_SIZES["tick"],
                    linespacing=1.15,
                    color=_pal.INK if val > 0 else _pal.GREY)
    if cbar:
        cb = ax.figure.colorbar(mesh, ax=ax, fraction=0.046, pad=0.02)
        cb.outline.set_visible(False)
        cb.ax.tick_params(direction="in", width=0.7, length=2.6,
                          labelsize=_typo.TEXT_SIZES["tick"] - 1.0)
        if cbar_label:
            cb.set_label(cbar_label, fontsize=_typo.TEXT_SIZES["label"] - 1.0, color=_pal.INK)
    return ax


__all__ = ["confusion"]