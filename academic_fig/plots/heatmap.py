# -*- coding: utf-8 -*-
"""heatmap —— 热力图（矩阵 + colorbar；支持 sequential / diverging / discrete 三套色阶）。"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_labels, as_matrix

#: 单元格之间的白线宽度（白纸风格：用留白分隔，不用黑框）
_CELL_LW = 0.7
#: 色条宽度 / 与绘图区的间距（按 axes 宽度分数；高度由 ``set_box_aspect(None)`` 拉满）
_CBAR_W = 0.046
_CBAR_PAD = 0.02


def heatmap(ax=None, matrix: Any | None = None, *, data: Any | None = None,
            rows: Sequence[str] | None = None,
            cols: Sequence[str] | None = None, kind: str = "seq",
            cbar: bool = True, cbar_label: str | None = None,
            vmin: float | None = None, vmax: float | None = None,
            center: float | None = None, annotate: bool | str = False,
            fmt: str = "{:.2f}", bins: int = 7, xlabel: str | None = None,
            ylabel: str | None = None, rotate_cols: float | None = None,
            row_zscore: bool = False):
    """画热力图。

    **这张图要让读者看到什么**：矩阵里的成块结构（哪一行/列同高同低），
    以及极值落在哪个格子——不是让读者去逐个读数字。

    塌陷点提醒
    1. 用 rainbow/jet → 感知不均匀且像 90 年代论文，改用本包 seq/div/disc 色阶；
    2. 没有 colorbar 或没写单位 → 颜色无法解释；
    3. 行内量纲差异大却不做 z-score → 大片同色，只剩一两行有对比。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    matrix : 2D array, optional
        数值矩阵（行 × 列），不接受 NaN（先补/删）。
    data : Mapping, optional
        ``{"matrix": …, "rows": …, "cols": …}``（给了就覆盖同名参数）。
    rows, cols : sequence of str, optional
        行/列标签，长度必须与矩阵一致；缺省用 1..n。
    kind : {"seq", "div", "disc"}
        ``seq`` 单向量（幅值）；``div`` 双向量（有正负/围绕基准，默认以 0 为中心）；
        ``disc`` 离散分档（分类型强度，利于印刷）。
    cbar : bool
        是否画 colorbar（无边框、刻度朝内）。
    cbar_label : str, optional
        colorbar 轴标签（写清量纲/单位）。
    vmin, vmax : float, optional
        色阶范围；``div`` 时若只给一边会自动对称。
    center : float, optional
        ``div`` 的中心值，默认 0。
    annotate : bool | {"auto"}
        是否在格子里标数值；``"auto"`` 只在矩阵较小时（≤ 6×6）标。
    bins : int
        ``disc`` 的分档数（3–12）。
    row_zscore : bool
        是否先对每行做 z-score（跨行量纲不可比时必须开，并在图注写明）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        matrix = _base.pick(data, "matrix", "values", default=matrix)
        rows = _base.pick(data, "rows", "index", default=rows)
        cols = _base.pick(data, "cols", "columns", default=cols)
    if matrix is None:
        raise ValueError("heatmap(): 缺少 matrix（或传 data={'matrix': …}）")
    m = as_matrix(matrix, "matrix", caller="heatmap")
    if row_zscore:
        mu = m.mean(axis=1, keepdims=True)
        sd = m.std(axis=1, keepdims=True)
        sd[sd == 0] = 1.0
        m = (m - mu) / sd
    n_row, n_col = m.shape
    if min(n_row, n_col) < 1:
        raise ValueError("heatmap(): 矩阵至少要有 1 行 1 列")
    row_names = as_labels(rows, n_row, "rows", caller="heatmap")
    col_names = as_labels(cols, n_col, "cols", caller="heatmap")
    kind_l = str(kind).lower()
    if kind_l not in ("seq", "div", "disc"):
        raise ValueError(f"heatmap(): kind 只支持 'seq'/'div'/'disc'（收到 {kind!r}）")
    if kind_l == "disc" and not 3 <= int(bins) <= 12:
        raise ValueError(f"heatmap(): bins 应在 3–12（收到 {bins}）")

    if vmin is None:
        vmin = float(np.min(m)) if kind_l != "div" else None
    if vmax is None:
        vmax = float(np.max(m)) if kind_l != "div" else None
    if kind_l == "div":
        c = 0.0 if center is None else float(center)
        if vmin is None and vmax is None:
            span = float(np.max(np.abs(m - c))) or 1.0
            vmin, vmax = c - span, c + span
        elif vmin is None:
            vmin = c - (float(vmax) - c)
        elif vmax is None:
            vmax = c + (c - float(vmin))
        if float(vmax) <= float(vmin):
            raise ValueError(f"heatmap(): div 的 vmax({vmax}) 必须大于 vmin({vmin})")

    norm = None
    disc_ticks = None
    if kind_l == "seq":
        cmap = _pal.cmap_seq()
    elif kind_l == "div":
        cmap = _pal.cmap_div()
    else:
        from matplotlib.colors import BoundaryNorm
        nb = int(bins)
        cmap = _pal.cmap_disc(nb)
        # 离散分档要「整数对齐」：数据本身是整数档（0/1/2…）时，分档边界放在
        # x.5 上，色条刻度就是 0、1、2…；否则色条会出现 0.000/0.857/… 这种
        # 半档读数（R-11）。
        integral = bool(np.all(np.isclose(m, np.round(m))) and np.all(np.isfinite(m)))
        if integral:
            lo = float(np.min(m))
            hi = float(np.max(m))
            if hi - lo + 1 < nb:      # 数据档数少于要求的分档数：按数据实际档数收窄
                nb = max(1, int(hi - lo) + 1)
                cmap = _pal.cmap_disc(nb)
            edges = np.arange(lo - 0.5, lo - 0.5 + nb + 1, dtype=float)
            disc_ticks = np.arange(lo, lo + nb, dtype=float)
        else:
            edges = np.linspace(float(vmin), float(vmax), nb + 1)
            disc_ticks = (edges[:-1] + edges[1:]) / 2.0
        edges[-1] += 1e-9
        norm = BoundaryNorm(edges, cmap.N)

    x_edges = np.arange(n_col + 1) - 0.5
    y_edges = np.arange(n_row + 1) - 0.5
    mesh = ax.pcolormesh(x_edges, y_edges, m, cmap=cmap, norm=norm,
                         vmin=None if norm is not None else vmin,
                         vmax=None if norm is not None else vmax,
                         edgecolors=_pal.PAPER, linewidth=_CELL_LW, shading="flat")
    ax.set_xlim(x_edges[0], x_edges[-1])
    ax.set_ylim(y_edges[-1], y_edges[0])  # 第一行在顶部，符合矩阵阅读习惯
    ax.set_xticks(np.arange(n_col), col_names)
    ax.set_yticks(np.arange(n_row), row_names)
    angle = rotate_cols
    if angle is None:
        angle = 0.0 if max((len(s) for s in col_names), default=0) <= 4 else 30.0
    ax.tick_params(axis="x", labelrotation=float(angle))
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right" if float(angle) else "center")
    ax.tick_params(length=0)  # 矩阵图不需要刻度线
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=_typo.TEXT_SIZES["label"])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=_typo.TEXT_SIZES["label"])

    show_nums = annotate is True or (annotate == "auto" and max(n_row, n_col) <= 6)
    if show_nums:
        span = float(vmax) - float(vmin) if float(vmax) > float(vmin) else 1.0
        mid = (float(vmax) + float(vmin)) / 2.0
        for i in range(n_row):
            for j in range(n_col):
                val = float(m[i, j])
                dark = abs(val - mid) > 0.42 * span and kind_l != "div"
                color = _pal.PAPER if dark else _pal.INK
                ax.text(j, i, fmt.format(val), ha="center", va="center",
                        fontsize=_typo.TEXT_SIZES["footnote"] - 0.5, color=color)

    if cbar:
        # 色条高度必须等于绘图区（ARCH §3）：``colorbar(ax=…)`` 走 make_axes，会给
        # cax 设 ``box_aspect=20``（默认 aspect），宽扁面板上因此只画到 65–85% 高，
        # 而调大 aspect 又只换得「色条变细、仍不等高」。布局（fraction/pad）照旧交给
        # make_axes，只把 box_aspect 清掉，cax 就填满自己的位置框。
        cb = ax.figure.colorbar(mesh, ax=ax, fraction=_CBAR_W, pad=_CBAR_PAD,
                                ticks=disc_ticks)
        cb.ax.set_box_aspect(None)
        cb.outline.set_visible(False)
        if disc_ticks is not None:
            cb.set_ticklabels([f"{t:g}" for t in disc_ticks])
        cb.ax.tick_params(direction="in", width=0.7, length=2.6,
                          labelsize=_typo.TEXT_SIZES["tick"] - 1.0, color=_pal.INK)
        if cbar_label:
            cb.set_label(cbar_label, fontsize=_typo.TEXT_SIZES["label"] - 1.0, color=_pal.INK)
    return ax


__all__ = ["heatmap"]