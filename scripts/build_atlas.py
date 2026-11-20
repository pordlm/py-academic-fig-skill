#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重建 ``assets/atlas/`` 精选参考图（README「参考图」一节用）。

为什么要有这个脚本
------------------
``assets/atlas/`` 原来是一批**一次性脚本**渲出来的快照，没有生成器：
框架的导出逻辑一改（例如 F-03 收紧四边留白），它们就悄悄落后于
``examples/out``——实测 8 张里 7 张四边只剩 1–7px，README 里挂的却是新代码的
效果图。这个脚本把「图集 = examples 里的同一批渲染器 + 同一批数据」写死成
可复现映射，跑一次即重新生成，且顺带断言每张都过四边留白下限。

映射关系（atlas 文件名 ← examples 里的渲染函数）
     fig01_bar          ← render_plots.fig_bar        （误差棒+显著性括号+强调柱）
     fig02_line         ← render_plots.fig_line       （多序列+虚实+±1 SD 带）
     fig03_violin       ← render_plots.fig_violin     （小提琴+抖动散点）
     fig04_scatter      ← render_plots.fig_scatter    （背景点云+分组+回归）
     fig05_roc          ← render_plots.fig_roc        （ROC+AUC 进图例）
     fig06_heatmap      ← render_plots.fig_heatmap    （行内 z-score 双色阶）
     fig07_km           ← render_plots.fig_km         （阶梯+删失+风险人数表）
     fig08_architecture ← diagrams.architecture       （arch_layers.json）

用法::

    python scripts/build_atlas.py            # 重建 8 张（PNG+PDF）
    python scripts/build_atlas.py --check    # 只量留白，不重画
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")            # 必须在 import pyplot 之前

REPO = Path(__file__).resolve().parents[1]
for extra in (REPO, REPO / "examples"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import matplotlib.pyplot as plt      # noqa: E402

import academic_fig as afg           # noqa: E402
from academic_fig import checks      # noqa: E402

ATLAS = REPO / "assets" / "atlas"
DATA = REPO / "examples" / "data"

#: atlas 文件名 → examples/render_plots.py 里的函数名
PLOT_MAP: dict[str, str] = {
    "fig01_bar": "fig_bar",
    "fig02_line": "fig_line",
    "fig03_violin": "fig_violin",
    "fig04_scatter": "fig_scatter",
    "fig05_roc": "fig_roc",
    "fig06_heatmap": "fig_heatmap",
    "fig07_km": "fig_km",
}


def _build_plots() -> None:
    import render_plots as rp        # examples/render_plots.py（已在 sys.path 上）

    afg.apply_theme()
    for stem, fn_name in PLOT_MAP.items():
        fig = getattr(rp, fn_name)()
        paths = afg.save(fig, ATLAS / stem)
        plt.close(fig)
        print(f"[ok] {stem:<20} <- render_plots.{fn_name:<12} "
              + ", ".join(p.suffix for p in afg.figure_paths(paths).values()))


def _build_architecture() -> None:
    import render_diagrams as rd     # examples/render_diagrams.py
    from academic_fig import diagrams

    afg.apply_theme()
    ax = diagrams.architecture(DATA / "diagrams" / "arch_layers.json")
    paths = afg.save(ax.figure, ATLAS / "fig08_architecture")
    plt.close(ax.figure)
    print(f"[ok] {'fig08_architecture':<20} <- diagrams.architecture      "
          + ", ".join(p.suffix for p in afg.figure_paths(paths).values()))
    del rd


def _report() -> int:
    """量 atlas 里每张 PNG 的四边留白；任一 < 下限返回 1。"""
    bad = 0
    for png in sorted(ATLAS.glob("*.png")):
        m = checks.png_margins(png)
        if not m:
            print(f"[??] {png.name}: 读不出留白")
            bad += 1
            continue
        worst = min(m["left"], m["right"], m["top"], m["bottom"])
        flag = "" if worst >= checks.MIN_MARGIN_PX else "   <<< 不足"
        if worst < checks.MIN_MARGIN_PX:
            bad += 1
        print(f"     {png.name:<26} L{m['left']:3d} R{m['right']:3d} "
              f"T{m['top']:3d} B{m['bottom']:3d}  min {worst:3d}{flag}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="build_atlas.py",
        description="重建 assets/atlas/ 精选参考图并核对四边留白")
    ap.add_argument("--check", action="store_true", help="只核对留白，不重画")
    args = ap.parse_args(argv)

    if not args.check:
        ATLAS.mkdir(parents=True, exist_ok=True)
        _build_plots()
        _build_architecture()

    print(f"\natlas 留白核对（下限 {checks.MIN_MARGIN_PX}px）：")
    rc = _report()
    print("[OK] atlas 全部合规" if rc == 0 else "[FAIL] atlas 有图留白不足")
    return rc


if __name__ == "__main__":
    sys.exit(main())