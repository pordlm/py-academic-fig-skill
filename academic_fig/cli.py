# -*- coding: utf-8 -*-
"""cli —— ``python -m academic_fig.cli`` 的命令行入口（check / list / init）。

子命令::

    python -m academic_fig.cli check --dir examples/out [--strict] [--json]
    python -m academic_fig.cli list [--category compare]
    python -m academic_fig.cli init --example bar [--out fig01_bar.py] [--force]
    python -m academic_fig.cli init --example architecture     # 示意图同样支持

退出码：``0`` 正常；``1`` 有 error（``check`` 的 ``--strict`` 或默认行为）；
``2`` 参数/用法错误（argparse 自己抛的也是 2）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from pprint import pformat
from typing import Sequence

from . import checks
from . import plots

#: ``init`` 用的最小可运行数据（每种图一条，物理/统计上都讲得通）
_DEMO: dict[str, tuple[str, str]] = {
    "bar": ('["对照组", "处理A", "处理B", "处理C"]',
            '[42.1, 55.3, 61.8, 58.2]', 'errors=[2.1, 2.8, 3.0, 2.6], highlight=[2]'),
    "grouped_bar": ('["2021", "2022", "2023", "2024"]',
                    '{"基线": [31, 34, 36, 39], "本文": [33, 41, 47, 52]}', ''),
    "stacked_bar": ('["一季度", "二季度", "三季度", "四季度"]',
                    '{"设备": [32, 35, 38, 41], "运维": [18, 17, 19, 20], "人力": [26, 27, 25, 24]}',
                    'normalize=True'),
    "lollipop": ('["指标A", "指标B", "指标C", "指标D", "指标E"]',
                 '[0.82, 0.71, 0.66, 0.54, 0.47]', 'highlight=[0]'),
    "line": ('[0, 2, 4, 6, 8, 10]',
             '{"基线": [0.62, 0.66, 0.69, 0.71, 0.72, 0.73], "本文": [0.63, 0.71, 0.78, 0.83, 0.86, 0.88]}',
             'ylabel="准确率"'),
    "area": ('[2018, 2019, 2020, 2021, 2022, 2023]',
             '{"光伏": [12, 18, 24, 33, 45, 58], "风电": [20, 24, 29, 35, 41, 48]}',
             'stacked=True'),
    "violin": ('{"对照组": [1.2, 1.4, 1.5, 1.9, 2.1, 2.4, 2.8], "处理组": [1.8, 2.2, 2.4, 2.9, 3.1, 3.6]}',
               '', 'show_points=True'),
    "box": ('{"对照组": [1.2, 1.4, 1.5, 1.9, 2.1, 2.4, 2.8], "处理组": [1.8, 2.2, 2.4, 2.9, 3.1, 3.6]}',
            '', 'show_points=True'),
    "hist": ('{"对照组": [1.1, 1.3, 1.4, 1.8, 2.0, 2.2, 2.5, 2.9], "处理组": [1.9, 2.1, 2.3, 2.6, 2.9, 3.2, 3.7]}',
             '', 'xlabel="响应时间（s）"'),
    "scatter": ('[1.2, 1.9, 2.4, 2.8, 3.5, 4.1, 4.6, 5.2, 5.9, 6.4]',
                '[2.1, 2.6, 3.4, 3.2, 4.5, 5.1, 5.0, 6.3, 6.9, 7.4]', 'fit=True'),
    "corr": ('{"matrix": [[1.0, 0.4, 2.1], [1.2, 0.5, 1.9], [1.9, 1.1, 2.4],'
             ' [2.1, 1.4, 2.2], [2.8, 1.9, 3.1], [3.2, 2.4, 2.9], [3.9, 3.1, 3.4],'
             ' [4.2, 3.6, 3.1], [5.1, 4.2, 3.8], [5.4, 4.8, 4.0]],'
             ' "names": ["温度", "压力", "流量"]}', '', 'mask_upper=False'),
    "forest": ('["研究1（n=120）", "研究2（n=86）", "研究3（n=210）"]',
               '[0.42, 0.55, 0.48]', 'lower=[0.21, 0.28, 0.31], upper=[0.63, 0.82, 0.65], pooled=(0.48, 0.36, 0.60)'),
    "roc": ('{"y_true": [0, 0, 0, 0, 1, 1, 1, 1], "y_score": [0.1, 0.35, 0.2, 0.5, 0.45, 0.65, 0.8, 0.9]}', '', ''),
    "pr": ('{"y_true": [0, 0, 0, 0, 1, 1, 1, 1], "y_score": [0.1, 0.35, 0.2, 0.5, 0.45, 0.65, 0.8, 0.9]}', '', ''),
    "confusion": ('{"matrix": [[48, 6], [9, 37]], "labels": ["良性", "恶性"]}', '', ''),
    "pca": ('{"matrix": [[1.2, 2.1], [1.9, 2.6], [2.4, 3.4], [4.1, 5.1], [4.6, 5.0], [5.2, 6.3]],'
            ' "groups": ["A", "A", "A", "B", "B", "B"]}', '', ''),
    "radar": ('["精度", "召回", "F1", "速度", "鲁棒性"]',
              '{"基线": [0.72, 0.65, 0.68, 0.81, 0.60], "本文": [0.84, 0.79, 0.81, 0.76, 0.78]}', ''),
    "km": ('[2, 3, 5, 6, 8, 9, 11, 13, 15, 17]', '[1, 1, 0, 1, 1, 0, 1, 1, 0, 1]',
           'risk_table=True'),
    "volcano": ('{"log2fc": [-2.4, -1.6, -0.3, 0.2, 1.4, 2.1, 2.8],'
                ' "pvalue": [0.001, 0.01, 0.4, 0.6, 0.02, 0.004, 0.0002],'
                ' "names": ["g1", "g2", "g3", "g4", "g5", "g6", "g7"]}', '', ''),
    "heatmap": ('{"matrix": [[1.0, 0.8, 0.2], [0.9, 0.7, 0.3], [0.1, 0.3, 1.0]],'
                ' "rows": ["样本1", "样本2", "样本3"], "cols": ["基因A", "基因B", "基因C"]}',
                '', 'kind="seq", cbar_label="表达量（TPM）"'),
    "sankey": ('[["文献检索", "初筛", 1240], ["初筛", "纳入", 186],'
               ' ["初筛", "排除", 1054], ["纳入", "分析", 172], ["纳入", "数据缺失", 14]]',
               '', 'source_label="来源", target_label="去向"'),
}

#: ``init --example`` 用的示意图最小 spec（自包含，不依赖 examples/data/ 里的 JSON）
_DIAGRAM_DEMO: dict[str, dict] = {
    "architecture": {
        "title": "分层框架示意",
        "layers": [
            {"name": "输入层", "nodes": [{"label": "观测数据"}, {"label": "先验知识"}]},
            {"name": "方法层", "nodes": [{"label": "特征提取"},
                                     {"label": "决策网络", "highlight": True}]},
            {"name": "输出层", "nodes": [{"label": "预测结果"}]},
        ],
        "links": [
            {"from": "观测数据", "to": "特征提取"},
            {"from": "先验知识", "to": "决策网络"},
            {"from": "特征提取", "to": "决策网络"},
            {"from": "决策网络", "to": "预测结果"},
        ],
        "footnote": "来源：本文方法框架；口径：模块大小不代表计算量或参数量。",
    },
    "flow": {
        "title": "处理流程示意",
        "direction": "v",
        "nodes": [
            {"id": "n1", "kind": "start", "row": 0, "col": 0, "label": "读入数据"},
            {"id": "n2", "kind": "step", "row": 1, "col": 0, "label": "预处理"},
            {"id": "n3", "kind": "decision", "row": 2, "col": 0, "label": "达标否？"},
            {"id": "n4", "kind": "step", "row": 2, "col": 1, "label": "调参"},
            {"id": "n5", "kind": "end", "row": 3, "col": 0, "label": "输出结果"},
        ],
        "edges": [
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4", "label": "否"},
            {"from": "n3", "to": "n5", "label": "是"},
            {"from": "n4", "to": "n2", "kind": "return", "label": "迭代"},
        ],
        "footnote": "来源：本文处理流程；口径：示意流程，判定阈值按工况设定。",
    },
    "field": {
        "title": "代价响应面",
        "kind": "both",
        "width": "single",
        "x": {"min": 0, "max": 1, "n": 31},
        "y": {"min": 0, "max": 1, "n": 31},
        "field": {"type": "gaussian_sum", "offset": 0.1,
                  "peaks": [{"cx": 0.4, "cy": 0.6, "amp": 1.0, "sx": 0.18, "sy": 0.15}]},
        "labels": {"x": "控制增益（归一化）", "y": "积分时间（归一化）", "z": "代价 J"},
        "levels": 8,
        "footnote": "来源：本文仿真设置；口径：代价归一到 [0, 1]，仅作示意。",
    },
    "geometry": {
        "title": "覆盖与作业边界",
        "x": {"min": -6, "max": 6, "label": "东向位置", "unit": "m"},
        "y": {"min": -5, "max": 5, "label": "北向位置", "unit": "m"},
        "regions": [{"poly": [[-4.5, -3.0], [4.0, -3.0], [4.0, 3.2], [-4.5, 3.2]],
                     "color": "WASH", "edge": "GREY", "ls": "dashed", "label": "作业边界"}],
        "circles": [{"center": [-1.5, 0.6], "r": 2.0, "color": "BLUE", "alpha": 0.1,
                     "edge": "BLUE", "label": "覆盖半径"}],
        "stations": {"pts": [[-1.5, 0.6], [2.0, -0.8]], "label": "测站"},
        "scale_bar": {"length": 2, "unit": "m", "position": "upper right"},
        "legend_loc": "lower left",
        "footnote": "来源：本文几何设置；口径：布设为示意，非实测坐标。",
    },
    "gate": {
        "title": "覆盖与时延的取舍",
        "kind": "pareto",
        "width": "single",
        "x": {"label": "平均响应时延", "unit": "ms", "min": 8, "max": 40},
        "y": {"label": "任务覆盖率", "unit": "%", "min": 80, "max": 102},
        "cloud": {"n": 40, "seed": 7, "x": {"min": 9, "max": 38}, "model": "log",
                  "a": 62, "b": 10, "noise": 1.5},
        "pareto": {"sense": ["min", "max"], "label": "帕累托前沿"},
        "thresholds": [{"axis": "y", "value": 95, "label": "目标 95%"}],
        "footnote": "来源：本文 40 次仿真；口径：示意数据；阈值线为自设目标，非官方指标。",
    },
}

_DIAGRAM_BODY = '''
# 示意图由 spec（dict 或 JSON 文件路径）驱动：版面、间距、文字都会自动排，
# 画完还会自查「文字是否溢出框 / 是否压线」，错版直接抛错而不是悄悄出图。
if getattr(afg, "diagrams", None) is None:
    raise SystemExit("这个安装里没有 diagrams（示意图模块）；可直接运行 examples/render_diagrams.py")

spec = {spec}

ax = afg.diagrams.{name}(spec)
paths = afg.save(ax.figure, "fig01_{name}")     # 同时出 PNG(300dpi) + PDF
print("已写出：", {{k: str(v) for k, v in paths.items()}})
'''


_HEADER = '''# -*- coding: utf-8 -*-
"""{title} —— 由 `academic_fig init --example {name}` 生成，可直接运行。

运行：python {filename}
"""
import matplotlib

matplotlib.use("Agg")          # 必须在 import pyplot 之前（无显示环境也能出图）

try:
    import academic_fig as afg     # noqa: E402
except ModuleNotFoundError:        # 在 skill 源码目录里试跑：把仓库根加进 sys.path
    import sys
    from pathlib import Path

    for _parent in Path(__file__).resolve().parents:
        if (_parent / "academic_fig" / "__init__.py").is_file():
            sys.path.insert(0, str(_parent))
            break
    try:
        import academic_fig as afg     # noqa: E402,F811
    except ModuleNotFoundError as _exc:  # 脚本被挪到了仓库外
        raise SystemExit(
            "找不到 academic_fig。请把这个脚本放回项目里运行，"
            "或先 pip install -e <academic-fig-skill 路径>，"
            "再把仓库根加入 PYTHONPATH。"
        ) from _exc

afg.apply_theme()               # 白纸 + 墨线 + 低饱和强调色（幂等，可重复调用）
{figline}
'''

_FOOTER = '''afg.footnote(fig, "数据来源：示例数据（请替换为真实来源）；口径：{note}。")
paths = afg.save(fig, "fig01_{name}")       # 同时出 PNG(300dpi) + PDF
print("已写出：", {paths_dict})
'''


#: 首参是「数据字典」的图型（生成脚本时改用 ``data=`` 传入）
_DICT_AS_DATA = frozenset({"corr", "pca", "roc", "pr", "confusion", "volcano", "heatmap"})
#: 必须极坐标轴的图型
_POLAR = frozenset({"radar"})

_FIGLINE = {
    "square": 'fig, ax = afg.paper_fig("single")   # 单栏 3.35in；双栏用 "double"（7.0in）',
    "polar": 'fig, ax = afg.paper_fig("single", subplot_kw={"projection": "polar"})  # 极坐标轴',
}


def _diagrams():
    """惰性导入示意图表；没装/没就绪时返回 ``None``（不挡数据图命令）。"""
    try:
        from . import diagrams
    except Exception:                                       # pragma: no cover
        return None
    return diagrams if getattr(diagrams, "DIAGRAMS", None) else None


def _diagram_script(name: str) -> str:
    """生成一张示意图的可运行起步脚本（spec 内嵌，不依赖 examples/data）。"""
    dia = _diagrams()
    meta = dia.DIAGRAMS[name]
    body = _HEADER.format(title=meta["desc"].split("：")[0], name=name,
                          filename=f"fig01_{name}.py", figline="").rstrip("\n") + "\n"
    body += _DIAGRAM_BODY.format(
        spec=pformat(_DIAGRAM_DEMO[name], width=92, sort_dicts=False), name=name)
    return body


def _demo_call(name: str) -> tuple[str, str, str]:
    """返回（首参表达式, 第二个位置参数, 附加关键字）。"""
    demos = _DEMO.get(name)
    if demos is None:
        raise SystemExit(f"没有 {name!r} 的示例；运行 `python -m academic_fig.cli list` 查看可用类型")
    if len(demos) == 2:
        first, second = demos
        extra = ""
    else:
        first, second, extra = demos
    return first, second, extra


def _render_snippet(name: str, call_name: str) -> str:
    first, second, extra = _demo_call(name)
    if name in _DICT_AS_DATA and first.lstrip().startswith("{"):
        args = f"data={first}"
    elif second:
        args = f"{first}, {second}"
    else:
        args = first
    if extra:
        args += f", {extra}"
    return f"afg.plots.{call_name}(ax, {args})\n"


def _init_script(name: str) -> str:
    meta = plots.REGISTRY[name]
    call = meta["func"]
    title = meta["desc"]
    figline = _FIGLINE["polar" if name in _POLAR else "square"]
    body = _HEADER.format(title=title, name=name, filename=f"fig01_{name}.py",
                          figline=figline)
    body += _render_snippet(name, call)
    body += "\n# 收口：统一坐标轴风格（幂等；apply_theme 之后任何手写 matplotlib 都该走这一步）\n"
    body += "afg.style_axes(ax)\n"
    body += _FOOTER.format(note="单栏 3.35in，n 见正文", name=name,
                           paths_dict="{k: str(v) for k, v in paths.items()}")
    return body


# ------------------------------------------------------------------ 子命令
def _version_line() -> str:
    """``academic_fig 0.2.0 (build 0.2.0+20261105-0931)``——每次 CLI 首行都打印。"""
    from . import __build__, __version__

    return f"academic_fig {__version__} (build {__build__})"


def _cmd_list(args: argparse.Namespace) -> int:
    order = list(plots.CATEGORIES)
    grouped: dict[str, list[tuple[str, dict[str, str]]]] = {c: [] for c in order}
    for name, meta in plots.REGISTRY.items():
        grouped.setdefault(meta["category"], []).append((name, meta))
    print(_version_line())
    print("academic_fig 图类型（共 %d 种，按大类分组）\n" % len(plots.REGISTRY))
    for cat in order:
        items = grouped.get(cat) or []
        if not items:
            continue
        if args.category and args.category not in (cat, plots.CATEGORIES[cat]):
            continue
        print(f"■ {plots.CATEGORIES[cat]}（{cat}）")
        for name, meta in items:
            print(f"  - {name:<12} {meta['desc']}")
            print(f"    {meta['sig']}")
            print(f"    用法：python -m academic_fig.cli init --example {name}")
        print()
    _list_diagrams(args.category)
    print("提示：不在列表里的图型，用 apply_theme() + paper_fig() + style_axes(ax) 手写，风格同样成立。")
    return 0


def _list_diagrams(category: str | None) -> None:
    """``list`` 的「示意图（diagrams）」一节：格式与数据图那节完全一致。"""
    dia = _diagrams()
    if dia is None:
        if category is None:
            print("（本安装里没有 diagrams 示意图模块）\n")
        return
    cats: list[tuple[str, str]] = []
    for key, cname in dia.CATEGORIES.items():
        if any(m.get("category") == key for m in dia.DIAGRAMS.values()):
            cats.append((key, cname))
    if category:
        cats = [c for c in cats if category in (c[0], c[1])]
    if not cats:
        return
    print("■ 示意图（diagrams）—— 共 %d 种，spec 驱动（没有数据）\n" % len(dia.DIAGRAMS))
    for key, cname in cats:
        print(f"  · {cname}（{key}）")
        for name, meta in dia.DIAGRAMS.items():
            if meta.get("category") != key:
                continue
            print(f"  - {name:<12} {meta['desc']}")
            print(f"    {meta['sig']}")
            print(f"    用法：python -m academic_fig.cli init --example {name}")
        print("  spec 可用键：" + "、".join(
            _spec_keys(dia, key)) + "（详见 prompts/ 与 examples/render_diagrams.py）")
        print()


def _spec_keys(dia, category: str) -> list[str]:
    """某一大类下所有 spec 键的并集（按出现顺序，去重）。"""
    keys: list[str] = []
    for meta in dia.DIAGRAMS.values():
        if meta.get("category") != category:
            continue
        for k in meta.get("spec_keys", ()):
            if k not in keys:
                keys.append(k)
    return keys


def _cmd_init(args: argparse.Namespace) -> int:
    dia = _diagrams()
    is_plot = args.example in plots.REGISTRY
    is_diagram = bool(dia) and args.example in dia.DIAGRAMS
    if not (is_plot or is_diagram):
        names = list(plots.REGISTRY) + (list(dia.DIAGRAMS) if dia else [])
        print(f"未知图类型 {args.example!r}；可用：{', '.join(names)}", file=sys.stderr)
        print("（带 spec 的示意图也可直接看 examples/render_diagrams.py）", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path(f"fig01_{args.example}.py")
    # --out 只要不以 .py 结尾就按目录理解（否则会写出一个没后缀、跑不起来的文件）
    if args.out and (out.is_dir() or out.suffix.lower() != ".py"
                     or str(args.out).endswith(("/", "\\"))):
        out = out / f"fig01_{args.example}.py"
    if out.exists() and not args.force:
        print(f"{out} 已存在；加 --force 覆盖", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    if is_plot:
        out.write_text(_init_script(args.example), encoding="utf-8")
        desc = plots.REGISTRY[args.example]["desc"]
    else:
        out.write_text(_diagram_script(args.example), encoding="utf-8")
        desc = dia.DIAGRAMS[args.example]["desc"]
    print(f"已生成 {out}（{desc}）")
    print(f"运行：python {out}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    stats: dict[str, object] = {}
    issues = checks.check_dir(args.dir, strict=args.strict,
                              scripts=args.script or None, stats=stats)
    skipped = list(stats.get("skipped") or [])
    skip_detail = dict(stats.get("skip_detail") or {})
    if args.json:
        print(json.dumps([i.to_dict() for i in issues], ensure_ascii=False, indent=2))
        # JSON 的 stdout 保持「问题数组」这一既有形状不变；跳过项走 stderr，
        # 机器读 stdout、人读 stderr，两边都不丢信息。
        for line in _skip_lines(skipped, skip_detail, args.dir):
            print(line, file=sys.stderr)
    else:
        print(_version_line())
        print(checks.format_report(issues, skipped=skipped))
        print(f"扫了 {stats.get('files', 0)} 个文件（PNG {stats.get('png', 0)} / "
              f"PDF {stats.get('pdf', 0)} / SVG {stats.get('svg', 0)}），"
              f"生成脚本 {stats.get('scripts', 0)} 个，目录：{args.dir}")
        for line in _skip_lines(skipped, skip_detail, args.dir):
            print(line)
    bad = checks.has_errors(issues)
    if bad and not args.strict:
        print("\n（未加 --strict：仅提示，退出码 0）")
        return 0
    return 1 if bad else 0


def _skip_lines(skipped: list[str], detail: dict[str, str], target: str) -> list[str]:
    """把「本次没做的检查」摆到台面上（R3-01：没检查 ≠ 检查通过）。"""
    if not skipped:
        return []
    lines = []
    for item in skipped:
        why = detail.get(item, "")
        lines.append(f"[info] 本次跳过：{item}" + (f" —— {why}" if why else ""))
    if any("字形" in s for s in skipped):
        lines.append(
            "[info] 纯图目录只能验尺寸/配色/命名/PDF 是否齐；要验字形与中文+$混排，"
            "请把生成脚本放进该目录（或 --script 指定），并跑 "
            "scripts/selftest_glyph_check.py 确认本机字体栈")
    return lines


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器（测试里也可直接用它）。"""
    parser = argparse.ArgumentParser(
        prog="python -m academic_fig.cli",
        description="academic_fig：白纸+墨线风格的论文插图工具箱（自检 / 图类型 / 起步脚本）",
    )
    parser.add_argument(
        "--version", action="store_true",
        help="打印版本与构建戳（含源码改动时间）后退出",
    )
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="检查出图目录（尺寸/dpi/PDF/配色/字体）")
    p_check.add_argument("--dir", default=".", help="产物目录（默认当前目录）")
    p_check.add_argument("--strict", action="store_true",
                         help="有 error 即退出码 1（CI 用）")
    p_check.add_argument("--json", action="store_true", help="输出 JSON（机器读）")
    p_check.add_argument("--script", action="append", default=[],
                         help="额外静态检查的脚本（可重复）")
    p_check.set_defaults(func=_cmd_check)

    p_list = sub.add_parser("list", help="列出图类型与用法")
    p_list.add_argument("--category", default=None, help="只看某个大类（键或中文名）")
    p_list.set_defaults(func=_cmd_list)

    p_init = sub.add_parser("init", help="生成可运行的起步脚本")
    p_init.add_argument("--example", required=True, help="图类型（见 list）")
    p_init.add_argument("--out", default=None, help="输出脚本路径")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在文件")
    p_init.set_defaults(func=_cmd_init)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主函数：返回退出码（``python -m`` 入口会 ``sys.exit`` 它）。"""
    _tame_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False) and not getattr(args, "command", None):
        print(_version_line())
        return 0
    if not getattr(args, "command", None):
        parser.error("缺少子命令：check / list / init（看版本用 --version）")
    return int(args.func(args))


def _tame_console() -> None:
    """Windows 控制台是 GBK 时，避免生僻字符（如箭头/勾号）直接抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):
            pass


if __name__ == "__main__":
    sys.exit(main())