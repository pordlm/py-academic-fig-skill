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
from ._common import as_1d, as_binary_mask, check_len, style_ls


def _average_precision(recall: np.ndarray, precision: np.ndarray) -> float:
    """AP = Σ (R_i − R_{i−1})·P_i（阶梯积分，与 sklearn 的 AP 同口径）。

    不能用平均 precision 代替：precision 在低召回区的点数分布与召回步长无关，
    ``mean(precision)`` 既不是积分也不是加权平均，会把「很靠后才有高精度」的
    曲线算高。曲线若从 R>0 起，先补一个 (0, P_0)。
    """
    rec = np.asarray(recall, dtype=float)
    pre = np.asarray(precision, dtype=float)
    if rec.size == 0:
        return 0.0
    if rec[0] > 0.0:
        rec = np.r_[0.0, rec]
        pre = np.r_[pre[0], pre]
    return float(np.sum(np.diff(rec) * pre[1:]))


def _check_supplied_curve(rec: np.ndarray, prec: np.ndarray, *, name: str,
                          caller: str = "pr") -> None:
    """校验用户自己给的 (recall, precision) 点。"""
    if rec.size < 2:
        raise ValueError(f"{caller}(): curves[{name!r}] 至少需要 2 个点")
    if np.any(np.diff(rec) < -1e-12):
        raise ValueError(f"{caller}(): curves[{name!r}] 的 recall 必须单调不减；"
                         f"请按阈值从高到低排列后重传")
    for arr, label in ((rec, "recall"), (prec, "precision")):
        if arr.min() < -1e-9 or arr.max() > 1.0 + 1e-9:
            raise ValueError(f"{caller}(): curves[{name!r}] 的 {label} 必须在 [0, 1]"
                             f"（收到 {arr.min():g}–{arr.max():g}）")


def _looks_like_curve(a: Any, b: Any) -> bool:
    """判断二元组是「已算好的 (recall, precision)」还是「(y_true, y_score)」。

    决定性依据是第一个数组的取值个数：标签只有两个取值（正/负类），而 recall
    在曲线里通常远多于两个。两组都在 [0, 1] 内才可能是曲线，所以
    ``(y_true, y_score)`` 里 y_true 是 0/1、y_score 是概率的情况不会误判。
    """
    try:
        fa = np.ravel(np.asarray(a, dtype=float))
        fb = np.ravel(np.asarray(b, dtype=float))
    except (TypeError, ValueError):
        return False
    if fa.size < 2 or fa.size != fb.size:
        return False
    if fa.min() < -1e-9 or fa.max() > 1.0 + 1e-9:
        return False
    uniq_a = np.unique(fa)
    if uniq_a.size <= 2 and bool(np.all((uniq_a == 0.0) | (uniq_a == 1.0))):
        return False  # 只取 0/1：更像标签向量，交给 pr_curve 去算
    return True


def pr_curve(y_true: Any, y_score: Any, positive: Any = 1) -> tuple[np.ndarray, np.ndarray, float]:
    """计算 PR 曲线与平均精确率（AP，纯 numpy）。

    Returns
    -------
    (recall, precision, ap) : (ndarray, ndarray, float)
    """
    yt = np.ravel(np.asarray(y_true))
    ys = as_1d(y_score, "y_score", caller="pr_curve")
    check_len("y_score", ys, yt.size, caller="pr_curve")
    if yt.size == 0:
        raise ValueError("pr_curve(): y_true 为空")
    pos = as_binary_mask(yt, positive, caller="pr_curve")
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
    ap = _average_precision(recall, precision)
    return recall, precision, ap


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
        多条曲线。给 ``(y_true, y_score)`` 由本函数算；给 ``(recall, precision)``
        点集则直接画（会自动与 ``(y_true, y_score)`` 区分），也可给
        ``{名: {"recall":…, "precision":…, "ap":…, "prevalence":…}}``。
        AP 缺省按 ``Σ(R_i−R_{i−1})·P_i`` 现算，不用平均 precision 顶替。
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
                if "recall" not in payload or "precision" not in payload:
                    raise ValueError(f"pr(): curves[{name!r}] 缺少 recall/precision 键")
                rec = as_1d(payload["recall"], f"curves[{name!r}].recall", caller="pr")
                prec = as_1d(payload["precision"], f"curves[{name!r}].precision", caller="pr")
                check_len("precision", prec, rec.size, caller="pr")
                _check_supplied_curve(rec, prec, name=str(name))
                ap_val = payload.get("ap")
                ap = float(ap_val) if ap_val is not None else _average_precision(rec, prec)
                if payload.get("prevalence") is not None:
                    prevalence = float(payload["prevalence"])
            elif isinstance(payload, (list, tuple)) and len(payload) == 2 and \
                    _looks_like_curve(payload[0], payload[1]):
                rec = as_1d(payload[0], f"curves[{name!r}].recall", caller="pr")
                prec = as_1d(payload[1], f"curves[{name!r}].precision", caller="pr")
                check_len("precision", prec, rec.size, caller="pr")
                _check_supplied_curve(rec, prec, name=str(name))
                ap = _average_precision(rec, prec)
            else:
                if not isinstance(payload, (list, tuple)) or len(payload) < 2:
                    raise ValueError(
                        f"pr(): curves[{name!r}] 需要 (y_true, y_score) 或 (recall, precision)")
                rec, prec, ap = pr_curve(payload[0], payload[1], positive=positive)
                yt = np.ravel(np.asarray(payload[0]))
                prevalence = float(np.mean(as_binary_mask(yt, positive, caller="pr")))
            entries.append((str(name), rec, prec, ap))
    elif y_true is not None and y_score is not None:
        rec, prec, ap = pr_curve(y_true, y_score, positive=positive)
        yt = np.ravel(np.asarray(y_true))
        prevalence = float(np.mean(as_binary_mask(yt, positive, caller="pr")))
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
