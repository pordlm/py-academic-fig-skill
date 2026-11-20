# -*- coding: utf-8 -*-
"""门限 / 帕累托前沿 / 多次运行包络：把「取舍」画成一条能读的线。

这类图最容易出问题的是**口径**：阈值线到底是实测指标还是作者自设的目标？
所以本模块做两件事——阈值线一律 CLAY 点划线 0.8pt，且图注里**自动**补一句
「自设目标，非官方指标」，不靠作者记。

spec 结构::

    {
      "title": "覆盖率与时延的取舍",
      "kind": "pareto",                  # pareto | threshold | band | scan
      "x": {"label": "平均时延", "unit": "ms"},
      "y": {"label": "覆盖率", "unit": "%"},
      "points": [[12, 91], [18, 95], [25, 97]],   # 或下面的 cloud / runs
      "cloud": {"n": 60, "seed": 7, "x": {"min": 8, "max": 40},
                "model": "tradeoff", "a": 80, "b": 40, "noise": 1.2},
      "pareto": {"sense": ["min", "max"], "label": "帕累托前沿"},
      "thresholds": [{"axis": "y", "value": 95, "label": "目标 95%",
                      "shade": true}],
      "runs": {"x": [0, 1, 2], "mid": [12, 20, 31], "lo": [10, 17, 26],
               "hi": [15, 24, 37], "label": "20 次运行"},
      "ideal": {"dx": 1, "dy": 1, "text": "更优"},
      "footnote": "来源：本文实验；口径：示意数据，非实测。"
    }

硬约束（prompts/40_diagram_gate.md）
-----------------------------------
* 被支配解 GREY_LIGHT，``s = 12``，alpha 0.6；帕累托前沿 BLUE 实心点 /
  ``steps-post`` 1.0pt；同图阈值线 ≤ 2 条；
* 阈值线 0.8pt ``ls="-."`` CLAY，图注必须写「自设目标，非官方指标」；
* 理想方向用角落细箭头（0.6pt）标注，文字 8.0pt。
"""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Patch

from ..layout import footnote as _footnote
from ..layout import paper_fig
from ..palette import BLUE, CLAY, GREY, GREY_LIGHT, INK, PAPER, tint
from ..style import legend as style_legend
from ._canvas import TITLE_FS, load_spec, resolve_color
from ._guard import check_spec_keys, ensure_theme

__all__ = ["gate", "pareto_front"]

GATE_KINDS = ("pareto", "threshold", "band", "scan")
DISCLAIMER = "自设目标，非官方指标"


def _axis_label(sp: dict, key: str) -> str:
    spec = sp.get(key) or {}
    text = str(spec.get("label") or "")
    unit = str(spec.get("unit") or "")
    if unit and text and "（" not in text and "(" not in text:
        return f"{text}（{unit}）"
    return text or unit


def _cloud(sp: dict) -> np.ndarray | None:
    c = sp.get("cloud")
    if not c:
        return None
    n = int(c.get("n", 60))
    seed = int(c.get("seed", 0))
    rng = np.random.RandomState(seed)
    x0 = float((c.get("x") or {}).get("min", 0.1))
    x1 = float((c.get("x") or {}).get("max", 1.0))
    xs = np.linspace(x0, x1, n)
    model = str(c.get("model", "tradeoff")).lower()
    if model == "tradeoff":
        ys = float(c.get("a", 0.2)) + float(c.get("b", 0.6)) / np.maximum(xs, 1e-6)
    elif model == "linear":
        ys = float(c.get("a", 0.0)) + float(c.get("b", 1.0)) * xs
    elif model == "convex":
        ys = float(c.get("a", 1.0)) * (xs ** float(c.get("b", 2.0)))
    elif model == "log":
        # 收益递减型取舍：x 越大 y 越好但边际递减（覆盖率随时延上升、饱和）。
        ys = float(c.get("a", 0.0)) + float(c.get("b", 1.0)) * np.log(
            np.maximum(xs, 1e-6))
    else:
        raise ValueError(
            f"gate(): cloud.model={model!r} 不支持；"
            f"可选 tradeoff / linear / convex / log")
    ys = ys + rng.normal(0.0, float(c.get("noise", 0.0)), n)
    return np.column_stack([xs, ys])


def _points(sp: dict) -> np.ndarray:
    pts = sp.get("points")
    if pts:
        arr = np.asarray(pts, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("gate(): points 必须是 [[x, y], …] 的二维数组")
        return arr
    gen = _cloud(sp)
    if gen is not None:
        return gen
    return np.zeros((0, 2))


def pareto_front(points, sense=("min", "max")) -> np.ndarray:
    """返回非支配解（按 x 升序）；``sense`` 每个目标取 ``"min"`` / ``"max"``。"""
    pts = np.asarray(points, dtype=float)
    if pts.size == 0:
        return pts.reshape(0, 2)
    sx = 1.0 if str(sense[0]).lower().startswith("min") else -1.0
    sy = 1.0 if str(sense[1]).lower().startswith("min") else -1.0
    ux = pts[:, 0] * sx
    uy = pts[:, 1] * sy
    keep = np.ones(len(pts), dtype=bool)
    for i in range(len(pts)):
        if not keep[i]:
            continue
        dominated = ((ux <= ux[i]) & (uy <= uy[i]) &
                     ((ux < ux[i]) | (uy < uy[i])))
        if dominated.any():
            keep[i] = False
    out = pts[keep]
    return out[np.argsort(out[:, 0])]


def _threshold(ax, sp: dict, item: dict):
    axis = str(item.get("axis", "y")).lower()
    val = float(item["value"])
    label = str(item.get("label") or "")
    if item.get("shade"):
        color = tint(resolve_color(sp.get("shade_color"), BLUE), 0.08)
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        if axis == "y":
            ax.axhspan(y0, val, facecolor=color, edgecolor="none", zorder=0)
        else:
            ax.axvspan(x0, val, facecolor=color, edgecolor="none", zorder=0)
    if axis == "y":
        ax.axhline(val, color=CLAY, lw=0.8, ls="-.", zorder=4)
        txt = label or f"{val:g}"
        # 标签写在线的下方、贴着左边界：上方留给图例，右端留给数据。
        ax.text(ax.get_xlim()[0] + 0.012 * (ax.get_xlim()[1] - ax.get_xlim()[0]),
                val, f" {txt}", fontsize=8.0, color=CLAY,
                ha="left", va="top", zorder=6,
                bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.85, pad=1.0))
    else:
        ax.axvline(val, color=CLAY, lw=0.8, ls="-.", zorder=4)
        # 竖排标签从底边往上长：顶部是图例与数据最密的地方。
        ax.text(val, ax.get_ylim()[0], f" {label or format(val, 'g')} ",
                fontsize=8.0, color=CLAY, ha="left", va="bottom", rotation=90,
                zorder=6,
                bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.85, pad=1.0))


def _ideal_arrow(ax, item: dict):
    text = str(item.get("text") or "更优")
    dx = float(item.get("dx", 1.0))
    dy = float(item.get("dy", 1.0))
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    sx, sy = x1 - x0, y1 - y0
    # 尾巴放在「理想方向的反侧」的空白角，箭头朝理想方向走一小段；
    # 文字永远在尾巴后方，因此不会越出坐标框。
    ox = x0 + (0.26 if dx < 0 else 0.74) * sx
    oy = y0 + (0.14 if dy > 0 else 0.30) * sy
    ax.annotate("", xy=(ox + dx * 0.09 * sx, oy + dy * 0.09 * sy),
                xytext=(ox, oy), zorder=9,
                arrowprops=dict(arrowstyle="-|>", mutation_scale=6, color=GREY,
                                lw=0.6, shrinkA=0, shrinkB=0))
    ax.text(ox - dx * 0.015 * sx, oy, text, fontsize=8.0, color=GREY,
            ha="left" if dx < 0 else "right",
            va="bottom" if dy > 0 else "top", zorder=9)


def gate(spec, *, kind=None, width=None, height=None, note=None, strict=True,
         title=None):
    """画一张门限 / 帕累托 / 包络图，返回 ``ax``。

    Parameters
    ----------
    spec : dict | str | pathlib.Path
        规格字典或 JSON 路径。
    kind : {"pareto", "threshold", "band", "scan"}, optional
        覆盖 ``spec["kind"]``。
    width : {"single", "double"} or float, optional
        画布宽度，默认单栏。
    height : float, optional
        画布高度，默认按 :func:`~academic_fig.layout.paper_fig` 的面板比例。
    note : str, optional
        覆盖 ``spec["footnote"]``；缺「自设目标，非官方指标」时自动补。
    strict : bool
        签名与其它示意图入口一致。
    title : str, optional
        覆盖 ``spec["title"]``。

    Returns
    -------
    matplotlib.axes.Axes
    """
    sp = load_spec(spec)
    ensure_theme()
    check_spec_keys(sp, __name__, strict=strict, extra=(kind,))
    kind = str(kind or sp.get("kind") or "pareto").lower()
    if kind not in GATE_KINDS:
        raise ValueError(f"gate(): kind={kind!r} 不支持；可选 {GATE_KINDS}")
    w = width if width is not None else sp.get("width", "single")
    fig, ax = paper_fig(w, height=height)
    handles, labels = [], []

    pts = _points(sp)
    if pts.size and kind in ("pareto", "threshold", "scan"):
        color = resolve_color(sp.get("point_color"), GREY_LIGHT)
        ax.scatter(pts[:, 0], pts[:, 1], s=12, facecolors=color,
                   edgecolors="none", alpha=0.6, zorder=2)

    # -- 多次运行包络 ----------------------------------------------------
    runs = sp.get("runs")
    if runs:
        rx = np.asarray(runs["x"], dtype=float)
        lo = np.asarray(runs.get("lo", runs.get("mid")), dtype=float)
        hi = np.asarray(runs.get("hi", runs.get("mid")), dtype=float)
        mid = np.asarray(runs["mid"], dtype=float) if runs.get("mid") is not None \
            else (lo + hi) / 2.0
        band_color = resolve_color(runs.get("color"), BLUE)
        ax.fill_between(rx, lo, hi, facecolor=tint(band_color, 0.16),
                        edgecolor="none", zorder=1)
        ax.plot(rx, mid, color=band_color, lw=1.0, zorder=5,
                drawstyle=str(runs.get("drawstyle", "default")))
        if runs.get("lines"):
            for seq in runs["lines"]:
                arr = np.asarray(seq, dtype=float)
                ax.plot(arr[:, 0], arr[:, 1], color=GREY_LIGHT, lw=0.6,
                        alpha=0.9, zorder=1)
        handles.append(Patch(facecolor=tint(band_color, 0.16), edgecolor="none"))
        labels.append(str(runs.get("label") or "多次运行包络"))
        handles.append(ax.plot([], [], color=band_color, lw=1.0)[0])
        labels.append(str(runs.get("label_mid") or "中位轨迹"))

    # -- 帕累托前沿 ------------------------------------------------------
    if kind == "pareto" and pts.size:
        sense = sp.get("pareto", {}).get("sense") or ("min", "max")
        if isinstance(sense, str):
            sense = (sense, sense)
        front = pareto_front(pts, sense)
        if front.size:
            front_color = resolve_color(sp.get("pareto", {}).get("color"), BLUE)
            ax.scatter(front[:, 0], front[:, 1], s=22, facecolors=front_color,
                       edgecolors=PAPER, linewidths=0.6, zorder=6)
            if sp.get("pareto", {}).get("steps", True):
                ax.plot(front[:, 0], front[:, 1], color=front_color, lw=1.0,
                        drawstyle="steps-post", zorder=5)
            else:
                ax.plot(front[:, 0], front[:, 1], color=front_color, lw=1.0,
                        zorder=5)
            handles.append(ax.scatter([], [], s=22, facecolors=front_color,
                                      edgecolors=INK, linewidths=0.5))
            labels.append(str(sp.get("pareto", {}).get("label") or "帕累托前沿"))

    # -- 轴（先定范围：阈值线/区带按最终坐标画才准） ---------------------
    ax.set_xlabel(_axis_label(sp, "x"), fontsize=10)
    ax.set_ylabel(_axis_label(sp, "y"), fontsize=10)
    xspec, yspec = sp.get("x") or {}, sp.get("y") or {}
    if xspec.get("min") is not None and xspec.get("max") is not None:
        ax.set_xlim(float(xspec["min"]), float(xspec["max"]))
    if yspec.get("min") is not None and yspec.get("max") is not None:
        ax.set_ylim(float(yspec["min"]), float(yspec["max"]))
    else:
        vals = []
        if pts.size:
            vals += [float(np.nanmin(pts[:, 1])), float(np.nanmax(pts[:, 1]))]
        if runs:
            vals += [float(np.nanmin(lo)), float(np.nanmax(hi))]
        vals += [float(t["value"]) for t in (sp.get("thresholds") or [])
                 if str(t.get("axis", "y")).lower() == "y"]
        if vals:
            span = (max(vals) - min(vals)) or 1.0
            ax.set_ylim(min(vals) - 0.10 * span, max(vals) + 0.14 * span)

    # -- 阈值线（最多 2 条） ---------------------------------------------
    ths = sp.get("thresholds") or []
    if len(ths) > 2:
        raise ValueError(
            f"gate(): 同图阈值线最多 2 条（收到 {len(ths)} 条）；"
            "多目标请拆成多面板")
    for item in ths:
        _threshold(ax, sp, item)

    # -- 理想方向 --------------------------------------------------------
    if sp.get("ideal"):
        _ideal_arrow(ax, sp["ideal"] if isinstance(sp["ideal"], dict)
                     else {"text": str(sp["ideal"])})

    if sp.get("title"):
        ax.set_title(str(title if title is not None else sp["title"]), fontsize=TITLE_FS,
                     loc="left", color=INK, pad=6)
    if handles:
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        style_legend(ax, loc=str(sp.get("legend_loc", "auto")), handles=handles,
                     labels=labels, fontsize=9)
        # 图例放不下时会抬坐标轴；门限图的范围是「设定值」，不能被图例改写。
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)

    base = str(note if note is not None else (sp.get("footnote") or "")).strip()
    if not base:
        raise ValueError(
            "gate(): 必须有图注（spec['footnote'] 或 note=…），写明来源 / 口径 / "
            "示意声明")
    if DISCLAIMER not in base:
        base = f"{base}  阈值线为{DISCLAIMER}。"
    _footnote(fig, base)
    return ax
