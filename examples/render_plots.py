# -*- coding: utf-8 -*-
"""render_plots.py —— 一条命令跑完 academic_fig 的示例图（21 张，按大类分目录）。

用法::

    python examples/render_plots.py                 # 输出到 examples/out/<大类>/
    python examples/render_plots.py --out examples/out --only trend
    python -m academic_fig.cli check --dir examples/out --strict

输出结构::

    examples/out/
      compare/fig01_bar.png|.pdf …      比较与组成
      trend/…                           趋势
      distribution/…                    分布
      relation/…                        关系
      inference/…                       统计推断
      ml/…                              机器学习
      dimred/…                          降维与多维
      survival/…                        生存分析
      omics/…                           组学
      flow/…                            流程与流向

脚本内 ``matplotlib.use("Agg")`` 在导入 ``pyplot`` 之前——服务器/CI 无显示环境也能跑。
数据全部来自 ``examples/data/*.csv|json``（示例数据，虚构但量纲合理，单个文件 < 20KB）。
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 必须在 import pyplot 之前

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:  # 允许直接 `python examples/render_plots.py`（不必先 pip install）
    sys.path.insert(0, str(ROOT))

import academic_fig as afg  # noqa: E402

DATA = HERE / "data"

#: 亚组中文名（数据文件里用 ASCII，方便任何环境读）
GROUP_CN = {"control": "对照", "dose_low": "低剂量", "dose_high": "高剂量"}
MODEL_CN = {"baseline": "基线", "cnn": "卷积网络", "ours": "本文方法"}


# ------------------------------------------------------------------ 数据读取
def rows(name: str) -> list[dict[str, str]]:
    """读 CSV（不依赖 pandas，任何 Python 都能跑）。"""
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"缺少示例数据 {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def col(table: list[dict[str, str]], key: str, cast=float) -> list:
    """取一列（缺失列直接报错，避免静默出空图）。"""
    if not table or key not in table[0]:
        raise SystemExit(f"数据缺少列 {key!r}")
    return [cast(row[key]) for row in table]


def grouped(table: list[dict[str, str]], key: str, value: str) -> dict[str, list[float]]:
    """按 key 列分组收集 value 列。"""
    out: dict[str, list[float]] = {}
    for row in table:
        out.setdefault(row[key], []).append(float(row[value]))
    return out


def mean_sd(values: list[float]) -> tuple[float, float]:
    """均值与样本标准差（n<2 时 sd=0）。"""
    mu = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return mu, sd


def note(fig, source: str, caliber: str) -> None:
    """统一图注：数据来源 + 口径（每张图都必须有）。"""
    afg.footnote(fig, f"数据来源：{source}；口径：{caliber}。")


# ------------------------------------------------------------------ 比较与组成
def fig_bar():
    table = rows("response.csv")
    by = grouped(table, "group", "value")
    order = ["control", "dose_low", "dose_high"]
    means = [mean_sd(by[g])[0] for g in order]
    sds = [mean_sd(by[g])[1] for g in order]
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", ylabel="响应值（a.u.）", title="不同剂量的响应")
    afg.plots.bar(ax, [GROUP_CN[g] for g in order], means, errors=sds,
                  highlight=[2], brackets=[(0, 2, "**")], width=0.58)
    note(fig, "examples/data/response.csv（示例数据，虚构）",
         "每组 n=12，柱高为均值，误差棒为 1 SD，** 表示 p<0.01（示例）")
    return fig


def fig_grouped_bar():
    table = rows("trend.csv")
    years = sorted({int(r["year"]) for r in table})
    series = {MODEL_CN[m]: [float(r["accuracy"]) for r in table
                            if r["method"] == m and int(r["year"]) in years]
              for m in ("baseline", "cnn", "ours")}
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", ylabel="准确率", xlabel="年份", title="三类方法的年度准确率")
    afg.plots.grouped_bar(ax, [str(y) for y in years], series)
    note(fig, "examples/data/trend.csv（示例数据，虚构）",
         "测试集 4 821 例，评价指标为 top-1 准确率，同一测试集内比较")
    return fig


def fig_stacked_bar():
    table = rows("composition.csv")
    labels = [r["quarter"] for r in table]
    stacks = {
        "计算": col(table, "compute"),
        "网络": col(table, "network"),
        "存储": col(table, "storage"),
        "人力": col(table, "personnel"),
    }
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", ylabel="占比（%）", xlabel="季度", title="成本结构变化")
    afg.plots.stacked_bar(ax, labels, stacks, normalize=True)
    note(fig, "examples/data/composition.csv（示例数据，虚构）",
         "每季度四项支出归一化到 100%，单位为人月折算的等效工时占比")
    return fig


def fig_lollipop():
    table = rows("importance.csv")
    names = col(table, "feature", str)
    vals = col(table, "importance")
    fig, ax = afg.paper_fig("single", height=2.55)
    afg.panel(ax, "(b)", xlabel="标准化重要性", title="特征重要性排序")
    afg.plots.lollipop(ax, names, vals, highlight=[0, 1], annotate=[0])
    note(fig, "examples/data/importance.csv（示例数据，虚构）",
         "置换重要性，10 折交叉验证均值，已按最大值归一化")
    return fig


# ------------------------------------------------------------------ 趋势
def fig_line():
    table = rows("trend.csv")
    years = sorted({int(r["year"]) for r in table})
    series = {MODEL_CN[m]: [float(r["accuracy"]) for r in table
                            if r["method"] == m and int(r["year"]) in years]
              for m in ("baseline", "cnn", "ours")}
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", ylabel="准确率", xlabel="年份", title="准确率随年份的变化")
    afg.plots.line(ax, years, series, ylim=(0.58, 0.86))
    note(fig, "examples/data/trend.csv（示例数据，虚构）",
         "每点为当年固定测试集的准确率，点线为同一协议下复现的结果")
    return fig


def fig_area():
    table = rows("composition.csv")
    x = list(range(len(table)))
    series = {
        "计算": col(table, "compute"),
        "网络": col(table, "network"),
        "存储": col(table, "storage"),
        "人力": col(table, "personnel"),
    }
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", ylabel="占比（%）", xlabel="季度序号", title="成本结构的连续变化")
    afg.plots.area(ax, x, series, stacked=True, normalize=True)
    ax.set_xticks(x[::2], [r["quarter"] for r in table][::2])
    note(fig, "examples/data/composition.csv（示例数据，虚构）",
         "按季度归一化到 100%；季度序号 0 表示 2021Q1")
    return fig


# ------------------------------------------------------------------ 分布
def fig_violin():
    table = rows("response.csv")
    by = grouped(table, "group", "value")
    data = {GROUP_CN[g]: by[g] for g in ("control", "dose_low", "dose_high")}
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", ylabel="响应值（a.u.）", title="三组响应的分布")
    afg.plots.violin(ax, data, show_points=True)
    note(fig, "examples/data/response.csv（示例数据，虚构）",
         "每组 n=12；小提琴为核密度，白点为原始观测，横线为中位数与四分位")
    return fig


def fig_box():
    table = rows("response.csv")
    by = grouped(table, "group", "value")
    data = {GROUP_CN[g]: by[g] for g in ("control", "dose_low", "dose_high")}
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(b)", ylabel="响应值（a.u.）", title="三组响应的四分位")
    afg.plots.box(ax, data, show_points=True)
    note(fig, "examples/data/response.csv（示例数据，虚构）",
         "箱体为 IQR，须线延伸到 1.5 IQR 内的极值，须端之外的点才算离群值（本例无）")
    return fig


def fig_hist():
    table = rows("response.csv")
    by = grouped(table, "group", "value")
    data = {GROUP_CN["control"]: by["control"], GROUP_CN["dose_high"]: by["dose_high"]}
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(c)", xlabel="响应值（a.u.）", title="对照组与高剂量组的分布")
    afg.plots.hist(ax, data, bins=9, reference=float(np.mean(by["control"])))
    note(fig, "examples/data/response.csv（示例数据，虚构）",
         "纵轴为概率密度（两组 n 相同可直接比较），灰虚线为对照组均值")
    return fig


# ------------------------------------------------------------------ 关系
def fig_scatter():
    table = rows("classification.csv")
    y_true = col(table, "y_true", int)
    x = col(table, "y_score_lr")
    y = col(table, "y_score_cnn")
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", xlabel="逻辑回归打分", ylabel="卷积网络打分",
              title="两种模型的打分一致性")
    afg.plots.scatter(ax, x, y, groups=["阳性" if t else "阴性" for t in y_true],
                      fit=True, equal=False)
    note(fig, "examples/data/classification.csv（示例数据，虚构）",
         "n=32，实线为最小二乘拟合，带为 95% 均值置信带")
    return fig


def fig_corr():
    table = rows("expression.csv")
    genes = col(table, "gene", str)
    samples = [k for k in table[0] if k != "gene"]
    matrix = np.array([[float(r[s]) for s in samples] for r in table]).T  # 样本 × 基因
    fig, ax = afg.paper_fig("single", height=3.05)
    afg.panel(ax, "(a)", title="基因表达相关矩阵")
    afg.plots.corr(ax, matrix, names=genes, method="pearson", mask_upper=True)
    note(fig, "examples/data/expression.csv（示例数据，虚构）",
         "n=6 个样本，Pearson 相关；上三角留白，对角线恒为 1")
    return fig


# ------------------------------------------------------------------ 统计推断
def fig_forest():
    labels = ["研究 A（n=120）", "研究 B（n=86）", "研究 C（n=210）",
              "研究 D（n=64）", "研究 E（n=158）"]
    est = [0.42, 0.55, 0.48, 0.61, 0.39]
    lo = [0.21, 0.28, 0.31, 0.33, 0.14]
    hi = [0.63, 0.82, 0.65, 0.89, 0.64]
    fig, ax = afg.paper_fig("double", height=3.35)
    afg.panel(ax, "(a)", xlabel="标准化均值差（95% CI）", title="五项研究的合并效应")
    afg.plots.forest(ax, labels, est, lower=lo, upper=hi,
                     pooled=(0.47, 0.38, 0.56), null=0.0, table=True,
                     weights=[120, 86, 210, 64, 158])
    note(fig, "示例数据（虚构，仅演示版式）",
         "随机效应模型，效应量为标准化均值差，方块面积 ∝ 权重")
    return fig


# ------------------------------------------------------------------ 机器学习
def fig_roc():
    table = rows("classification.csv")
    y_true = col(table, "y_true", int)
    curves = {
        "逻辑回归": (y_true, col(table, "y_score_lr")),
        "卷积网络": (y_true, col(table, "y_score_cnn")),
    }
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", xlabel="假阳性率 FPR", ylabel="真阳性率 TPR", title="ROC 曲线")
    afg.plots.roc(ax, curves=curves)
    note(fig, "examples/data/classification.csv（示例数据，虚构）",
         "正类 16 例、负类 16 例；AUC 由梯形法在全部阈值上积分")
    return fig


def fig_pr():
    table = rows("classification.csv")
    y_true = col(table, "y_true", int)
    curves = {
        "逻辑回归": (y_true, col(table, "y_score_lr")),
        "卷积网络": (y_true, col(table, "y_score_cnn")),
    }
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", title="精确率-召回率曲线")
    afg.plots.pr(ax, curves=curves)
    note(fig, "examples/data/classification.csv（示例数据，虚构）",
         "正类比例 0.5；AP 为阶梯积分，随机基线即正类比例")
    return fig


def fig_confusion():
    table = rows("classification.csv")
    y_true = col(table, "y_true", int)
    score = col(table, "y_score_cnn")
    pred = [1 if s >= 0.5 else 0 for s in score]
    m = np.zeros((2, 2), dtype=int)
    for t, p in zip(y_true, pred):
        m[t, p] += 1
    fig, ax = afg.paper_fig("single", height=2.5)
    afg.panel(ax, "(a)", title="混淆矩阵（阈值 0.5）")
    afg.plots.confusion(ax, m, labels=["阴性", "阳性"], normalize=False)
    note(fig, "examples/data/classification.csv（示例数据，虚构）",
         "n=32；对角线为正确分类，格内为样本数")
    return fig


# ------------------------------------------------------------------ 降维
def fig_pca():
    # 三个工况各 15 个样本、6 个传感特征；工况之间平移+放大，工况内加噪声
    rng = np.random.default_rng(7)
    centers = {"工况 A": 0.0, "工况 B": 2.6, "工况 C": 5.1}
    feats = ["振动", "温度", "压力", "流量", "电流", "转速"]
    matrix, groups = [], []
    for name, shift in centers.items():
        base = rng.normal(0.0, 1.0, size=(15, len(feats)))
        base[:, 0] += shift
        base[:, 1] += 0.55 * shift
        base[:, 2] -= 0.35 * shift
        matrix.append(base)
        groups.extend([name] * 15)
    matrix = np.vstack(matrix)
    fig, ax = afg.paper_fig("single", height=2.55)
    afg.panel(ax, "(a)", title="三种工况在主成分空间的分离")
    afg.plots.pca(ax, matrix, groups=groups, feature_names=feats,
                  biplot=True, ellipse=True)
    note(fig, "示例：合成传感数据（n=45，3 工况 × 15 样本 × 6 特征）",
         "先按特征标准化；箭头为前两个主成分上的特征载荷，椭圆为 95% 置信域")
    return fig


def fig_radar():
    payload = json.loads((DATA / "radar.json").read_text(encoding="utf-8"))
    fig, ax = afg.paper_fig("single", height=3.1, subplot_kw={"projection": "polar"})
    afg.plots.radar(ax, payload["indicators"], payload["series"], rmax=1.0)
    afg.panel(ax, "(b)", title="五项指标的综合轮廓")
    note(fig, "examples/data/radar.json（示例数据，虚构）",
         "五项指标均归一化到 0–1，顺时针依次为准确率->召回率->F1->速度->鲁棒性")
    return fig


# ------------------------------------------------------------------ 生存
def fig_km():
    table = rows("survival.csv")
    by: dict[str, tuple[list[float], list[int]]] = {}
    for r in table:
        t, e = by.setdefault(r["group"], ([], []))
        t.append(float(r["time"]))
        e.append(int(r["event"]))
    groups = {"标准化疗": by["standard"], "联合方案": by["combined"]}
    fig, ax = afg.paper_fig("single", height=3.9)  # 底部要给风险人数表留一条带
    afg.panel(ax, "(a)", xlabel="随访时间（月）", ylabel="生存率", title="两组生存曲线")
    afg.plots.km(ax, groups=groups, risk_table=True,
                 risk_times=[5, 10, 15, 20, 25, 30])
    note(fig, "examples/data/survival.csv（示例数据，虚构）",
         "每组 n=12；竖线为删失点，底部为 5–30 月每 5 月的风险人数")
    return fig


# ------------------------------------------------------------------ 组学
def fig_volcano():
    table = rows("volcano.csv")
    fig, ax = afg.paper_fig("single")
    afg.panel(ax, "(a)", title="差异表达基因")
    afg.plots.volcano(ax, col(table, "log2fc"), col(table, "pvalue"),
                      names=col(table, "gene", str), fc_thresh=1.0, p_thresh=0.05,
                      top_n=6)
    note(fig, "examples/data/volcano.csv（示例数据，虚构）",
         "阈值 |log2FC|≥1 且 p<0.05，蓝点为下调、砖红点为上调；"
         "纵轴为原始 p 的 −log10，未做多重校正")
    return fig


def fig_heatmap():
    table = rows("expression.csv")
    genes = col(table, "gene", str)
    samples = [k for k in table[0] if k != "gene"]
    matrix = np.array([[float(r[s]) for s in samples] for r in table])
    fig, ax = afg.paper_fig("single", height=3.2)
    afg.panel(ax, "(a)", title="基因表达的逐行 z-score")
    afg.plots.heatmap(ax, matrix, rows=genes, cols=samples, kind="div",
                      row_zscore=True, cbar_label="z-score", annotate=False)
    note(fig, "examples/data/expression.csv（示例数据，虚构）",
         "每行（基因）单独 z-score，蓝-白-砖红双色阶以 0 为中心")
    return fig


# ------------------------------------------------------------------ 流程
def fig_sankey():
    payload = json.loads((DATA / "flow.json").read_text(encoding="utf-8"))
    fig, ax = afg.paper_fig("double", height=3.3)
    afg.plots.sankey(ax, payload["links"], nodes=payload.get("nodes"),
                     source_label="毕业去向", target_label="落实单位", value_fmt="{:.0f}")
    note(fig, "examples/data/flow.json（示例数据，虚构）",
         "单位为人；总样本 1 240 人，含暂未落实 63 人，流量按人数等比压缩")
    return fig


#: 大类 -> [(图名, 构造函数)]，顺序即输出顺序
FIGURES: dict[str, list[tuple[str, object]]] = {
    "compare": [("bar", fig_bar), ("grouped_bar", fig_grouped_bar),
                ("stacked_bar", fig_stacked_bar), ("lollipop", fig_lollipop)],
    "trend": [("line", fig_line), ("area", fig_area)],
    "distribution": [("violin", fig_violin), ("box", fig_box), ("hist", fig_hist)],
    "relation": [("scatter", fig_scatter), ("corr", fig_corr)],
    "inference": [("forest", fig_forest)],
    "ml": [("roc", fig_roc), ("pr", fig_pr), ("confusion", fig_confusion)],
    "dimred": [("pca", fig_pca), ("radar", fig_radar)],
    "survival": [("km", fig_km)],
    "omics": [("volcano", fig_volcano), ("heatmap", fig_heatmap)],
    "flow": [("sankey", fig_sankey)],
}


def render(out_dir: Path, only: str | None = None) -> list[Path]:
    """按大类渲染所有示例图，返回写出的文件列表。"""
    written: list[Path] = []
    for category, items in FIGURES.items():
        if only and only not in (category, afg.plots.CATEGORIES.get(category, "")):
            continue
        for index, (name, builder) in enumerate(items, start=1):
            fig = builder()
            base = out_dir / category / f"fig{index:02d}_{name}"
            paths = afg.save(fig, base)
            plt.close(fig)
            written.extend(afg.figure_paths(paths).values())
            print(f"  [ok] {category}/{base.name:<22} -> {', '.join(sorted(afg.figure_paths(paths)))}")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 academic_fig 示例图（按大类分目录）")
    parser.add_argument("--out", default=str(HERE / "out"), help="输出根目录（默认 examples/out）")
    parser.add_argument("--only", default=None,
                        help="只渲染某个大类（compare/trend/distribution/… 或中文名）")
    args = parser.parse_args(argv)

    afg.apply_theme()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录：{out_dir}")
    written = render(out_dir, only=args.only)
    if not written:
        print("没有匹配的大类，检查 --only 取值", file=sys.stderr)
        return 2
    print(f"\n完成：{len(written)} 个文件（{len(written) // 2} 张图，PNG+PDF）")
    print(f"自检：python -m academic_fig.cli check --dir {out_dir} --strict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
