# -*- coding: utf-8 -*-
"""场量与响应面：声明式「场」→ 等高线 / 3D 曲面 / 散点场。

示意图要能**只用数据规格**画出来，所以场不是外部文件，而是公式：

* ``gaussian_sum`` —— 若干高斯凸起/凹陷叠加（响应面、覆盖强度、代价面都用它）；
* ``radial`` —— 单峰径向衰减；
* ``saddle`` —— 鞍点（门限图里常见的折衷面）；
* ``ripples`` —— 周期起伏（时频面、干涉图的示意）；
* ``plane`` —— 线性倾斜面；
* ``grid`` —— 直接给 ``x/y/z`` 三个数组（JSON 里内联数值，做精确复现）。

spec 结构::

    {
      "title": "代价响应面",
      "kind": "both",                     # contourf | contour | both | surface3d | scatter
      "x": {"min": 0, "max": 1, "n": 41},
      "y": {"min": 0, "max": 1, "n": 41},
      "field": {"type": "gaussian_sum", "offset": 0.15,
                "peaks": [{"cx": 0.35, "cy": 0.62, "amp": 1.0, "sx": 0.16, "sy": 0.13},
                          {"cx": 0.74, "cy": 0.30, "amp": 0.55, "sx": 0.20, "sy": 0.18}]},
      "labels": {"x": "控制增益 k_p", "y": "积分时间 T_i（s）", "z": "代价 J"},
      "levels": 9,
      "mark_extrema": true,
      "footnote": "来源：本文仿真设置；口径：归一化代价，仅作示意。"
    }

硬约束（prompts/40_diagram_field.md）
-----------------------------------
* 单调场用 :func:`~academic_fig.palette.cmap_seq`，有零平衡点的场用
  :func:`~academic_fig.palette.cmap_div`；禁 jet/rainbow；
* ``contourf`` + ``contour``（0.6–0.8pt）+ ``clabel``（8.0pt, inline），等值线 6–12 条；
* 色条标注 8.5pt、刻度 8.0pt、外框 0.8pt；
* 极值点 ``*`` 5pt（CLAY），坐标内联；
* **图注必须写明采样步长与采样点数**——本模块自动追加，不靠作者记；
* 3D 曲面：视角固定、``shade=False``、无自动网格、三个 pane 白底细边。
"""
from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt

from ..layout import footnote as _footnote
from ..palette import CLAY, GREY_LIGHT, INK, PAPER, cmap_div, cmap_seq
from ..style import axes as style_axes
from ._canvas import DOUBLE, SINGLE, TITLE_FS, load_spec
from ._guard import check_spec_keys, ensure_theme

__all__ = ["field", "sample_field", "FIELD_KINDS"]

FIELD_KINDS = ("contourf", "contour", "both", "surface3d", "scatter")
MARGINS = (0.14, 0.17, 0.96, 0.91)
# 2D 场的英寸边距：左（刻度 + 轴标签）/ 下（x 轴标签）/ 上（标题）/ 右（色条）
L_BOX, B_BOX, T_BOX, R_BOX = 0.74, 0.62, 0.50, 0.74
CB_LABEL_FS = 8.5
CB_TICK_FS = 8.0
CLABEL_FS = 8.0
LEVELS = 9


# --------------------------------------------------------------------------- 场
def _axis(spec: dict, key: str) -> np.ndarray:
    ax = spec.get(key) or {}
    lo = float(ax.get("min", 0.0))
    hi = float(ax.get("max", 1.0))
    n = int(ax.get("n", 41))
    if not hi > lo:
        raise ValueError(f"field(): {key} 的 max 必须大于 min（收到 {lo} → {hi}）")
    if n < 2:
        raise ValueError(f"field(): {key}.n 至少为 2（收到 {n}）")
    return np.linspace(lo, hi, n)


def _eval_field(f: dict, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """在给定网格上算场值——散点场也走这里，保证两种画法同源。"""
    kind = str(f.get("type", "gaussian_sum")).lower()
    if kind == "gaussian_sum":
        Z = np.full(X.shape, float(f.get("offset", 0.0)))
        for pk in f.get("peaks") or []:
            cx, cy = float(pk.get("cx", 0.5)), float(pk.get("cy", 0.5))
            sx = abs(float(pk.get("sx", pk.get("sigma", 0.15)))) or 1e-6
            sy = abs(float(pk.get("sy", pk.get("sigma", sx)))) or 1e-6
            amp = float(pk.get("amp", 1.0))
            th = np.deg2rad(float(pk.get("theta", 0.0)))
            dx, dy = X - cx, Y - cy
            u = dx * np.cos(th) + dy * np.sin(th)
            v = -dx * np.sin(th) + dy * np.cos(th)
            Z = Z + amp * np.exp(-0.5 * ((u / sx) ** 2 + (v / sy) ** 2))
        return Z
    if kind == "radial":
        cx, cy = float(f.get("cx", 0.5)), float(f.get("cy", 0.5))
        r = np.hypot(X - cx, Y - cy)
        sig = abs(float(f.get("sigma", 0.3))) or 1e-6
        return float(f.get("amp", 1.0)) * np.exp(-0.5 * (r / sig) ** 2)
    if kind == "saddle":
        cx, cy = float(f.get("cx", 0.5)), float(f.get("cy", 0.5))
        return (float(f.get("a", 1.0)) * ((X - cx) ** 2 - (Y - cy) ** 2)
                + float(f.get("offset", 0.0)))
    if kind == "ripples":
        cx, cy = float(f.get("cx", 0.5)), float(f.get("cy", 0.5))
        r = np.hypot(X - cx, Y - cy)
        return float(f.get("amp", 1.0)) * np.cos(float(f.get("k", 18.0)) * r)
    if kind == "plane":
        return (float(f.get("a", 1.0)) * (X - 0.5) + float(f.get("b", 0.0)) * (Y - 0.5)
                + float(f.get("c", 0.0)))
    raise ValueError(
        f"field(): field.type={kind!r} 不支持；可选 gaussian_sum / radial / "
        "saddle / ripples / plane / grid")


def sample_field(spec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """按规格生成 ``(X, Y, Z)``——不读任何外部数据文件。"""
    sp = spec if isinstance(spec, dict) else load_spec(spec)
    grid = sp.get("grid")
    if grid:
        xs = np.asarray(grid["x"], dtype=float)
        ys = np.asarray(grid["y"], dtype=float)
        zs = np.asarray(grid["z"], dtype=float)
        if zs.shape != (ys.size, xs.size):
            raise ValueError(
                f"field(): grid['z'] 形状应为 {(ys.size, xs.size)}，收到 {zs.shape}")
        X, Y = np.meshgrid(xs, ys)
        return X, Y, zs
    X, Y = np.meshgrid(_axis(sp, "x"), _axis(sp, "y"))
    return X, Y, _eval_field(sp.get("field") or {"type": "gaussian_sum"}, X, Y)


def _sampling_note(X, Y, kind: str, n_points: int, seed: int) -> str:
    dx = float(X[0, 1] - X[0, 0]) if X.shape[1] > 1 else 0.0
    dy = float(Y[1, 0] - Y[0, 0]) if Y.shape[0] > 1 else 0.0
    if kind == "scatter":
        return (f"散点 {n_points} 点，seed = {seed}；"
                f"等效步长 Δx ≈ {dx:.3g}、Δy ≈ {dy:.3g}。")
    return (f"网格 {X.shape[1]}×{X.shape[0]} = {n_points} 点，"
            f"Δx = {dx:.3g}、Δy = {dy:.3g}。")


def _compose_note(sp: dict, note, sampling: str) -> str:
    base = str(note if note is not None else (sp.get("footnote") or "")).strip()
    if not base:
        raise ValueError(
            "field(): 必须有图注（spec['footnote'] 或 note=…），写明来源 / 口径 / "
            "示意声明——这是本 skill 的硬规则，不是可选项")
    if "采样" in base:
        return base
    return f"{base}  {sampling}"


def _width_in(width) -> float:
    if isinstance(width, str):
        return {"single": SINGLE, "double": DOUBLE}[width]
    return float(width)


def _colorbar(fig, im, cax, label: str):
    """色条画在给定的 ``cax`` 上：与绘图区等高，不会顶出画布。"""
    cb = fig.colorbar(im, cax=cax)
    if label:
        cb.set_label(label, fontsize=CB_LABEL_FS, color=INK)
    cb.ax.tick_params(labelsize=CB_TICK_FS, direction="in", width=0.8, length=3.0,
                      colors=INK)
    cb.outline.set_linewidth(0.8)
    cb.outline.set_edgecolor(INK)
    return cb


# --------------------------------------------------------------------------- 2D
def _mark_extrema(ax, X, Y, Z, sp: dict):
    if sp.get("mark_extrema", True):
        iy, ix = np.unravel_index(int(np.nanargmax(Z)), Z.shape)
        x0, y0 = float(X[iy, ix]), float(Y[iy, ix])
        ax.plot([x0], [y0], marker="*", ms=5.0, mfc=CLAY, mec=CLAY, mew=0.0,
                ls="none", zorder=9)
        txt = str(sp.get("extrema_label") or "峰值")
        # 写在左上角而不是贴着极值点：贴点写一定会压住等高线数字（1.05 / 0.90），
        # 角注 + 单独的星标既清楚又不打架。
        ax.text(0.02, 0.98, f"{txt} ({x0:.2f}, {y0:.2f})", transform=ax.transAxes,
                ha="left", va="top", fontsize=CB_LABEL_FS, color=INK, zorder=9,
                bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.88, pad=1.8))
    for mk in sp.get("marks") or []:
        mx, my = float(mk["x"]), float(mk["y"])
        ax.plot([mx], [my], marker=str(mk.get("marker", "o")), ms=5.0, mfc="none",
                mec=INK, mew=1.0, ls="none", zorder=9)
        if mk.get("text"):
            ax.annotate(str(mk["text"]), xy=(mx, my), xytext=(5, 5),
                        textcoords="offset points", fontsize=CB_LABEL_FS,
                        color=INK, ha="left", va="bottom", zorder=9)


def _draw_2d(fig, sp: dict, X, Y, Z, kind: str, *, ax, cax=None):
    style_axes(ax, equal=True)
    diverging = sp.get("diverging")
    if diverging is None:
        diverging = bool(np.nanmin(Z) < -1e-9 < np.nanmax(Z))
    cmap = cmap_div() if diverging else cmap_seq()
    levels = min(max(int(sp.get("levels", LEVELS)), 6), 12)
    zmin, zmax = float(np.nanmin(Z)), float(np.nanmax(Z))
    if abs(zmax - zmin) < 1e-12:
        zmax = zmin + 1.0
    fmt = "%.2f" if max(abs(zmin), abs(zmax)) <= 10 else "%.0f"
    filled = None
    if kind in ("contourf", "both"):
        filled = ax.contourf(X, Y, Z, levels=levels, cmap=cmap, vmin=zmin,
                             vmax=zmax, antialiased=True)
    if kind == "contourf":
        # 这条等值线只为 clabel 服务：线本身要看不见，但**不能给 0.0**。
        # matplotlib 的 ``contour.negative_linestyle`` 默认 ``dashed``，负等值级
        # 会被画成虚线；虚线 dash 序列按 linewidth 缩放，0.0 缩成全 0，PDF 后端
        # 于是抛 ``ValueError: At least one value in the dash list must be positive``
        # （PNG 后端容忍，所以只有「负值场 + 存 PDF」才炸）。给个不可见的正线宽，
        # 并显式 solid —— 双保险，别让 dash 缩放这条链再有机会。
        lines = ax.contour(X, Y, Z, levels=levels, colors=INK, linewidths=0.001,
                           linestyles="solid")
        if sp.get("clabel", True):
            ax.clabel(lines, fmt=fmt, fontsize=CLABEL_FS, inline=True)
        im = filled
    else:
        lw = 0.7 if kind == "contour" else 0.55
        lines = ax.contour(X, Y, Z, levels=levels, colors=INK, linewidths=lw,
                           linestyles="solid",
                           alpha=1.0 if kind == "contour" else 0.8)
        if sp.get("clabel", True):
            ax.clabel(lines, fmt=fmt, fontsize=CLABEL_FS, inline=True,
                      inline_spacing=3)
        im = filled if filled is not None else lines
    _mark_extrema(ax, X, Y, Z, sp)
    labels = sp.get("labels") or {}
    ax.set_xlabel(str(labels.get("x", "")), fontsize=10)
    ax.set_ylabel(str(labels.get("y", "")), fontsize=10)
    ax.set_xlim(float(X[0, 0]), float(X[0, -1]))
    ax.set_ylim(float(Y[0, 0]), float(Y[-1, 0]))
    if im is not None and cax is not None:
        _colorbar(fig, im, cax, str(labels.get("z", "")))
    return ax


# --------------------------------------------------------------------------- 3D
def _draw_3d(sp: dict, X, Y, Z, width, height=None):
    w = _width_in(width if width is not None else sp.get("width", "double"))
    h = float(height) if height is not None else w * (0.80 if w > 5.0 else 0.94)
    fig = plt.figure(figsize=(w, h))
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0.01, 0.02, 0.84, 0.92], projection="3d", facecolor=PAPER)
    cmap = cmap_div() if (np.nanmin(Z) < -1e-9 < np.nanmax(Z)) else cmap_seq()
    z0, z1 = float(np.nanmin(Z)), float(np.nanmax(Z))
    surf = ax.plot_surface(X, Y, Z, cmap=cmap, vmin=z0, vmax=z1, linewidth=0.0,
                           antialiased=True, shade=False, rstride=1, cstride=1,
                           alpha=0.98, edgecolor="none")
    ax.contour(X, Y, Z, levels=6, colors=INK, linewidths=0.45, linestyles="solid",
               offset=z0, zdir="z")
    ax.set_zlim(z0, z1)
    ax.view_init(elev=float(sp.get("elev", 22.0)), azim=float(sp.get("azim", -64.0)))
    ax.grid(False)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor(PAPER)
        axis.pane.set_edgecolor(GREY_LIGHT)
        axis.pane.set_linewidth(0.6)
        info = axis._axinfo
        info["grid"]["linewidth"] = 0.0
        if "axisline" in info:
            info["axisline"]["color"] = INK
            info["axisline"]["linewidth"] = 0.8
        info["tick"]["inward_factor"] = 0.2
        info["tick"]["outward_factor"] = 0.0
    ax.tick_params(labelsize=8.0, pad=1.0, width=0.7, colors=INK, length=2.5)
    ax.set_box_aspect(tuple(float(v) for v in
                            (sp.get("box_aspect") or (1.25, 1.35, 0.95))))
    labels = sp.get("labels") or {}
    ax.set_xlabel(str(labels.get("x", "")), fontsize=10, labelpad=1.5)
    ax.set_ylabel(str(labels.get("y", "")), fontsize=10, labelpad=1.5)
    # z 轴标签会正好撞到右侧色条的刻度，所以只留一处：有色条就把名字交给色条。
    show_cb = sp.get("colorbar", True)
    if labels.get("z") and not show_cb:
        ax.set_zlabel(str(labels["z"]), fontsize=10, labelpad=2.0)
    if show_cb:
        cb = fig.colorbar(surf, ax=ax, fraction=0.030, pad=0.015, shrink=0.62,
                          anchor=(0.0, 0.5))
        if labels.get("z"):
            cb.set_label(str(labels["z"]), fontsize=CB_LABEL_FS, color=INK)
        cb.ax.tick_params(labelsize=CB_TICK_FS, direction="in", width=0.8,
                          length=2.5)
        cb.outline.set_linewidth(0.8)
        cb.outline.set_edgecolor(INK)
    return fig, ax


# --------------------------------------------------------------------------- 散点场
def _draw_scatter(fig, sp: dict, X, Y, Z, *, ax, cax=None):
    style_axes(ax, equal=True)
    n = int(sp.get("n_points", 90))
    seed = int(sp.get("seed", 0))
    rng = np.random.RandomState(seed)
    xs = rng.uniform(float(X[0, 0]), float(X[0, -1]), n)
    ys = rng.uniform(float(Y[0, 0]), float(Y[-1, 0]), n)
    f = sp.get("field") or {"type": "gaussian_sum"}
    zs = _eval_field(f, xs.reshape(1, -1), ys.reshape(1, -1)).ravel()
    cmap = cmap_div() if (np.nanmin(zs) < -1e-9 < np.nanmax(zs)) else cmap_seq()
    sc = ax.scatter(xs, ys, c=zs, s=float(sp.get("point_size", 14.0)), cmap=cmap,
                    edgecolors="none", alpha=0.95, zorder=3)
    labels = sp.get("labels") or {}
    ax.set_xlabel(str(labels.get("x", "")), fontsize=10)
    ax.set_ylabel(str(labels.get("y", "")), fontsize=10)
    ax.set_xlim(float(X[0, 0]), float(X[0, -1]))
    ax.set_ylim(float(Y[0, 0]), float(Y[-1, 0]))
    if cax is not None:
        _colorbar(fig, sc, cax, str(labels.get("z", "")))
    return ax


# --------------------------------------------------------------------------- 入口
def field(spec, *, kind=None, width=None, height=None, note=None, strict=True):
    """画一张场量 / 响应面图，返回 ``ax``。

    Parameters
    ----------
    spec : dict | str | pathlib.Path
        规格字典或 JSON 路径（场由公式声明，不读外部数据文件）。
    kind : {"contourf", "contour", "both", "surface3d", "scatter"}, optional
        覆盖 ``spec["kind"]``，默认 ``"both"``。
    width : {"single", "double"} or float, optional
        覆盖 ``spec["width"]``；二维场默认单栏（一个方形面板就是一个单栏图），
        3D 曲面默认双栏。
    height : float, optional
        只对 3D 生效；二维场的高度由数据域长宽比推出（equal aspect 的前提）。
    note : str, optional
        覆盖 ``spec["footnote"]``（图注必填：来源 / 口径 / 示意声明）。
    strict : bool
        签名与其它示意图入口保持一致；场图不做文本框溢出复核。

    Returns
    -------
    matplotlib.axes.Axes
    """
    sp = load_spec(spec)
    ensure_theme()
    check_spec_keys(sp, __name__, strict=strict, extra=(kind,))
    kind = str(kind or sp.get("kind") or "both").lower()
    if kind not in FIELD_KINDS:
        raise ValueError(f"field(): kind={kind!r} 不支持；可选 {FIELD_KINDS}")
    X, Y, Z = sample_field(sp)
    n = int(sp.get("n_points", 90)) if kind == "scatter" else X.shape[0] * X.shape[1]
    seed = int(sp.get("seed", 0))
    text = _compose_note(sp, note, _sampling_note(X, Y, kind, n, seed))

    if kind == "surface3d":
        fig, ax = _draw_3d(sp, X, Y, Z, width if width is not None else sp.get("width"),
                           height=height)
        if sp.get("title"):
            ax.set_title(str(sp["title"]), fontsize=TITLE_FS, color=INK, pad=2)
        _footnote(fig, text)
        return ax

    w_in = _width_in(width if width is not None else sp.get("width", "single"))
    xr = float(X[0, -1] - X[0, 0]) or 1.0
    yr = float(Y[-1, 0] - Y[0, 0]) or 1.0
    # 2D 版式按英寸摆：左边距给刻度与轴标签，右边距给色条（色条与绘图区等高），
    # 上边距给标题，下边距给 x 轴标签。这样色条不会顶出画布、也不会压刻度。
    ax_w = w_in - L_BOX - R_BOX
    if ax_w < 1.2:
        raise ValueError(
            f"field(): 画布宽 {w_in:.2f}in 扣掉边距后只剩 {ax_w:.2f}in，"
            "装不下绘图区；请用 width='double' 或更大的数值")
    ax_h = ax_w * (yr / xr)
    fig_h = ax_h + B_BOX + T_BOX
    fig = plt.figure(figsize=(w_in, fig_h))
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([L_BOX / w_in, B_BOX / fig_h, ax_w / w_in, ax_h / fig_h])
    cax = None
    if sp.get("colorbar", True):
        cax = fig.add_axes([(L_BOX + ax_w + 0.20) / w_in, B_BOX / fig_h,
                            0.13 / w_in, ax_h / fig_h])
    if kind == "scatter":
        ax = _draw_scatter(fig, sp, X, Y, Z, ax=ax, cax=cax)
    else:
        ax = _draw_2d(fig, sp, X, Y, Z, kind, ax=ax, cax=cax)
    if sp.get("title"):
        ax.set_title(str(sp["title"]), fontsize=TITLE_FS, color=INK, pad=4)
    _footnote(fig, text)
    return ax
