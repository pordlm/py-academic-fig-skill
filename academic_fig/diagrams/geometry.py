# -*- coding: utf-8 -*-
"""几何 / 覆盖 / 可达性示意图：等比坐标 + 极浅填充 + 空心测点。

示意图里最容易被画「假」的就是几何关系：半径不等于半径、覆盖区被拉成椭圆、
比例尺只是个装饰。所以这里的第一条就是 ``set_aspect("equal")``，画布高度由
数据域长宽比反推（:func:`~academic_fig.diagrams._canvas.square_fig`），
几何量因此是**可量的**。

spec 结构::

    {
      "title": "三站覆盖与可达域",
      "x": {"min": -6, "max": 6, "label": "东向位置", "unit": "m"},
      "y": {"min": -6, "max": 6, "label": "北向位置", "unit": "m"},
      "regions": [
        {"poly": [[-5, -4], [5, -4], [5, 4], [-5, 4]],
         "color": "BLUE", "alpha": 0.08, "edge": "BLUE", "lw": 0.8,
         "ls": "dashed", "label": "可达域"}
      ],
      "circles": [
        {"center": [0, 0], "r": 3.0, "color": "BLUE", "alpha": 0.10,
         "edge": "BLUE", "lw": 0.8, "label": "覆盖半径 R = 3 m"}
      ],
      "lines": [
        {"pts": [[-5, 0], [5, 0]], "color": "GREY", "ls": "dashed", "lw": 0.8,
         "label": "参考轴"}
      ],
      "stations": {"pts": [[0, 0], [3, 1]], "label": "测站"},
      "keypoints": {"pts": [[1.2, -2.0]], "labels": ["最坏点"], "label": "关键点"},
      "arrows": [{"from": [0, 0], "to": [3, 1], "label": "基线"}],
      "annotations": [{"x": 1.2, "y": -2.0, "text": "残差最大", "to": [1.2, -2.0]}],
      "scale_bar": {"length": 2, "unit": "m", "position": "lower right"},
      "footnote": "来源：…；口径：示意几何，非真实测点。"
    }

硬约束（prompts/40_diagram_geometry.md）
--------------------------------------
* 等比坐标：``set_aspect("equal")`` + 方形轴盒（域为方形时 ``set_box_aspect(1)``）；
* 覆盖/可达区：极浅填充（alpha ≤ 0.15）+ 同色 0.8pt 边框；
* 测站空心圆 / 关键点实心黑点，``ms = 5``；
* 参考结构一律虚线，箭头 0.9pt 细线 ``-|>``；
* 必须有比例尺或带物理单位的坐标轴。
"""
from __future__ import annotations

import math

from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, Patch, Polygon

from ..palette import BLUE, GREY, INK, INK_SOFT, PAPER, tint
from ..style import axes as style_axes
from ..style import legend as style_legend
from ._canvas import (
    NOTE_FS,
    SCENE_MARGINS,
    TITLE_FS,
    load_spec,
    resolve_color,
    scene_axes,
    square_fig,
)
from ._guard import check_spec_keys, ensure_theme

__all__ = ["geometry"]

PAD = 0.04
STATION_S = 26.0
KEY_S = 18.0


def _ls(value, default="-"):
    v = str(value or default).lower()
    return {"solid": "-", "dash": (0, (5, 2.5)), "dashed": (0, (5, 2.5)),
            "dotted": (0, (1.5, 2.0)), "dashdot": "-.", "none": "none"}.get(v, v)


def _axis_label(sp: dict, key: str) -> str:
    spec = sp.get(key) or {}
    text = str(spec.get("label") or "")
    unit = str(spec.get("unit") or "")
    if unit and text and "（" not in text and "(" not in text:
        return f"{text}（{unit}）"
    if unit and not text:
        return f"{unit}"
    return text


def _collect_points(sp: dict) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for reg in sp.get("regions") or []:
        pts += [(float(p[0]), float(p[1])) for p in reg.get("poly") or []]
    for c in sp.get("circles") or []:
        cx, cy = float(c["center"][0]), float(c["center"][1])
        r = float(c.get("r", 0.0))
        pts += [(cx - r, cy - r), (cx + r, cy + r)]
    for ln in sp.get("lines") or []:
        pts += [(float(p[0]), float(p[1])) for p in ln.get("pts") or []]
    for key in ("stations", "keypoints"):
        node = sp.get(key) or {}
        raw = node.get("pts") if isinstance(node, dict) else node
        pts += [(float(p[0]), float(p[1])) for p in (raw or [])]
    for ar in sp.get("arrows") or []:
        pts += [(float(ar["from"][0]), float(ar["from"][1])),
                (float(ar["to"][0]), float(ar["to"][1]))]
    for an in sp.get("annotations") or []:
        pts.append((float(an["x"]), float(an["y"])))
    return pts


def _limits(sp: dict, pts):
    def one(key, idx):
        spec = sp.get(key) or {}
        if spec.get("min") is not None and spec.get("max") is not None:
            return float(spec["min"]), float(spec["max"])
        vals = [p[idx] for p in pts] or [0.0, 1.0]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        return lo - PAD * span, hi + PAD * span
    x0, x1 = one("x", 0)
    y0, y1 = one("y", 1)
    if not x1 > x0 or not y1 > y0:
        raise ValueError("geometry(): x/y 范围必须 max > min")
    return (x0, x1), (y0, y1)


def _nice(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = math.floor(math.log10(value))
    base = 10.0 ** exp
    for mult in (1.0, 2.0, 5.0, 10.0):
        if value <= mult * base * 1.02:
            return mult * base
    return 10.0 * base


def _scale_bar(ax, sp: dict, xr: float, yr: float):
    sb = sp.get("scale_bar")
    if sb is False or sb is None:
        return
    sb = sb if isinstance(sb, dict) else {}
    length = float(sb.get("length") or _nice(0.22 * xr))
    unit = str(sb.get("unit") or (sp.get("x") or {}).get("unit") or "")
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    pos = str(sb.get("position", "lower right")).lower()
    x_end = x0 + 0.92 * (x1 - x0) if "right" in pos else x0 + 0.08 * (x1 - x0) + length
    x_start = x_end - length
    y = y0 + 0.07 * (y1 - y0) if "lower" in pos else y1 - 0.08 * (y1 - y0)
    tick = 0.022 * (y1 - y0)
    ax.plot([x_start, x_end], [y, y], color=INK, lw=1.2, solid_capstyle="butt",
            zorder=8)
    for xx in (x_start, x_end):
        ax.plot([xx, xx], [y - tick / 2.0, y + tick / 2.0], color=INK, lw=1.0,
                solid_capstyle="butt", zorder=8)
    txt = sb.get("label") or (f"{length:g} {unit}".strip())
    ax.text((x_start + x_end) / 2.0, y + tick * 1.1, str(txt), ha="center",
            va="bottom", fontsize=NOTE_FS, color=INK, zorder=8)


def geometry(spec, *, width=None, height=None, note=None, strict=True,
             title=None, legend=True):
    """画一张几何/覆盖示意图，返回 ``ax``。

    Parameters
    ----------
    spec : dict | str | pathlib.Path
        规格字典或 JSON 路径。
    width : {"single", "double"} or float, optional
        画布宽度，默认 ``spec["width"]`` 或单栏。
    height : float, optional
        覆盖画布高度；默认由数据域长宽比推出（等比坐标的前提）。
    note : str, optional
        覆盖 ``spec["footnote"]``。
    strict : bool
        签名与其它示意图入口一致；几何图无文本框，保留参数便于统一调用。
    title : str, optional
        覆盖 ``spec["title"]``。
    legend : bool
        是否画图例（有带 label 的元素才画）。

    Returns
    -------
    matplotlib.axes.Axes
    """
    sp = load_spec(spec)
    ensure_theme()
    check_spec_keys(sp, __name__, strict=strict, extra=())
    pts = _collect_points(sp)
    (x0, x1), (y0, y1) = _limits(sp, pts)
    w = width if width is not None else sp.get("width", "single")
    xr, yr = x1 - x0, y1 - y0
    fig = square_fig(w, xr, yr, margins=SCENE_MARGINS)
    if height is not None:
        fig.set_size_inches(fig.get_size_inches()[0], float(height))
    ax = scene_axes(fig, margins=SCENE_MARGINS)
    style_axes(ax, equal=True)

    handles, labels = [], []

    # -- 区域（极浅填充） ------------------------------------------------
    for reg in sp.get("regions") or []:
        poly = [(float(p[0]), float(p[1])) for p in reg.get("poly") or []]
        if len(poly) < 3:
            raise ValueError("geometry(): regions[].poly 至少需要 3 个点")
        face = resolve_color(reg.get("color"), BLUE)
        # alpha 只压填充，不压边框：否则 alpha=0 的「安全边界」圆环会整条消失。
        ax.add_patch(Polygon(poly, closed=True,
                             facecolor=to_rgba(face, float(reg.get("alpha", 0.10))),
                             edgecolor=resolve_color(reg.get("edge"), face),
                             linewidth=float(reg.get("lw", 0.8)),
                             linestyle=_ls(reg.get("ls"), "-"),
                             joinstyle="miter", zorder=1))
        if reg.get("label"):
            # 图例色块要跟实际观感一致：描边类（alpha≈0）用空心块，填充类才用淡色块。
            _a = float(reg.get("alpha", 0.10))
            handles.append(Patch(facecolor=tint(face, 0.20) if _a > 0.02 else "none",
                                 edgecolor=resolve_color(reg.get("edge"), face),
                                 linewidth=0.6, linestyle=_ls(reg.get("ls"), "-")))
            labels.append(str(reg["label"]))

    # -- 圆（覆盖半径） --------------------------------------------------
    for c in sp.get("circles") or []:
        cx, cy = float(c["center"][0]), float(c["center"][1])
        r = float(c.get("r", 0.0))
        face = resolve_color(c.get("color"), BLUE)
        ax.add_patch(Circle((cx, cy), r,
                            facecolor=to_rgba(face, float(c.get("alpha", 0.10))),
                            edgecolor=resolve_color(c.get("edge"), face),
                            linewidth=float(c.get("lw", 0.8)),
                            linestyle=_ls(c.get("ls"), "-"), zorder=1))
        if c.get("label"):
            _a = float(c.get("alpha", 0.10))
            handles.append(Patch(facecolor=tint(face, 0.20) if _a > 0.02 else "none",
                                 edgecolor=resolve_color(c.get("edge"), face),
                                 linewidth=0.6, linestyle=_ls(c.get("ls"), "-")))
            labels.append(str(c["label"]))

    # -- 线（参考结构：虚线） --------------------------------------------
    for ln in sp.get("lines") or []:
        seq = [(float(p[0]), float(p[1])) for p in ln.get("pts") or []]
        color = resolve_color(ln.get("color"), GREY)
        ax.plot([p[0] for p in seq], [p[1] for p in seq], color=color,
                lw=float(ln.get("lw", 0.8)), ls=_ls(ln.get("ls"), "dashed"),
                zorder=2, solid_capstyle="butt")
        if ln.get("label"):
            handles.append(Line2D([], [], color=color, lw=float(ln.get("lw", 0.8)),
                                  ls=_ls(ln.get("ls"), "dashed")))
            labels.append(str(ln["label"]))

    # -- 箭头 ------------------------------------------------------------
    for ar in sp.get("arrows") or []:
        p0 = (float(ar["from"][0]), float(ar["from"][1]))
        p1 = (float(ar["to"][0]), float(ar["to"][1]))
        color = resolve_color(ar.get("color"), INK)
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=8,
                                     linewidth=0.9, color=color,
                                     linestyle=_ls(ar.get("ls"), "-"),
                                     shrinkA=0.0, shrinkB=0.0, zorder=5))
        if ar.get("label"):
            mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
            ax.text(mx, my, str(ar["label"]), fontsize=NOTE_FS, color=INK_SOFT,
                    ha="center", va="bottom", zorder=8,
                    bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.9, pad=1.2))

    # -- 测站（空心圆）与关键点（实心黑） --------------------------------
    st = sp.get("stations") or {}
    st_pts = st.get("pts") if isinstance(st, dict) else st
    if st_pts:
        xs = [float(p[0]) for p in st_pts]
        ys = [float(p[1]) for p in st_pts]
        ax.scatter(xs, ys, s=STATION_S, facecolors="none",
                   edgecolors=resolve_color(st.get("edge"), INK) if isinstance(st, dict)
                   else INK, linewidths=1.0, zorder=6)
        if isinstance(st, dict) and st.get("label"):
            handles.append(Line2D([], [], marker="o", ls="none", ms=5,
                                  mfc="none", mec=INK, mew=1.0))
            labels.append(str(st["label"]))

    kp = sp.get("keypoints") or {}
    kp_pts = kp.get("pts") if isinstance(kp, dict) else kp
    if kp_pts:
        xs = [float(p[0]) for p in kp_pts]
        ys = [float(p[1]) for p in kp_pts]
        ax.scatter(xs, ys, s=KEY_S, facecolors=INK, edgecolors=INK,
                   linewidths=0.5, zorder=7)
        if isinstance(kp, dict) and kp.get("label"):
            handles.append(Line2D([], [], marker="o", ls="none", ms=4.5,
                                  mfc=INK, mec=INK))
            labels.append(str(kp["label"]))
        for (px, py), txt in zip(kp_pts, kp.get("labels") or []):
            ax.annotate(str(txt), xy=(float(px), float(py)), xytext=(5, 5),
                        textcoords="offset points", fontsize=NOTE_FS,
                        color=INK, ha="left", va="bottom", zorder=9)

    # -- 标注 ------------------------------------------------------------
    for an in sp.get("annotations") or []:
        ax_x, ax_y = float(an["x"]), float(an["y"])
        txt = str(an.get("text", ""))
        target = an.get("to")
        if target:
            ax.annotate(txt, xy=(float(target[0]), float(target[1])),
                        xytext=(ax_x, ax_y), fontsize=NOTE_FS, color=INK,
                        ha="center", va="bottom", zorder=9,
                        bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.85,
                                  pad=1.5),
                        arrowprops=dict(arrowstyle="-|>", mutation_scale=8,
                                        color=INK_SOFT, lw=0.8, shrinkA=1,
                                        shrinkB=2))
        else:
            ax.text(ax_x, ax_y, txt, fontsize=NOTE_FS, color=INK, ha="center",
                    va="bottom", zorder=9)

    # -- 轴与比例尺 ------------------------------------------------------
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_xlabel(_axis_label(sp, "x"), fontsize=10)
    ax.set_ylabel(_axis_label(sp, "y"), fontsize=10)
    ratio = yr / xr
    ax.set_box_aspect(1.0 if abs(ratio - 1.0) < 0.02 else ratio)
    if sp.get("ticks", True):
        ax.set_xticks(ax.get_xticks())
    else:
        ax.set_xticks([])
        ax.set_yticks([])
    _scale_bar(ax, sp, xr, yr)
    if legend and handles:
        style_legend(ax, loc=str(sp.get("legend_loc", "auto")), handles=handles,
                     labels=labels, fontsize=9,
                     ncol=int(sp.get("legend_ncol", 1)),
                     # 几何图里图例难免压在填充/虚线上：垫一层纸色底，不画边框。
                     frameon=True, facecolor=PAPER, edgecolor="none",
                     framealpha=0.94)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)

    if title is not None or sp.get("title"):
        ax.set_title(str(title if title is not None else sp["title"]),
                     fontsize=TITLE_FS, color=INK, pad=5)
    text = note if note is not None else sp.get("footnote")
    if text:
        from ..layout import footnote as _footnote
        _footnote(fig, str(text))
    return ax
