#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配色检查的「自证有效」测试（F-01）。

为什么需要这个脚本
------------------
配色检查曾经**空转**：它按色相判定，matplotlib 默认色 `#1F77B4` 的色相恰好落在
允许色相附近，于是 jet 色阶和默认 C0 都能通过——检查器永远说「没问题」。
改判据（RGB 最近色距）之后必须能证明它真的拦得住，否则等于换了一种空转。

本脚本做三件事：

1. **反例必被抓**：临时目录里画 (a) `jet` 色阶散点、(b) matplotlib 默认 C0 折线、
   (c) `tab10` 分组柱，逐个过 :func:`academic_fig.checks.check_dir`，
   断言每个文件至少 1 条 ``code='color'`` 的 error；
2. **正例不被误伤**：同一目录画一张只用 ``palette`` 语义色的图，断言 0 条配色问题；
3. **正式产物零污染**：对 ``examples/out``（若存在）跑一遍，断言 0 条配色问题。

顺带打印每张图的四边留白（非白像素外接框），留白 < ``MIN_MARGIN_PX`` 时给出警示
（留白的强制校验在 ``scripts/check_margins.py``，这里只做提示）。

退出码：全部断言通过 0，否则 1。

用法::

    python scripts/selftest_color_check.py
    python scripts/selftest_color_check.py --verbose   # 打印每条 issue 原文
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")           # 必须在 import pyplot 之前；无显示环境也能跑

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:   # 直接 python scripts/selftest_color_check.py
    sys.path.insert(0, str(REPO))

import numpy as np                              # noqa: E402
import matplotlib.pyplot as plt                 # noqa: E402

import academic_fig as afg                      # noqa: E402
from academic_fig import checks, palette as pal  # noqa: E402

OUT = REPO / "examples" / "out"


# --------------------------------------------------------------------------- #
# 反例 / 正例
# --------------------------------------------------------------------------- #
def _save(fig, base: Path, afg_save: bool = False) -> Path:
    """落盘成 300dpi PNG；返回 PNG 路径。

    ``afg_save=True`` 走框架的 :func:`academic_fig.save`（自带尺寸校验），
    反例故意不走，免得框架的越界告警掩盖「配色检查是否生效」这一被测目标。
    """
    if afg_save:
        return afg.save(fig, base, formats=("png",))["png"]
    path = base.with_suffix(".png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def make_jet(workdir: Path) -> Path:
    """反例 1：``jet`` 连续色阶散点。"""
    rng = np.random.default_rng(7)
    x, y = rng.normal(size=(2, 400))
    fig, ax = plt.subplots(figsize=(3.35, 2.6))
    sc = ax.scatter(x, y, c=x + y, cmap="jet", s=18, linewidths=0, vmin=-3, vmax=3)
    fig.colorbar(sc, ax=ax)
    return _save(fig, workdir / "fig01_jet")


def make_default_c0(workdir: Path) -> Path:
    """反例 2：matplotlib 默认配色周期第一色 ``#1F77B4``（C0）。"""
    t = np.linspace(0, 2 * np.pi, 60)
    fig, ax = plt.subplots(figsize=(3.35, 2.6))
    ax.plot(t, np.sin(t) * 10 + 40, linewidth=1.6)     # 不给 color → 默认 C0
    return _save(fig, workdir / "fig02_default")


def make_tab10(workdir: Path) -> Path:
    """反例 3：``tab10`` 分组柱状图。"""
    fig, ax = plt.subplots(figsize=(3.35, 2.6))
    vals = np.array([12, 18, 9, 15, 7])
    ax.bar(np.arange(5), vals, color=plt.get_cmap("tab10").colors[:5])
    return _save(fig, workdir / "fig03_tab10")


def make_good(workdir: Path) -> Path:
    """正例：只用 ``palette`` 语义色 + ``tint()`` 浅底。"""
    afg.apply_theme()
    fig, ax = afg.paper_fig("single")
    x = np.arange(5)
    ax.bar(x, [12, 18, 9, 15, 7], color=pal.BLUE, width=0.55, linewidth=0.6,
           edgecolor=pal.INK, zorder=3)
    ax.plot(x, [14, 16, 11, 13, 9], color=pal.CLAY, marker="o", markersize=3.2,
            linewidth=1.0, zorder=4)
    ax.axhspan(0, 5, color=pal.tint(pal.CLAY, 0.12), zorder=1)
    afg.panel(ax, "(a)", title="正例：语义色", xlabel="类别", ylabel="响应值（a.u.）")
    afg.footnote(fig, "数据来源：自测脚本；口径：单批次均值。")
    return _save(fig, workdir / "fig04_good", afg_save=True)


# --------------------------------------------------------------------------- #
# 断言
# --------------------------------------------------------------------------- #
def _color_issues(path: Path):
    """取 ``path.parent`` 目录里属于 ``path`` 的配色 issue。

    :class:`academic_fig.checks.Issue` 的 ``file`` 是相对被扫目录的 POSIX 路径，
    所以按名字比对，不要拿绝对路径去 resolve。
    """
    name = path.name
    return [i for i in checks.check_dir(path.parent, glyph_probe=False)
            if i.code == "color" and Path(str(i.file)).name == name]


def _margins_line(path: Path) -> str:
    m = checks.png_margins(path)
    if not m:
        return f"{path.name}: 留白读不出"
    worst = min(m["left"], m["right"], m["top"], m["bottom"])
    flag = "" if worst >= checks.MIN_MARGIN_PX else "  <== 留白不足"
    return (f"{path.name}: 左 {m['left']:3d} 右 {m['right']:3d} "
            f"上 {m['top']:3d} 下 {m['bottom']:3d} px（最小 {worst}）{flag}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="selftest_color_check.py",
        description="证明配色检查真的能拦住 jet / tab10 / matplotlib 默认色。")
    ap.add_argument("--verbose", action="store_true", help="打印每条 issue 原文")
    args = ap.parse_args(argv)

    failures: list[str] = []
    print("=" * 72)
    print("配色检查自证（F-01）：反例必须被抓，正例不能被误伤")
    print("=" * 72)

    with tempfile.TemporaryDirectory(prefix="afg_colorcheck_") as tmp:
        workdir = Path(tmp)
        cases = [
            ("jet 色阶散点", make_jet(workdir)),
            ("matplotlib 默认 C0", make_default_c0(workdir)),
            ("tab10 分组柱", make_tab10(workdir)),
        ]
        for label, png in cases:
            issues = _color_issues(png)
            ok = len(issues) >= 1
            print(f"[{'PASS' if ok else 'FAIL'}] 反例 {label}: "
                  f"{len(issues)} 条配色 issue")
            if not ok:
                failures.append(f"反例「{label}」没有被配色检查抓到")
            for it in issues[:3]:
                print(f"        - {it.message}")
                if args.verbose and it.fix_hint:
                    print(f"          修法：{it.fix_hint}")

        good_png = make_good(workdir)
        good_issues = _color_issues(good_png)
        ok = not good_issues
        print(f"[{'PASS' if ok else 'FAIL'}] 正例 语义色图: "
              f"{len(good_issues)} 条配色 issue（应为 0）")
        if not ok:
            failures.append("正例（只用 palette 语义色）被误报")
            for it in good_issues[:3]:
                print(f"        - {it.message}")
        print("       " + _margins_line(good_png))

    if OUT.is_dir():
        issues = [i for i in checks.check_dir(OUT, glyph_probe=False)
                  if i.code == "color"]
        ok = not issues
        print(f"[{'PASS' if ok else 'FAIL'}] 正式产物 examples/out: "
              f"{len(issues)} 条配色 issue（应为 0）")
        if not ok:
            failures.append(f"examples/out 有 {len(issues)} 条配色问题")
            for it in issues[:5]:
                print(f"        - {it.file}: {it.message}")
        narrow = []
        for png in sorted(OUT.rglob("*.png")):
            m = checks.png_margins(png)
            if not m:
                continue
            worst = min(m["left"], m["right"], m["top"], m["bottom"])
            if worst < checks.MIN_MARGIN_PX:
                narrow.append((png, m, worst))
        if narrow:
            print(f"[WARN] {len(narrow)} 张图四边留白 < {checks.MIN_MARGIN_PX}px"
                  f"（强制校验见 scripts/check_margins.py）")
            for png, m, worst in narrow[:8]:
                print(f"        - {png.relative_to(REPO).as_posix()}: 最小 {worst}px")
        else:
            print(f"[PASS] 全 {len(list(OUT.rglob('*.png')))} 张图四边留白 "
                  f"≥ {checks.MIN_MARGIN_PX}px")
    else:
        print("[SKIP] examples/out 不存在，跳过正式产物核对")

    print("-" * 72)
    if failures:
        print(f"结论：{len(failures)} 项未通过")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("结论：配色检查有效（反例全抓、正例无误报、正式产物零污染）")
    return 0


if __name__ == "__main__":
    sys.exit(main())