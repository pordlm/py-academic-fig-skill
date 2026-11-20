#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""场量图「负值场 → PDF」导出的回归测试（t24 R4-01）。

为什么需要这个脚本
-------------------
``field(kind="contourf")`` 里那条「只为 clabel 服务」的等值线曾经写成
``linewidths=0.0``。而 matplotlib 的 ``contour.negative_linestyle`` 默认是
``dashed``：负等值级会被画成虚线，虚线 dash 序列按 linewidth 缩放，``0.0`` 缩成
全 0 → **PDF 后端直接** ``ValueError: At least one value in the dash list must be
positive``（``backend_bases.RendererBase.set_dashes``）。PNG 后端容忍这种非法 dash，
所以症状是「PNG 能出、PDF 必崩」，而且**只有场里存在负值**时才触发——正峰场
一路绿灯，t2/t5/t13 的示例全是正场，因此三轮都没抓到。

diverging 场量图（一正一负双峰）恰恰是这个 kind 的主用例，等于主用例的 PDF 一直是
坏的。本脚本把它固化成回归：

1. **负值场 × 三种 kind**（``contourf`` / ``contour`` / ``both``）各存 PNG+PDF，
   断言两种格式都落盘、且 PDF > 10 KB（不是空壳）；
2. **结构断言**：图里每个 ``QuadContourSet`` 的线宽都 > 0，且没有虚线样式——
   即使将来有人把线宽改回 0.0 或把 ``linestyles`` 交还给 rcParams，也会当场红；
3. **用例自证**：断言这些等值级里确实有负值（否则这个测试根本没测到负值路径，
   属于换了种空转）；
4. **正场不回归**：全正场的 ``contourf`` 依旧正常出图（不能为了修负值把正场弄坏）。

退出码：全部断言通过 0，否则 1。

用法::

    python scripts/selftest_field_export.py
    python scripts/selftest_field_export.py --keep     # 保留落盘目录，便于肉眼看图
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")           # 必须在 import pyplot 之前；无显示环境也能跑

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:   # 直接 python scripts/selftest_field_export.py
    sys.path.insert(0, str(REPO))

import academic_fig as afg                       # noqa: E402
import academic_fig.diagrams as dg               # noqa: E402
from matplotlib.contour import QuadContourSet     # noqa: E402

MIN_PDF_BYTES = 10_000

# 一正一负双峰：场里既有正值也有负值 → 等值级必然跨零，正是崩溃路径。
DIVERGING_FIELD = {
    "x": {"min": 0, "max": 1, "n": 41},
    "y": {"min": 0, "max": 1, "n": 41},
    "field": {
        "type": "gaussian_sum",
        "offset": 0.0,
        "peaks": [
            {"cx": 0.35, "cy": 0.5, "amp": 1.2, "sx": 0.13, "sy": 0.16, "theta": 20},
            {"cx": 0.68, "cy": 0.45, "amp": -1.0, "sx": 0.12, "sy": 0.18, "theta": -15},
        ],
    },
    "labels": {"x": "x", "y": "y", "z": "势 φ"},
    "footnote": "示意计算（非实验数据）：高斯叠加场，双峰一正一负。",
}

POSITIVE_FIELD = {
    "x": {"min": 0, "max": 1, "n": 41},
    "y": {"min": 0, "max": 1, "n": 41},
    "field": {
        "type": "gaussian_sum",
        "offset": 0.2,
        "peaks": [
            {"cx": 0.40, "cy": 0.52, "amp": 1.0, "sx": 0.16, "sy": 0.18, "theta": 10},
            {"cx": 0.70, "cy": 0.40, "amp": 0.6, "sx": 0.12, "sy": 0.14, "theta": -20},
        ],
    },
    "labels": {"x": "x", "y": "y", "z": "势 φ"},
    "footnote": "示意计算（非实验数据）：高斯叠加场，全正。",
}


def _contour_sets(ax) -> list[QuadContourSet]:
    return [c for c in ax.collections if isinstance(c, QuadContourSet)]


def _dash_styles(cs: QuadContourSet) -> list[str]:
    """把 ContourSet 的每个线型归一成字符串，便于断言「没有虚线」。

    ``ContourSet.linestyles`` 有两种形态：单值（``"solid"`` / ``None``，此时它
    直接就是字符串，**别去迭代它**）或与 levels 等长的列表。
    """
    raw = getattr(cs, "linestyles", None)
    if raw is None or isinstance(raw, str):
        return ["solid"] if raw in (None, "solid") else [raw]
    out = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif item is None:
            out.append("solid")
        else:
            out.append("custom")          # (offset, (on, off)) 之类
    return out


def check_case(name: str, spec: dict, out_dir: Path, *, expect_negative: bool) -> list[str]:
    fails: list[str] = []
    try:
        ax = dg.field(dict(spec, kind=name))
        base = out_dir / f"fig01_field_{name}"
        paths = afg.save(ax.figure, base, formats=("png", "pdf"), check_name=False)
    except Exception as exc:                  # noqa: BLE001 —— 崩溃本身就是被测现象
        # 旧代码在 PDF 后端抛 ValueError: At least one value in the dash list must be
        # positive；这里必须**接住并报 FAIL**，否则门禁变成「脚本崩了 = 没测」。
        print(f"[FAIL]  {name:<10} 导出抛异常：{type(exc).__name__}: {exc}")
        return [f"{name}: 导出崩溃（{type(exc).__name__}: {exc}）"]

    for fmt in ("png", "pdf"):
        p = paths.get(fmt)
        if p is None or not p.exists() or p.stat().st_size == 0:
            fails.append(f"{name}: {fmt.upper()} 未落盘")
    pdf = paths.get("pdf")
    if pdf is not None and pdf.exists() and pdf.stat().st_size <= MIN_PDF_BYTES:
        fails.append(f"{name}: PDF 只有 {pdf.stat().st_size:,}B（≤ {MIN_PDF_BYTES:,}B），像空壳")

    sets = _contour_sets(ax)
    if not sets:
        fails.append(f"{name}: 图里没有 QuadContourSet，断言无从谈起")
    levels_all: list[float] = []
    for cs in sets:
        lws = [float(v) for v in cs.get_linewidths()]
        if lws and min(lws) <= 0.0:
            fails.append(f"{name}: 有等值线线宽 = {min(lws):g}（dash 会被缩成全 0，PDF 又会崩）")
        dashed = [s for s in _dash_styles(cs) if s != "solid"]
        if dashed:
            fails.append(f"{name}: 等值线用了非实线线型 {sorted(set(dashed))}（负值级会被画成虚线）")
        levels_all.extend(float(v) for v in cs.levels)

    has_neg = any(v < 0 for v in levels_all)
    if expect_negative and not has_neg:
        fails.append(f"{name}: 等值级全是正值 {levels_all[:3]}…，这条用例没测到负值路径")
    if not expect_negative and has_neg:
        fails.append(f"{name}: 正场用例里出现了负等值级，用例本身不对")

    sizes = "  ".join(f"{k}={v.stat().st_size:,}B" for k, v in afg.figure_paths(paths).items() if v.exists())
    tag = "ok" if not fails else "FAIL"
    print(f"[{tag}]  {name:<10} 等值线 {len(sets)} 组 / 等值级 {len(levels_all)} 个"
          f"{'（含负值）' if has_neg else ''}  {sizes}")
    for f in fails:
        print(f"        - {f}")
    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", action="store_true", help="保留落盘目录")
    args = ap.parse_args(argv)

    afg.apply_theme()
    out_dir = Path(tempfile.mkdtemp(prefix="afg_field_export_"))
    fails: list[str] = []
    try:
        for kind in ("contourf", "contour", "both"):
            fails += check_case(kind, DIVERGING_FIELD, out_dir, expect_negative=True)
        # 正场：修负值不能把正场弄坏（contourf 是默认推荐用法）
        fails += check_case("contourf", POSITIVE_FIELD, out_dir, expect_negative=False)
    finally:
        if args.keep:
            print(f"落盘目录：{out_dir}")
        else:
            shutil.rmtree(out_dir, ignore_errors=True)

    print("==> 全部通过" if not fails else f"==> {len(fails)} 条失败")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())