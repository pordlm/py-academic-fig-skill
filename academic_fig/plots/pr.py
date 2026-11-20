# -*- coding: utf-8 -*-
"""pr —— 精确率-召回率曲线（不均衡数据比 ROC 更敏感；基线是正类比例）。

**这张图要让读者看到什么**：在「尽量不漏检」的前提下还能保住多少精确率，
以及相对随机基线（正类占比）提升了多少（AUC-PR）。

塌陷点提醒
1. 不画基线（正类比例）→ 读者会把 0.3 的 AUC-PR 误判为「很差」；
2. 正类比例不同却直接比较 AUC-PR → 必须在图注写明 prevalence；
3. 只给曲线不给 AP 值 → 无法排序比较。
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from .. import palette as _pal
from .. import typography as _typo
from . import base as _base
from ._common import check_len, style_ls


def pr_curve(y_true: Any, y_score: Any, positive: Any = 1) -> tuple[np.ndarray, np.ndarray, float]:
    """计算 PR 曲线与平均精确率（AP，纯 numpy）。

    Returns
    -------
    (recall, precision, ap) : (ndarray, ndarray, float)
    """
    yt = np.ravel(np.asarray(y_true))
    ys = np.ravel(np.asarray(y_score, dtype=float))
    check_len("y_score", ys, yt.size, caller="pr_curve")
    if yt.size == 0:
        raise ValueError("pr_curve(): y_true 为空")
    pos = yt == positive
    n_pos = int(pos.sum())
    if n_pos == 0 or n_pos == yt.size:
        raise ValueError("pr_curve(): y_true 必须同时包含正类与负类（检查 positive 参数）")
    order = np.argsort(-ys, kind="mergesort")
    ys_s, pos_s = ys[order], pos[order]
    distinct = np.where(np.diff(ys_s))[0]
    idx = np.r_[distinct, yt.size - 1]
    tp = np.cumsum(pos_s)[idx].astype(float)
    predicted = (idx + 1).astype(float)
    precision = tp / predicted
    recall = tp / n_pos
    recall = np.r_[0.0, recall]
    precision = np.r_[1.0, precision]
    ap = float(-np.sum(np.diff(recall) * precision[1:])) if recall.size > 1 else 0.0
    return recall, precision, abs(ap)


def pr(ax=None, y_true: Any | None = None, y_score: Any | None = None, *,
       data: Any | None = None, curves: Mapping[str, Any] | None = None,
       positive: Any = 1, label: str | None = None, legend: bool = True,
       baseline: bool | None = None, annotate_ap: bool = True):
    """画 PR 曲线。

    Parameters
    ----------
    ax : matplotlib.axes.Axes, optional
        目标坐标轴；``None`` 时新建。
    y_true, y_score : sequence, optional
        真值标签与分数（等长）。
    data : Mapping, optional
        ``{"y_true": …, "y_score": …}`` 或 ``{"curves": {...}}``。
    curves : Mapping[str, (y_true, y_score) | (recall, precision)], optional
        多条曲线；也可直接给 ``{名: {"recall":…, "precision":…, "ap":…}}``。
    positive : Any
        正类取值，默认 1。
    baseline : bool, optional
        是否画随机基线（默认在有多条曲线或 AP 明显时自动画）。
    annotate_ap : bool
        是否把 AP 写进图例。

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
    prevalence = None
    if curves:
        if not isinstance(curves, Mapping):
            raise ValueError("pr(): curves 必须是 {名称: (y_true, y_score)} 的映射")
        for name, payload in curves.items():
            if isinstance(payload, Mapping):
                rec = np.ravel(np.asarray(payload["recall"], dtype=float))
                prec = np.ravel(np.asarray(payload["precision"], dtype=float))
                check_len("precision", prec, rec.size, caller="pr")
                ap = float(payload.get("ap", 0.0)) or float(np.mean(prec))
            else:
                rec, prec, ap = pr_curve(payload[0], payload[1], positive=positive)
                yt = np.ravel(np.asarray(payload[0]))
                prevalence = float(np.mean(yt == positive))
            entries.append((str(name), rec, prec, ap))
    elif y_true is not None and y_score is not None:
        rec, prec, ap = pr_curve(y_true, y_score, positive=positive)
        yt = np.ravel(np.asarray(y_true))
        prevalence = float(np.mean(yt == positive))
        entries.append((label or "本文方法", rec, prec, ap))
    else:
        raise ValueError("pr(): 需要 (y_true, y_score) 或 curves={名: (y_true, y_score)}")

    show_base = baseline if baseline is not None else prevalence is not None
    if show_base and prevalence is not None:
        ax.axhline(prevalence, color=_pal.GREY, lw=0.8, ls=(0, (4, 3)), zorder=1.2,
                   label=f"随机基线（正类 {prevalence:.0%}）")

    for i, (name, rec, prec, ap) in enumerate(entries):
        text = f"{name}（AP={ap:.3f}）" if annotate_ap else name
        ax.plot(rec, prec, color=_pal.CATEGORICAL[i % len(_pal.CATEGORICAL)],
                lw=1.15, ls=style_ls(i), zorder=3 + i * 0.1, label=text)

    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.02)
    ax.set_xlabel("召回率 Recall（灵敏度）", fontsize=_typo.TEXT_SIZES["label"])
    ax.set_ylabel("精确率 Precision（阳性预测值）", fontsize=_typo.TEXT_SIZES["label"])
    if legend:
        _base.legend(ax, loc="lower left")
    return ax


__all__ = ["pr", "pr_curve"]