# -*- coding: utf-8 -*-
"""一条命令跑出全部示意图 → ``examples/out/diagrams/``。

用法::

    python examples/render_diagrams.py
    python examples/render_diagrams.py --out examples/out/diagrams
    python examples/render_diagrams.py --only flow

每张图都来自 ``examples/data/diagrams/*.json`` 的纯数据规格——换论文只要改 JSON，
不用动 Python。图注（来源 / 口径 / 示意声明）写在规格里，缺了渲染器会直接报错，
这是本 skill 的硬规则。
"""
import matplotlib

matplotlib.use("Agg")                                   # 无显示环境也能跑

import sys
from pathlib import Path

from matplotlib import pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import academic_fig as afg                              # noqa: E402
from academic_fig import diagrams                       # noqa: E402

DATA = HERE / "data" / "diagrams"

# (编号, 名称, 入口, 规格文件, 覆盖参数)
FIGURES = [
    ("01", "arch_layers", "architecture", "arch_layers.json", {}),
    ("02", "arch_fusion", "architecture", "arch_fusion.json", {}),
    ("03", "flow_vertical", "flow", "flow_vertical.json", {}),
    ("04", "flow_swimlane", "flow", "flow_swimlane.json", {}),
    ("05", "field_gaussian", "field", "field_gaussian.json", {}),
    ("06", "field_surface", "field", "field_surface.json", {}),
    ("07", "geometry_coverage", "geometry", "geometry_coverage.json", {}),
    ("08", "geometry_ring", "geometry", "geometry_ring.json", {}),
    ("09", "gate_pareto", "gate", "gate_pareto.json", {}),
    ("10", "gate_band", "gate", "gate_band.json", {}),
    # 盲测反馈的难例：3 层里有 3 条跨列长连线，靠 auto_cols 重排列位消掉横穿
    ("11", "arch_crossing", "architecture", "arch_crossing.json", {}),
]

# 示意图是「刚性版式」：画布多大，模块就按英寸铺多大，缩 figsize 不会让文字跟着缩。
# 因此每个例子都必须显式说明要多宽的画布 + 落在哪个栏宽，否则内容宽会偏离稿面
# （3.35in / 7.0in ± 0.15in，由 ``cli check`` 判）。数值是按各规格二分反解出来的
# 「内容宽 = 栏宽 − 2×留白」的临界点，改规格后若报 width 错，重跑本脚本即可看到。
WIDTHS = {
    "arch_layers": ("double", "double"),        # 3 层 × 3 列，单栏排不下
    "arch_fusion": ("double", "double"),        # 2 列 4 层带="{...}" 标注，单栏会拉成 3.38×6.00in（aspect 0.56 越界）
    "flow_vertical": ("single", "single"),
    "flow_swimlane": ("double", "double"),      # 4 条泳道并排
    "field_gaussian": ("single", "single"),
    "field_surface": ("single", "single"),
    "geometry_coverage": (3.90, "single"),      # 覆盖图有 0.38in 内部白边，需略宽画布
    "geometry_ring": (3.60, "single"),          # 3.95 会裁到右边距 0px；3.60 落 3.35in 干净
    "gate_pareto": ("single", "single"),
    "gate_band": ("single", "single"),
    "arch_crossing": ("double", "double"),      # 跨列长连线 + auto_cols
}


def render(out_dir, only=None):
    """渲染全部（或 ``only`` 命中的）示意图，返回写出的文件列表。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    afg.apply_theme()

    written = []
    for idx, name, entry, spec_name, kwargs in FIGURES:
        if only and only.lower() not in (name + " " + entry).lower():
            continue
        spec_path = DATA / spec_name
        if not spec_path.exists():
            raise FileNotFoundError(f"缺规格文件：{spec_path}")
        fn = diagrams.RENDERERS[entry]
        # WIDTHS 的键是去后缀的规格名（"geometry_ring"），而 spec_name 带 .json；
        # 早先直接拿 spec_name 查表 → 全部命中默认值 (None, "auto")，画布宽与目标栏宽
        # 都不生效（静默死代码），几何圆环因此被 tight 裁成 3.20in 贴容差下限。
        width_in, target = WIDTHS.get(Path(spec_name).stem, (None, "auto"))
        kw = dict(kwargs)
        if width_in is not None:
            kw["width"] = width_in
        ax = fn(spec_path, **kw)
        paths = afg.save(ax.figure, out_dir / f"fig{idx}_{name}", target_width=target)
        plt.close(ax.figure)
        written.append(paths)
        print(f"[ok] {entry:<12} {spec_name:<22} -> "
              + ", ".join(str(p.name) for p in afg.figure_paths(paths).values()))
    return written


def render_assets(out_dir=None):
    """生成 A/B 对比与「交叉让位」演示图 → ``assets/``。

    注意：这些也是交付资产，必须走 ``afg.save``（300dpi + PNG/PDF 双出），
    不能用裸 ``savefig(dpi=200)``——那会被 ``cli check --dir assets --strict``
    判成 dpi 不足 + 缺 PDF（R-10）。
    """
    import json

    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    afg.apply_theme()                      # 中文字体/字号：不做的话全是方框
    spec = json.loads((DATA / "arch_fusion.json").read_text(encoding="utf-8"))

    shots = {}
    for key, lb, tag in (("A", "none", "A　层带不描边"),
                         ("B", "ink", "B　细缺口描边")):
        ax = diagrams.architecture(spec, layer_border=lb)
        paths = afg.save(ax.figure, assets / f"fig02_arch_fusion_border{key}",
                         target_width="double")
        shots[key] = paths["png"]
        plt.close(ax.figure)
        print(f"[ok] layer_border={lb:<5} {tag} -> "
              + ", ".join(p.name for p in afg.figure_paths(paths).values()))

    # 并排拼版：左 A 右 B。用 matplotlib 摆（不引入 PIL），同样走 afg.save，
    # 于是拼版也有 300dpi 与 PDF。
    import matplotlib.image as mpimg

    fig, axs = plt.subplots(1, 2, figsize=(afg.DOUBLE, afg.DOUBLE * 0.50),
                            squeeze=False)
    for i, (key, title) in enumerate((("A", "(a) layer_border=none"),
                                      ("B", "(b) layer_border=ink"))):
        ax = axs[0][i]
        ax.imshow(mpimg.imread(str(shots[key])))
        ax.set_axis_off()
        afg.panel(ax, title=title, box=False)
    afg.footnote(fig, "A/B 对比：同一份 architecture spec 只改 layer_border；"
                      "口径：拼版宽度 7.0in，两图等比缩放。")
    paths = afg.save(fig, assets / "arch_border_ab", target_width="double",
                     check_name=False)  # 拼版资产，非正文 figNN
    plt.close(fig)
    print("[ok] A/B 拼版 -> " + ", ".join(p.name for p in afg.figure_paths(paths).values()))

    # 交叉让位自检：给「已画的一条横线」造一个真交点，看是否开 0.06in 白口。
    # 这张图天然是白底白线（只在线上开白口），存成 PNG 信息量为零，
    # 所以只做数值自检、不出图。
    from academic_fig.diagrams._canvas import Diagram

    arch_mod = sys.modules["academic_fig.diagrams.architecture"]

    d = Diagram(width="single", height=2.0)
    d.ax.__dict__["_afg_drawn"] = [((0.4, 1.0), (2.4, 1.0), 6.0)]
    arch_mod._yield_crossings(d, [(1.4, 0.4), (1.4, 1.6)], zorder=6.03)
    stubs = [ln for ln in d.ax.lines
             if str(ln.get_color()).upper() == str(afg.palette.PAPER).upper()]
    print(f"[ok] 交叉让位自检：交点 1 处 → 白口 {len(stubs)} 条，"
          f"线宽 {stubs[0].get_linewidth():.2f}pt（= 0.06in）" if stubs
          else "[!!] 交叉让位自检失败：没有开白口")
    plt.close(d.ax.figure)
    return [assets / "arch_border_ab.png"]


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="渲染 academic_fig 示意图（分层框架 / 流程泳道 / 场量响应面 / "
                    "几何覆盖 / 门限权衡）")
    parser.add_argument("--out", default=str(HERE / "out" / "diagrams"),
                        help="输出目录（默认 examples/out/diagrams）")
    parser.add_argument("--only", default=None,
                        help="只渲染名字或入口里含该关键词的图，例如 --only flow")
    parser.add_argument("--assets", action="store_true",
                        help="额外生成 assets/ 下的 A/B 层带对比与交叉让位演示图")
    args = parser.parse_args(argv)

    if args.assets:
        render_assets(args.out)
        return 0

    written = render(args.out, only=args.only)
    total = sum(len(p) for p in written)
    print(f"\n完成：{len(written)} 张示意图、{total} 个文件 → {Path(args.out)}")
    if not written:
        print("（--only 没命中任何图，检查关键词拼写）")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())