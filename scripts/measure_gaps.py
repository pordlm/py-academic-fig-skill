# -*- coding: utf-8 -*-
"""像素级量层带边框上的「穿框白口」宽度（t12 验收用）。

用法::

    python scripts/measure_gaps.py                 # 默认量 fig01/02/05/06
    python scripts/measure_gaps.py --dpi 300 --limit 16

做法不是「肉眼看图」，而是把图**按 300dpi 原样重画一遍**（``bbox_inches=None``，
保证 1px = 1/300in），再从 ``ax`` 里取出每条层带的上下边框数据坐标，换算成像素
行，沿该行扫一条 3px 高的带子：

* 边框是 INK（#1A1A1A），填充是 WASH（#F6F4F0）——两者亮度差极大，阈值 200 很稳；
* 白口是 PAPER（#FFFFFF），在该行上表现为一段「亮」；
* 只统计**两侧都被边框包住**的亮段（排除圆角处的起止）且宽 2–80px 的段。

输出每处白口的中心（px / in）与宽度（px），并按 :data:`BORDER_BREAK` 的口径
断言 ≤16px（目标 ≤12px）。同时用 ``ax._afg_links`` 复核「每处白口正下方都确实
有一条连线穿过」，避免把别的缺口当成白口。
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np                                            # noqa: E402
from matplotlib import pyplot as plt                          # noqa: E402
from matplotlib.patches import FancyBboxPatch                  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import academic_fig as afg                                     # noqa: E402
from academic_fig import diagrams                              # noqa: E402
from academic_fig.diagrams import _canvas as canvas            # noqa: E402
from academic_fig.palette import PAPER                         # noqa: E402

DATA = ROOT / "examples" / "data" / "diagrams"

# (编号, 名称, 入口, 规格文件)
FIGURES = [
    ("01", "arch_layers", "architecture", "arch_layers.json"),
    ("02", "arch_fusion", "architecture", "arch_fusion.json"),
    ("11", "arch_crossing", "architecture", "arch_crossing.json"),
    ("05", "field_gaussian", "field", "field_gaussian.json"),
    ("06", "field_surface", "field", "field_surface.json"),
]

DARK = 200          # 亮度低于它算墨线
MIN_RUN, MAX_RUN = 3, 80


def _bands(ax):
    """层带 = zorder 为 1 的 FancyBboxPatch（模块框是 3，场景框更高）。

    :func:`academic_fig.diagrams._canvas.rounded_box` 把 ``pad`` 内缩后再交给
    ``FancyBboxPatch``（它自己再外扩），所以补丁框比可见外沿小 ``2*pad``——
    这里加回去，量到的才是真正的边框位置。
    """
    pad = canvas.BOX_PAD
    out = []
    for p in ax.patches:
        if isinstance(p, FancyBboxPatch) and abs(p.get_zorder() - 1.0) < 1e-6:
            out.append((p.get_x() - pad, p.get_y() - pad,
                        p.get_width() + 2 * pad, p.get_height() + 2 * pad))
    return out


def _longest(mask) -> int:
    """最长连续 True 段长度。"""
    best = run = 0
    for v in mask:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def _runs(mask):
    """把布尔序列切成 (start, end) 的连续 True 段，end 不含。"""
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def _link_crosses(ax, x_data: float, y_data: float, tol_px: float, px_per_in: float):
    """该处是否真有一条（近）竖直连线穿过——白口必须服务一条线。"""
    tol = tol_px / px_per_in
    for p0, p1, _lw in ax.__dict__.get("_afg_links") or []:
        if abs(p0[0] - p1[0]) > 1e-3:                  # 只认竖直段
            continue
        lo, hi = sorted((p0[1], p1[1]))
        if lo - 0.02 <= y_data <= hi + 0.02 and abs(p0[0] - x_data) <= tol + 1e-3:
            return True
    return False


def measure(idx, name, entry, spec_name, dpi=300):
    spec = DATA / spec_name
    fn = diagrams.RENDERERS[entry]
    ax = fn(spec)
    fig = ax.figure
    fig.set_dpi(dpi)
    fig.canvas.draw()

    bands = _bands(ax)
    if not bands:
        plt.close(fig)
        print(f"fig{idx}_{name:<16} 无层带（{entry}），跳过")
        return []

    w_in, h_in = fig.get_size_inches()
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "probe.png"
        fig.savefig(png, dpi=dpi, facecolor=PAPER, bbox_inches=None, pad_inches=0)
        from PIL import Image
        img = np.asarray(Image.open(png).convert("L"), dtype=np.uint8)
    H, W = img.shape

    # 坐标映射：宽度方向 axes 铺满画布（fig 宽 = 规格宽），x 一一对应；高度方向
    # 存盘时脚注会让画布长高几 px，bb 已经不准，所以不硬套——先用「期望的层带
    # 边框 y 值」去图里搜一个竖直偏移 b（row = b - dpi*y），命中率最高者即为真值。
    # 这样既不依赖存盘前后的尺寸，又顺带证明了「这一行确实是边框」。
    xlim = ax.get_xlim()
    px_per_in = W / float(xlim[1] - xlim[0])

    edges = []
    for bi, (bx, by, bw, bh) in enumerate(bands):
        edges += [(bi, "top", by + bh), (bi, "bottom", by)]
    edges.sort(key=lambda t: -t[2])

    row_frac = (img < DARK).sum(axis=1) / float(W)
    best_b, best_score, best_rows = None, -1.0, None
    for b in np.arange(0.0, H + dpi, 0.5):
        rows = [int(round(b - dpi * y)) for _bi, _s, y in edges]
        if min(rows) < 2 or max(rows) > H - 3:
            continue
        score = float(np.mean([row_frac[max(0, r - 1):r + 2].max() for r in rows]))
        if score > best_score:
            best_b, best_score, best_rows = b, score, rows
    if best_score < 0.70:
        raise RuntimeError(
            f"层带边框定位失败（最佳命中率 {best_score:.2f} < 0.70）；"
            "可能是阈值或画布宽度变了，检查 measure_gaps 的假设")

    results = []
    for row, (bi, side, y) in zip(best_rows, edges):
        strip = img[max(0, row - 1):row + 2]
        dark = strip.min(axis=0) < DARK
        cols = np.where(dark)[0]
        x_lo, x_hi = int(cols[0]) + 18, int(cols[-1]) - 18     # 让开圆角（≈15px）
        # 白口里通常还有一条 3.8px 的箭头轴穿过（zorder 6 在 PAPER 白口之上），
        # 所以「缺口宽度」要按两侧**长暗段**（边框本体）之间的空档算，不能只数亮像素。
        segs = [(s + x_lo, e + x_lo) for s, e in _runs(dark[x_lo:x_hi])
                if (e - s) >= 12]
        for (s0, e0), (s1, e1) in zip(segs, segs[1:]):
            width = s1 - e0
            if not (MIN_RUN <= width <= MAX_RUN):
                continue
            cx_px = (e0 + s1) / 2.0
            cx_in = cx_px / px_per_in
            ok = _link_crosses(ax, cx_in, y, tol_px=3.0, px_per_in=px_per_in)
            results.append(dict(band=bi, side=side, y=y, x=cx_in,
                                px=cx_px, width=width, link=ok, row=row))
    plt.close(fig)

    widths = [r["width"] for r in results]
    bad = [r for r in results if not r["link"]]
    print(f"fig{idx}_{name:<16} 层带 {len(bands)} 条，白口 {len(results)} 处，"
          f"宽 {min(widths) if widths else 0}–{max(widths) if widths else 0}px"
          f"（口径 {canvas.gap_width_px(dpi):.1f}px）"
          + ("" if not bad else f"  !! {len(bad)} 处找不到穿线"))
    for r in results:
        print(f"    band{r['band']} {r['side']:<6} y={r['y']:.3f}in "
              f"x={r['x']:.3f}in ({r['px']:.0f}px)  宽 {r['width']}px"
              f"  {'线✓' if r['link'] else '线✗'}")
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="量层带穿框白口的像素宽度")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--limit", type=float, default=16.0,
                    help="单处白口宽度上限（px），默认 16")
    args = ap.parse_args(argv)
    afg.apply_theme()

    all_res = []
    for idx, name, entry, spec in FIGURES:
        all_res += measure(idx, name, entry, spec, dpi=args.dpi)

    print()
    if not all_res:
        print("没有任何白口可量（图里没有层带）。")
        return 0
    top = max(r["width"] for r in all_res)
    print(f"最宽的一处白口：{top}px @ {args.dpi}dpi"
          f"（{top / args.dpi * 72:.2f}pt），口径 {canvas.gap_width_px(args.dpi):.1f}px")
    ok = top <= args.limit and all(r["link"] for r in all_res)
    print("结论：" + ("通过（全部 ≤%.0fpx，且每处都有连线穿过）" % args.limit
                    if ok else "不通过（超宽或有孤立缺口）"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())