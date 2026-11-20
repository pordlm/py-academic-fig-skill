# -*- coding: utf-8 -*-
"""风格样张（showcase）：一张 6 面板双栏图，把「同一套风格」摆在同一条基线里。

用途：README 的第一眼效果图（``assets/style_preview.png``），也用来验证
「数据图 + 框架图混排」时版式与配色确实是一套：白纸、墨线、0.8pt 四边细框、
刻度朝内、无网格、低饱和强调色、中文标注、图注写来源与口径。

六个面板：
    (a) 柱状图 —— 组间比较，只强调一根关键柱
    (b) 折线图 —— 多序列趋势 + 置信带
    (c) 热力图 —— 逐行 z-score 的表达矩阵
    (d) 散点图 —— 分组 + 回归线 + R²
    (e) 小提琴图 —— 分布形状对比（合成双峰，n=48/组），内嵌中位与四分位
    (f) 分层框架图 —— 与数据图同一套色板与线宽（手绘原语，非 diagrams 模块）

运行：
    python examples/render_showcase.py                  # -> assets/style_preview.png|pdf
    python examples/render_showcase.py --out assets
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")          # 必须在 import pyplot / academic_fig 之前

import argparse               # noqa: E402
import csv                    # noqa: E402
import sys                    # noqa: E402
import warnings               # noqa: E402
from pathlib import Path       # noqa: E402

import numpy as np            # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import academic_fig as afg    # noqa: E402
from academic_fig import palette as pal  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

DATA = HERE / "data"
STEM = "style_preview"
HEIGHT = 5.9   # 双栏宽 7.0in 固定；高度按内容调，低于 5.0 面板就挤了


# --------------------------------------------------------------------------- 数据
def read_csv(name: str) -> list[dict[str, str]]:
    """读 examples/data 下的 csv（刻意不依赖 pandas）。"""
    with (DATA / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_response() -> tuple[list[str], list[np.ndarray]]:
    rows = read_csv("response.csv")
    order = ["control", "dose_low", "dose_high"]
    cn = {"control": "对照", "dose_low": "低剂量", "dose_high": "高剂量"}
    groups = [np.array([float(r["value"]) for r in rows if r["group"] == g]) for g in order]
    return [cn[g] for g in order], groups


def load_trend() -> tuple[list[int], dict[str, np.ndarray]]:
    rows = read_csv("trend.csv")
    years = sorted({int(r["year"]) for r in rows})
    names = {"baseline": "基线方法", "cnn": "卷积网络", "ours": "本文方法"}
    series = {cn: np.array([float(next(r["accuracy"] for r in rows
                                        if int(r["year"]) == y and r["method"] == m))
                            for y in years])
              for m, cn in names.items()}
    return years, series


def load_expression() -> tuple[list[str], np.ndarray]:
    rows = read_csv("expression.csv")
    genes = [r["gene"] for r in rows]
    cols = ["ctrl_1", "ctrl_2", "ctrl_3", "treat_1", "treat_2", "treat_3"]
    matrix = np.array([[float(r[c]) for c in cols] for r in rows])
    return genes, matrix


def load_distributions(seed: int = 23) -> tuple[list[str], dict[str, np.ndarray]]:
    """面板 (e) 专用的合成分布：三组各 n=48，均值 42/50/60，σ 6–8，轻微双峰。

    为什么不复用 ``response.csv``：那是 n=12、σ≈1.5 的重复测量数据，σ/量程 ≈ 0.05，
    提琴会被压成三个小色块（看着像画坏了）。而「分布形状」这一格要展示的正是形状，
    所以 σ 必须与量程同量级，并且故意做成双峰，尾部、中位线与四分位线才立得住。

    每个模式给 (权重, 均值, 标准差)，权重按 n 取整后再补齐到 n；种子固定，图可复现。
    """
    spec: dict[str, tuple[tuple[float, float, float], ...]] = {
        "对照": ((0.60, 38.5, 5.0), (0.40, 46.5, 6.0)),
        "低剂量": ((0.55, 46.5, 5.0), (0.45, 55.5, 6.5)),
        "高剂量": ((0.50, 55.5, 5.5), (0.50, 65.5, 7.0)),
    }
    n = 48
    rng = np.random.default_rng(seed)
    out: dict[str, np.ndarray] = {}
    for name, modes in spec.items():
        counts = [int(round(n * w)) for w, _, _ in modes]
        counts[-1] = n - sum(counts[:-1])
        parts = [rng.normal(mu, sd, c) for (_, mu, sd), c in zip(modes, counts)]
        sample = np.concatenate(parts)
        rng.shuffle(sample)          # 打散，抖动点不会按模式排成条纹
        out[name] = sample
    return list(spec), out


def synthetic_scatter(seed: int = 11) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """三个工位的合成标定数据：同一物理量与标准值的关系。"""
    rng = np.random.default_rng(seed)
    n = 18
    truth = np.linspace(12.0, 96.0, n)
    offsets = {"工位 A": 0.0, "工位 B": 1.9, "工位 C": -1.4}
    groups, xs, ys = [], [], []
    for name, off in offsets.items():
        noise = rng.normal(0.0, 2.6, n)
        xs.append(truth)
        ys.append(off + 0.985 * truth + noise)
        groups.append(np.array([name] * n, dtype=object))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(groups)


# ------------------------------------------------------------------ 面板 (f) 框架图
def framework_panel(ax) -> None:
    """四层框架图：只用 palette 的填充/描边与 0.8pt 墨线，和数据图同一套语言。

    放在 examples 里手绘，是因为 diagrams.architecture 会自带画布；
    要出正式框架图请用 ``afg.diagrams.architecture(spec, width="double")``。
    """
    layers = [
        ("数据", ["传感阵列", "工况库"]),
        ("模型", ["残差网络", "注意力"]),
        ("决策", ["健康评分", "阈值告警"]),
    ]
    # 面板只有 1/3 栏宽，模块名必须短、字号必须小，否则四个汉字就撑满一个框
    box_w, box_h, gap_x = 0.305, 0.150, 0.065
    x_start, y0, step = 0.250, 0.800, 0.290
    fs_module = 8.0
    fs_layer = 8.0
    centers: list[list[tuple[float, float]]] = []

    for i, (layer_name, modules) in enumerate(layers):
        y = y0 - i * step
        ax.add_patch(FancyBboxPatch(
            (0.03, y - box_h / 2 - 0.026), 0.94, box_h + 0.052,
            boxstyle="round,pad=0.006,rounding_size=0.010",
            linewidth=0.8, edgecolor=pal.INK, facecolor=pal.WASH, zorder=1))
        ax.text(0.135, y, layer_name, ha="center", va="center",
                fontsize=fs_layer, color=pal.GREY, zorder=3)
        row = []
        for j, mod in enumerate(modules):
            x = x_start + j * (box_w + gap_x)
            core = (i == 2 and j == 0)
            ax.add_patch(FancyBboxPatch(
                (x, y - box_h / 2), box_w, box_h,
                boxstyle="round,pad=0.006,rounding_size=0.016",
                linewidth=1.0 if core else 0.8,
                edgecolor=pal.BLUE if core else pal.INK_SOFT,
                facecolor=pal.BLUE_T if core else pal.PAPER, zorder=2))
            ax.text(x + box_w / 2, y, mod, ha="center", va="center",
                    fontsize=fs_module, color=pal.INK, zorder=3)
            row.append((x + box_w / 2, y))
        centers.append(row)

    for i in range(len(layers) - 1):
        for j, (x_from, y_from) in enumerate(centers[i]):
            x_to, y_to = centers[i + 1][j]
            ax.add_patch(FancyArrowPatch(
                (x_from, y_from - box_h / 2 - 0.004), (x_to, y_to + box_h / 2 + 0.004),
                arrowstyle="-|>", mutation_scale=7.0, linewidth=0.9,
                color=pal.INK_SOFT, shrinkA=0.0, shrinkB=0.0, zorder=1))

    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.02, 1.0)
    ax.set_axis_off()


# --------------------------------------------------------------------------- 出图
def build(height: float | None = None) -> object:
    """组装 2×3 双栏样张，返回 Figure。"""
    afg.apply_theme()

    fig, axes = afg.paper_fig("double", nrows=2, ncols=3,
                              height=HEIGHT if height is None else height,
                              wspace=0.42, hspace=0.52)
    ax_a, ax_b, ax_c = axes[0]
    ax_d, ax_e, ax_f = axes[1]

    # (a) 柱状图：均值±SD，只强调高剂量组
    names, groups = load_response()
    means = np.array([g.mean() for g in groups])
    sds = np.array([g.std(ddof=1) for g in groups])
    afg.plots.bar(ax_a, names, means, errors=sds, ylabel="响应值（a.u.）",
                  highlight=[2], brackets=[(0, 2, "*")], annotate=False)
    afg.panel(ax_a, label="(a)", title="组间响应差异", xlabel="")

    # (b) 折线图：三序列 + 置信带（带按 ±1 SD 造，示意）
    years, series = load_trend()
    series = {k: v * 100.0 for k, v in series.items()}   # 比例 -> 百分数，与轴名一致
    rng = np.random.default_rng(3)
    band = {k: (v - rng.uniform(0.6, 1.4, v.size),
                v + rng.uniform(0.6, 1.4, v.size)) for k, v in series.items()}
    afg.plots.line(ax_b, years, series, band=band,
                   ylabel="准确率（%）", xlabel="年份")
    afg.panel(ax_b, label="(b)", title="逐年精度趋势")

    # (c) 热力图：逐行 z-score，色条独立
    genes, expr = load_expression()
    afg.plots.heatmap(ax_c, expr, rows=genes, kind="div", center=0.0,
                      row_zscore=True, cbar=True, cbar_label="行内 z 值",
                      xlabel="样本", ylabel="")
    ax_c.set_xticks(np.arange(6))
    ax_c.set_xticklabels(["对照1", "对照2", "对照3", "处理1", "处理2", "处理3"],
                         rotation=30, ha="right")
    afg.panel(ax_c, label="(c)", title="表达矩阵（行内标准化）")

    # (d) 散点图：三分组 + 回归线 + R²
    xs, ys, gs = synthetic_scatter()
    afg.plots.scatter(ax_d, xs, ys, groups=gs, fit=True, s=18.0,
                      xlabel="标准值（kPa）", ylabel="示值（kPa）")
    afg.panel(ax_d, label="(d)", title="三工位标定一致性")

    # (e) 小提琴图：分布形状 + 中位/四分位（数据是合成的双峰分布，见 load_distributions）
    dist_groups = load_distributions()[1]
    afg.plots.violin(ax_e, dist_groups, ylabel="响应值（a.u.）", xlabel="",
                     show_points=True, points_size=3.4, widths=0.60)
    afg.panel(ax_e, label="(e)", title="分布形状对比")

    # (f) 框架图：和数据图同一套色板/线宽
    framework_panel(ax_f)
    afg.panel(ax_f, label="(f)", title="系统框架（示意，非真实指标）")

    afg.footnote(
        fig,
        "数据来源：examples/data/ 下 response.csv、trend.csv、expression.csv（示例数据，"
        "为演示版式而构造）；散点与面板 (e) 为合成数据（n=54 标定；n=48/组 双峰，种子 23）。"
        "口径：柱与误差棒为均值 ± 1 SD；折线带为 ± 1 SD 示意；热力图为行内 z 值；"
        "提琴图给中位线与四分位；面板 (f) 为手绘示意。")
    return fig


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成风格样张（6 面板双栏）")
    ap.add_argument("--out", default=str(ROOT / "assets"),
                    help="输出目录，默认 assets/")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig = build()
    # 样张名刻意不叫 figNN_*（它是封面图不是论文插图），这里静音命名提醒
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r".*figNN_name.*")
        paths = afg.save(fig, out_dir / STEM, dpi=args.dpi,
                         formats=("png", "pdf"))
    for kind, path in afg.figure_paths(paths).items():
        size_kb = path.stat().st_size / 1024.0
        print(f"[ok] {kind}: {path}  ({size_kb:.0f} KB)")
    print(f"完成：{len(afg.figure_paths(paths))} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())