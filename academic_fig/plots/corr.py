# -*- coding: utf-8 -*-
"""corr —— 相关矩阵热图（双色 cmap，可掩上三角，格内标相关系数）。

**这张图要让读者看到什么**：哪些变量成块共变、哪些几乎无关，
以及相关方向（正/负）——不是让读者逐个读小数。

塌陷点提醒
1. 用 rainbow/jet 表达正负 → 改用本包 div（蓝-白-砖红），零点视觉上必须居中；
2. 不标显著性/样本量 → 小样本的高相关不可信，图注要写 n；
3. 矩阵上下三角都画 → 信息重复且挤，默认掩上三角。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_labels, as_matrix


def corrcoef(matrix: Any, *, method: str = "pearson") -> tuple[np.ndarray, int]:
    """计算相关矩阵（numpy 实现，不含 scipy 依赖）。

    Returns
    -------
    (corr, n) : (ndarray, int)
        相关矩阵（p×p）与样本数。
    """
    X = as_matrix(matrix, "matrix", caller="corr").astype(float)
    if X.shape[0] < 3:
        raise ValueError(f"corr(): 至少需要 3 个样本（收到 {X.shape[0]} 个）")
    n, p = X.shape
    if p < 2:
        raise ValueError(f"corr(): 至少需要 2 个变量（收到 {p} 个）")

    def _rank(a: np.ndarray) -> np.ndarray:
        order = a.argsort()
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(a.size, dtype=float)
        # 处理并列：同值取平均秩
        vals, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
        if np.any(counts > 1):
            sums = np.zeros(vals.size)
            np.add.at(sums, inv, ranks)
            ranks = (sums / counts)[inv]
        return ranks

    if method == "spearman":
        X = np.column_stack([_rank(X[:, j]) for j in range(p)])
    elif method != "pearson":
        raise ValueError(f"corr(): method 只支持 'pearson'/'spearman'（收到 {method!r}）")

    sd = X.std(axis=0, ddof=1)
    sd[sd == 0] = 1e-12
    Z = (X - X.mean(axis=0)) / sd
    C = (Z.T @ Z) / (n - 1)
    return np.clip(C, -1.0, 1.0), n


def corr(ax=None, matrix: Any | None = None, *, data: Any | None = None,
         names: Sequence[str] | None = None, method: str = "pearson",
         mask_upper: bool = True, annotate: bool | str = True, fmt: str = "{:.2f}",
         cbar: bool = True, cbar_label: str | None = None, vmin: float = -1.0,
         vmax: float = 1.0, triangle: bool = False):
    """画相关矩阵热图。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    matrix : 2D array | ndarray, optional
        样本 × 变量矩阵（会先算相关），或已是方阵的相关矩阵。
    data : Mapping, optional
        ``{"matrix": …, "names": …}``（给了就覆盖同名参数）。
    names : sequence of str, optional
        变量名，长度等于变量数；缺省 V1..Vp。
    method : {"pearson", "spearman"}
        相关系数类型；顺序变量/有离群时用 spearman。
    mask_upper : bool
        是否掩掉上三角（避免重复信息）。
    annotate : bool | {"auto"}
        是否在格内写系数；``"auto"`` 在变量数 ≤ 10 时写。
    triangle : bool
        是否画下三角（掩上三角且不留空白）；默认 False 时保留方形矩阵。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        matrix = _base.pick(data, "matrix", "values", default=matrix)
        names = _base.pick(data, "names", "labels", default=names)
    if matrix is None:
        raise ValueError("corr(): 缺少 matrix（样本 × 变量，或相关矩阵）")
    M = np.asarray(matrix, dtype=float)
    if M.ndim != 2:
        raise ValueError(f"corr(): matrix 必须是二维（收到 {M.ndim} 维）")
    if M.shape[0] == M.shape[1] and np.allclose(M, M.T) and np.allclose(np.diag(M), 1.0):
        C, n = M, 0
        p = M.shape[0]
    else:
        C, n = corrcoef(M, method=method)
        p = C.shape[0]
    labels = as_labels(names, p, "names", caller="corr")

    shown = np.ma.array(C, mask=np.zeros_like(C, dtype=bool))
    if mask_upper:
        shown.mask = np.triu(np.ones_like(C, dtype=bool), k=1)

    # 低饱和双色：白纸为中心，正相关走浅砖红、负相关走浅蓝
    from matplotlib.colors import LinearSegmentedColormap

    cm = LinearSegmentedColormap.from_list(
        "paper_div",
        [_pal.tint(_pal.BLUE, 0.55), _pal.tint(_pal.BLUE, 0.26), _pal.PAPER,
         _pal.tint(_pal.CLAY, 0.26), _pal.tint(_pal.CLAY, 0.55)])
    # 对角线恒为 1，涂满色块只会抢走注意力：按中性色（0）填，数字照旧写 1.00
    fill = np.array(shown, dtype=float, copy=True)
    np.fill_diagonal(fill, 0.0)
    shown_fill = np.ma.array(fill, mask=np.ma.getmaskarray(shown))
    mesh = ax.pcolormesh(np.arange(p + 1) - 0.5, np.arange(p + 1) - 0.5, shown_fill,
                         cmap=cm, vmin=float(vmin), vmax=float(vmax),
                         edgecolors=_pal.PAPER, linewidth=0.7, shading="flat")
    ax.set_xlim(-0.5, p - 0.5)
    ax.set_ylim(p - 0.5, -0.5)
    ax.set_xticks(np.arange(p), labels, rotation=45 if p > 4 else 0)
    ax.tick_params(length=0)
    if p > 4:
        for lab in ax.get_xticklabels():
            lab.set_ha("right")
            lab.set_rotation_mode("anchor")
    ax.set_yticks(np.arange(p), labels if not mask_upper else
                  [lab if i == 0 or True else "" for i, lab in enumerate(labels)])

    # 单栏 3.35in 里塞 10×10 只有 0.2in 一格，写「-0.83」会顶到格线：
    # 先按格子实际宽度决定要不要标数字、标多大。
    try:
        cell_in = ax.get_window_extent().width / ax.figure.dpi / p
    except Exception:  # noqa: BLE001 - 无渲染器时按"能标"处理
        cell_in = 0.4
    if annotate == "auto":
        do_annot = cell_in >= 0.30
    else:
        do_annot = bool(annotate)
    num_fs = _typo.TEXT_SIZES["tick"] - 1.0 if cell_in >= 0.34 else _typo.TEXT_SIZES["footnote"] - 1.4
    if do_annot:
        for i in range(p):
            for j in range(p):
                if mask_upper and j > i:
                    continue
                val = float(C[i, j])
                ax.text(j, i, fmt.format(val), ha="center", va="center",
                        fontsize=num_fs, color=_pal.INK if val < 0.999 else _pal.GREY)

    if cbar:
        # 旋转的列标签会占掉右下角：把 colorbar 往右挪一点，别压住标签
        cb = ax.figure.colorbar(mesh, ax=ax, fraction=0.046,
                                pad=0.10 if p > 4 else 0.03)
        cb.outline.set_visible(False)
        cb.ax.tick_params(direction="in", width=0.7, length=2.6,
                          labelsize=_typo.TEXT_SIZES["tick"] - 1.0)
        cb.set_label(cbar_label or f"相关系数（{method}）",
                     fontsize=_typo.TEXT_SIZES["label"] - 1.0, color=_pal.INK)
    if n:
        # 放画框上方右侧（panel 标题在左上，这里空着），别压住矩阵右下角的系数
        ax.annotate(f"n = {n}", xy=(1.0, 1.012), xycoords="axes fraction",
                    ha="right", va="bottom", fontsize=_typo.TEXT_SIZES["footnote"],
                    color=_pal.GREY)
    return ax


__all__ = ["corr", "corrcoef"]