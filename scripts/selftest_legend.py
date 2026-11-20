#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""``afg.legend()`` 的回归测试（t28 B1 / B2）。

为什么需要这个脚本
------------------
``style.legend()`` 里曾经有两处错误，都是「看起来没事」的类型，靠人眼和成品图
发现不了：

**B1 —— ``ax.relim()`` 把视窗缩进数据里。**
为了等 ``fill_between``/``errorbar`` 把范围落进 viewLim，这段代码先 ``relim()``
再 ``autoscale_view()``。但 ``relim()`` 的语义是「按 artist 重算 dataLim」，对
scatter（``PathCollection``）+ 回归线这种组合会把 dataLim 收缩：实测
``y`` 从 ``(-1.294, 1.166)`` 缩到 ``(-1.043, 0.932)``，随后 autoscale 把视窗一起
缩掉 —— 交付图 ``relation/fig01_scatter`` 有 **18/32 个点（56%）画到框外**。
典型症状是「图例位置挑得没问题，但底部一排点不见了」。修法是**不碰视窗**：
只 ``fig.canvas.draw()``，让 matplotlib 自己的 autoscale 把集合算进来。

**B2 —— 合并已有图例的代码路径必然崩溃。**
``Legend`` 没有 ``get_legend_handles_labels()``（那是 ``Axes`` 的方法），而这一行
正写在 docstring 承诺的「不会静默覆盖已有图例，新条目合并进去」分支里 —— 也就是
说那条承诺从写下那天起就是必崩的。

断言（对承诺逐条写，而不是「看起来对」）
----------------------------------------
1. ``scatter(fit=True)`` + 图例：不抛异常；``ylim`` 覆盖数据 ``y.min()/y.max()``
   （留 2% 余量判定），且**框外点数 == 0**；
2. ``afg.legend(ax)`` 连调两次：不抛异常；第二次返回的条目数**不减少**；
   另加一条「合并新条目」：散点图已有图例后补一条带 label 的参考线，再调
   ``afg.legend(ax)``，条目数必须 +1（这是合并语义的正向证据，不是幂等）；
3. **像素级**：渲染后统计「与画框边线相接」的 marker 数（中心距边线 < marker 半径，
   或中心已在框外），必须为 0 —— 防止将来又把视窗缩回去。

退出码：全部断言通过 0，否则 1。

用法::

    python scripts/selftest_legend.py
    python scripts/selftest_legend.py --keep     # 保留落盘目录，便于肉眼看图
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")           # 必须在 import pyplot 之前；无显示环境也能跑

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:   # 直接 python scripts/selftest_legend.py
    sys.path.insert(0, str(REPO))

import numpy as np                               # noqa: E402

import academic_fig as afg                       # noqa: E402

DATA = REPO / "examples" / "data" / "classification.csv"
MARGIN_FRAC = 0.02              # 覆盖判定的余量（视窗比数据紧 2% 以内算覆盖）
EDGE_TOL_PX = 0.5               # 中心距边线多少像素算「贴线」
DEFAULT_MARKER_PT = 5.0         # 未显式给 s 时的 marker 直径（pt，保守估计）


def load_scores() -> tuple[np.ndarray, np.ndarray, list[str]]:
    """读示例数据：两种模型的打分 + 真实标签（分组名）。"""
    with DATA.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    x = np.array([float(r["y_score_lr"]) for r in rows], dtype=float)
    y = np.array([float(r["y_score_cnn"]) for r in rows], dtype=float)
    groups = ["阳性" if int(r["y_true"]) else "阴性" for r in rows]
    return x, y, groups


def outside_count(ax, x: np.ndarray, y: np.ndarray) -> int:
    """落在视窗外的点数（零余量，严格判定）。"""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    out = (x < x0) | (x > x1) | (y < y0) | (y > y1)
    return int(np.sum(out))


def covers_data(ax, values: np.ndarray, axis: str = "y") -> bool:
    """视窗是否覆盖数据（允许比数据紧 2% 以内）。"""
    lo, hi = (ax.get_ylim() if axis == "y" else ax.get_xlim())
    v0, v1 = float(np.min(values)), float(np.max(values))
    span = max(v1 - v0, 1e-12)
    return lo <= v0 + span * MARGIN_FRAC and hi >= v1 - span * MARGIN_FRAC


def touching_markers(fig, ax, x: np.ndarray, y: np.ndarray) -> list[str]:
    """渲染后与画框边线相接（或已在框外）的 marker。

    marker 中心距任一边线小于自身半径 → 视觉上一定被切；中心越界 → 整颗在外面。
    半径按 ``scatter`` 默认 marker 尺寸保守取值（宁可多报，不可漏报）。
    """
    fig.canvas.draw()
    bb = ax.get_window_extent()
    radius_px = DEFAULT_MARKER_PT / 2.0 * fig.dpi / 72.0
    disp = ax.transData.transform(np.column_stack([x, y]))
    hits: list[str] = []
    for (px, py), xv, yv in zip(disp, x, y):
        if not (bb.x0 <= px <= bb.x1 and bb.y0 <= py <= bb.y1):
            hits.append(f"({xv:.3f},{yv:.3f}) 中心已在框外")
            continue
        gaps = (px - bb.x0, bb.x1 - px, py - bb.y0, bb.y1 - py)
        if min(gaps) < radius_px + EDGE_TOL_PX:
            hits.append(f"({xv:.3f},{yv:.3f}) 距边线 {min(gaps):.1f}px < 半径 {radius_px:.1f}px")
    return hits


def _draw_scatter(*, fit: bool, band: bool = True, legend: bool = True):
    x, y, groups = load_scores()
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", xlabel="逻辑回归打分", ylabel="卷积网络打分")
    afg.plots.scatter(ax, x, y, groups=groups, fit=fit, fit_band=band,
                      legend=legend, equal=False)
    return fig, ax, x, y


def case_coverage(fit: bool, band: bool) -> list[str]:
    """断言 1/3：不裁点，且没有 marker 贴到画框上。"""
    fails: list[str] = []
    tag = f"fit={fit!s:<5} band={band!s:<5}"
    try:
        fig, ax, x, y = _draw_scatter(fit=fit, band=band)
        fig.canvas.draw()
    except Exception as exc:                  # noqa: BLE001 —— 崩溃本身即被测现象
        print(f"[FAIL]  {tag} 抛异常：{type(exc).__name__}: {exc}")
        return [f"{tag}: 抛异常 {type(exc).__name__}: {exc}"]

    out = outside_count(ax, x, y)
    y0, y1 = ax.get_ylim()
    if out:
        fails.append(f"{tag}: {out}/{len(x)} 个点在框外（ylim=({y0:.3f}, {y1:.3f})，"
                     f"数据 y=({y.min():.3f}, {y.max():.3f})）")
    if not covers_data(ax, y, "y"):
        fails.append(f"{tag}: ylim=({y0:.3f}, {y1:.3f}) 没覆盖数据 y∈[{y.min():.3f}, {y.max():.3f}]")
    if not covers_data(ax, x, "x"):
        fails.append(f"{tag}: xlim 没覆盖数据 x∈[{x.min():.3f}, {x.max():.3f}]")

    touching = touching_markers(fig, ax, x, y)
    if touching:
        fails.append(f"{tag}: {len(touching)} 个 marker 与画框相接（例：{touching[0]}）")
    print(f"[{'ok' if not fails else 'FAIL'}]  {tag} ylim=({y0:.3f}, {y1:.3f})  "
          f"框外 {out}/{len(x)}  贴边 {len(touching)}")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return fails


def case_merge_twice() -> list[str]:
    """断言 2：连调两次 ``afg.legend`` 不崩、条目不减（幂等而非覆盖）。"""
    fails: list[str] = []
    fig, ax, _x, _y = _draw_scatter(fit=True)
    n1 = len(ax.get_legend().get_texts()) if ax.get_legend() is not None else 0
    try:
        first = afg.legend(ax)
        second = afg.legend(ax)
    except Exception as exc:                  # noqa: BLE001
        print(f"[FAIL]  连调两次 legend()：{type(exc).__name__}: {exc}")
        return [f"连调两次 legend(): {type(exc).__name__}: {exc}"]
    n2 = len(first.get_texts()) if first is not None else 0
    n3 = len(second.get_texts()) if second is not None else 0
    if second is None:
        fails.append("连调两次 legend(): 第二次返回 None（轴上有条目却拿不到图例）")
    if n3 < n1:
        fails.append(f"连调两次 legend(): 条目从 {n1} 减到 {n3}（覆盖了已有图例）")
    print(f"[{'ok' if not fails else 'FAIL'}]  连调两次 legend()   条目 {n1} -> {n2} -> {n3}")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return fails


def case_merge_new_entry() -> list[str]:
    """合并语义的正向证据：补一条带 label 的参考线后被合并进图例（条目 +1）。"""
    fails: list[str] = []
    fig, ax, _x, _y = _draw_scatter(fit=True)
    before = len(ax.get_legend().get_texts()) if ax.get_legend() is not None else 0
    ax.plot([0.0, 1.0], [0.1, 1.0], color=afg.palette.CLAY, lw=1.0, label="参考线")
    try:
        leg = afg.legend(ax)
    except Exception as exc:                  # noqa: BLE001
        print(f"[FAIL]  合并新条目：{type(exc).__name__}: {exc}")
        return [f"合并新条目: {type(exc).__name__}: {exc}"]
    after = len(leg.get_texts()) if leg is not None else 0
    labels = [t.get_text() for t in leg.get_texts()] if leg is not None else []
    if after != before + 1:
        fails.append(f"合并新条目：条目 {before} -> {after}（期望 {before + 1}），标签 {labels}")
    if "参考线" not in labels:
        fails.append(f"合并新条目：新条目「参考线」不在图例里，实际 {labels}")
    print(f"[{'ok' if not fails else 'FAIL'}]  合并新条目           条目 {before} -> {after}  {labels}")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", action="store_true", help="保留落盘目录")
    args = ap.parse_args(argv)

    afg.apply_theme()
    out_dir = Path(tempfile.mkdtemp(prefix="afg_legend_"))
    fails: list[str] = []
    try:
        for fit, band in ((True, True), (True, False), (False, False)):
            fails += case_coverage(fit=fit, band=band)
        fails += case_merge_twice()
        fails += case_merge_new_entry()
        # 存一张「散点 + 回归 + 图例」的落盘图，供肉眼看底部一排点是否完整
        fig, ax, _x, _y = _draw_scatter(fit=True)
        afg.legend(ax)
        afg.footnote(fig, "数据来源：examples/data/classification.csv；口径：n=32，最小二乘拟合。")
        afg.save(fig, out_dir / "fig01_legend_scatter", formats=("png", "pdf"),
                 check_name=False)
        import matplotlib.pyplot as plt
        plt.close(fig)
    finally:
        if args.keep:
            print(f"落盘目录：{out_dir}")
        else:
            shutil.rmtree(out_dir, ignore_errors=True)

    print("==> 全部通过" if not fails else f"==> {len(fails)} 条失败")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())