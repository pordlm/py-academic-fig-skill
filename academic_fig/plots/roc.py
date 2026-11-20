# -*- coding: utf-8 -*-
"""roc —— ROC 曲线（多曲线 + AUC 直接写进图例，对角虚线为随机基线）。

**这张图要让读者看到什么**：不同判定方案在「漏检 vs 误报」之间的取舍谁更靠左上，
以及它们相对随机猜测（对角线）多出多少面积（AUC）。

塌陷点提醒
1. 不写 AUC 或类别定义 → 读者无法比较/复现（正类是哪一个必须写清）；
2. 只画曲线不画对角线 → 失去「是否优于随机」的参照；
3. 曲线多于 5 条还都是实线同色系 → 改线型 + 只保留重点曲线。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import as_1d, check_len, style_ls


def _looks_like_curve(a: Any, b: Any) -> bool:
    """判断二元组是「已算好的 (fpr, tpr)」还是「(y_true, y_score)」。

    ROC 点的共同特征：都在 [0, 1] 内、两个方向都单调不减、且从原点附近起步
    （``roc_curve`` 会显式补 ``(0, 0)``）。标签向量 0/1 起伏，两条都不满足。
    """
    try:
        fa = np.ravel(np.asarray(a, dtype=float))
        fb = np.ravel(np.asarray(b, dtype=float))
    except (TypeError, ValueError):
        return False
    if fa.size < 2 or fa.size != fb.size or fa.ndim != 1 or fb.ndim != 1:
        return False
    if fa.min() < -1e-9 or fa.max() > 1.0 + 1e-9:
        return False
    if fb.min() < -1e-9 or fb.max() > 1.0 + 1e-9:
        return False
    if not (np.all(np.diff(fa) >= -1e-9) and np.all(np.diff(fb) >= -1e-9)):
        return False
    return bool(fa[0] <= 0.05 and fb[0] <= 0.05)


def roc_curve(y_true: Any, y_score: Any, positive: Any = 1) -> tuple[np.ndarray, np.ndarray, float]:
    """计算 ROC 点与 AUC（纯 numpy，ties 用「同分同阈值」处理）。

    Returns
    -------
    (fpr, tpr, auc) : (ndarray, ndarray, float)
    """
    yt = np.ravel(np.asarray(y_true))
    ys = np.ravel(np.asarray(y_score, dtype=float))
    check_len("y_score", ys, yt.size, caller="roc_curve")
    if yt.size == 0:
        raise ValueError("roc_curve(): y_true 为空")
    pos = yt == positive
    if yt.dtype.kind in "OUS":
        # CSV 读进来常常是字符串 "0"/"1"：按字符串再比一次
        pos = yt.astype(str) == str(positive)
    if pos.all() or not pos.any():
        raise ValueError("roc_curve(): y_true 必须同时包含正类与负类（检查 positive 参数）")
    order = np.argsort(-ys, kind="mergesort")
    ys_sorted = ys[order]
    pos_sorted = pos[order]
    # 只在不同分数处切阈值
    distinct = np.where(np.diff(ys_sorted))[0]
    idx = np.r_[distinct, yt.size - 1]
    tp = np.cumsum(pos_sorted)[idx].astype(float)
    fp = (np.cumsum(~pos_sorted)[idx]).astype(float)
    tpr = tp / tp[-1] if tp[-1] else np.zeros_like(tp)
    fpr = fp / fp[-1] if fp[-1] else np.zeros_like(fp)
    fpr = np.r_[0.0, fpr]
    tpr = np.r_[0.0, tpr]
    auc = float(np.trapezoid(tpr, fpr)) if hasattr(np, "trapezoid") else float(np.trapz(tpr, fpr))
    return fpr, tpr, auc


def roc(ax=None, y_true: Any | None = None, y_score: Any | None = None, *,
        data: Any | None = None, label: str | None = None,
        curves: Mapping[str, Any] | None = None, positive: Any = 1,
        legend: bool = True, diagonal: bool = True, annotate_auc: bool = True,
        xlim: tuple[float, float] = (0.0, 1.0), ylim: tuple[float, float] = (0.0, 1.02)):
    """画 ROC 曲线。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    y_true : sequence, optional
        真值标签（0/1 或字符串），与 ``y_score`` 等长。
    y_score : sequence of float, optional
        预测分数/概率（越大越像正类）。
    data : Mapping, optional
        ``{"y_true": …, "y_score": …}`` 或 ``{"curves": {...}}``。
    label : str, optional
        单条曲线的名字（写清方案与正类定义）。
    curves : Mapping[str, (fpr, tpr) | dict], optional
        多条现成曲线：``{名: (fpr, tpr)}``，或 ``{名: {"fpr":…, "tpr":…, "auc":…}}``；
        可直接用 ``{"名": (y_true, y_score)}`` 让本函数算。
    positive : Any
        正类取值，默认 1。
    annotate_auc : bool
        是否把 AUC 写进图例（推荐保留）。

    Returns
    -------
    matplotlib.axes.Axes
        画好图的坐标轴。
    """
    ax = _base.ensure_ax(ax)
    if data is not None:
        y_true = _base.pick(data, "y_true", "labels", default=y_true)
        y_score = _base.pick(data, "y_score", "scores", default=y_score)
        if curves is None:
            curves = _base.pick(data, "curves", default=None)

    entries: list[tuple[str, np.ndarray, np.ndarray, float]] = []
    if curves:
        if not isinstance(curves, Mapping):
            raise ValueError("roc(): curves 必须是 {名称: (fpr, tpr)} 的映射")
        for i, (name, payload) in enumerate(curves.items()):
            if isinstance(payload, Mapping):
                fpr = as_1d(payload["fpr"], f"curves[{name!r}].fpr", caller="roc")
                tpr = as_1d(payload["tpr"], f"curves[{name!r}].tpr", caller="roc")
                check_len("tpr", tpr, fpr.size, caller="roc")
                auc = float(payload.get("auc", np.nan))
                if not np.isfinite(auc):
                    auc = float(np.trapezoid(tpr, fpr)) if hasattr(np, "trapezoid") \
                        else float(np.trapz(tpr, fpr))
            elif isinstance(payload, (list, tuple)) and len(payload) == 2 and \
                    _looks_like_curve(payload[0], payload[1]):
                fpr = as_1d(payload[0], f"curves[{name!r}].fpr", caller="roc")
                tpr = as_1d(payload[1], f"curves[{name!r}].tpr", caller="roc")
                check_len("tpr", tpr, fpr.size, caller="roc")
                auc = float(np.trapezoid(tpr, fpr)) if hasattr(np, "trapezoid") \
                    else float(np.trapz(tpr, fpr))
            elif isinstance(payload, (list, tuple)) and len(payload) == 3 and \
                    _looks_like_curve(payload[0], payload[1]):
                fpr = as_1d(payload[0], f"curves[{name!r}].fpr", caller="roc")
                tpr = as_1d(payload[1], f"curves[{name!r}].tpr", caller="roc")
                check_len("tpr", tpr, fpr.size, caller="roc")
                auc = float(payload[2])
            else:
                fpr, tpr, auc = roc_curve(payload[0], payload[1], positive=positive)
            entries.append((str(name), fpr, tpr, auc))
    elif y_true is not None and y_score is not None:
        fpr, tpr, auc = roc_curve(y_true, y_score, positive=positive)
        entries.append((label or "本文方法", fpr, tpr, auc))
    else:
        raise ValueError("roc(): 需要 (y_true, y_score) 或 curves={名: (fpr, tpr)}")

    if diagonal:
        ax.plot([0, 1], [0, 1], color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1,
                label="随机基线")
    for i, (name, fpr, tpr, auc) in enumerate(entries):
        text = f"{name}（AUC={auc:.3f}）" if annotate_auc else name
        ax.plot(fpr, tpr, color=_pal.CATEGORICAL[i % len(_pal.CATEGORICAL)],
                lw=1.15, ls=style_ls(i), zorder=3 + i * 0.1, label=text)

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel("假阳性率 FPR（1 − 特异度）", fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylabel("真阳性率 TPR（灵敏度）", fontsize=_typo.TEXT_SIZES["label"])
    if legend:
        _base.legend(ax, loc="lower right")
    return ax


__all__ = ["roc", "roc_curve"]